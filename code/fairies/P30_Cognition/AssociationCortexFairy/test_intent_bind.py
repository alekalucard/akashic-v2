import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from fairies.P30_Cognition.AssociationCortexFairy.fairy import AssociationCortexFairy, ConceptGraph

def test_intent_bind_with_helix():
    """_intent_bind should accept helix_coord and use it for features/weights."""
    fairy = AssociationCortexFairy()
    fairy._graph = ConceptGraph(max_nodes=10000, max_edges=50000)

    fairy._intent_bind({
        "text": "neural network training",
        "source": "nous",
        "context": {"card_id": "test-123"},
        "helix_coord": {
            "affect": {"domain": "CURIOSITY", "intensity": 700},
            "semantic": {"domain": "SCIENCE", "specificity": 600},
            "temporal": {"scale": "DAILY", "position": 500},
        },
    })

    graph = fairy.get_graph()
    assert "neural" in graph.nodes or "network" in graph.nodes, "Should add concept nodes"

    for key, node in graph.nodes.items():
        if "helix_affect" in node.features:
            assert node.features["helix_affect"]["domain"] == "CURIOSITY"
            break
    else:
        assert False, "Should attach helix features to at least one node"

def test_intent_bind_without_helix():
    """_intent_bind should work without helix_coord (backwards compatible)."""
    fairy = AssociationCortexFairy()
    fairy._graph = ConceptGraph(max_nodes=10000, max_edges=50000)

    fairy._intent_bind({
        "text": "hello world",
        "source": "test",
    })

    graph = fairy.get_graph()
    assert len(graph.nodes) >= 1, "Should still add nodes without helix"

if __name__ == "__main__":
    test_intent_bind_with_helix()
    test_intent_bind_without_helix()
    print("All tests passed!")
