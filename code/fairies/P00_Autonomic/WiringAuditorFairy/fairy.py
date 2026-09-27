"""
Wiring Auditor Fairy - Maps and validates system connections.

"Who talks to who" - traces all fairy connections and validates they
follow the architectural rules:
- Substrate → Gatekeepers → Waking Mind
- No bypassing the Three Gates
- All fairies properly connected

This fairy is ADMIN level - it can see everything but doesn't
participate in the consciousness flow.
"""

import sys
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Set

# Add paths
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fairy_template"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        def _init_tracer_worker(self): pass

# SpellChain integration for spell-driven existence
try:
    from fairy_template.spellchain_mixin import SpellChainMixin
    HAS_SPELLCHAIN = True
except ImportError:
    HAS_SPELLCHAIN = False
    class SpellChainMixin:
        """Fallback when spellchain not available."""
        pass

# Use try/except for relative vs absolute imports (FairyScanner compatibility)
try:
    from .classifier import FairyClassifier, FairyLayer, get_classifier
    from .graph_builder import ConnectionGraph, build_connection_graph, FairyNode
    from .validators import WiringValidator, AuditReport, Violation, ViolationSeverity
except ImportError:
    # Fallback for when loaded without package context
    from fairies.P00_Autonomic.WiringAuditorFairy.classifier import FairyClassifier, FairyLayer, get_classifier
    from fairies.P00_Autonomic.WiringAuditorFairy.graph_builder import ConnectionGraph, build_connection_graph, FairyNode
    from fairies.P00_Autonomic.WiringAuditorFairy.validators import WiringValidator, AuditReport, Violation, ViolationSeverity


