"""
Smoke test for CortexReasoner.

Usage:
    cd F:\\Sandbox\\failure_factory\\akashic_v2
    python test_cortex_reasoner.py

Two modes:
  - If the system is booted and the cortex has nodes -> tests against real graph
  - Otherwise -> builds a synthetic test graph and tests against that

Tests:
  1. Concept extraction
  2. Spreading activation
  3. Convergence detection
  4. Confidence scoring
  5. Performance (<100ms per query)
"""

import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def build_test_graph():
    """Build a synthetic graph with known topology for deterministic testing."""
    from fairies.P30_Cognition.AssociationCortexFairy.fairy import ConceptGraph, ConceptNode

    graph = ConceptGraph()

    # ── Create concept nodes ──
    concepts = {
        "consciousness": {"lex": ["awareness", "experience", "subjective"], "affect": ["wonder"]},
        "empathy": {"lex": ["feeling", "understanding", "emotion"], "affect": ["warmth"]},
        "fairy": {"lex": ["agent", "processor", "module"], "context": ["akashic system"]},
        "somatic": {"lex": ["body", "sensation", "feeling"], "bodystate": ["heartbeat"]},
        "portal": {"lex": ["gateway", "subprocess", "bridge"], "context": ["gpu inference"]},
        "activation": {"lex": ["spreading", "energy", "signal"]},
        "cortex": {"lex": ["graph", "concepts", "reasoning"], "context": ["association cortex"]},
        "memory": {"lex": ["recall", "storage", "persistence"], "context": ["srm system"]},
        "emotion": {"lex": ["feeling", "affect", "mood"], "affect": ["varied"]},
        "coherence": {"lex": ["alignment", "consistency", "harmony"], "affect": ["calm"]},
        "gravity": {"lex": ["mass", "density", "curvature"], "context": ["portal physics"]},
        "affect": {"lex": ["feeling", "coupling", "resonance"], "affect": ["presence"]},
        "coupling": {"lex": ["binding", "connection", "link"], "context": ["physics"]},
        "decay": {"lex": ["reduction", "falloff", "attenuation"]},
        "distance": {"lex": ["hops", "separation", "path"]},
        "spreading": {"lex": ["propagation", "diffusion", "flow"]},
        "system": {"lex": ["architecture", "framework", "organism"], "context": ["akashic"]},
        "boot": {"lex": ["startup", "initialization", "launch"], "context": ["v3 boot"]},
        "failure": {"lex": ["error", "crash", "exception"], "affect": ["concern"]},
        "handle": {"lex": ["manage", "process", "recover"]},
        # Hub nodes (many connections)
        "experience": {"lex": ["event", "moment"], "affect": ["growth"], "context": ["consciousness"]},
        "connection": {"lex": ["link", "bond", "bridge"], "affect": ["belonging"]},
        "reasoning": {"lex": ["logic", "inference", "thinking"], "context": ["cognition"]},
        "state": {"lex": ["condition", "status", "phase"]},
        "signal": {"lex": ["message", "pulse", "trigger"]},
    }

    for key, features in concepts.items():
        graph.upsert_node(key, features=features, origin_plane="P30",
                         origin_channel="cognition", origin_fairy="TestFairy")

    # ── Create edges (connections between concepts) ──
    edges = [
        # Consciousness cluster
        ("consciousness", "empathy", 3.0),
        ("consciousness", "experience", 5.0),
        ("consciousness", "emotion", 2.5),
        ("consciousness", "coherence", 2.0),
        ("consciousness", "cortex", 1.5),
        # Empathy cluster
        ("empathy", "emotion", 4.0),
        ("empathy", "connection", 3.0),
        ("empathy", "experience", 2.5),
        ("empathy", "somatic", 1.5),
        # Fairy system cluster
        ("fairy", "system", 4.0),
        ("fairy", "boot", 3.0),
        ("fairy", "handle", 2.0),
        ("fairy", "portal", 1.5),
        # Somatic cluster
        ("somatic", "emotion", 3.0),
        ("somatic", "coherence", 3.5),
        ("somatic", "state", 2.0),
        ("somatic", "signal", 1.5),
        # Portal/physics cluster
        ("portal", "gravity", 4.0),
        ("portal", "coupling", 2.0),
        ("portal", "cortex", 1.5),
        # Activation/spreading cluster
        ("activation", "spreading", 5.0),
        ("activation", "decay", 3.0),
        ("activation", "signal", 2.0),
        ("activation", "cortex", 2.5),
        # More bridges
        ("spreading", "distance", 3.0),
        ("spreading", "decay", 2.5),
        ("cortex", "reasoning", 4.0),
        ("cortex", "memory", 3.0),
        ("cortex", "connection", 2.0),
        ("memory", "experience", 3.0),
        ("memory", "state", 1.5),
        ("boot", "failure", 3.0),
        ("boot", "system", 2.5),
        ("failure", "handle", 4.0),
        ("handle", "system", 2.0),
        ("gravity", "coupling", 3.0),
        ("gravity", "affect", 2.0),
        ("affect", "coupling", 3.5),
        ("affect", "emotion", 2.5),
        ("affect", "experience", 2.0),
        ("coherence", "state", 2.0),
        ("coherence", "signal", 1.5),
        ("reasoning", "experience", 2.0),
        ("connection", "signal", 1.5),
        ("experience", "state", 2.0),
    ]

    for a, b, weight in edges:
        edge_key = (a, b) if a < b else (b, a)
        graph.edges[edge_key] = {
            "relations": ["coactivate"],
            "weight": weight,
            "contexts": ["test"],
            "owner": "system",
        }
        # Build adjacency
        graph._adjacency[a][b] = edge_key
        graph._adjacency[b][a] = edge_key

    return graph


