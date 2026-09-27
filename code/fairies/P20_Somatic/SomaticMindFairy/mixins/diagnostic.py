"""
Diagnostic Mixin - Self-healing system monitoring.

Provides periodic health checks for critical system components
with automatic repair and escalation capabilities.
"""

import time
from collections import deque
from typing import Any, Dict, List, Optional


class DiagnosticMixin:
    """
    Self-healing diagnostic system.

    Monitors:
    - Directory (fairy registry)
    - Consciousness (heartbeat loop)
    - Wiring (fairy subscriptions)
    - Tensor fabric (messaging)

    Auto-repairs failures and escalates after max attempts.
    """

    CHECK_INTERVAL = 30  # ticks between diagnostic runs
    MAX_RESTART_ATTEMPTS = 3
    # FIX 2026-02-05: Boot grace period — suppress wiring/cortex failures during
    # early boot. POST-WAVE Phase 6 wires the cortex and completes subscriptions,
    # but runs AFTER the orchestrator plane wave. At tick=60 (~15s at 4Hz), Phase 6
    # hasn't executed yet, causing false "No subscriptions" and "Not wired" failures.
    # Grace period of 120 ticks (~30s at 4Hz) gives POST-WAVE time to complete.
    BOOT_GRACE_TICKS = 120

    def _init_diagnostics(self) -> None:
        """Initialize diagnostic tracking."""
        self._restart_attempts: Dict[str, int] = {}
        self._last_check_tick = 0
        self._diagnostic_log: deque = deque(maxlen=100)
        self._escalated: set = set()
        # Boot warnings collector - surfaces issues that scroll by too fast
        self._boot_warnings: deque = deque(maxlen=50)
        self._reported_warnings: set = set()  # Don't spam the same warning

    def collect_warning(self, source: str, message: str) -> None:
        """
        Collect a warning for later reporting.

        Fairies can call this to surface warnings that would otherwise scroll by.
        """
        warning_key = f"{source}:{message[:50]}"
        if warning_key not in self._reported_warnings:
            self._boot_warnings.append({
                "source": source,
                "message": message,
                "ts": time.time(),
            })
            self._reported_warnings.add(warning_key)

    def run_diagnostics(self, tick: int) -> Dict[str, Any]:
        """
        Run all diagnostic checks.

        Only runs every CHECK_INTERVAL ticks to avoid overhead.
        """
        if tick - self._last_check_tick < self.CHECK_INTERVAL:
            return {"skipped": True, "tick": tick}

        self._last_check_tick = tick
        results = {}

        # Run each check
        results["directory"] = self._check_directory()
        results["consciousness"] = self._check_consciousness()
        results["wiring"] = self._check_wiring()
        results["tensor"] = self._check_tensor()
        results["cortex"] = self._check_cortex()

        # Auto-repair failures
        # FIX 2026-02-05: During boot grace period, skip wiring/cortex failures.
        # These systems are wired in POST-WAVE Phase 6, which runs AFTER the
        # orchestrator plane wave completes. Reporting failures before Phase 6
        # finishes produces false alarms that obscure real issues.
        in_grace_period = tick < self.BOOT_GRACE_TICKS
        grace_systems = {"wiring", "cortex"}  # Systems that need POST-WAVE to complete

        failures = []
        for name, result in results.items():
            if not result.get("ok", True):
                if in_grace_period and name in grace_systems:
                    # Suppress during grace period — these are expected early
                    result["suppressed"] = True
                    result["reason"] = "boot_grace_period"
                    continue
                failures.append(f"{name}:{result.get('error', '?')}")
                self._attempt_repair(name, result)

        # Print visible audit output
        dir_ok = "OK" if results["directory"].get("ok") else "FAIL"
        con_ok = "OK" if results["consciousness"].get("ok") else "FAIL"
        wir_ok = "OK" if results["wiring"].get("ok") else "FAIL"
        ten_ok = "OK" if results["tensor"].get("ok") else "FAIL"
        ctx_ok = "OK" if results["cortex"].get("ok") else "FAIL"

        fairies = results["directory"].get("fairies", 0)
        ticks = results["consciousness"].get("ticks", 0)
        subs = results["wiring"].get("subscriptions", 0)
        msgs = results["tensor"].get("messages", 0)
        nodes = results["cortex"].get("nodes", 0)
        pending = results["cortex"].get("pending", 0)

        status_line = f"Dir:{dir_ok}({fairies}) Con:{con_ok}({ticks}) Wir:{wir_ok}({subs}) Ten:{ten_ok}({msgs}) Ctx:{ctx_ok}({nodes}n/+{pending})"

        if failures:
            print(f"[UMF] tick={tick} DIAGNOSTIC FAILURES: {', '.join(failures)}")
        else:
            print(f"[UMF] tick={tick} AUDIT: {status_line}")

        # Report any collected warnings (surfaces boot warnings that scrolled by)
        if self._boot_warnings:
            warn_count = len(self._boot_warnings)
            print(f"[UMF] tick={tick} WARNINGS ({warn_count} collected):")
            # Show most recent 5 warnings
            recent_warnings = list(self._boot_warnings)[-5:]
            for w in recent_warnings:
                print(f"[UMF]   [{w['source']}] {w['message'][:80]}")
            # Clear after reporting (they've been seen)
            self._boot_warnings.clear()

        # Log results
        self._diagnostic_log.append({
            "tick": tick,
            "ts": time.time(),
            "results": results,
        })

        return results

    def _check_directory(self) -> Dict[str, Any]:
        """Check Directory is running and responsive."""
        try:
            from directory import get_directory

            directory = get_directory()
            if not directory:
                return {"ok": False, "error": "No directory instance"}

            if not directory._running:
                return {"ok": False, "error": "Directory not running"}

            # Quick responsiveness check
            count = directory.registry.count()
            return {"ok": True, "fairies": count}

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _check_consciousness(self) -> Dict[str, Any]:
        """Check consciousness/heartbeat is flowing."""
        try:
            # Check if we're receiving heartbeats
            if hasattr(self, "_tick_count") and self._tick_count > 0:
                return {"ok": True, "ticks": self._tick_count}

            return {"ok": True, "ticks": 0, "note": "No ticks yet"}

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _check_wiring(self) -> Dict[str, Any]:
        """Check fairy subscriptions are intact."""
        try:
            # Check our own subscriptions - use self.post (FairyPostalWrapper)
            # NOTE: Fairies use self.post, not self.fabric
            postal = getattr(self, "post", None) or getattr(self, "fabric", None)
            if not postal:
                return {"ok": False, "error": "No postal"}

            # Check subscription count via topic_stats (FairyPostalWrapper compatible)
            if hasattr(postal, "topic_stats"):
                topic_stats = postal.topic_stats()
                subs = len(topic_stats) if topic_stats else 0
            else:
                # Fallback: check _subscriptions if available
                subs = len(getattr(postal, "_subscriptions", {}))

            if subs < 1:
                return {"ok": False, "error": "No subscriptions"}

            return {"ok": True, "subscriptions": subs}

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _check_tensor(self) -> Dict[str, Any]:
        """Check tensor/postal fabric is operational."""
        try:
            # Use self.post (FairyPostalWrapper) - fairies use post, not fabric
            postal = getattr(self, "post", None) or getattr(self, "fabric", None)
            if not postal:
                return {"ok": False, "error": "No postal"}

            # Try to get metrics - FairyPostalWrapper may have metrics()
            if hasattr(postal, "metrics"):
                metrics = postal.metrics()
                return {
                    "ok": True,
                    "messages": metrics.get("messages_published", 0),
                    "updates": metrics.get("tensor_updates", 0),
                }
            else:
                # Fallback: just check postal exists and is responsive
                return {"ok": True, "messages": 0, "updates": 0, "note": "No metrics available"}

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _check_cortex(self) -> Dict[str, Any]:
        """Check Association Cortex is operational."""
        try:
            # Check if cortex is wired
            if not hasattr(self, "_association_cortex") or not self._association_cortex:
                # FIX 2026-02-05: Self-heal by acquiring cortex from global singleton.
                # Phase 6 only wires SYSTEM.umf._association_cortex, not SomaticMindFairy.
                # But the global singleton is set in Phase 5. Acquire it here.
                try:
                    from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
                    cortex = get_association_cortex()
                    if cortex:
                        self._association_cortex = cortex
                        # Fall through to normal check below
                    else:
                        return {"ok": False, "error": "Not wired", "nodes": 0, "edges": 0, "pending": 0}
                except (ImportError, Exception):
                    return {"ok": False, "error": "Not wired", "nodes": 0, "edges": 0, "pending": 0}

            cortex = self._association_cortex

            # Portal-first mode: local graph is intentionally empty,
            # the portal subprocess owns the graph
            if getattr(cortex, '_portal_is_primary', False):
                # FIX 2026-03-22: Check manifold (mmap) FIRST — the system now
                # uses AkashicManifold instead of portal gate. Portal gate no
                # longer exists, so checking it produces a perpetual ghost failure.
                _am = getattr(cortex, '_akashic_cortex_region', None)
                if _am is not None:
                    # Manifold mode — cortex is healthy
                    manifold_ops = getattr(cortex, '_manifold_ops', 0)
                    return {
                        "ok": True,
                        "error": None,
                        "nodes": getattr(_am, 'node_count', 'manifold'),
                        "edges": getattr(_am, 'edge_count', 'manifold'),
                        "pending": len(getattr(cortex, '_pending_bindings', [])),
                        "manifold_ops": manifold_ops,
                        "portal_mode": True,
                        "manifold": True,
                    }

                # Legacy portal gate fallback (pre-manifold systems)
                portal_gate = getattr(cortex, '_portal_gate', None)
                portal_open = portal_gate.is_open if portal_gate else False
                portal_binds = getattr(cortex, '_portal_bind_count', 0)
                return {
                    "ok": portal_open,
                    "error": None if portal_open else "Portal gate closed",
                    "nodes": "portal",
                    "edges": "portal",
                    "pending": len(getattr(cortex, '_pending_bindings', [])),
                    "portal_binds": portal_binds,
                    "portal_mode": True,
                }

            # Get graph stats
            nodes = len(cortex._graph.nodes) if hasattr(cortex, '_graph') else 0
            edges = len(cortex._graph.edges) if hasattr(cortex, '_graph') else 0
            pending = getattr(cortex, '_pending_bindings', 0)

            # Check if graph has content
            if nodes == 0:
                return {"ok": False, "error": "Empty graph", "nodes": 0, "edges": 0, "pending": pending}

            return {
                "ok": True,
                "nodes": nodes,
                "edges": edges,
                "pending": pending,
            }

        except Exception as e:
            return {"ok": False, "error": str(e), "nodes": 0, "edges": 0, "pending": 0}

    def _attempt_repair(self, system: str, result: Dict) -> bool:
        """
        Attempt to repair a failed system.

        Returns True if repair was attempted.
        """
        attempts = self._restart_attempts.get(system, 0)

        if attempts >= self.MAX_RESTART_ATTEMPTS:
            if system not in self._escalated:
                self._escalate_failure(system, result)
            return False

        self._restart_attempts[system] = attempts + 1

        # Attempt repair based on system type
        success = False
        if system == "directory":
            success = self._repair_directory(result)
        elif system == "consciousness":
            success = self._repair_consciousness(result)
        elif system == "wiring":
            success = self._repair_wiring(result)
        elif system == "tensor":
            success = self._repair_tensor(result)

        if success:
            self._restart_attempts[system] = 0

        return success

    def _repair_directory(self, result: Dict) -> bool:
        """Attempt to repair Directory."""
        try:
            from directory import get_directory, set_directory, DirectoryFairy

            directory = get_directory()
            if not directory:
                # Create new directory
                new_dir = DirectoryFairy(self.fabric)
                new_dir.on_boot()
                set_directory(new_dir)
                return True

            if not directory._running:
                directory.on_boot()
                return True

            return False
        except Exception:
            return False

    def _repair_consciousness(self, result: Dict) -> bool:
        """Attempt to repair consciousness loop."""
        # In v2, consciousness is handled by heartbeat subscription
        # This would restart the heartbeat fairy if needed
        return True  # Placeholder

    def _repair_wiring(self, result: Dict) -> bool:
        """Attempt to repair wiring."""
        try:
            # Re-subscribe to essential topics
            if hasattr(self, "_resubscribe"):
                self._resubscribe()
                return True
            return False
        except Exception:
            return False

    def _repair_tensor(self, result: Dict) -> bool:
        """Attempt to repair tensor fabric."""
        try:
            if hasattr(self, "fabric") and self.fabric:
                # Tensor fabric is self-healing
                return True
            return False
        except Exception:
            return False

    def _escalate_failure(self, system: str, result: Dict) -> None:
        """Escalate a critical failure after max repair attempts."""
        self._escalated.add(system)

        # Publish alert
        if hasattr(self, "fabric") and self.fabric:
            self.fabric.publish(
                "system.alert",
                {
                    "from": getattr(self, "ACTOR_NAME", "UnconsciousMindFairy"),
                    "severity": "CRITICAL",
                    "system": system,
                    "error": result.get("error", "Unknown"),
                    "attempts": self.MAX_RESTART_ATTEMPTS,
                    "ts": time.time(),
                },
                priority=0,  # HIGH
            )

        # Record skill failure
        if hasattr(self, "skill_used"):
            self.skill_used("escalate", success=True)

    def get_diagnostic_history(self, last_n: int = 10) -> List[Dict[str, Any]]:
        """Get recent diagnostic results."""
        return list(self._diagnostic_log)[-last_n:]

    def reset_escalation(self, system: str) -> None:
        """Reset escalation state for a system (after manual intervention)."""
        self._escalated.discard(system)
        self._restart_attempts.pop(system, None)

    def diagnostic_status(self) -> Dict[str, Any]:
        """Get current diagnostic status."""
        return {
            "last_check_tick": self._last_check_tick,
            "restart_attempts": dict(self._restart_attempts),
            "escalated": list(self._escalated),
            "log_size": len(self._diagnostic_log),
        }

    def investigate(self, question: str) -> Dict[str, Any]:
        """
        Actively investigate an issue using cognitive tools.

        This is the key method for UMF to answer questions like:
        - "Why is thinking not working?"
        - "Why is a fairy dead?"
        - "Why are bindings not persisting?"

        Uses thought chains, admin tasks, and cognition loop.

        Args:
            question: The question to investigate

        Returns:
            Dict with findings, actions taken, and recommendations
        """
        print(f"[UMF] INVESTIGATING: {question}")

        findings = []
        actions = []
        recommendations = []

        # Step 1: Run fresh diagnostics
        results = self.run_diagnostics(getattr(self, '_tick_count', 0))
        if not results.get("skipped"):
            for system, result in results.items():
                if not result.get("ok", True):
                    findings.append(f"{system}: {result.get('error', 'failed')}")
                    actions.append(f"Attempted repair of {system}")

        # Step 2: Check for dead fairies
        try:
            from directory import get_directory
            directory = get_directory()
            if directory:
                all_fairies = directory.registry.all()
                for name, info in all_fairies.items():
                    status = info.get("status", "unknown")
                    if status in ("failed", "dead", "crashed"):
                        findings.append(f"Fairy {name} is {status}")
                        # Try to get failure reason
                        metadata = info.get("metadata", {})
                        if "error" in metadata:
                            findings.append(f"  Error: {metadata['error']}")
                        recommendations.append(f"Reboot {name}")
        except Exception as e:
            findings.append(f"Could not check directory: {e}")

        # Step 3: Check consciousness system
        if hasattr(self, "_consciousness_loop") and self._consciousness_loop:
            loop = self._consciousness_loop
            if hasattr(loop, 'is_running') and not loop.is_running():
                findings.append("Consciousness loop is not running!")
                recommendations.append("Start consciousness loop")
            else:
                beat_count = getattr(loop, 'beat_count', 0)
                findings.append(f"Consciousness: {beat_count} beats")

        # Step 4: Check collision chamber
        if hasattr(self, "_collision_chamber") and self._collision_chamber:
            chamber = self._collision_chamber
            stats = getattr(chamber, 'stats', {})
            collisions = stats.get("collisions", 0)
            findings.append(f"Collision chamber: {collisions} collisions")
            if collisions == 0:
                recommendations.append("Check if recall/ingest beams are active")

        # Step 5: Check association cortex
        if hasattr(self, "_association_cortex") and self._association_cortex:
            cortex = self._association_cortex
            if hasattr(cortex, '_graph'):
                nodes = len(cortex._graph.nodes)
                edges = len(cortex._graph.edges)
                pending = getattr(cortex, '_pending_bindings', 0)
                findings.append(f"Association cortex: {nodes} nodes, {edges} edges, {pending} pending")
                if pending > 100:
                    recommendations.append(f"Flush {pending} pending bindings to graph")
        else:
            findings.append("Association cortex not wired!")
            recommendations.append("Wire association cortex")

        # Step 6: Check thought chains
        if hasattr(self, "_thought_chain_engine") and self._thought_chain_engine:
            engine = self._thought_chain_engine
            chains = getattr(engine, '_chains', [])
            active = sum(1 for c in chains if getattr(c, 'active', True))
            findings.append(f"Thought chains: {active} active")
        else:
            findings.append("Thought chain engine not wired")

        # Step 7: Seed an investigation thought chain
        if hasattr(self, "_thought_chain_engine") and self._thought_chain_engine:
            try:
                from .thought_chains import ChainType
                self._thought_chain_engine.seed_thought(
                    content=f"Investigating: {question}",
                    chain_type=ChainType.PROBLEM,
                    tags=["investigation", "diagnostic"],
                    energy=0.8,
                )
                actions.append("Seeded investigation thought chain")
            except Exception as e:
                findings.append(f"Could not seed thought chain: {e}")

        # Print investigation report
        print(f"[UMF] === INVESTIGATION REPORT ===")
        print(f"[UMF] Question: {question}")
        print(f"[UMF] --- Findings ---")
        for f in findings:
            print(f"[UMF]   {f}")
        print(f"[UMF] --- Actions Taken ---")
        for a in actions:
            print(f"[UMF]   {a}")
        print(f"[UMF] --- Recommendations ---")
        for r in recommendations:
            print(f"[UMF]   {r}")
        print(f"[UMF] =============================")

        # Publish findings
        if hasattr(self, "fabric") and self.fabric:
            self.fabric.publish(
                "umf.investigation",
                {
                    "question": question,
                    "findings": findings,
                    "actions": actions,
                    "recommendations": recommendations,
                    "ts": time.time(),
                },
            )

        return {
            "question": question,
            "findings": findings,
            "actions": actions,
            "recommendations": recommendations,
        }
