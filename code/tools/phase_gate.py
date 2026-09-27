"""
PHASE GATE VERIFICATION TOOL
============================
Checks work completion before proceeding to next phase.

Usage:
    from tools.phase_gate import PhaseGate
    gate = PhaseGate()
    result = await gate.verify_phase(1)
    if result.passed:
        proceed_to_next_phase()
    else:
        print(result.failures)

Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

import asyncio
import importlib
import sys
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any
import json

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class VerificationResult:
    """Result of a phase verification."""
    phase: int
    passed: bool
    checks: List[Dict[str, Any]] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "passed": self.passed,
            "checks": self.checks,
            "failures": self.failures,
            "warnings": self.warnings,
            "timestamp": self.timestamp.isoformat()
        }

    def to_codex_entry(self) -> str:
        """Format for Akashic Codex."""
        status = "[PASSED]" if self.passed else "[FAILED]"
        lines = [
            f"## Phase {self.phase} Verification - {status}",
            f"**Timestamp:** {self.timestamp.isoformat()}",
            "",
            "### Checks Performed"
        ]
        for check in self.checks:
            marker = "[OK]" if check.get("passed") else "[X]"
            lines.append(f"- {marker} {check.get('name')}: {check.get('result')}")

        if self.failures:
            lines.extend(["", "### Failures"])
            for f in self.failures:
                lines.append(f"- [X] {f}")

        if self.warnings:
            lines.extend(["", "### Warnings"])
            for w in self.warnings:
                lines.append(f"- [!] {w}")

        return "\n".join(lines)


class PhaseGate:
    """
    Verifies phase completion before allowing progression.

    Each phase has specific criteria that must pass.
    Results are logged to Akashic Codex for learning.
    """

    def __init__(self):
        self.results_path = PROJECT_ROOT / "Claude_Office" / "audits" / "phase_results"
        self.results_path.mkdir(parents=True, exist_ok=True)

    async def verify_phase(self, phase: int) -> VerificationResult:
        """Verify a specific phase."""
        verifiers = {
            1: self._verify_phase_1_ignition,
            2: self._verify_phase_2_imports,
            3: self._verify_phase_3_empathic_loops,
            4: self._verify_phase_4_cleanup,
            5: self._verify_phase_5_directory,
        }

        if phase not in verifiers:
            return VerificationResult(
                phase=phase,
                passed=False,
                failures=[f"Unknown phase: {phase}"]
            )

        result = await verifiers[phase]()

        # Save result
        self._save_result(result)

        return result

    async def _verify_phase_1_ignition(self) -> VerificationResult:
        """
        Phase 1: Ignition Sequence
        - waking.complete published?
        - ConsciousnessLoop received it?
        - Acknowledgment sent back?
        """
        result = VerificationResult(phase=1, passed=True)

        # Check 1: WakingSequenceFairy publishes waking.complete
        check1 = await self._check_code_contains(
            "P00_Autonomic/nervous_system/waking_sequence_fairy.py",
            ["waking.complete", "publish"],
            "WakingSequenceFairy publishes waking.complete"
        )
        result.checks.append(check1)
        if not check1["passed"]:
            result.failures.append("WakingSequenceFairy does not publish waking.complete")
            result.passed = False

        # Check 2: ConsciousnessLoop subscribes to waking.complete
        check2 = await self._check_code_contains(
            "P00_Autonomic/nervous_system/consciousness_loop_fairy.py",
            ["waking.complete", "subscribe"],
            "ConsciousnessLoop subscribes to waking.complete"
        )
        result.checks.append(check2)
        if not check2["passed"]:
            result.warnings.append("ConsciousnessLoop may not subscribe to waking.complete")

        # Check 3: Acknowledgment exists (consciousness.ignited)
        check3 = await self._check_code_contains(
            "P00_Autonomic/nervous_system/consciousness_loop_fairy.py",
            ["consciousness.ignited", "publish"],
            "ConsciousnessLoop publishes acknowledgment"
        )
        result.checks.append(check3)
        if not check3["passed"]:
            result.warnings.append("No acknowledgment signal (empathic loop not closed)")

        # Check 4: Test boot sequence
        check4 = await self._test_import("fairies.P00_Autonomic.nervous_system.waking_sequence_fairy")
        result.checks.append({
            "name": "WakingSequenceFairy imports",
            "passed": check4,
            "result": "Import successful" if check4 else "Import failed"
        })
        if not check4:
            result.failures.append("WakingSequenceFairy fails to import")
            result.passed = False

        return result

    async def _verify_phase_2_imports(self) -> VerificationResult:
        """
        Phase 2: Import Resolution
        - All imports resolve?
        - No ImportError on boot?
        - Re-export shims work?
        """
        result = VerificationResult(phase=2, passed=True)

        # Check key imports from both paths
        test_imports = [
            ("fairies.P00_Autonomic.postal", "Fifth Ring path"),
            ("P00_Autonomic.postal", "Legacy path (should re-export)"),
            ("fairies.P10_Memory", "Memory plane"),
            ("fairies.P30_Cognition", "Cognition plane"),
        ]

        for module, desc in test_imports:
            success = await self._test_import(module)
            result.checks.append({
                "name": f"Import {module}",
                "passed": success,
                "result": f"{desc}: {'OK' if success else 'FAILED'}"
            })
            if not success and "fairies." in module:
                # Fifth Ring imports are critical
                result.failures.append(f"Critical import failed: {module}")
                result.passed = False
            elif not success:
                result.warnings.append(f"Legacy import failed: {module}")

        # Check re-export shims exist
        shim_paths = [
            "P00_Autonomic/__init__.py",
            "P10_Memory/__init__.py",
            "P20_Somatic/__init__.py",
            "P30_Cognition/__init__.py",
        ]
        for shim in shim_paths:
            exists = (PROJECT_ROOT / shim).exists()
            result.checks.append({
                "name": f"Re-export shim {shim}",
                "passed": exists,
                "result": "Exists" if exists else "Missing"
            })
            if not exists:
                result.warnings.append(f"Re-export shim missing: {shim}")

        return result

    async def _verify_phase_3_empathic_loops(self) -> VerificationResult:
        """
        Phase 3: Empathic Loop Closure
        - Pain relief propagates?
        - Goal completion notifies?
        - Attention gets feedback?
        """
        result = VerificationResult(phase=3, passed=True)

        # Check for loop closure patterns
        loop_checks = [
            ("fairies/P30_Cognition/pain_drives.py", ["relieve", "callback"], "Pain loop closure"),
            ("fairies/P30_Cognition/goal_scheduler", ["complete", "notify"], "Goal loop closure"),
            ("fairies/P30_Cognition/AttentionControllerFairy", ["result", "feedback"], "Attention loop closure"),
        ]

        for path, patterns, desc in loop_checks:
            check = await self._check_code_contains(path, patterns, desc)
            result.checks.append(check)
            if not check["passed"]:
                result.warnings.append(f"Loop may not be closed: {desc}")

        # Check for AFFECT2 return pattern
        return_patterns = await self._grep_codebase("update_origin|notify_source|close_loop")
        result.checks.append({
            "name": "AFFECT2 return patterns exist",
            "passed": len(return_patterns) > 0,
            "result": f"Found {len(return_patterns)} return patterns"
        })

        return result

    async def _verify_phase_4_cleanup(self) -> VerificationResult:
        """
        Phase 4: Zombie Cleanup + Postal Unification
        - No duplicate fairy classes?
        - PostalUnifier exists?
        - _extract_payload centralized?
        """
        result = VerificationResult(phase=4, passed=True)

        # Check PostalUnifier exists
        unifier_path = PROJECT_ROOT / "fairies" / "P00_Autonomic" / "postal_unifier.py"
        result.checks.append({
            "name": "PostalUnifier exists",
            "passed": unifier_path.exists(),
            "result": "Found" if unifier_path.exists() else "Missing"
        })
        if not unifier_path.exists():
            result.warnings.append("PostalUnifier not created yet")

        # Check shared utils
        utils_path = PROJECT_ROOT / "fairies" / "P00_Autonomic" / "utils" / "payload.py"
        result.checks.append({
            "name": "Shared _extract_payload",
            "passed": utils_path.exists(),
            "result": "Centralized" if utils_path.exists() else "Still duplicated"
        })

        # Check for archive
        archive_path = PROJECT_ROOT / "_archive"
        result.checks.append({
            "name": "Archive created",
            "passed": archive_path.exists(),
            "result": "Backup exists" if archive_path.exists() else "No backup"
        })

        return result

    async def _verify_phase_5_directory(self) -> VerificationResult:
        """
        Phase 5: Directory + CharacterSheets + TracerDaemon
        - DirectoryFairy registered?
        - CharacterSheet mixin available?
        - Error routing works?
        """
        result = VerificationResult(phase=5, passed=True)

        # Check DirectoryFairy
        check1 = await self._check_code_contains(
            "fairies/P00_Autonomic/DirectoryFairy",
            ["ACTOR_PLANE", "ACTOR_CHANNEL"],
            "DirectoryFairy registered"
        )
        result.checks.append(check1)
        if not check1["passed"]:
            result.failures.append("DirectoryFairy not properly registered")
            result.passed = False

        # Check CharacterSheet
        check2 = await self._check_code_contains(
            "fairies/P10_Memory/memory_cards.py",
            ["CharacterSheet", "CharacterSheetMixin"],
            "CharacterSheet system"
        )
        result.checks.append(check2)

        # Check error routing
        check3 = await self._check_code_contains(
            "fairies/P00_Autonomic/DirectoryFairy",
            ["TracerDaemon", "report_error"],
            "Error routing to TracerDaemon"
        )
        result.checks.append(check3)

        return result

    # Helper methods

    async def _check_code_contains(self, path: str, patterns: List[str], description: str) -> Dict[str, Any]:
        """Check if a file/directory contains all patterns."""
        full_path = PROJECT_ROOT / path
        if not full_path.exists():
            # Try with fairies/ prefix
            full_path = PROJECT_ROOT / "fairies" / path

        if not full_path.exists():
            return {
                "name": description,
                "passed": False,
                "result": f"Path not found: {path}"
            }

        # Read all files in path
        content = ""
        if full_path.is_file():
            try:
                content = full_path.read_text(encoding="utf-8")
            except:
                content = ""
        else:
            for f in full_path.rglob("*.py"):
                try:
                    content += f.read_text(encoding="utf-8")
                except:
                    pass

        # Check all patterns
        found = all(p.lower() in content.lower() for p in patterns)

        return {
            "name": description,
            "passed": found,
            "result": f"All patterns found" if found else f"Missing patterns: {[p for p in patterns if p.lower() not in content.lower()]}"
        }

    async def _test_import(self, module: str) -> bool:
        """Test if a module can be imported."""
        try:
            importlib.import_module(module)
            return True
        except Exception as e:
            return False

    async def _grep_codebase(self, pattern: str) -> List[str]:
        """Search codebase for pattern."""
        results = []
        for f in PROJECT_ROOT.rglob("*.py"):
            if "_archive" in str(f) or "__pycache__" in str(f):
                continue
            try:
                content = f.read_text(encoding="utf-8")
                if pattern.lower() in content.lower():
                    results.append(str(f))
            except:
                pass
        return results

    def _save_result(self, result: VerificationResult):
        """Save result to file and codex."""
        # JSON result
        json_path = self.results_path / f"phase_{result.phase}_{result.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2)

        # Codex entry
        codex_path = self.results_path / f"phase_{result.phase}_latest.md"
        with open(codex_path, "w", encoding="utf-8") as f:
            f.write(result.to_codex_entry())


# Convenience functions
async def verify_phase_1() -> VerificationResult:
    return await PhaseGate().verify_phase(1)

async def verify_phase_2() -> VerificationResult:
    return await PhaseGate().verify_phase(2)

async def verify_phase_3() -> VerificationResult:
    return await PhaseGate().verify_phase(3)

async def verify_phase_4() -> VerificationResult:
    return await PhaseGate().verify_phase(4)

async def verify_phase_5() -> VerificationResult:
    return await PhaseGate().verify_phase(5)

async def verify_all_phases() -> Dict[int, VerificationResult]:
    """Verify all phases and return results."""
    gate = PhaseGate()
    results = {}
    for phase in range(1, 6):
        results[phase] = await gate.verify_phase(phase)
        if not results[phase].passed:
            print(f"[STOP] Phase {phase} FAILED - stopping verification")
            break
        print(f"[OK] Phase {phase} PASSED")
    return results


if __name__ == "__main__":
    # CLI interface
    import sys

    async def main():
        if len(sys.argv) > 1:
            phase = int(sys.argv[1])
            result = await PhaseGate().verify_phase(phase)
        else:
            print("Verifying all phases...")
            results = await verify_all_phases()
            return

        print(result.to_codex_entry())

    asyncio.run(main())
