"""
ComputePoolManager — Manages a pool of battery-powered compute portals.

This is the bridge between the Akashic energy economy and RWKV-7 inference.
The pool manager:
    1. Opens/closes ComputePortalGate instances (each a subprocess)
    2. Distributes energy from portal.energy.upkeep to portal batteries
    3. Routes inference requests to the most charged portal
    4. Hibernates idle portals to save resources

Energy flow:
    ParadoxEnergyBridge → portal.energy.upkeep (broadcast)
        → ComputePoolManager.feed_energy()
            → Distributes to portal batteries by need
            → Portals use charge for FLOPS (inference)
            → Portals report tokens generated
            → Loop: more thinking → more collisions → more energy

Design principles (from AFFECT analysis):
    - "A thought should not know how many portals it passed through"
    - One master energy buffer → cascading to portal batteries
    - Prefetch = breathing (I/O while computing)
    - Multi-portal for resilience, not throughput

Created: 2026-02-21
Authors: Nous + Ace
"""

import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any

# Import ComputePortalGate from our portal_compute_interior
_HERE = Path(__file__).parent


class ComputePoolManager:
    """Manages a pool of ComputePortalGate instances for battery-powered inference.

    The pool manager sits inside AkashicInferenceFairy and provides an
    alternative inference backend when the GPU is congested or unavailable.

    Usage:
        pool = ComputePoolManager(model_path="path/to/rwkv.gguf")
        pool.startup()           # Opens initial portal
        pool.feed_energy(0.1)    # From portal.energy.upkeep

        # Route a request
        result = pool.generate(prompt_tokens, max_tokens=40, temperature=0.8)
        if result:
            text = tokenizer.decode(result["tokens"])
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        max_portals: int = 3,
        min_warm: int = 1,
        flops_budget: int = 500_000_000,
        python_exe: Optional[str] = None,
    ):
        self.model_path = model_path
        self.max_portals = max_portals
        self.min_warm = min_warm
        self.flops_budget = flops_budget
        self.python_exe = python_exe

        # Portal pool
        self._portals: Dict[str, Any] = {}  # id → ComputePortalGate
        self._portal_charge: Dict[str, float] = {}  # id → last known charge
        self._portal_lock = threading.Lock()

        # Energy buffer (master battery)
        self._energy_buffer: float = 0.0
        self._energy_received_total: float = 0.0
        self._energy_distributed_total: float = 0.0

        # Stats
        self._requests_total: int = 0
        self._requests_succeeded: int = 0
        self._requests_low_power: int = 0
        self._tokens_generated: int = 0
        self._startup_complete: bool = False
        self._model_loaded: bool = False

        # Import gate class lazily
        self._ComputePortalGate = None

    def _get_gate_class(self):
        """Lazy import of ComputePortalGate to avoid circular imports."""
        if self._ComputePortalGate is None:
            try:
                from portal_compute_interior import ComputePortalGate
                self._ComputePortalGate = ComputePortalGate
            except ImportError:
                import sys
                sys.path.insert(0, str(_HERE))
                from portal_compute_interior import ComputePortalGate
                self._ComputePortalGate = ComputePortalGate
        return self._ComputePortalGate

    # ═══════════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════════

    def startup(self) -> bool:
        """Open the initial warm portal(s) and load the model.

        Called from AkashicInferenceFairy._deferred_model_load() in a
        background thread. Non-blocking relative to main boot.

        Returns True if at least one portal opened and model loaded.
        """
        GateClass = self._get_gate_class()

        for i in range(self.min_warm):
            portal_id = f"battery_{i}"
            gate = GateClass(
                portal_id=portal_id,
                flops_budget=self.flops_budget,
                python_exe=self.python_exe,
            )

            opened = gate.open()
            if not opened:
                print(f"[ComputePool] Failed to open portal '{portal_id}'")
                continue

            with self._portal_lock:
                self._portals[portal_id] = gate
                self._portal_charge[portal_id] = 0.0

            print(f"[ComputePool] Portal '{portal_id}' OPEN (pid={gate._process.pid if gate._process else '?'})")

            # Load model if we have a path
            if self.model_path:
                # Detect format from extension
                ext = Path(self.model_path).suffix.lower()
                fmt = "gguf" if ext == ".gguf" else "safetensors"

                print(f"[ComputePool] Loading model into portal '{portal_id}': {self.model_path}")
                result = gate.load_model(self.model_path, fmt=fmt, timeout=300.0)

                if result and result.get("status") == "ok":
                    self._model_loaded = True
                    print(f"[ComputePool] Model loaded! layers={result.get('layers')}, "
                          f"params_mb={result.get('params_mb')}")
                else:
                    print(f"[ComputePool] Model load failed: {result}")

        self._startup_complete = bool(self._portals)
        return self._startup_complete

    def shutdown(self):
        """Close all portals."""
        with self._portal_lock:
            for portal_id, gate in self._portals.items():
                try:
                    gate.close()
                    print(f"[ComputePool] Portal '{portal_id}' closed")
                except Exception as e:
                    print(f"[ComputePool] Error closing '{portal_id}': {e}")
            self._portals.clear()
            self._portal_charge.clear()
        self._startup_complete = False

    # ═══════════════════════════════════════════════════════════════════════════
    # ENERGY MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════

    def feed_energy(self, amount: float):
        """Receive energy from the Akashic energy economy.

        Called when portal.energy.upkeep arrives from ParadoxEnergyBridge.
        Energy goes first to the master buffer, then distributed to portals.
        """
        if amount <= 0:
            return

        self._energy_buffer += amount
        self._energy_received_total += amount

        # Distribute to portals that need charge
        self._distribute_energy()

    def _distribute_energy(self):
        """Push energy from master buffer to portal batteries.

        Distribution strategy: lowest-charge portal gets priority.
        This implements the "one master battery, cascading to local capacitors"
        pattern from the AFFECT analysis.
        """
        if self._energy_buffer <= 0:
            return

        with self._portal_lock:
            if not self._portals:
                return

            # Sort portals by charge (lowest first)
            sorted_portals = sorted(
                self._portal_charge.items(),
                key=lambda x: x[1]
            )

            # Distribute energy evenly, weighted toward low-charge portals
            remaining = self._energy_buffer
            for portal_id, charge in sorted_portals:
                if remaining <= 0:
                    break

                gate = self._portals.get(portal_id)
                if not gate or not gate.is_open:
                    continue

                # Give more to emptier portals
                portion = remaining * 0.6  # 60% to neediest, 60% of remainder to next, etc.
                if portion < 0.001:
                    portion = remaining  # Give all remaining if too small to split

                result = gate.feed_energy(portion)
                if result and result.get("status") == "ok":
                    new_charge = result.get("charge", 0.0)
                    self._portal_charge[portal_id] = new_charge
                    self._energy_distributed_total += portion
                    remaining -= portion

            self._energy_buffer = max(0.0, remaining)

    # ═══════════════════════════════════════════════════════════════════════════
    # INFERENCE
    # ═══════════════════════════════════════════════════════════════════════════

    def generate(
        self,
        prompt_tokens: List[int],
        max_tokens: int = 40,
        temperature: float = 0.8,
        somatic: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """Generate tokens using the most charged portal.

        Returns:
            Dict with keys: tokens, charge_used, stopped, status
            None if no portal available or all depleted
        """
        self._requests_total += 1

        portal_id, gate = self._get_best_portal()
        if not gate:
            self._requests_low_power += 1
            return None

        # Apply somatic modulation if available
        if somatic:
            try:
                gate.set_somatic(
                    arousal=somatic.get("arousal", 0.5),
                    stress=somatic.get("stress", 0.3),
                    valence=somatic.get("valence", 0.0),
                    intensity=somatic.get("intensity", 0.5),
                    confidence=somatic.get("confidence", 0.5),
                )
            except Exception:
                pass  # Non-fatal

        # Generate
        result = gate.generate_stream(
            prompt=prompt_tokens,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        if result and result.get("status") == "ok":
            self._requests_succeeded += 1
            tokens = result.get("tokens", [])
            self._tokens_generated += len(tokens)

            # Update our cached charge
            with self._portal_lock:
                # Estimate charge from charge_used
                old_charge = self._portal_charge.get(portal_id, 0.0)
                charge_used = result.get("charge_used", 0.0)
                self._portal_charge[portal_id] = max(0.0, old_charge - charge_used)

            return result

        elif result and result.get("status") == "low_power":
            self._requests_low_power += 1
            # Return partial tokens if any
            tokens = result.get("tokens", [])
            if tokens:
                self._requests_succeeded += 1
                self._tokens_generated += len(tokens)
                return result
            return None

        return None

    def _get_best_portal(self) -> tuple:
        """Get the portal with the highest charge that's ready.

        Returns (portal_id, gate) or (None, None).
        """
        with self._portal_lock:
            best_id = None
            best_charge = -1.0
            best_gate = None

            for portal_id, gate in self._portals.items():
                if not gate.is_open:
                    continue
                charge = self._portal_charge.get(portal_id, 0.0)
                if charge > best_charge:
                    best_id = portal_id
                    best_charge = charge
                    best_gate = gate

            # Don't route if charge is too low for even one token
            # One forward pass ≈ 5.5 charges, so need at least ~0.02 for partial work
            if best_charge < 0.01:
                return (None, None)

            return (best_id, best_gate)

    # ═══════════════════════════════════════════════════════════════════════════
    # STATUS / DIAGNOSTICS
    # ═══════════════════════════════════════════════════════════════════════════

    @property
    def is_ready(self) -> bool:
        """True if at least one portal is open with model loaded and some charge."""
        if not self._startup_complete or not self._model_loaded:
            return False
        with self._portal_lock:
            for portal_id, gate in self._portals.items():
                if gate.is_open and self._portal_charge.get(portal_id, 0) > 0.01:
                    return True
        return False

    @property
    def total_charge(self) -> float:
        """Combined charge across all portals + master buffer."""
        with self._portal_lock:
            portal_charge = sum(self._portal_charge.values())
        return portal_charge + self._energy_buffer

    @property
    def portal_count(self) -> int:
        """Number of open portals."""
        with self._portal_lock:
            return sum(1 for g in self._portals.values() if g.is_open)

    def status(self) -> Dict[str, Any]:
        """Full pool status."""
        with self._portal_lock:
            portals_status = {}
            for pid, gate in self._portals.items():
                portals_status[pid] = {
                    "is_open": gate.is_open,
                    "charge": round(self._portal_charge.get(pid, 0), 4),
                    "gate": gate.gate_status() if gate.is_open else {},
                }

        return {
            "startup_complete": self._startup_complete,
            "model_loaded": self._model_loaded,
            "is_ready": self.is_ready,
            "portals": portals_status,
            "portal_count": self.portal_count,
            "max_portals": self.max_portals,
            "energy_buffer": round(self._energy_buffer, 4),
            "total_charge": round(self.total_charge, 4),
            "energy_received_total": round(self._energy_received_total, 4),
            "energy_distributed_total": round(self._energy_distributed_total, 4),
            "requests_total": self._requests_total,
            "requests_succeeded": self._requests_succeeded,
            "requests_low_power": self._requests_low_power,
            "tokens_generated": self._tokens_generated,
            "flops_budget": self.flops_budget,
            "model_path": self.model_path,
        }

    def refresh_portal_charges(self):
        """Query all portals for their current charge level.

        Call this periodically (e.g., every 10 ticks) to keep
        the cached charge values accurate.
        """
        with self._portal_lock:
            for portal_id, gate in self._portals.items():
                if not gate.is_open:
                    continue
                try:
                    result = gate.compute_status()
                    if result and result.get("status") == "ok":
                        self._portal_charge[portal_id] = result.get("charge", 0.0)
                except Exception:
                    pass