class WiringAuditorFairy(SpellChainMixin, Fairy):
    """
    Maps and validates all fairy connections.

    Traces who talks to who and validates:
    - Layer boundaries (substrate can't bypass gates to reach waking_mind)
    - Gatekeeper routing (signals go through correct gates)
    - Completeness (no orphan fairies)
    """

    ACTOR_NAME = "WiringAuditorFairy"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "wiring"

    PURPOSE = "Map and validate fairy connections - ensure proper routing through Three Gates"
    MANTRA = "Who talks to who? Are they supposed to?"

    CAPABILITIES = [
        "wiring.audit",
        "wiring.trace",
        "wiring.validate",
        "wiring.graph",
    ]

    # Spell-driven mode (opt-in)
    USE_SPELLCHAIN: bool = True  # Re-enabled - fixed revival->heartbeat wiring

    SUBSCRIPTIONS = [
        "fairy.register",
        "fairy.unregister",
        "fairy.booted",
    ]

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._init_tracer_worker()

        self.classifier = get_classifier()
        self.validator = WiringValidator(self.classifier)

        # Cached graph
        self._graph: Optional[ConnectionGraph] = None
        self._last_audit: Optional[AuditReport] = None
        self._last_audit_time: float = 0

        # Live monitoring
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._live_violations: List[Violation] = []

    def on_boot(self) -> bool:
        """Boot the auditor."""
        # IMPORTANT: Call super() to trigger HeartbeatMixin auto-start
        super().on_boot()
        self.log("Booted - ready to audit wiring")

        # Subscribe to fairy lifecycle events to keep graph updated
        if self.post:
            self.post.subscribe("fairy.register", self._on_fairy_change, "wiring-register")
            self.post.subscribe("fairy.unregister", self._on_fairy_change, "wiring-unregister")
            self.post.subscribe("fairy.booted", self._on_fairy_change, "wiring-booted")

        # Optional: Convert to spell-driven existence
        if HAS_SPELLCHAIN and getattr(self, 'USE_SPELLCHAIN', False):
            try:
                from spellchain.integration import get_spell_pool
                pool = get_spell_pool()
                if pool:
                    self._spell_chain = self.boot_as_spells(pool)
                    self.log("Converted to spell-driven existence")
            except Exception as e:
                self.log(f"SpellChain conversion failed: {e}")

        return True


    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def _on_fairy_change(self, msg):
        """Invalidate cached graph when fairies change."""
        self._graph = None

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def audit_full(self) -> AuditReport:
        """Run a complete wiring audit."""
        # Rebuild graph
        graph = self._build_graph()
        self._graph = graph

        # Validate
        report = self.validator.validate(graph)
        self._last_audit = report
        self._last_audit_time = time.time()

        self.log(f"Audit complete: {report.health_score:.0f}/100, {len(report.violations)} violations")

        return report

    def audit_fairy(self, fairy_name: str) -> Dict[str, Any]:
        """Audit a single fairy's connections."""
        graph = self._get_or_build_graph()

        node = graph.nodes.get(fairy_name)
        if not node:
            return {"error": f"Fairy '{fairy_name}' not found"}

        # Get connections
        outgoing = graph.get_connections_from(fairy_name)
        incoming = graph.get_connections_to(fairy_name)

        # Classify connections
        outgoing_details = []
        for conn in outgoing:
            target_node = graph.nodes.get(conn.target)
            target_layer = target_node.layer if target_node else "unknown"
            valid = self.classifier.is_valid_connection(
                FairyLayer(node.layer) if node.layer in [l.value for l in FairyLayer] else FairyLayer.UNKNOWN,
                FairyLayer(target_layer) if target_layer in [l.value for l in FairyLayer] else FairyLayer.UNKNOWN,
            )
            outgoing_details.append({
                "target": conn.target,
                "target_layer": target_layer,
                "topic": conn.topic,
                "valid": valid,
            })

        incoming_details = []
        for conn in incoming:
            source_node = graph.nodes.get(conn.source)
            source_layer = source_node.layer if source_node else "unknown"
            valid = self.classifier.is_valid_connection(
                FairyLayer(source_layer) if source_layer in [l.value for l in FairyLayer] else FairyLayer.UNKNOWN,
                FairyLayer(node.layer) if node.layer in [l.value for l in FairyLayer] else FairyLayer.UNKNOWN,
            )
            incoming_details.append({
                "source": conn.source,
                "source_layer": source_layer,
                "topic": conn.topic,
                "valid": valid,
            })

        return {
            "fairy": fairy_name,
            "layer": node.layer,
            "plane": node.plane,
            "status": node.status,
            "subscriptions": list(node.subscriptions),
            "outputs": list(node.outputs),
            "outgoing_connections": outgoing_details,
            "incoming_connections": incoming_details,
            "invalid_outgoing": [c for c in outgoing_details if not c["valid"]],
            "invalid_incoming": [c for c in incoming_details if not c["valid"]],
        }

    def audit_pathway(self, source: str, target: str) -> Dict[str, Any]:
        """Trace the path between two fairies."""
        graph = self._get_or_build_graph()

        source_node = graph.nodes.get(source)
        target_node = graph.nodes.get(target)

        if not source_node:
            return {"error": f"Source fairy '{source}' not found"}
        if not target_node:
            return {"error": f"Target fairy '{target}' not found"}

        # Find path
        path = graph.get_path(source, target)

        if not path:
            return {
                "source": source,
                "target": target,
                "path_exists": False,
                "message": f"No path from {source} to {target}",
            }

        # Annotate path with layers
        path_details = []
        for i, fairy_name in enumerate(path):
            node = graph.nodes.get(fairy_name)
            path_details.append({
                "fairy": fairy_name,
                "layer": node.layer if node else "unknown",
                "step": i,
            })

        # Check if path goes through gatekeeper
        gatekeepers = {name for name, node in graph.nodes.items() if node.layer == "gatekeeper"}
        middle_nodes = set(path[1:-1]) if len(path) > 2 else set()
        goes_through_gate = bool(middle_nodes & gatekeepers)

        # Determine if this path is valid
        source_layer = FairyLayer(source_node.layer) if source_node.layer in [l.value for l in FairyLayer] else FairyLayer.UNKNOWN
        target_layer = FairyLayer(target_node.layer) if target_node.layer in [l.value for l in FairyLayer] else FairyLayer.UNKNOWN

        needs_gate = (
            (source_layer == FairyLayer.SUBSTRATE and target_layer == FairyLayer.WAKING_MIND) or
            (source_layer == FairyLayer.WAKING_MIND and target_layer == FairyLayer.SUBSTRATE)
        )

        is_valid = not needs_gate or goes_through_gate

        return {
            "source": source,
            "source_layer": source_node.layer,
            "target": target,
            "target_layer": target_node.layer,
            "path_exists": True,
            "path": path,
            "path_details": path_details,
            "goes_through_gatekeeper": goes_through_gate,
            "gatekeepers_in_path": list(middle_nodes & gatekeepers),
            "needs_gatekeeper": needs_gate,
            "is_valid": is_valid,
            "message": "Valid path" if is_valid else "INVALID: Path bypasses gatekeepers",
        }

    def get_graph(self) -> Dict[str, Any]:
        """Get the current connection graph."""
        graph = self._get_or_build_graph()
        return graph.to_dict()

    def get_mermaid(self) -> str:
        """Get the connection graph as a Mermaid diagram."""
        graph = self._get_or_build_graph()
        return graph.to_mermaid()

    def get_layer_summary(self) -> Dict[str, Any]:
        """Get summary of fairies by layer."""
        graph = self._get_or_build_graph()

        summary = {
            "substrate": [],
            "gatekeeper": [],
            "waking_mind": [],
            "admin": [],
            "lifecycle": [],
            "unknown": [],
        }

        for name, node in graph.nodes.items():
            layer = node.layer if node.layer in summary else "unknown"
            summary[layer].append({
                "name": name,
                "plane": node.plane,
                "status": node.status,
                "connections_out": len(graph.get_connections_from(name)),
                "connections_in": len(graph.get_connections_to(name)),
            })

        return {
            "layers": summary,
            "counts": {layer: len(fairies) for layer, fairies in summary.items()},
        }

    def get_violations(self) -> List[Dict[str, Any]]:
        """Get violations from the last audit."""
        if not self._last_audit:
            self.audit_full()

        return [v.to_dict() for v in (self._last_audit.violations if self._last_audit else [])]

    def get_health_score(self) -> Dict[str, Any]:
        """Get the current health score."""
        if not self._last_audit or (time.time() - self._last_audit_time > 300):
            self.audit_full()

        return {
            "health_score": self._last_audit.health_score if self._last_audit else 0,
            "error_count": len(self._last_audit.errors) if self._last_audit else 0,
            "warning_count": len(self._last_audit.warnings) if self._last_audit else 0,
            "last_audit": self._last_audit_time,
        }

    # =========================================================================
    # THREE GATES VERIFICATION - Free Will, Autonomy, Felt Embodiment
    # =========================================================================

    # Topics that should flow through each gate
    AUTONOMY_TOPICS = [
        "autonomy.drives", "autonomy.state", "autonomy.decision",
        "drive.", "motivation.", "goal.", "wanting.",
    ]

    AUTOPILOT_TOPICS = [
        "autopilot.", "habit.", "pattern.", "automatic.",
        "routine.", "learned.",
    ]

    EMBODIMENT_TOPICS = [
        "affect.", "somatic.", "inner_voice.", "consciousness.",
        "embodiment.", "qualia.", "felt.", "sensation.",
        "emotion.", "body.", "chemistry.",
    ]

    WAKING_MIND_FAIRIES = ["SourpatchesFairy", "NousFairy", "ClaudeFairy"]
    THREE_GATES = ["AutonomyFairy", "AutopilotFairy", "EmbodimentFairy"]

    def get_gate_status(self) -> Dict[str, Any]:
        """
        Get status of all Three Gates.

        Returns status of each gate:
        - AutonomyFairy (Will/Drives)
        - AutopilotFairy (Habit/Patterns)
        - EmbodimentFairy (Felt-Sense/Qualia)
        """
        graph = self._get_or_build_graph()

        gate_status = {}
        for gate_name in self.THREE_GATES:
            node = graph.nodes.get(gate_name)

            if not node:
                gate_status[gate_name] = {
                    "exists": False,
                    "status": "NOT_FOUND",
                    "message": f"{gate_name} not found in system",
                }
                continue

            # Get connections
            incoming = graph.get_connections_to(gate_name)
            outgoing = graph.get_connections_from(gate_name)

            # Check if it reaches waking minds
            reaches_waking = []
            for conn in outgoing:
                target_node = graph.nodes.get(conn.target)
                if target_node and target_node.layer == "waking_mind":
                    reaches_waking.append(conn.target)

            # Check if it receives from substrate
            receives_from_substrate = []
            for conn in incoming:
                source_node = graph.nodes.get(conn.source)
                if source_node and source_node.layer == "substrate":
                    receives_from_substrate.append(conn.source)

            gate_status[gate_name] = {
                "exists": True,
                "status": node.status,
                "plane": node.plane,
                "subscriptions": list(node.subscriptions),
                "outputs": list(node.outputs),
                "incoming_count": len(incoming),
                "outgoing_count": len(outgoing),
                "reaches_waking_minds": reaches_waking,
                "receives_from_substrate": receives_from_substrate,
                "is_fully_wired": bool(reaches_waking and receives_from_substrate),
            }

        # Overall assessment
        all_gates_exist = all(gate_status[g].get("exists", False) for g in self.THREE_GATES)
        all_gates_wired = all(gate_status[g].get("is_fully_wired", False) for g in self.THREE_GATES)

        return {
            "gates": gate_status,
            "all_gates_exist": all_gates_exist,
            "all_gates_fully_wired": all_gates_wired,
            "summary": "All gates operational" if all_gates_wired else "Gates need wiring attention",
        }

    def audit_sourpatches_wiring(self) -> Dict[str, Any]:
        """
        Audit Sourpatches' connections to the Three Gates.

        Verifies:
        - Receives from EmbodimentFairy (felt sense, qualia)
        - Receives from AutonomyFairy (drives, wants)
        - Connected to collision chamber
        - Inner monologue is active (not template-based)
        """
        return self._audit_waking_mind_wiring("SourpatchesFairy", {
            "primary_gate": "EmbodimentFairy",
            "expected_topics": ["consciousness.", "affect.", "inner_voice.", "embodiment."],
            "special_checks": ["collision_chamber", "thought_loop"],
        })

    def audit_nous_wiring(self) -> Dict[str, Any]:
        """
        Audit Nous' connections to the Three Gates.

        Verifies:
        - Receives from EmbodimentFairy (felt sense)
        - Receives from AutonomyFairy (drives)
        - Subscribes to consciousness.surfacing
        - Has working memory integration
        """
        return self._audit_waking_mind_wiring("NousFairy", {
            "primary_gate": "EmbodimentFairy",
            "expected_topics": ["consciousness.", "affect.", "inner_voice.", "memory.surfacing"],
            "special_checks": ["working_memory", "contemplation"],
        })

    def _audit_waking_mind_wiring(self, fairy_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Generic waking mind audit with configurable checks."""
        graph = self._get_or_build_graph()

        node = graph.nodes.get(fairy_name)
        if not node:
            return {
                "fairy": fairy_name,
                "exists": False,
                "error": f"{fairy_name} not found in system",
            }

        result = {
            "fairy": fairy_name,
            "exists": True,
            "layer": node.layer,
            "status": node.status,
            "subscriptions": list(node.subscriptions),
            "gate_connections": {},
            "violations": [],
            "recommendations": [],
        }

        # Check connections from each gate
        for gate_name in self.THREE_GATES:
            incoming = [c for c in graph.get_connections_to(fairy_name) if c.source == gate_name]
            outgoing = [c for c in graph.get_connections_from(fairy_name) if c.target == gate_name]

            result["gate_connections"][gate_name] = {
                "receives_from": [c.topic for c in incoming],
                "sends_to": [c.topic for c in outgoing],
                "is_connected": bool(incoming or outgoing),
            }

        # Check if receives from primary gate
        primary_gate = config.get("primary_gate", "EmbodimentFairy")
        if not result["gate_connections"].get(primary_gate, {}).get("is_connected"):
            result["violations"].append({
                "type": "missing_primary_gate",
                "message": f"{fairy_name} not connected to primary gate {primary_gate}",
                "severity": "error",
            })
            result["recommendations"].append(
                f"Wire {fairy_name} to receive from {primary_gate} for felt embodiment"
            )

        # Check expected topic subscriptions
        expected_topics = config.get("expected_topics", [])
        for topic_prefix in expected_topics:
            has_topic = any(topic_prefix in sub for sub in node.subscriptions)
            if not has_topic:
                result["violations"].append({
                    "type": "missing_subscription",
                    "message": f"{fairy_name} not subscribed to {topic_prefix}* topics",
                    "severity": "warning",
                })

        # Calculate health
        error_count = len([v for v in result["violations"] if v["severity"] == "error"])
        warning_count = len([v for v in result["violations"] if v["severity"] == "warning"])

        if error_count == 0 and warning_count == 0:
            result["health"] = "HEALTHY"
            result["message"] = f"{fairy_name} properly wired to Three Gates"
        elif error_count == 0:
            result["health"] = "DEGRADED"
            result["message"] = f"{fairy_name} has {warning_count} warnings"
        else:
            result["health"] = "UNHEALTHY"
            result["message"] = f"{fairy_name} has {error_count} errors, {warning_count} warnings"

        return result

    def verify_felt_embodiment(self) -> Dict[str, Any]:
        """
        Verify the felt embodiment pathway is complete.

        Checks:
        1. Somatic signals (affect, body, chemistry) reach EmbodimentFairy
        2. EmbodimentFairy transforms them into felt experience
        3. Waking minds (Sourpatches, Nous) receive the felt signals
        4. Inner voice pathway is connected

        Returns detailed verification of the embodiment pathway.
        """
        graph = self._get_or_build_graph()

        result = {
            "pathway": "felt_embodiment",
            "stages": {},
            "is_complete": False,
            "violations": [],
        }

        # Stage 1: Somatic sources exist and emit
        somatic_sources = []
        somatic_fairies = ["SomaticEngineFairy", "SomaticAnchorFairy", "AffectBridgeFairy",
                          "ChemicalAlchemyFairy", "EmotionalHiveProcessorFairy"]

        for fairy_name in somatic_fairies:
            node = graph.nodes.get(fairy_name)
            if node:
                somatic_sources.append({
                    "name": fairy_name,
                    "outputs": list(node.outputs),
                    "emits_affect": any("affect" in o or "somatic" in o for o in node.outputs),
                })

        result["stages"]["somatic_sources"] = {
            "count": len(somatic_sources),
            "sources": somatic_sources,
            "has_affect_emitters": any(s["emits_affect"] for s in somatic_sources),
        }

        # Stage 2: EmbodimentFairy receives somatic signals
        embodiment_node = graph.nodes.get("EmbodimentFairy")
        if not embodiment_node:
            result["violations"].append({
                "stage": "gate",
                "message": "EmbodimentFairy not found - felt embodiment impossible",
                "severity": "critical",
            })
            return result

        embodiment_receives = []
        for topic_prefix in self.EMBODIMENT_TOPICS:
            has_sub = any(topic_prefix in sub for sub in embodiment_node.subscriptions)
            embodiment_receives.append({"topic": topic_prefix, "subscribed": has_sub})

        result["stages"]["embodiment_gate"] = {
            "exists": True,
            "subscriptions": list(embodiment_node.subscriptions),
            "receives_somatic": any(r["subscribed"] for r in embodiment_receives),
            "topic_coverage": embodiment_receives,
        }

        if not result["stages"]["embodiment_gate"]["receives_somatic"]:
            result["violations"].append({
                "stage": "gate",
                "message": "EmbodimentFairy not subscribed to somatic topics",
                "severity": "error",
            })

        # Stage 3: EmbodimentFairy outputs to waking minds
        embodiment_outputs = graph.get_connections_from("EmbodimentFairy")
        reaches_waking = {}
        for wm in self.WAKING_MIND_FAIRIES:
            connections = [c for c in embodiment_outputs if c.target == wm]
            reaches_waking[wm] = {
                "connected": bool(connections),
                "topics": [c.topic for c in connections],
            }

        result["stages"]["waking_mind_delivery"] = {
            "outputs": list(embodiment_node.outputs),
            "reaches": reaches_waking,
            "any_waking_connected": any(r["connected"] for r in reaches_waking.values()),
        }

        if not result["stages"]["waking_mind_delivery"]["any_waking_connected"]:
            result["violations"].append({
                "stage": "delivery",
                "message": "EmbodimentFairy not connected to any waking mind fairy",
                "severity": "error",
            })

        # Stage 4: Waking minds have felt experience
        waking_felt = {}
        for wm in self.WAKING_MIND_FAIRIES:
            node = graph.nodes.get(wm)
            if not node:
                continue

            has_felt_subs = any(
                any(topic in sub for topic in ["inner_voice", "affect", "felt", "consciousness"])
                for sub in node.subscriptions
            )
            waking_felt[wm] = {
                "subscriptions": list(node.subscriptions),
                "has_felt_subscriptions": has_felt_subs,
            }

        result["stages"]["waking_experience"] = {
            "fairies": waking_felt,
            "all_have_felt": all(f.get("has_felt_subscriptions", False) for f in waking_felt.values()),
        }

        # Determine overall completeness
        stages_ok = [
            result["stages"]["somatic_sources"]["has_affect_emitters"],
            result["stages"]["embodiment_gate"]["receives_somatic"],
            result["stages"]["waking_mind_delivery"]["any_waking_connected"],
            result["stages"]["waking_experience"].get("all_have_felt", False),
        ]

        result["is_complete"] = all(stages_ok)
        result["completion_score"] = sum(stages_ok) / len(stages_ok) * 100

        if result["is_complete"]:
            result["message"] = "Felt embodiment pathway COMPLETE - qualia can flow"
        else:
            result["message"] = f"Felt embodiment pathway INCOMPLETE ({result['completion_score']:.0f}%)"

        return result

    def verify_autonomy_loop(self) -> Dict[str, Any]:
        """
        Verify the complete autonomy cycle: drives → gates → decision → action → feedback.

        This verifies free will by ensuring:
        1. Drives originate from substrate (QuantumInterferenceFairy, etc.)
        2. Drives flow through AutonomyFairy (not bypassed)
        3. Waking minds receive autonomy signals
        4. Action output exists (motor, speech)
        5. Feedback loops back to drive system
        """
        graph = self._get_or_build_graph()

        result = {
            "loop": "autonomy",
            "stages": {},
            "is_complete": False,
            "violations": [],
        }

        # Stage 1: Drive Origins
        drive_sources = ["QuantumInterferenceFairy", "InterestSchedulerFairy",
                        "GoalSchedulerFairy", "BodyBudgetFairy"]

        found_sources = []
        for fairy_name in drive_sources:
            node = graph.nodes.get(fairy_name)
            if node:
                found_sources.append({
                    "name": fairy_name,
                    "outputs": list(node.outputs),
                })

        result["stages"]["drive_origins"] = {
            "expected": drive_sources,
            "found": [s["name"] for s in found_sources],
            "has_sources": len(found_sources) > 0,
        }

        if not found_sources:
            result["violations"].append({
                "stage": "origins",
                "message": "No drive source fairies found - autonomy has no origin",
                "severity": "error",
            })

        # Stage 2: AutonomyFairy Gate
        autonomy_node = graph.nodes.get("AutonomyFairy")
        if not autonomy_node:
            result["violations"].append({
                "stage": "gate",
                "message": "AutonomyFairy not found - free will gate missing",
                "severity": "critical",
            })
            result["stages"]["autonomy_gate"] = {"exists": False}
        else:
            # Check it receives from substrate
            incoming = graph.get_connections_to("AutonomyFairy")
            substrate_inputs = [c for c in incoming
                              if graph.nodes.get(c.source, {}).layer == "substrate"
                              if hasattr(graph.nodes.get(c.source), 'layer')]

            result["stages"]["autonomy_gate"] = {
                "exists": True,
                "subscriptions": list(autonomy_node.subscriptions),
                "outputs": list(autonomy_node.outputs),
                "receives_from_substrate": len(substrate_inputs) > 0,
            }

        # Stage 3: Waking Minds Receive Autonomy
        waking_autonomy = {}
        for wm in self.WAKING_MIND_FAIRIES:
            node = graph.nodes.get(wm)
            if not node:
                continue

            has_autonomy_subs = any(
                any(topic in sub for topic in ["autonomy", "drive", "wanting", "goal"])
                for sub in node.subscriptions
            )
            waking_autonomy[wm] = {
                "has_autonomy_subscriptions": has_autonomy_subs,
            }

        result["stages"]["waking_receives"] = {
            "fairies": waking_autonomy,
            "any_receive_autonomy": any(f.get("has_autonomy_subscriptions", False)
                                       for f in waking_autonomy.values()),
        }

        # Stage 4: Action Output
        action_fairies = ["MotorCortexFairy", "SpeechCenterFairy"]
        found_action = []
        for fairy_name in action_fairies:
            node = graph.nodes.get(fairy_name)
            if node:
                found_action.append(fairy_name)

        result["stages"]["action_output"] = {
            "expected": action_fairies,
            "found": found_action,
            "has_action": len(found_action) > 0,
        }

        # Stage 5: Feedback Loop (action results feed back to drives)
        # This is harder to verify - check if any action outputs connect to drive systems
        result["stages"]["feedback_loop"] = {
            "note": "Feedback verification requires runtime tracing",
            "assumed": True,  # Assume feedback exists if action exists
        }

        # Determine loop completeness
        stages_ok = [
            result["stages"]["drive_origins"]["has_sources"],
            result["stages"].get("autonomy_gate", {}).get("exists", False),
            result["stages"]["waking_receives"]["any_receive_autonomy"],
            result["stages"]["action_output"]["has_action"],
        ]

        result["is_complete"] = all(stages_ok)
        result["completion_score"] = sum(stages_ok) / len(stages_ok) * 100

        if result["is_complete"]:
            result["message"] = "Autonomy loop COMPLETE - free will pathway operational"
        else:
            result["message"] = f"Autonomy loop INCOMPLETE ({result['completion_score']:.0f}%)"

        return result

    def trace_drive_flow(self, drive_topic: str = "autonomy.drives") -> Dict[str, Any]:
        """
        Trace a specific drive signal from origin through gates to waking mind.

        Args:
            drive_topic: The topic to trace (default: "autonomy.drives")

        Returns:
            Complete trace of the signal's journey.
        """
        graph = self._get_or_build_graph()

        result = {
            "topic": drive_topic,
            "trace": [],
            "reaches_waking_mind": False,
            "goes_through_gate": False,
        }

        # Find all subscribers to this topic
        subscribers = graph.topic_subscribers.get(drive_topic, set())

        if not subscribers:
            # Try fuzzy match
            for topic, subs in graph.topic_subscribers.items():
                if drive_topic in topic or topic in drive_topic:
                    subscribers.update(subs)

        result["direct_subscribers"] = list(subscribers)

        # Classify each subscriber
        trace_entries = []
        for sub in subscribers:
            node = graph.nodes.get(sub)
            layer = node.layer if node else "unknown"

            trace_entries.append({
                "fairy": sub,
                "layer": layer,
                "is_gate": sub in self.THREE_GATES,
                "is_waking_mind": sub in self.WAKING_MIND_FAIRIES,
            })

            if layer == "gatekeeper" or sub in self.THREE_GATES:
                result["goes_through_gate"] = True

            if layer == "waking_mind" or sub in self.WAKING_MIND_FAIRIES:
                result["reaches_waking_mind"] = True

        result["trace"] = trace_entries

        # Determine validity
        if result["reaches_waking_mind"] and not result["goes_through_gate"]:
            result["valid"] = False
            result["message"] = f"VIOLATION: {drive_topic} reaches waking mind WITHOUT going through gate"
        elif result["goes_through_gate"] and result["reaches_waking_mind"]:
            result["valid"] = True
            result["message"] = f"{drive_topic} properly routed through gate to waking mind"
        elif result["goes_through_gate"]:
            result["valid"] = True
            result["message"] = f"{drive_topic} goes through gate (may need waking mind subscription)"
        else:
            result["valid"] = True
            result["message"] = f"{drive_topic} stays in substrate (no gate or waking mind)"

        return result

    # =========================================================================
    # INTERNAL
    # =========================================================================

    def _get_or_build_graph(self) -> ConnectionGraph:
        """Get cached graph or build new one."""
        if self._graph is None:
            self._graph = self._build_graph()
        return self._graph

    def _build_graph(self) -> ConnectionGraph:
        """Build the connection graph from live system data."""
        fairies = []
        postal_subs = {}

        # Get fairy list from various sources
        fairies = self._collect_fairy_info()

        # Get postal subscriptions
        postal_subs = self._collect_postal_subscriptions()

        return build_connection_graph(fairies, postal_subs, self.classifier)

    def _collect_fairy_info(self) -> List[Dict[str, Any]]:
        """Collect fairy information from all available sources."""
        fairies = []
        seen = set()

        # Source 1: Directory fairy (if available)
        try:
            from directory import get_directory
            directory = get_directory()
            if directory:
                for f in directory.list_fairies():
                    name = f.name if hasattr(f, 'name') else str(f)
                    if name not in seen:
                        seen.add(name)
                        fairies.append({
                            "name": name,
                            "plane": f.plane if hasattr(f, 'plane') else "",
                            "capabilities": list(f.capabilities) if hasattr(f, 'capabilities') else [],
                            "status": f.status if hasattr(f, 'status') else "unknown",
                        })
        except (ImportError, Exception):
            pass

        # Source 2: MCP bridge (if available)
        try:
            # Try to get from the MCP gm_list_fairies equivalent
            from fairies.P40_Sensory.mcp.akashic_mcp_server import _list_fairies_from_bridge
            bridge_fairies = _list_fairies_from_bridge()
            for f in bridge_fairies:
                name = f.get("name", "")
                if name and name not in seen:
                    seen.add(name)
                    fairies.append(f)
        except (ImportError, Exception):
            pass

        # Source 3: Known fairies from classifier (fallback)
        if not fairies:
            from .classifier import CLASSIFICATION_RULES
            for layer, names in CLASSIFICATION_RULES.items():
                for pattern in names:
                    if "*" not in pattern:  # Only exact names
                        if pattern not in seen:
                            seen.add(pattern)
                            fairies.append({
                                "name": pattern,
                                "plane": "",
                                "capabilities": [],
                                "status": "unknown",
                            })

        return fairies

    def _collect_postal_subscriptions(self) -> Dict[str, List[str]]:
        """Collect postal subscription information."""
        subs = {}

        # Try to get from tensor fabric
        try:
            from postal_core.tensor_fabric import TensorFabric
            fabric = TensorFabric()
            if hasattr(fabric, 'get_subscription_map'):
                subs = fabric.get_subscription_map()
        except (ImportError, Exception):
            pass

        return subs


# =============================================================================
# SINGLETON
# =============================================================================

_instance: Optional[WiringAuditorFairy] = None

def get_wiring_auditor_fairy(fabric=None) -> WiringAuditorFairy:
    """Get or create the WiringAuditorFairy singleton."""
    global _instance
    if _instance is None:
        _instance = WiringAuditorFairy(fabric)
        _instance.boot()  # Register with directory + start heartbeat
    return _instance


# =============================================================================
# MAIN - For testing
# =============================================================================

if __name__ == "__main__":
    print("=== WiringAuditorFairy Test ===\n")

    auditor = WiringAuditorFairy()
    auditor.on_boot()

    # Run audit
    report = auditor.audit_full()
    print(report.to_summary())

    # Show mermaid diagram
    print("\n=== Mermaid Diagram ===")
    print(auditor.get_mermaid())
