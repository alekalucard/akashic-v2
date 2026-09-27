# Checklist Validation System
# ALL GREEN OR FAILED - No "partially working" states
#
# Every component has a checklist. If ANY check fails, the whole thing fails.
# This forces clean design and proper error handling.

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Any
from datetime import datetime
import traceback


class CheckStatus(Enum):
    """Status of a single check."""
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"  # Only for optional checks


@dataclass
class CheckResult:
    """Result of running a single check."""
    name: str
    status: CheckStatus
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.status == CheckStatus.PASS

    @property
    def failed(self) -> bool:
        return self.status == CheckStatus.FAIL

    def __str__(self) -> str:
        icon = {"pass": "[OK]", "fail": "[FAIL]", "skip": "[SKIP]"}[self.status.value]
        return f"{icon} {self.name}: {self.message}"


@dataclass
class Check:
    """A single check in a checklist."""
    name: str
    description: str
    checker: Callable[[], bool]  # Returns True if passed
    required: bool = True  # If False, failure doesn't fail the whole checklist
    error_handler: Optional[Callable[[Exception], str]] = None

    def run(self) -> CheckResult:
        """Run this check and return result."""
        import time
        start = time.perf_counter()

        try:
            passed = self.checker()
            duration = (time.perf_counter() - start) * 1000

            if passed:
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.PASS,
                    message=self.description,
                    duration_ms=duration
                )
            else:
                return CheckResult(
                    name=self.name,
                    status=CheckStatus.FAIL if self.required else CheckStatus.SKIP,
                    message=f"Check failed: {self.description}",
                    duration_ms=duration
                )

        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            error_msg = self.error_handler(e) if self.error_handler else str(e)

            return CheckResult(
                name=self.name,
                status=CheckStatus.FAIL if self.required else CheckStatus.SKIP,
                message=f"Exception: {error_msg}",
                duration_ms=duration,
                details={"exception": str(e), "traceback": traceback.format_exc()}
            )


class Checklist:
    """
    A collection of checks that must ALL pass for the component to be valid.

    Usage:
        checklist = Checklist("MyComponent")
        checklist.add("has_tracer", "Tracer ID assigned", lambda: self.tracer_id is not None)
        checklist.add("connected", "Connected to postal", lambda: self.postal.is_connected())

        result = checklist.run()
        if result.all_passed:
            print("Ready!")
        else:
            print(f"Failed: {result.failures}")
    """

    def __init__(self, name: str, owner: Any = None):
        self.name = name
        self.owner = owner
        self.checks: List[Check] = []
        self._last_result: Optional[ChecklistResult] = None

    def add(
        self,
        name: str,
        description: str,
        checker: Callable[[], bool],
        required: bool = True,
        error_handler: Optional[Callable[[Exception], str]] = None
    ) -> Checklist:
        """Add a check to the checklist. Returns self for chaining."""
        self.checks.append(Check(
            name=name,
            description=description,
            checker=checker,
            required=required,
            error_handler=error_handler
        ))
        return self

    def add_check(self, check: Check) -> Checklist:
        """Add a pre-built Check object."""
        self.checks.append(check)
        return self

    def run(self) -> ChecklistResult:
        """
        Run all checks and return aggregate result.

        Returns:
            ChecklistResult with all individual results and aggregate status
        """
        results: List[CheckResult] = []

        for check in self.checks:
            result = check.run()
            results.append(result)

        self._last_result = ChecklistResult(
            checklist_name=self.name,
            results=results
        )

        return self._last_result

    @property
    def last_result(self) -> Optional[ChecklistResult]:
        """Get the last run result without re-running."""
        return self._last_result

    def is_valid(self) -> bool:
        """Quick check: run checklist and return True if all passed."""
        return self.run().all_passed

    def __len__(self) -> int:
        return len(self.checks)

    def __repr__(self) -> str:
        return f"Checklist({self.name}, {len(self.checks)} checks)"


@dataclass
class ChecklistResult:
    """Aggregate result of running a checklist."""
    checklist_name: str
    results: List[CheckResult]
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def all_passed(self) -> bool:
        """True only if ALL required checks passed."""
        return all(r.status != CheckStatus.FAIL for r in self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.PASS)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.FAIL)

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.SKIP)

    @property
    def total_count(self) -> int:
        return len(self.results)

    @property
    def failures(self) -> List[CheckResult]:
        """Get all failed checks."""
        return [r for r in self.results if r.status == CheckStatus.FAIL]

    @property
    def passes(self) -> List[CheckResult]:
        """Get all passed checks."""
        return [r for r in self.results if r.status == CheckStatus.PASS]

    @property
    def total_duration_ms(self) -> float:
        return sum(r.duration_ms for r in self.results)

    @property
    def progress_bar(self) -> str:
        """ASCII progress bar showing pass/fail ratio."""
        if not self.results:
            return "[]"
        width = 10
        filled = int((self.passed_count / self.total_count) * width)
        return "[" + ("=" * filled) + ("-" * (width - filled)) + "]"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "checklist": self.checklist_name,
            "passed": self.all_passed,
            "summary": f"{self.passed_count}/{self.total_count}",
            "results": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "message": r.message,
                    "duration_ms": r.duration_ms
                }
                for r in self.results
            ],
            "timestamp": self.timestamp.isoformat()
        }

    def __str__(self) -> str:
        status = "PASSED" if self.all_passed else "FAILED"
        return f"[{self.checklist_name}] {status} {self.progress_bar} {self.passed_count}/{self.total_count}"

    def __repr__(self) -> str:
        return self.__str__()


# Standard checks that can be reused
def make_not_none_check(name: str, description: str, getter: Callable[[], Any]) -> Check:
    """Create a check that passes if getter() returns non-None."""
    return Check(
        name=name,
        description=description,
        checker=lambda: getter() is not None
    )


def make_type_check(name: str, description: str, getter: Callable[[], Any], expected_type: type) -> Check:
    """Create a check that passes if getter() returns expected type."""
    return Check(
        name=name,
        description=description,
        checker=lambda: isinstance(getter(), expected_type)
    )


def make_callable_check(name: str, description: str, target: Any, method_name: str) -> Check:
    """Create a check that passes if target has callable method_name."""
    return Check(
        name=name,
        description=description,
        checker=lambda: hasattr(target, method_name) and callable(getattr(target, method_name))
    )
