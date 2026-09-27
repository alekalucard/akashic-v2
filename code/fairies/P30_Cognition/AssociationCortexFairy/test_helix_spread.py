import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from fairies.P30_Cognition.AssociationCortexFairy.fairy import ConceptGraph

def test_spread_respects_helix_weights():
    """Spreading activation should prefer paths through similar helix domains."""
    graph = ConceptGraph(max_nodes=1000, max_edges=5000)

    # Create a graph:
    # JOY_A --strong(0.8)-- JOY_B --strong(0.8)-- JOY_C
    #   |
    # weak(0.2)
    #   |
    # FEAR_A

    # JOY cluster
    graph.upsert_node("joy_a", {"helix_affect": {"domain": "JOY", "intensity": 500}})
    graph.upsert_node("joy_b", {"helix_affect": {"domain": "JOY", "intensity": 600}})
    graph.upsert_node("joy_c", {"helix_affect": {"domain": "JOY", "intensity": 700}})

    # FEAR node
    graph.upsert_node("fear_a", {"helix_affect": {"domain": "FEAR", "intensity": 500}})

    # Strong links within JOY cluster
    graph.link("joy_a", "joy_b", "coactivate", weight=0.8)
    graph.link("joy_b", "joy_c", "coactivate", weight=0.8)

    # Weak cross-domain link
    graph.link("joy_a", "fear_a", "coactivate", weight=0.2)

    # Spread from joy_a
    activations = graph.spread_activation("joy_a", max_hops=2)

    print(f"Activations from joy_a:")
    for k, v in sorted(activations.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v:.4f}")

    # joy_c should be more activated than fear_a (same emotional domain)
    joy_c_act = activations.get("joy_c", 0)
    fear_a_act = activations.get("fear_a", 0)

    assert joy_c_act > fear_a_act, \
        f"JOY cluster should activate more ({joy_c_act}) than FEAR ({fear_a_act})"

    print(f"\njoy_c activation: {joy_c_act:.4f}")
    print(f"fear_a activation: {fear_a_act:.4f}")
    print(f"Ratio: {joy_c_act / max(fear_a_act, 0.001):.2f}x stronger")

if __name__ == "__main__":
    test_spread_respects_helix_weights()
    print("\nAll tests passed!")
