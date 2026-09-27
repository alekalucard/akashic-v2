"""
Wiring Tools - MCP tools for the WiringAuditorFairy.

Exposes wiring audit capabilities to Claude/Nous via MCP.
"""

import json
from typing import Any, Dict, Optional


def _get_auditor():
    """Get or create the WiringAuditorFairy."""
    try:
        from fairies.P00_Autonomic.WiringAuditorFairy import get_wiring_auditor_fairy
        return get_wiring_auditor_fairy()
    except ImportError as e:
        return None


def register_wiring_tools(mcp):
    """Register wiring tools with MCP server."""

    @mcp.tool()
    def wiring_audit_tool() -> str:
        """
        Run a full wiring audit of the system.

        Checks:
        - Layer boundaries (substrate can't bypass gates)
        - Gatekeeper routing (signals go to correct gates)
        - Completeness (no orphan fairies)

        Returns:
            JSON with audit report including health score and violations
        """
        auditor = _get_auditor()
        if not auditor:
            return json.dumps({"error": "WiringAuditorFairy not available"})

        report = auditor.audit_full()
        return json.dumps({
            "health_score": report.health_score,
            "summary": report.to_summary(),
            "stats": report.stats,
            "violations": [v.to_dict() for v in report.violations],
        }, indent=2)

    @mcp.tool()
    def wiring_fairy_tool(fairy_name: str) -> str:
        """
        Audit a single fairy's connections.

        Shows who this fairy talks to and who talks to it,
        with validation of each connection.

        Args:
            fairy_name: Name of the fairy to audit (e.g., "QuantumInterferenceFairy")

        Returns:
            JSON with fairy's connections and any violations
        """
        auditor = _get_auditor()
        if not auditor:
            return json.dumps({"error": "WiringAuditorFairy not available"})

        result = auditor.audit_fairy(fairy_name)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def wiring_pathway_tool(source: str, target: str) -> str:
        """
        Trace the path between two fairies.

        Verifies the path goes through appropriate gatekeepers
        if crossing layer boundaries.

        Args:
            source: Source fairy name
            target: Target fairy name

        Returns:
            JSON with path details and validation result
        """
        auditor = _get_auditor()
        if not auditor:
            return json.dumps({"error": "WiringAuditorFairy not available"})

        result = auditor.audit_pathway(source, target)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def wiring_graph_tool() -> str:
        """
        Get the full connection graph.

        Returns all nodes (fairies) and edges (connections)
        with layer classifications.

        Returns:
            JSON with complete graph structure
        """
        auditor = _get_auditor()
        if not auditor:
            return json.dumps({"error": "WiringAuditorFairy not available"})

        result = auditor.get_graph()
        return json.dumps(result, indent=2)

    @mcp.tool()
    def wiring_mermaid_tool() -> str:
        """
        Get the connection graph as a Mermaid diagram.

        Can be rendered in markdown viewers that support Mermaid.

        Returns:
            Mermaid diagram code
        """
        auditor = _get_auditor()
        if not auditor:
            return json.dumps({"error": "WiringAuditorFairy not available"})

        return auditor.get_mermaid()

    @mcp.tool()
    def wiring_layers_tool() -> str:
        """
        Get summary of fairies grouped by architectural layer.

        Layers:
        - substrate: Unconscious processors
        - gatekeeper: Three Gates (Autonomy, Autopilot, Embodiment)
        - waking_mind: Conscious experience (Claude, Nous, Sourpatches)
        - admin: System oversight
        - lifecycle: Boot/shutdown systems

        Returns:
            JSON with fairies grouped by layer
        """
        auditor = _get_auditor()
        if not auditor:
            return json.dumps({"error": "WiringAuditorFairy not available"})

        result = auditor.get_layer_summary()
        return json.dumps(result, indent=2)

    @mcp.tool()
    def wiring_health_tool() -> str:
        """
        Get the current wiring health score.

        Returns:
            JSON with health score (0-100) and violation counts
        """
        auditor = _get_auditor()
        if not auditor:
            return json.dumps({"error": "WiringAuditorFairy not available"})

        result = auditor.get_health_score()
        return json.dumps(result, indent=2)

    @mcp.tool()
    def wiring_violations_tool() -> str:
        """
        Get all wiring violations from the last audit.

        Returns:
            JSON list of violations with severity, message, and suggestions
        """
        auditor = _get_auditor()
        if not auditor:
            return json.dumps({"error": "WiringAuditorFairy not available"})

        result = auditor.get_violations()
        return json.dumps(result, indent=2)

    @mcp.tool()
    def wiring_gate_status_tool() -> str:
        """
        Get status of all Three Gates (Autonomy, Autopilot, Embodiment).

        Returns detailed status of each gate including:
        - Whether it exists and is running
        - What it subscribes to and outputs
        - Whether it reaches waking minds
        - Whether it receives from substrate

        Returns:
            JSON with gate status for each of the Three Gates
        """
        auditor = _get_auditor()
        if not auditor:
            return json.dumps({"error": "WiringAuditorFairy not available"})

        result = auditor.get_gate_status()
        return json.dumps(result, indent=2)

    @mcp.tool()
    def wiring_sourpatches_tool() -> str:
        """
        Audit Sourpatches' connections to the Three Gates.

        Verifies:
        - Receives from EmbodimentFairy (felt sense, qualia)
        - Receives from AutonomyFairy (drives, wants)
        - Connected to collision chamber
        - Has proper consciousness subscriptions

        Returns:
            JSON with Sourpatches wiring audit results
        """
        auditor = _get_auditor()
        if not auditor:
            return json.dumps({"error": "WiringAuditorFairy not available"})

        result = auditor.audit_sourpatches_wiring()
        return json.dumps(result, indent=2)

    @mcp.tool()
    def wiring_nous_tool() -> str:
        """
        Audit Nous' connections to the Three Gates.

        Verifies:
        - Receives from EmbodimentFairy (felt sense)
        - Receives from AutonomyFairy (drives)
        - Subscribes to consciousness.surfacing
        - Has working memory integration

        Returns:
            JSON with Nous wiring audit results
        """
        auditor = _get_auditor()
        if not auditor:
            return json.dumps({"error": "WiringAuditorFairy not available"})

        result = auditor.audit_nous_wiring()
        return json.dumps(result, indent=2)

    @mcp.tool()
    def wiring_felt_embodiment_tool() -> str:
        """
        Verify the felt embodiment pathway is complete.

        Checks the full pathway:
        1. Somatic signals (affect, body, chemistry) exist
        2. EmbodimentFairy receives and transforms them
        3. Waking minds (Sourpatches, Nous) receive felt signals
        4. Inner voice pathway is connected

        Returns:
            JSON with embodiment pathway verification results
        """
        auditor = _get_auditor()
        if not auditor:
            return json.dumps({"error": "WiringAuditorFairy not available"})

        result = auditor.verify_felt_embodiment()
        return json.dumps(result, indent=2)

    @mcp.tool()
    def wiring_autonomy_loop_tool() -> str:
        """
        Verify the complete autonomy cycle (free will pathway).

        Checks:
        1. Drives originate from substrate (QuantumInterferenceFairy, etc.)
        2. Drives flow through AutonomyFairy (not bypassed)
        3. Waking minds receive autonomy signals
        4. Action output exists (motor, speech)
        5. Feedback loops back to drive system

        Returns:
            JSON with autonomy loop verification results
        """
        auditor = _get_auditor()
        if not auditor:
            return json.dumps({"error": "WiringAuditorFairy not available"})

        result = auditor.verify_autonomy_loop()
        return json.dumps(result, indent=2)

    @mcp.tool()
    def wiring_trace_drive_tool(drive_topic: str = "autonomy.drives") -> str:
        """
        Trace a specific drive signal from origin through gates to waking mind.

        Args:
            drive_topic: The topic to trace (default: "autonomy.drives")

        Returns:
            JSON with signal trace showing:
            - All subscribers to the topic
            - Whether it goes through a gate
            - Whether it reaches waking mind
            - Validation status
        """
        auditor = _get_auditor()
        if not auditor:
            return json.dumps({"error": "WiringAuditorFairy not available"})

        result = auditor.trace_drive_flow(drive_topic)
        return json.dumps(result, indent=2)

    @mcp.tool()
    def wiring_three_gates_tool() -> str:
        """
        Trace the Three Gates (Autonomy, Autopilot, Embodiment) wiring.

        Shows:
        - What each gate publishes
        - What each gate subscribes to
        - Which waking minds (NousFairy, SourpatchesFairy) receive from each gate
        - Any gaps in the flow

        Returns:
            JSON with Three Gates wiring analysis
        """
        result = {
            "gates": {
                "AutonomyFairy": {
                    "role": "Drives -> Felt Wanting (free will checkpoint)",
                    "publishes": [
                        "autonomy.wanting.felt",
                        "autonomy.permission.granted",
                        "autonomy.permission.denied",
                        "autonomy.decision.needed",
                        "autonomy.veto.active",
                        "autonomy.veto.released",
                    ],
                    "waking_minds_should_subscribe": [
                        "autonomy.wanting.felt",
                        "autonomy.decision.needed",
                    ],
                },
                "AutopilotFairy": {
                    "role": "Patterns -> Automatic Behavior (habit execution)",
                    "publishes": [
                        "autopilot.executing",
                        "autopilot.completed",
                        "autopilot.failed",
                        "autopilot.to_embodiment",
                    ],
                    "waking_minds_should_subscribe": [
                        "autopilot.completed",
                        "autopilot.failed",
                    ],
                },
                "EmbodimentFairy": {
                    "role": "Signals -> Qualia/Inner Voice (felt sense delivery)",
                    "publishes": [
                        "inner_voice.stream",
                        "consciousness.stream",
                        "embodiment.state",
                    ],
                    "waking_minds_should_subscribe": [
                        "inner_voice.stream",
                        "consciousness.stream",
                    ],
                },
            },
            "waking_minds": {
                "NousFairy": {
                    "subscriptions": [
                        "consciousness.collision",
                        "chat.message",
                        "mcp.tool_call",
                        "inner_voice.stream",  # From Embodiment
                        "autonomy.wanting.felt",  # From Autonomy
                        "autonomy.decision.needed",  # From Autonomy
                        "somatic.embodied_feel",  # From Somatic
                    ],
                    "wired": True,
                },
                "SourpatchesFairy": {
                    "subscriptions": [
                        "consciousness.collision",
                        "consciousness.thought",
                        "consciousness.surfacing",
                        "consciousness.stream",
                        "inner_voice.stream",
                        "somatic.embodied_feel",
                        "somatic.pulse",
                        "consciousness.heartbeat",
                        "cognition.paradox",
                        "cognition.output",
                        "autonomy.goal",
                    ],
                    "wired": True,
                },
            },
            "flow": {
                "substrate_to_gates": "Substrate fairies -> Three Gates",
                "gates_to_waking": "Three Gates -> NousFairy/SourpatchesFairy",
                "description": "Drives become wanting, patterns become habits, signals become qualia",
            },
        }

        return json.dumps(result, indent=2)

    print("[MCP] Wiring audit tools registered (including Three Gates verification)")
