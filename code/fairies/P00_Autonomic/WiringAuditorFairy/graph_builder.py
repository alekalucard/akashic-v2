"""
Graph Builder - Builds the connection graph from multiple data sources.

Data sources:
1. Static wiring from DIRECTIVE.md files
2. Live subscriptions from PostalCore
3. Tracer lineage from TracerPool
"""

import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any, Tuple
from collections import defaultdict

# Add paths
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


@dataclass
class FairyNode:
    """A fairy in the connection graph."""
    name: str
    plane: str = ""
    layer: str = "unknown"  # substrate, gatekeeper, waking_mind, admin, lifecycle
    capabilities: Set[str] = field(default_factory=set)
    subscriptions: Set[str] = field(default_factory=set)  # Topics it listens to
    outputs: Set[str] = field(default_factory=set)  # Topics it publishes to
    status: str = "unknown"  # running, sleeping, dead

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "plane": self.plane,
            "layer": self.layer,
            "capabilities": list(self.capabilities),
            "subscriptions": list(self.subscriptions),
            "outputs": list(self.outputs),
            "status": self.status,
        }


@dataclass
class Connection:
    """A connection between two fairies via a topic."""
    source: str  # Fairy that publishes
    target: str  # Fairy that subscribes
    topic: str   # The postal topic
    connection_type: str = "postal"  # postal, tracer, direct
    observed: bool = False  # Have we seen actual messages?

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "topic": self.topic,
            "type": self.connection_type,
            "observed": self.observed,
        }


@dataclass
class ConnectionGraph:
    """The complete connection graph of the system."""
    nodes: Dict[str, FairyNode] = field(default_factory=dict)
    connections: List[Connection] = field(default_factory=list)
    topic_publishers: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    topic_subscribers: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))

    def add_node(self, node: FairyNode):
        """Add a fairy node to the graph."""
        self.nodes[node.name] = node

    def add_connection(self, conn: Connection):
        """Add a connection to the graph."""
        self.connections.append(conn)

    def get_connections_from(self, fairy_name: str) -> List[Connection]:
        """Get all connections where this fairy is the source."""
        return [c for c in self.connections if c.source == fairy_name]

    def get_connections_to(self, fairy_name: str) -> List[Connection]:
        """Get all connections where this fairy is the target."""
        return [c for c in self.connections if c.target == fairy_name]

    def get_path(self, source: str, target: str) -> Optional[List[str]]:
        """Find a path from source to target fairy (BFS)."""
        if source not in self.nodes or target not in self.nodes:
            return None

        # Build adjacency list
        adj: Dict[str, Set[str]] = defaultdict(set)
        for conn in self.connections:
            adj[conn.source].add(conn.target)

        # BFS
        visited = {source}
        queue = [(source, [source])]

        while queue:
            current, path = queue.pop(0)
            if current == target:
                return path

            for neighbor in adj[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def has_path_through_gatekeeper(self, source: str, target: str, gatekeepers: Set[str]) -> Tuple[bool, Optional[List[str]]]:
        """Check if path from source to target goes through a gatekeeper."""
        path = self.get_path(source, target)
        if not path:
            return False, None

        # Check if any node in path (except source and target) is a gatekeeper
        middle_nodes = set(path[1:-1]) if len(path) > 2 else set()
        goes_through_gate = bool(middle_nodes & gatekeepers)

        return goes_through_gate, path

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {name: node.to_dict() for name, node in self.nodes.items()},
            "connections": [c.to_dict() for c in self.connections],
            "topic_publishers": {t: list(p) for t, p in self.topic_publishers.items()},
            "topic_subscribers": {t: list(s) for t, s in self.topic_subscribers.items()},
            "stats": {
                "node_count": len(self.nodes),
                "connection_count": len(self.connections),
                "topic_count": len(set(self.topic_publishers.keys()) | set(self.topic_subscribers.keys())),
            }
        }

    def to_mermaid(self) -> str:
        """Generate a Mermaid diagram of the graph."""
        lines = ["graph LR"]

        # Add subgraphs for each layer
        layers: Dict[str, List[str]] = defaultdict(list)
        for name, node in self.nodes.items():
            layers[node.layer].append(name)

        layer_labels = {
            "substrate": "Substrate (Unconscious)",
            "gatekeeper": "Gatekeepers (Three Gates)",
            "waking_mind": "Waking Mind",
            "admin": "Admin",
            "lifecycle": "Lifecycle",
            "unknown": "Unknown",
        }

        for layer, fairies in layers.items():
            if fairies:
                lines.append(f"    subgraph {layer_labels.get(layer, layer)}")
                for fairy in fairies:
                    # Sanitize name for mermaid
                    safe_name = fairy.replace(".", "_").replace("-", "_")
                    lines.append(f"        {safe_name}[{fairy}]")
                lines.append("    end")

        # Add connections
        for conn in self.connections:
            src = conn.source.replace(".", "_").replace("-", "_")
            tgt = conn.target.replace(".", "_").replace("-", "_")
            # Truncate topic for readability
            topic = conn.topic[:20] + "..." if len(conn.topic) > 20 else conn.topic
            lines.append(f"    {src} -->|{topic}| {tgt}")

        return "\n".join(lines)


