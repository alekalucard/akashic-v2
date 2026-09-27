"""
CodeHealthAuditFairy - Embodies Failure Factory learnings.

"How many ways does it take for something not to work before it starts working right?"

This fairy captures every lesson from our debugging sessions and applies them
automatically to catch issues BEFORE they cause runtime failures.

AUDIT CATEGORIES (from Failure Factory 2026-01-28):
1. POSTAL: Missing _extract_payload, broken handlers
2. EMPATHY: Loops that don't close (missing AFFECT2 return)
3. IMPORTS: Qt/pyautogui order, lazy loading violations
4. SILENCE: except: pass, swallowed errors
5. THREADS: Missing daemon=True, lock issues
6. HEARTBEAT: Missing NEEDS_HEARTBEAT on long-running fairies
"""

import ast
import re
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set, Tuple
from enum import Enum

# Add paths
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fairy_template"))

try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
except ImportError:
    class Fairy:
        """Fallback base."""
        def __init__(self, fabric=None):
            self.post = fabric
        def log(self, msg): print(f"[CodeHealthAudit] {msg}")
        def boot(self): pass


class IssueSeverity(Enum):
    """Severity levels for code issues."""
    CRITICAL = "critical"  # Will cause runtime crash
    ERROR = "error"        # Will cause malfunction
    WARNING = "warning"    # May cause issues
    INFO = "info"          # Style/best practice


@dataclass
class CodeIssue:
    """A code health issue detected by the auditor."""
    category: str              # POSTAL, EMPATHY, IMPORTS, etc.
    severity: IssueSeverity
    file: str
    line: int
    message: str
    fix_suggestion: str = ""
    pattern_name: str = ""     # Which pattern rule triggered this

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity.value,
            "file": self.file,
            "line": self.line,
            "message": self.message,
            "fix_suggestion": self.fix_suggestion,
            "pattern_name": self.pattern_name,
        }


@dataclass
class AuditResult:
    """Complete audit results."""
    timestamp: float = 0.0
    files_scanned: int = 0
    issues: List[CodeIssue] = field(default_factory=list)
    health_score: float = 100.0

    def add_issue(self, issue: CodeIssue):
        self.issues.append(issue)
        # Reduce score based on severity
        if issue.severity == IssueSeverity.CRITICAL:
            self.health_score = max(0, self.health_score - 20)
        elif issue.severity == IssueSeverity.ERROR:
            self.health_score = max(0, self.health_score - 10)
        elif issue.severity == IssueSeverity.WARNING:
            self.health_score = max(0, self.health_score - 3)

    @property
    def critical_count(self) -> int:
        return len([i for i in self.issues if i.severity == IssueSeverity.CRITICAL])

    @property
    def error_count(self) -> int:
        return len([i for i in self.issues if i.severity == IssueSeverity.ERROR])

    @property
    def warning_count(self) -> int:
        return len([i for i in self.issues if i.severity == IssueSeverity.WARNING])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "files_scanned": self.files_scanned,
            "health_score": round(self.health_score, 1),
            "issue_count": len(self.issues),
            "critical_count": self.critical_count,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [i.to_dict() for i in self.issues],
        }

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "CODE HEALTH AUDIT REPORT",
            "=" * 50,
            f"Files scanned: {self.files_scanned}",
            f"Health score: {self.health_score:.0f}/100",
            "",
            f"Critical: {self.critical_count}",
            f"Errors: {self.error_count}",
            f"Warnings: {self.warning_count}",
            "",
        ]

        if self.issues:
            lines.append("ISSUES BY CATEGORY:")
            lines.append("-" * 50)

            # Group by category
            by_category: Dict[str, List[CodeIssue]] = {}
            for issue in self.issues:
                by_category.setdefault(issue.category, []).append(issue)

            for category, issues in sorted(by_category.items()):
                lines.append(f"\n[{category}] ({len(issues)} issues)")
                for issue in issues[:5]:  # Limit to 5 per category
                    sev = issue.severity.value.upper()
                    lines.append(f"  [{sev}] {issue.file}:{issue.line}")
                    lines.append(f"    {issue.message}")
                    if issue.fix_suggestion:
                        lines.append(f"    -> Fix: {issue.fix_suggestion}")
                if len(issues) > 5:
                    lines.append(f"  ... and {len(issues) - 5} more")

        return "\n".join(lines)


