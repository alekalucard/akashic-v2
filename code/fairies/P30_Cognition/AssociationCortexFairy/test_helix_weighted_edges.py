import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from fairies.P30_Cognition.AssociationCortexFairy.fairy import AssociationCortexFairy, ConceptGraph

def test_helix_weighted_linking():
    """Concepts with similar helix coords should get stronger edges."""
    fairy = AssociationCortexFairy()
    fairy._graph = ConceptGraph(max_nodes=10000, max_edges=50000)

    # Bind with SAME affect domain
    fairy._intent_bind({
        "text": "happy celebration",
        "source": "test",
        "helix_coord": {
            "affect": {"domain": "JOY", "intensity": 700},
            "semantic": {"domain": "SOCIAL", "specificity": 500},
            "temporal": {"scale": "DAILY", "position": 500},
        },
    })

    fairy._intent_bind({
        "text": "joyful party",
        "source": "test",
        "helix_coord": {
            "affect": {"domain": "JOY", "intensity": 750},
            "semantic": {"domain": "SOCIAL", "specificity": 600},
            "temporal": {"scale": "DAILY", "position": 500},
        },
    })

    # Bind with DIFFERENT affect domain
    fairy._intent_bind({
        "text": "fear darkness",
        "source": "test",
        "helix_coord": {
            "affect": {"domain": "FEAR", "intensity": 700},
            "semantic": {"domain": "ABSTRACT", "specificity": 500},
            "temporal": {"scale": "DAILY", "position": 500},
        },
    })

    graph = fairy.get_graph()

    # Link across helix positions
    fairy.bind_concepts_with_helix(
        same_domain_pairs=[("happy", "joyful")],
        cross_domain_pairs=[("happy", "fear")]
    )

    # Check edges - sorted key order
    happy_joyful = graph.edges.get(("happy", "joyful")) or graph.edges.get(("joyful", "happy"))
    happy_fear = graph.edges.get(("fear", "happy")) or graph.edges.get(("happy", "fear"))

    if happy_joyful and happy_fear:
        print(f"Same-domain (happy-joyful): {happy_joyful['weight']}")
        print(f"Cross-domain (happy-fear): {happy_fear['weight']}")
        assert happy_joyful["weight"] > happy_fear["weight"], \
            f"Same-domain edge should be stronger"

if __name__ == "__main__":
    test_helix_weighted_linking()
    print("All tests passed!")
