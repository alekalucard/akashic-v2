# ===============================================================================
# DYNAMIC FAIRY SCANNER - Self-Perception for Autonomous Evolution
# ===============================================================================
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > inf)"
#
# Unlike the static fairy_census.py registry, this module READS the actual
# fairy files to determine their true wiring state. Essential for:
# - Self-diagnosis
# - Autonomous patching
# - Evolution verification
# ===============================================================================

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class FairyScanResult:
    """Result of scanning a fairy file for wiring state."""
    name: str
    file_path: str
    exists: bool
    has_postal: bool
    has_heartbeat: bool
    has_collision: bool
    has_dual_loop: bool
    has_on_boot: bool
    is_postal_exempt: bool
    subscriptions: List[str]
    handlers: List[str]
    
    @property
    def is_fully_wired(self) -> bool:
        """True if fairy has both postal and heartbeat."""
        return self.has_postal and self.has_heartbeat
    
    @property
    def wiring_score(self) -> float:
        """Score from 0.0 to 1.0 based on features present."""
        checks = [
            self.has_postal,
            self.has_heartbeat,
            self.has_collision,
            self.has_dual_loop,
        ]
        return sum(checks) / len(checks) if checks else 0.0


def scan_fairy(name: str, file_path: str) -> FairyScanResult:
    """
    Dynamically scan a fairy file to determine its actual wiring state.
    
    This reads the file content rather than relying on static registry entries.
    """
    result = FairyScanResult(
        name=name,
        file_path=file_path,
        exists=os.path.exists(file_path),
        has_postal=False,
        has_heartbeat=False,
        has_collision=False,
        has_dual_loop=False,
        has_on_boot=False,
        is_postal_exempt=False,
        subscriptions=[],
        handlers=[],
    )
    
    if not result.exists:
        return result
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        return result
    
    # Check for postal integration
    result.has_postal = 'self.post' in content or 'SharedPostalHub' in content
    
    # Check for heartbeat subscription
    result.has_heartbeat = 'heartbeat.pulse' in content or 'somatic.pulse' in content
    
    # Check for collision subscription
    result.has_collision = 'consciousness.collision' in content
    
    # Check for dual loop
    result.has_dual_loop = 'working_stream' in content or 'reflective_stream' in content
    
    # Check for on_boot
    result.has_on_boot = 'def on_boot(self)' in content
    
    # Some fairies are exempt from postal (monitoring/debug tools)
    result.is_postal_exempt = not result.has_postal and not result.has_on_boot
    
    # Extract subscriptions
    sub_pattern = r'\.subscribe\(["\']([\w.]+)["\'](,|\))'
    result.subscriptions = re.findall(sub_pattern, content)
    result.subscriptions = [s[0] for s in result.subscriptions]
    
    # Extract handlers
    handler_pattern = r'def (_on_[a-z_]+)\(self'
    result.handlers = re.findall(handler_pattern, content)
    
    return result


def scan_all_fairies(registry: Dict = None) -> Dict[str, FairyScanResult]:
    """
    Scan all fairies from the registry.
    
    If registry is None, imports from fairy_census.py
    """
    if registry is None:
        from fairies.P00_Autonomic.nervous_system.fairy_census import FAIRY_REGISTRY
        registry = FAIRY_REGISTRY
    
    # Known path corrections
    path_corrections = {
        'CartographerFairy': 'P00_Autonomic/nervous_system/cartographer_fairy.py',
    }
    
    results = {}
    for name, profile in registry.items():
        path = path_corrections.get(name, profile.file_path)
        results[name] = scan_fairy(name, path)
    
    return results


def get_wiring_report() -> str:
    """Generate a human-readable wiring report."""
    results = scan_all_fairies()
    
    lines = [
        "=" * 70,
        "FAIRY WIRING SCAN REPORT",
        "=" * 70,
        "",
    ]
    
    fully_wired = 0
    exempt = 0
    needs_work = []
    
    for name, scan in results.items():
        if not scan.exists:
            lines.append(f"[??] {name:<35} FILE NOT FOUND")
            needs_work.append(name)
        elif scan.is_postal_exempt:
            lines.append(f"[EX] {name:<35} (exempt)")
            exempt += 1
        elif scan.is_fully_wired:
            extras = []
            if scan.has_collision: extras.append('COLL')
            if scan.has_dual_loop: extras.append('DUAL')
            extra_str = f" + {', '.join(extras)}" if extras else ""
            lines.append(f"[OK] {name:<35} POST + HB{extra_str}")
            fully_wired += 1
        else:
            missing = []
            if not scan.has_postal: missing.append('postal')
            if not scan.has_heartbeat: missing.append('heartbeat')
            lines.append(f"[  ] {name:<35} needs: {', '.join(missing)}")
            needs_work.append(name)
    
    lines.extend([
        "",
        "=" * 70,
        f"FULLY WIRED: {fully_wired} | EXEMPT: {exempt} | NEEDS WORK: {len(needs_work)}",
        "=" * 70,
    ])
    
    return "\n".join(lines)


if __name__ == "__main__":
    print(get_wiring_report())