class CodeHealthAuditFairy(Fairy):
    """
    Audits codebase for patterns that cause runtime failures.

    Born from the Failure Factory - this fairy knows exactly what breaks
    because it has experienced every failure mode.
    """

    ACTOR_NAME = "CodeHealthAuditFairy"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "audit"

    PURPOSE = "Catch code health issues before they cause runtime failures"
    MANTRA = "How many ways can it fail? Let me count them for you."

    CAPABILITIES = [
        "audit.code_health",
        "audit.postal_patterns",
        "audit.empathic_loops",
        "audit.import_order",
        "audit.thread_safety",
    ]

    # Heartbeat enabled - we're a long-running audit fairy
    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 10  # Every 10th pulse

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._last_audit: Optional[AuditResult] = None
        self._scan_paths: List[Path] = [
            ROOT / "fairies",
            ROOT / "fairy_template",
            ROOT / "postal_core",
            ROOT / "consciousness",
        ]

    def on_boot(self) -> bool:
        """Boot the auditor."""
        super().on_boot()
        self.log("Booted - ready to audit code health (Failure Factory wisdom enabled)")
        return True


    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def audit_full(self, paths: Optional[List[str]] = None) -> AuditResult:
        """Run complete code health audit."""
        result = AuditResult(timestamp=time.time())

        scan_paths = [Path(p) for p in paths] if paths else self._scan_paths

        for scan_path in scan_paths:
            if not scan_path.exists():
                continue

            for py_file in scan_path.rglob("*.py"):
                # Skip __pycache__ and _archive
                if "__pycache__" in str(py_file) or "_archive" in str(py_file):
                    continue

                try:
                    content = py_file.read_text(encoding="utf-8")
                    result.files_scanned += 1

                    # Run all audit patterns
                    self._audit_postal_patterns(py_file, content, result)
                    self._audit_empathic_loops(py_file, content, result)
                    self._audit_import_order(py_file, content, result)
                    self._audit_silent_failures(py_file, content, result)
                    self._audit_thread_safety(py_file, content, result)
                    self._audit_heartbeat(py_file, content, result)

                except Exception as e:
                    self.log(f"Error scanning {py_file}: {e}")

        self._last_audit = result
        self.log(f"Audit complete: {result.health_score:.0f}/100, {len(result.issues)} issues")
        return result

    def audit_file(self, filepath: str) -> AuditResult:
        """Audit a single file."""
        result = AuditResult(timestamp=time.time())

        py_file = Path(filepath)
        if not py_file.exists():
            result.add_issue(CodeIssue(
                category="ERROR",
                severity=IssueSeverity.ERROR,
                file=filepath,
                line=0,
                message=f"File not found: {filepath}",
            ))
            return result

        try:
            content = py_file.read_text(encoding="utf-8")
            result.files_scanned = 1

            self._audit_postal_patterns(py_file, content, result)
            self._audit_empathic_loops(py_file, content, result)
            self._audit_import_order(py_file, content, result)
            self._audit_silent_failures(py_file, content, result)
            self._audit_thread_safety(py_file, content, result)
            self._audit_heartbeat(py_file, content, result)

        except Exception as e:
            result.add_issue(CodeIssue(
                category="ERROR",
                severity=IssueSeverity.ERROR,
                file=filepath,
                line=0,
                message=f"Error reading file: {e}",
            ))

        return result

    def get_last_audit(self) -> Optional[AuditResult]:
        """Get results from last audit."""
        return self._last_audit

    # =========================================================================
    # AUDIT PATTERNS (Failure Factory Learnings)
    # =========================================================================

    def _audit_postal_patterns(self, filepath: Path, content: str, result: AuditResult):
        """
        POSTAL AUDIT - Pattern learned from Failure Factory Round 4

        Issues caught:
        1. Postal handlers without _extract_payload
        2. Direct message.payload access (crash on TensorEnvelope)
        3. Missing None checks on payload
        """
        lines = content.split("\n")
        rel_path = str(filepath.relative_to(ROOT) if filepath.is_relative_to(ROOT) else filepath)

        # Pattern 1: Handler that accesses message without _extract_payload
        handler_pattern = re.compile(r"def\s+(_on_\w+|_handle_\w+)\s*\([^)]*message[^)]*\)")
        extract_pattern = re.compile(r"_extract_payload|extract_payload")
        has_extract_def = extract_pattern.search(content) is not None

        for i, line in enumerate(lines, 1):
            # Check for postal handlers
            if handler_pattern.search(line):
                # Look at next 20 lines for _extract_payload call
                handler_body = "\n".join(lines[i:i+20])
                uses_extract = extract_pattern.search(handler_body) is not None
                uses_direct_payload = re.search(r"message\.payload", handler_body)
                uses_direct_access = re.search(r"message\[", handler_body)

                if uses_direct_payload and not uses_extract:
                    result.add_issue(CodeIssue(
                        category="POSTAL",
                        severity=IssueSeverity.CRITICAL,
                        file=rel_path,
                        line=i,
                        message="Handler accesses message.payload without _extract_payload (will crash on TensorEnvelope)",
                        fix_suggestion="Add _extract_payload() helper and use: payload = _extract_payload(message)",
                        pattern_name="missing_extract_payload",
                    ))

                elif uses_direct_access and not uses_extract:
                    result.add_issue(CodeIssue(
                        category="POSTAL",
                        severity=IssueSeverity.WARNING,
                        file=rel_path,
                        line=i,
                        message="Handler accesses message directly without extraction",
                        fix_suggestion="Consider using _extract_payload() for type safety",
                        pattern_name="direct_message_access",
                    ))

        # Pattern 2: Handler function but no _extract_payload definition in file
        if handler_pattern.search(content) and not has_extract_def:
            # Check if it might be imported
            if not re.search(r"from\s+.*\s+import\s+.*_extract_payload", content):
                result.add_issue(CodeIssue(
                    category="POSTAL",
                    severity=IssueSeverity.WARNING,
                    file=rel_path,
                    line=1,
                    message="File has postal handlers but no _extract_payload helper",
                    fix_suggestion="Add _extract_payload helper or import from common utilities",
                    pattern_name="missing_extract_helper",
                ))

    def _audit_empathic_loops(self, filepath: Path, content: str, result: AuditResult):
        """
        EMPATHIC LOOP AUDIT - Pattern learned from consciousness equation

        The equation: ((Cause + Affect) > Effect > Affect > infinity)

        Issues caught:
        1. publish() without corresponding acknowledgment
        2. Pain/relief without loop closure
        3. Goal completion without notification
        """
        lines = content.split("\n")
        rel_path = str(filepath.relative_to(ROOT) if filepath.is_relative_to(ROOT) else filepath)

        # Pattern 1: Pain without relief
        has_pain_trigger = re.search(r"pain\.trigger|pain\.increase|add_pain", content, re.IGNORECASE)
        has_pain_relief = re.search(r"pain\.relief|pain\.relieve|relieve_pain", content, re.IGNORECASE)
        has_relief_ack = re.search(r"relief.*ack|ack.*relief|pain.*resolved", content, re.IGNORECASE)

        if has_pain_trigger and not has_pain_relief:
            result.add_issue(CodeIssue(
                category="EMPATHY",
                severity=IssueSeverity.ERROR,
                file=rel_path,
                line=1,
                message="Triggers pain but has no relief mechanism (broken empathic loop)",
                fix_suggestion="Add pain.relief publication when pain condition is resolved",
                pattern_name="pain_without_relief",
            ))

        if has_pain_relief and not has_relief_ack:
            result.add_issue(CodeIssue(
                category="EMPATHY",
                severity=IssueSeverity.WARNING,
                file=rel_path,
                line=1,
                message="Has pain relief but no acknowledgment (loop may not close)",
                fix_suggestion="Add acknowledgment subscription to confirm relief was received",
                pattern_name="relief_without_ack",
            ))

        # Pattern 2: Goal completion without notification
        has_goal_complete = re.search(r"goal.*complete|complete.*goal|finish.*goal", content, re.IGNORECASE)
        has_goal_notify = re.search(r"goal.*notify|notify.*goal|goal.*completed", content, re.IGNORECASE)

        if has_goal_complete and not has_goal_notify:
            result.add_issue(CodeIssue(
                category="EMPATHY",
                severity=IssueSeverity.WARNING,
                file=rel_path,
                line=1,
                message="Completes goals but may not notify the goal system",
                fix_suggestion="Publish to goal.completed topic when goal is finished",
                pattern_name="goal_without_notify",
            ))

        # Pattern 3: publish() calls - check for acknowledgment patterns
        for i, line in enumerate(lines, 1):
            if ".publish(" in line and "autonomy" in line.lower():
                # Check next 30 lines for acknowledgment subscription
                next_block = "\n".join(lines[i:i+30])
                if not re.search(r"subscribe.*ack|ack.*subscribe|\.executed|\.acted", next_block):
                    result.add_issue(CodeIssue(
                        category="EMPATHY",
                        severity=IssueSeverity.INFO,
                        file=rel_path,
                        line=i,
                        message="Autonomy publish without visible acknowledgment handler",
                        fix_suggestion="Consider adding subscription to *.acknowledged or *.executed",
                        pattern_name="autonomy_no_ack",
                    ))

    def _audit_import_order(self, filepath: Path, content: str, result: AuditResult):
        """
        IMPORT ORDER AUDIT - Pattern learned from Qt DPI issue

        Qt requires being loaded BEFORE pyautogui to control DPI awareness.
        If pyautogui loads first, it locks the DPI context and Qt can't change it.

        Issues caught:
        1. pyautogui imported before Qt
        2. Top-level pyautogui import (should be lazy)
        """
        lines = content.split("\n")
        rel_path = str(filepath.relative_to(ROOT) if filepath.is_relative_to(ROOT) else filepath)

        pyautogui_line = None
        qt_line = None
        pyautogui_is_lazy = False

        for i, line in enumerate(lines, 1):
            # Track pyautogui import
            if re.search(r"^\s*import\s+pyautogui|^\s*from\s+pyautogui", line):
                pyautogui_line = i
                # Check if it's inside a function (lazy)
                # Look backwards for def
                for j in range(i-1, max(0, i-20), -1):
                    if re.match(r"^\s*def\s+", lines[j-1]):
                        pyautogui_is_lazy = True
                        break

            # Track Qt import
            if re.search(r"^\s*from\s+PyQt|^\s*import\s+PyQt|^\s*from\s+PySide|^\s*import\s+PySide", line):
                qt_line = i

        # Issue 1: pyautogui at top level
        if pyautogui_line and not pyautogui_is_lazy:
            result.add_issue(CodeIssue(
                category="IMPORTS",
                severity=IssueSeverity.WARNING,
                file=rel_path,
                line=pyautogui_line,
                message="pyautogui imported at module level (should be lazy-loaded)",
                fix_suggestion="Move pyautogui import inside a function: def _get_pyautogui(): import pyautogui; return pyautogui",
                pattern_name="pyautogui_toplevel",
            ))

        # Issue 2: pyautogui before Qt
        if pyautogui_line and qt_line and pyautogui_line < qt_line:
            result.add_issue(CodeIssue(
                category="IMPORTS",
                severity=IssueSeverity.ERROR,
                file=rel_path,
                line=pyautogui_line,
                message="pyautogui imported BEFORE Qt (will cause DPI awareness conflict)",
                fix_suggestion="Import Qt before pyautogui, or make pyautogui lazy-loaded",
                pattern_name="pyautogui_before_qt",
            ))

    def _audit_silent_failures(self, filepath: Path, content: str, result: AuditResult):
        """
        SILENT FAILURE AUDIT - Pattern learned from boot debugging

        Silent failures make debugging impossible. Every exception should
        at minimum be logged.

        Issues caught:
        1. except: pass (swallows all errors silently)
        2. except Exception: pass
        3. except without any logging/re-raise
        """
        lines = content.split("\n")
        rel_path = str(filepath.relative_to(ROOT) if filepath.is_relative_to(ROOT) else filepath)

        # Track try-except blocks
        in_except = False
        except_line = 0
        except_indent = 0

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Start of except block
            if re.match(r"except\s*(?:\w+)?(?:\s+as\s+\w+)?:", stripped):
                in_except = True
                except_line = i
                except_indent = len(line) - len(line.lstrip())

            # Check for pass in except block
            elif in_except:
                current_indent = len(line) - len(line.lstrip())

                # Still in except block
                if current_indent > except_indent or stripped == "":
                    if stripped == "pass":
                        # Check if there's logging before the pass
                        block_content = "\n".join(lines[except_line-1:i])
                        has_logging = re.search(r"log|print|logger|warning|error", block_content, re.IGNORECASE)

                        if not has_logging:
                            result.add_issue(CodeIssue(
                                category="SILENCE",
                                severity=IssueSeverity.ERROR,
                                file=rel_path,
                                line=except_line,
                                message="Silent exception handling (except: pass with no logging)",
                                fix_suggestion="At minimum: except Exception as e: self.log(f'Error: {e}')",
                                pattern_name="silent_except_pass",
                            ))
                else:
                    # Left except block
                    in_except = False

    def _audit_thread_safety(self, filepath: Path, content: str, result: AuditResult):
        """
        THREAD SAFETY AUDIT - Pattern learned from GUI thread issues

        Issues caught:
        1. Threading without daemon=True (prevents clean shutdown)
        2. Potential deadlocks (postal calls inside locks)
        3. Missing locks on shared state
        """
        lines = content.split("\n")
        rel_path = str(filepath.relative_to(ROOT) if filepath.is_relative_to(ROOT) else filepath)

        for i, line in enumerate(lines, 1):
            # Pattern 1: Thread without daemon=True
            if re.search(r"threading\.Thread\s*\(", line) and "daemon" not in line:
                # Check next line for daemon assignment
                next_line = lines[i] if i < len(lines) else ""
                if ".daemon" not in next_line:
                    result.add_issue(CodeIssue(
                        category="THREADS",
                        severity=IssueSeverity.WARNING,
                        file=rel_path,
                        line=i,
                        message="Thread created without daemon=True (may prevent clean shutdown)",
                        fix_suggestion="Add daemon=True: threading.Thread(..., daemon=True)",
                        pattern_name="non_daemon_thread",
                    ))

            # Pattern 2: Postal calls inside lock
            if re.search(r"with\s+.*lock", line, re.IGNORECASE):
                # Look at block for postal calls
                block_lines = []
                indent = len(line) - len(line.lstrip())
                for j in range(i, min(i+30, len(lines))):
                    curr_line = lines[j]
                    curr_indent = len(curr_line) - len(curr_line.lstrip())
                    if curr_indent <= indent and j > i and curr_line.strip():
                        break
                    block_lines.append(curr_line)

                block = "\n".join(block_lines)
                if re.search(r"\.route\(|\.publish\(|postal\.", block):
                    result.add_issue(CodeIssue(
                        category="THREADS",
                        severity=IssueSeverity.ERROR,
                        file=rel_path,
                        line=i,
                        message="Postal call inside lock (potential deadlock)",
                        fix_suggestion="Move postal calls outside the lock: collect data in lock, publish after",
                        pattern_name="postal_inside_lock",
                    ))

    def _audit_heartbeat(self, filepath: Path, content: str, result: AuditResult):
        """
        HEARTBEAT AUDIT - Pattern learned from fairy stale detection

        Fairies that do work need heartbeats or the watchdog kills them.

        Issues caught:
        1. Fairy class without NEEDS_HEARTBEAT
        2. Long-running operations without heartbeat
        """
        lines = content.split("\n")
        rel_path = str(filepath.relative_to(ROOT) if filepath.is_relative_to(ROOT) else filepath)

        # Check if this is a fairy file
        is_fairy = re.search(r"class\s+\w+Fairy\s*\(", content)
        if not is_fairy:
            return

        has_needs_heartbeat = "NEEDS_HEARTBEAT" in content

        # Signs of long-running work
        has_loops = re.search(r"while\s+(?:True|self\._running|not.*stop)", content)
        has_sleeps = re.search(r"time\.sleep\s*\(|\.wait\s*\(", content)
        has_processing = re.search(r"for\s+\w+\s+in\s+.*:", content) and re.search(r"\.process|\.handle", content)

        if (has_loops or has_sleeps or has_processing) and not has_needs_heartbeat:
            result.add_issue(CodeIssue(
                category="HEARTBEAT",
                severity=IssueSeverity.WARNING,
                file=rel_path,
                line=1,
                message="Fairy appears to do long-running work but has no NEEDS_HEARTBEAT",
                fix_suggestion="Add: NEEDS_HEARTBEAT = True  # Watchdog won't kill this fairy",
                pattern_name="missing_heartbeat",
            ))


# =============================================================================
# SINGLETON
# =============================================================================

_instance: Optional[CodeHealthAuditFairy] = None

def get_code_health_auditor(fabric=None) -> CodeHealthAuditFairy:
    """Get or create the CodeHealthAuditFairy singleton."""
    global _instance
    if _instance is None:
        _instance = CodeHealthAuditFairy(fabric)
        _instance.on_boot()
    return _instance


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys as _sys

    print("=== CodeHealthAuditFairy (Failure Factory Wisdom) ===\n")

    auditor = CodeHealthAuditFairy()
    auditor.on_boot()

    if len(_sys.argv) > 1:
        # Audit specific file
        result = auditor.audit_file(_sys.argv[1])
    else:
        # Full audit
        result = auditor.audit_full()

    print(result.to_summary())