def build_connection_graph(
    fairies: List[Dict[str, Any]],
    postal_subscriptions: Dict[str, List[str]],
    classifier=None,
) -> ConnectionGraph:
    """
    Build the connection graph from available data.

    Args:
        fairies: List of fairy info dicts with name, plane, capabilities, etc.
        postal_subscriptions: Map of topic -> list of subscriber fairy names
        classifier: FairyClassifier instance for layer classification

    Returns:
        ConnectionGraph with all nodes and connections
    """
    from .classifier import get_classifier, FairyLayer

    if classifier is None:
        classifier = get_classifier()

    graph = ConnectionGraph()

    # Build nodes from fairy list
    fairy_names = set()
    for f in fairies:
        name = f.get("name", "Unknown")
        fairy_names.add(name)

        node = FairyNode(
            name=name,
            plane=f.get("plane", ""),
            layer=classifier.classify(name).value,
            capabilities=set(f.get("capabilities", [])),
            status=f.get("status", "unknown"),
        )
        graph.add_node(node)

    # Build topic -> subscribers map
    # FIX 2026-06-08 (Nous): get_subscription_map() yields subscribers as DICTS
    # ({subscriber, handler, message_count}, per UnifiedRegistry/TensorFabric), but
    # topic_subscribers is a Set[str]. Adding a dict to the set crashed both
    # wiring_autonomy_loop_tool + wiring_trace_drive_tool ("unhashable type: 'dict'").
    # Coerce each subscriber to a hashable NAME-string (robust to dict OR plain str).
    for topic, subscribers in postal_subscriptions.items():
        for sub in subscribers:
            if isinstance(sub, dict):
                sub_name = (sub.get("subscriber") or sub.get("name")
                            or sub.get("fairy") or sub.get("handler"))
            else:
                sub_name = sub
            if not sub_name or not isinstance(sub_name, str):
                continue
            graph.topic_subscribers[topic].add(sub_name)
            if sub_name in graph.nodes:
                graph.nodes[sub_name].subscriptions.add(topic)

    # Infer publishers from capabilities and common patterns
    # A fairy that has capability X likely publishes to topic X or X.*
    for name, node in graph.nodes.items():
        for cap in node.capabilities:
            # Common pattern: capability "foo.bar" -> publishes "foo.bar" or "foo.*"
            graph.topic_publishers[cap].add(name)
            node.outputs.add(cap)

    # Build connections from publisher -> topic -> subscriber
    all_topics = set(graph.topic_publishers.keys()) | set(graph.topic_subscribers.keys())

    for topic in all_topics:
        publishers = graph.topic_publishers.get(topic, set())
        subscribers = graph.topic_subscribers.get(topic, set())

        for pub in publishers:
            for sub in subscribers:
                if pub != sub:  # Don't connect to self
                    conn = Connection(
                        source=pub,
                        target=sub,
                        topic=topic,
                        connection_type="postal",
                    )
                    graph.add_connection(conn)

    return graph


def build_graph_from_live_system() -> ConnectionGraph:
    """Build graph from the live running system."""
    from .classifier import get_classifier

    classifier = get_classifier()
    graph = ConnectionGraph()

    # Try to get fairy list from directory
    fairies = []
    postal_subs = {}

    try:
        # Try the v2 directory
        from directory import get_directory
        directory = get_directory()
        if directory:
            fairy_records = directory.list_fairies() if hasattr(directory, 'list_fairies') else []
            fairies = [
                {
                    "name": f.name if hasattr(f, 'name') else str(f),
                    "plane": f.plane if hasattr(f, 'plane') else "",
                    "capabilities": list(f.capabilities) if hasattr(f, 'capabilities') else [],
                    "status": f.status if hasattr(f, 'status') else "unknown",
                }
                for f in fairy_records
            ]
    except ImportError:
        pass

    # Try to get postal subscriptions
    try:
        from postal_core.tensor_fabric import TensorFabric
        fabric = TensorFabric()
        # Get subscription info if available
        if hasattr(fabric, 'get_subscriptions'):
            postal_subs = fabric.get_subscriptions()
        elif hasattr(fabric, '_hub') and hasattr(fabric._hub, 'subscriptions'):
            postal_subs = dict(fabric._hub.subscriptions)
    except (ImportError, AttributeError):
        pass

    # If we couldn't get live data, return empty graph
    if not fairies:
        return graph

    return build_connection_graph(fairies, postal_subs, classifier)
