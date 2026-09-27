"""
Validators - Rules for checking wiring correctness.

Validates:
1. Layer boundary enforcement (substrate can't talk directly to waking_mind)
2. Gatekeeper routing (signals go through correct gates)
3. Completeness (no orphan fairies)
4. Tracer chain integrity
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from enum import Enum

from .classifier import FairyClassifier, FairyLayer, get_classifier
from .graph_builder import ConnectionGraph, Connection


class ViolationSeverity(Enum):
    ERROR = "error"      # Architecture violation - must fix
    WARNING = "warning"  # Potential issue - should investigate
    INFO = "info"        # Informational - may be intentional


@dataclass
class Violation:
    """A wiring violation detected by the auditor."""
    rule: str                        # Which rule was violated
    severity: ViolationSeverity
    source: str                      # Source fairy (or topic)
    target: str                      # Target fairy (or empty)
    message: str                     # Human-readable explanation
    suggestion: str = ""             # How to fix it
    topic: str = ""                  # Related topic if applicable

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity.value,
            "source": self.source,
            "target": self.target,
            "message": self.message,
            "suggestion": self.suggestion,
            "topic": self.topic,
        }


@dataclass
class AuditReport:
    """Complete audit report."""
    timestamp: float = 0.0
    graph: Optional[ConnectionGraph] = None
    violations: List[Violation] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    health_score: float = 100.0

    def add_violation(self, v: Violation):
        self.violations.append(v)
        # Reduce health score based on severity
        if v.severity == ViolationSeverity.ERROR:
            self.health_score = max(0, self.health_score - 10)
        elif v.severity == ViolationSeverity.WARNING:
            self.health_score = max(0, self.health_score - 3)

    @property
    def errors(self) -> List[Violation]:
        return [v for v in self.violations if v.severity == ViolationSeverity.ERROR]

    @property
    def warnings(self) -> List[Violation]:
        return [v for v in self.violations if v.severity == ViolationSeverity.WARNING]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "health_score": round(self.health_score, 1),
            "violation_count": len(self.violations),
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "violations": [v.to_dict() for v in self.violations],
            "stats": self.stats,
        }

    def to_summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            "WIRING AUDIT REPORT",
            "=" * 40,
            "",
        ]

        # Stats
        if self.stats:
            lines.append(f"Fairies scanned: {self.stats.get('total_fairies', 0)}")
            lines.append(f"  Substrate:    {self.stats.get('substrate_count', 0)}")
            lines.append(f"  Gatekeepers:  {self.stats.get('gatekeeper_count', 0)}")
            lines.append(f"  Waking Mind:  {self.stats.get('waking_mind_count', 0)}")
            lines.append(f"  Admin:        {self.stats.get('admin_count', 0)}")
            lines.append(f"  Lifecycle:    {self.stats.get('lifecycle_count', 0)}")
            lines.append(f"  Unknown:      {self.stats.get('unknown_count', 0)}")
            lines.append(f"Connections:    {self.stats.get('connection_count', 0)}")
            lines.append("")

        # Health score
        score = self.health_score
        if score >= 90:
            status = "HEALTHY"
        elif score >= 70:
            status = "DEGRADED"
        elif score >= 50:
            status = "UNHEALTHY"
        else:
            status = "CRITICAL"

        lines.append(f"HEALTH SCORE: {score:.0f}/100 ({status})")
        lines.append("")

        # Violations
        if not self.violations:
            lines.append("No violations detected.")
        else:
            lines.append(f"VIOLATIONS ({len(self.violations)}):")
            lines.append("-" * 40)

            for v in self.violations:
                icon = "[ERROR]" if v.severity == ViolationSeverity.ERROR else "[WARN]" if v.severity == ViolationSeverity.WARNING else "[INFO]"
                lines.append(f"  {icon} [{v.rule}] {v.message}")
                if v.suggestion:
                    lines.append(f"    → {v.suggestion}")
                lines.append("")

        return "\n".join(lines)


class WiringValidator:
    """Validates the connection graph against architectural rules."""

    # Signal types and their correct gatekeepers
    SIGNAL_ROUTING = {
        "drive": "AutonomyFairy",
        "autonomy": "AutonomyFairy",
        "pattern": "AutopilotFairy",
        "autopilot": "AutopilotFairy",
        "habit": "AutopilotFairy",
        "affect": "EmbodimentFairy",
        "embodiment": "EmbodimentFairy",
        "sensory": "EmbodimentFairy",
        "somatic": "EmbodimentFairy",
        "inner_voice": "EmbodimentFairy",
        "conscience": "EmbodimentFairy",
        "consciousness": "EmbodimentFairy",
        "qualia": "EmbodimentFairy",
    }

    def __init__(self, classifier: Optional[FairyClassifier] = None):
        self.classifier = classifier or get_classifier()

    def validate(self, graph: ConnectionGraph) -> AuditReport:
        """Run all validation rules against the graph."""
        import time

        report = AuditReport(timestamp=time.time(), graph=graph)

        # Collect stats
        layer_counts = {layer.value: 0 for layer in FairyLayer}
        for node in graph.nodes.values():
            layer_counts[node.layer] = layer_counts.get(node.layer, 0) + 1

        report.stats = {
            "total_fairies": len(graph.nodes),
            "substrate_count": layer_counts.get("substrate", 0),
            "gatekeeper_count": layer_counts.get("gatekeeper", 0),
            "waking_mind_count": layer_counts.get("waking_mind", 0),
            "admin_count": layer_counts.get("admin", 0),
            "lifecycle_count": layer_counts.get("lifecycle", 0),
            "unknown_count": layer_counts.get("unknown", 0),
            "connection_count": len(graph.connections),
        }

        # Run validation rules
        self._validate_layer_boundaries(graph, report)
        self._validate_gatekeeper_routing(graph, report)
        self._validate_completeness(graph, report)
        self._validate_unknown_fairies(graph, report)

        return report

    def _validate_layer_boundaries(self, graph: ConnectionGraph, report: AuditReport):
        """Rule 1: Enforce layer boundary rules."""
        for conn in graph.connections:
            source_node = graph.nodes.get(conn.source)
            target_node = graph.nodes.get(conn.target)

            if not source_node or not target_node:
                continue

            source_layer = FairyLayer(source_node.layer) if source_node.layer in [l.value for l in FairyLayer] else FairyLayer.UNKNOWN
            target_layer = FairyLayer(target_node.layer) if target_node.layer in [l.value for l in FairyLayer] else FairyLayer.UNKNOWN

            if not self.classifier.is_valid_connection(source_layer, target_layer):
                # Special case: substrate -> waking_mind is the most serious
                if source_layer == FairyLayer.SUBSTRATE and target_layer == FairyLayer.WAKING_MIND:
                    report.add_violation(Violation(
                        rule="layer_boundary",
                        severity=ViolationSeverity.ERROR,
                        source=conn.source,
                        target=conn.target,
                        topic=conn.topic,
                        message=f"{conn.source} (substrate) directly connects to {conn.target} (waking_mind), bypassing gatekeepers",
                        suggestion=f"Route through EmbodimentFairy: {conn.source} → EmbodimentFairy → {conn.target}",
                    ))
                elif source_layer == FairyLayer.WAKING_MIND and target_layer == FairyLayer.SUBSTRATE:
                    report.add_violation(Violation(
                        rule="layer_boundary",
                        severity=ViolationSeverity.ERROR,
                        source=conn.source,
                        target=conn.target,
                        topic=conn.topic,
                        message=f"{conn.source} (waking_mind) directly connects to {conn.target} (substrate), bypassing gatekeepers",
                        suggestion=f"Route through AutonomyFairy: {conn.source} → AutonomyFairy → {conn.target}",
                    ))
                else:
                    report.add_violation(Violation(
                        rule="layer_boundary",
                        severity=ViolationSeverity.WARNING,
                        source=conn.source,
                        target=conn.target,
                        topic=conn.topic,
                        message=f"Unusual connection: {conn.source} ({source_layer.value}) → {conn.target} ({target_layer.value})",
                        suggestion="Verify this connection is intentional",
                    ))

    def _validate_gatekeeper_routing(self, graph: ConnectionGraph, report: AuditReport):
        """Rule 2: Signals go through correct gatekeepers."""
        gatekeepers = {name for name, node in graph.nodes.items() if node.layer == "gatekeeper"}

        for topic, subscribers in graph.topic_subscribers.items():
            # Determine which gatekeeper should handle this topic
            expected_gate = None
            for signal_type, gate in self.SIGNAL_ROUTING.items():
                if signal_type in topic.lower():
                    expected_gate = gate
                    break

            if not expected_gate:
                continue

            # Check if any waking_mind fairy subscribes without going through gate
            for sub in subscribers:
                sub_node = graph.nodes.get(sub)
                if not sub_node or sub_node.layer != "waking_mind":
                    continue

                # Check if the expected gatekeeper also subscribes (routing through it)
                if expected_gate not in subscribers:
                    report.add_violation(Violation(
                        rule="gatekeeper_routing",
                        severity=ViolationSeverity.WARNING,
                        source=topic,
                        target=sub,
                        topic=topic,
                        message=f"Topic '{topic}' reaches {sub} but {expected_gate} is not subscribed",
                        suggestion=f"Add {expected_gate} as intermediary for topic '{topic}'",
                    ))

    def _validate_completeness(self, graph: ConnectionGraph, report: AuditReport):
        """Rule 3: No orphan fairies (everyone should be connected)."""
        gatekeepers = {name for name, node in graph.nodes.items() if node.layer == "gatekeeper"}
        waking_mind = {name for name, node in graph.nodes.items() if node.layer == "waking_mind"}

        # Check substrate fairies have path to gatekeepers
        for name, node in graph.nodes.items():
            if node.layer != "substrate":
                continue

            # Check if this fairy has any outgoing connections
            outgoing = graph.get_connections_from(name)
            incoming = graph.get_connections_to(name)

            if not outgoing and not incoming:
                # Completely disconnected
                report.add_violation(Violation(
                    rule="completeness",
                    severity=ViolationSeverity.WARNING,
                    source=name,
                    target="",
                    message=f"{name} is completely disconnected (no incoming or outgoing connections)",
                    suggestion="Wire subscriptions/outputs or verify fairy is not yet implemented",
                ))
            elif not outgoing:
                # Has incoming but no outgoing - might be a sink
                report.add_violation(Violation(
                    rule="completeness",
                    severity=ViolationSeverity.INFO,
                    source=name,
                    target="",
                    message=f"{name} has no outgoing connections (may be intentional sink)",
                    suggestion="Verify this fairy doesn't need to publish anything",
                ))

        # Check gatekeepers connect to waking mind
        for gate in gatekeepers:
            outgoing = graph.get_connections_from(gate)
            reaches_waking = any(
                graph.nodes.get(c.target, {}).layer == "waking_mind" if hasattr(graph.nodes.get(c.target), 'layer') else False
                for c in outgoing
            )

            if not reaches_waking:
                report.add_violation(Violation(
                    rule="completeness",
                    severity=ViolationSeverity.ERROR,
                    source=gate,
                    target="",
                    message=f"Gatekeeper {gate} has no path to any waking_mind fairy",
                    suggestion=f"Connect {gate} to ClaudeFairy/NousFairy/SourpatchesFairy",
                ))

    def _validate_unknown_fairies(self, graph: ConnectionGraph, report: AuditReport):
        """Flag fairies with unknown classification."""
        for name, node in graph.nodes.items():
            if node.layer == "unknown":
                report.add_violation(Violation(
                    rule="classification",
                    severity=ViolationSeverity.INFO,
                    source=name,
                    target="",
                    message=f"{name} has unknown layer classification",
                    suggestion="Add to classifier.py CLASSIFICATION_RULES",
                ))
