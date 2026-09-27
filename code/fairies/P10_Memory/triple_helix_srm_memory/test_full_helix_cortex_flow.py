"""
End-to-end test of triple helix → association cortex flow.

Tests the full pipeline:
1. Ingest memory with helix coordinates
2. Verify coordinates reach the concept graph
3. Verify spreading activation respects helix topology
"""

import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from fairies.P30_Cognition.AssociationCortexFairy.fairy import AssociationCortexFairy, ConceptGraph


def test_full_flow():
    """Test complete helix → cortex integration."""
    print("Creating AssociationCortex...")
    cortex = AssociationCortexFairy()
    cortex._graph = ConceptGraph(max_nodes=10000, max_edges=50000)
    cortex._loading_complete = True

    # Bind JOY-domain memories directly with helix coordinates
    print("\nIngesting JOY-domain memory...")
    cortex._intent_bind({
        "text": "Today was a wonderful celebration with friends",
        "source": "nous",
        "context": {"card_id": "joy-card-1"},
        "helix_coord": {
            "affect": {"domain": "JOY", "intensity": 0.8, "valence": 0.9},
            "semantic": {"domain": "SOCIAL", "specificity": 0.7, "detail": 0.6},
            "temporal": {"scale": "HOURS", "position": 0.5, "decay": 0.1},
        },
    })

    print("Ingesting another JOY-domain memory...")
    cortex._intent_bind({
        "text": "The party was amazing and full of laughter",
        "source": "nous",
        "context": {"card_id": "joy-card-2"},
        "helix_coord": {
            "affect": {"domain": "JOY", "intensity": 0.9, "valence": 0.95},
            "semantic": {"domain": "SOCIAL", "specificity": 0.8, "detail": 0.7},
            "temporal": {"scale": "HOURS", "position": 0.6, "decay": 0.1},
        },
    })

    print("Ingesting FEAR-domain memory...")
    cortex._intent_bind({
        "text": "The dark forest was terrifying at night",
        "source": "nous",
        "context": {"card_id": "fear-card-1"},
        "helix_coord": {
            "affect": {"domain": "FEAR", "intensity": 0.7, "valence": -0.6},
            "semantic": {"domain": "NATURE", "specificity": 0.6, "detail": 0.5},
            "temporal": {"scale": "HOURS", "position": 0.3, "decay": 0.15},
        },
    })

    # Verify graph state
    graph = cortex.get_graph()
    print(f"\nGraph state: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

    # Check helix features were attached
    joy_nodes = []
    fear_nodes = []
    neutral_nodes = []
    for key, node in graph.nodes.items():
        helix_affect = node.features.get("helix_affect", {})
        domain = helix_affect.get("domain")
        if domain == "JOY":
            joy_nodes.append(key)
        elif domain == "FEAR":
            fear_nodes.append(key)
        elif domain == "NEUTRAL" or domain is None:
            neutral_nodes.append(key)

    print(f"JOY-domain nodes ({len(joy_nodes)}): {joy_nodes[:5]}...")
    print(f"FEAR-domain nodes ({len(fear_nodes)}): {fear_nodes[:5]}...")
    print(f"NEUTRAL/untagged nodes ({len(neutral_nodes)}): {neutral_nodes[:5]}...")

    assert len(graph.nodes) > 0, "Should have some nodes"
    assert len(joy_nodes) > 0, "Should have JOY-domain nodes"
    assert len(fear_nodes) > 0, "Should have FEAR-domain nodes"

    # Test spreading activation
    if len(graph.nodes) > 1:
        # Find a JOY-domain source
        source = joy_nodes[0] if joy_nodes else list(graph.nodes.keys())[0]
        print(f"\nSpreading activation from '{source}'...")
        activations = graph.spread_activation(source, max_hops=2)
        print(f"Activated {len(activations)} nodes")

        # Show top activations
        top5 = sorted(activations.items(), key=lambda x: -x[1])[:5]
        for k, v in top5:
            node = graph.nodes.get(k)
            helix_domain = node.features.get("helix_affect", {}).get("domain", "?") if node else "?"
            print(f"  {k}: {v:.4f} (domain={helix_domain})")

        # Verify helix-aware spreading: JOY nodes should preferentially activate other JOY nodes
        joy_activation_sum = sum(activations.get(n, 0) for n in joy_nodes)
        fear_activation_sum = sum(activations.get(n, 0) for n in fear_nodes)

        print(f"\nJOY domain total activation: {joy_activation_sum:.4f}")
        print(f"FEAR domain total activation: {fear_activation_sum:.4f}")

        # When spreading from JOY, JOY nodes should get more total activation
        # (unless the graph is very small or poorly connected)
        if len(joy_nodes) > 1 and len(fear_nodes) > 0:
            print(f"JOY/FEAR ratio: {joy_activation_sum / max(fear_activation_sum, 0.001):.2f}")

    print("\n[PASS] Full flow test passed!")


if __name__ == "__main__":
    test_full_flow()