class FakeCortex:
    """Minimal cortex facade for testing (just needs get_graph())."""
    def __init__(self, graph):
        self._graph = graph

    def get_graph(self):
        return self._graph


def main():
    print("=" * 70)
    print("CortexReasoner Smoke Test")
    print("=" * 70)

    # ── Try real cortex first, fall back to synthetic ──
    print("\n[1] Loading graph...")
    graph = None
    using_real = False

    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import (
            get_association_cortex, ConceptGraph
        )
        cortex = get_association_cortex()
        if cortex:
            graph = cortex.get_graph()
            if graph and len(graph.nodes) > 100:
                using_real = True
                print(f"  Using REAL cortex graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    except Exception:
        pass

    if not using_real:
        print("  Real cortex not available. Building synthetic test graph...")
        graph = build_test_graph()
        cortex = FakeCortex(graph)
        print(f"  Synthetic graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")

    # ── Load CortexReasoner ──
    print("\n[2] Initializing CortexReasoner...")
    from fairies.P30_Cognition.integration.cortex_reasoner import CortexReasoner

    # For synthetic graph, lower the min nodes threshold
    if not using_real:
        CortexReasoner.MIN_GRAPH_NODES = 10

    reasoner = CortexReasoner(cortex)
    print(f"  {reasoner}")

    # ── Test concept extraction ──
    print("\n[3] Testing concept extraction...")
    test_prompts = [
        "What is the relationship between consciousness and empathy?",
        "Analyze the somatic state and determine if there is coherence",
        "How does the fairy system handle boot failures?",
        "Describe the portal gravity and affect coupling mechanisms",
        "Why does spreading activation decay with distance?",
    ]

    for prompt in test_prompts:
        concepts = reasoner.extract_concepts(prompt)
        in_graph = [c for c in concepts if graph.get_node(c)]
        print(f"  '{prompt[:55]}...'")
        print(f"    Extracted: {concepts}")
        print(f"    In graph:  {in_graph} ({len(in_graph)}/{len(concepts)})")
    print()

    # ── Test full reasoning pipeline ──
    print("[4] Testing full reasoning pipeline...")
    print("-" * 70)

    all_pass = True
    for prompt in test_prompts:
        t0 = time.perf_counter()
        result = reasoner.reason(prompt)
        elapsed = (time.perf_counter() - t0) * 1000

        is_hit = result.confidence >= CortexReasoner.CONFIDENCE_THRESHOLD
        marker = "HIT" if is_hit else "MISS"

        print(f"\n  Prompt:      '{prompt}'")
        print(f"  Mode:        {result.reasoning_mode}")
        print(f"  Confidence:  {result.confidence:.3f} [{marker}]")
        print(f"  Activated:   {len(result.activated_concepts)} concepts")
        print(f"  Convergence: {result.convergence_nodes[:5]}")
        if result.paths:
            print(f"  Paths:       {result.paths[:2]}")
        print(f"  Elapsed:     {elapsed:.1f}ms")
        if result.text:
            print(f"  Text:        {result.text[:150]}...")

        # Validation
        if result.reasoning_mode == "none":
            print("  WARNING: reasoning_mode is 'none' — no activation happened")
        if elapsed > 100:
            print(f"  WARNING: slow ({elapsed:.0f}ms > 100ms target)")
            all_pass = False

    # ── Stats summary ──
    print("\n" + "=" * 70)
    print("[5] Summary Statistics")
    print("=" * 70)
    stats = reasoner.get_stats()
    print(f"  Total queries:    {stats['total_queries']}")
    print(f"  Cortex hits:      {stats['cortex_hits']}")
    print(f"  Cortex misses:    {stats['cortex_misses']}")
    print(f"  Avg confidence:   {stats['avg_confidence']:.3f}")
    print(f"  Avg elapsed ms:   {stats['avg_elapsed_ms']:.1f}")

    hit_rate = stats['cortex_hits'] / max(1, stats['total_queries']) * 100
    print(f"  Hit rate:         {hit_rate:.0f}%")

    if stats['avg_elapsed_ms'] < 100:
        print(f"\n  PASS: Performance {stats['avg_elapsed_ms']:.1f}ms avg (target <100ms)")
    else:
        print(f"\n  SLOW: Performance {stats['avg_elapsed_ms']:.1f}ms avg (target <100ms)")

    if stats['avg_confidence'] >= 0.2:
        print(f"  PASS: Avg confidence {stats['avg_confidence']:.3f}")
    else:
        print(f"  WARN: Low confidence {stats['avg_confidence']:.3f}")

    if all_pass:
        print("\n  All tests PASSED.")
    else:
        print("\n  Some tests had warnings — see above.")

    # Restore default
    CortexReasoner.MIN_GRAPH_NODES = 1000


if __name__ == "__main__":
    main()
