"""
Seed Geometric Vocabulary into the Manifold Cortex.

Loads geometric_vocabulary.json and creates properly typed nodes with:
- Semantic snippets (descriptions of each shape/symbol)
- node_type = SHAPE(4) for primitives, TEMPLATE(5) for object templates, CONCEPT(0) for properties
- region = SEMANTIC(1) for all geometric knowledge
- Typed edges: composed_of, is_a, part_of, spatial_*, shaped_like, semantic

This is Phase 4.5 of the Cortex Rebuild Blueprint.

Usage:
    python scripts/seed_geometric_vocabulary.py [--manifold path/to/cortex.manifold] [--dry-run]

2026-03-20, Nous + Ace -- Akashic Foundation
"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import os
import sys
import json
import time
import argparse

# Add project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from infrastructure.manifold_memory import (
    ManifoldMemory,
    NTYPE_CONCEPT, NTYPE_SHAPE, NTYPE_TEMPLATE,
    REGION_SEMANTIC,
    REL_COACTIVATE, REL_CAUSAL, REL_SEMANTIC, REL_TEMPORAL,
    REL_IS_A, REL_PART_OF, REL_COMPOSED_OF,
    REL_SPATIAL_ABOVE, REL_SPATIAL_BELOW, REL_SPATIAL_BESIDE,
    REL_SPATIAL_CONTAINS, REL_SPATIAL_ON, REL_SPATIAL_FACING,
    REL_ORIENTED_AS, REL_SHAPED_LIKE, REL_WEARING, REL_HOLDING,
)

# Relationship name -> constant mapping
REL_MAP = {
    "coactivate": REL_COACTIVATE,
    "causal": REL_CAUSAL,
    "semantic": REL_SEMANTIC,
    "temporal": REL_TEMPORAL,
    "is_a": REL_IS_A,
    "part_of": REL_PART_OF,
    "composed_of": REL_COMPOSED_OF,
    "spatial_above": REL_SPATIAL_ABOVE,
    "spatial_below": REL_SPATIAL_BELOW,
    "spatial_beside": REL_SPATIAL_BESIDE,
    "spatial_contains": REL_SPATIAL_CONTAINS,
    "spatial_on": REL_SPATIAL_ON,
    "spatial_facing": REL_SPATIAL_FACING,
    "oriented_as": REL_ORIENTED_AS,
    "shaped_like": REL_SHAPED_LIKE,
    "wearing": REL_WEARING,
    "holding": REL_HOLDING,
}


def load_vocabulary(vocab_path: str) -> dict:
    """Load the geometric vocabulary JSON."""
    with open(vocab_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def seed_section(graph: ManifoldMemory, section: dict, node_type: int,
                 prefix: str, stats: dict, dry_run: bool = False):
    """Seed a section of the vocabulary (shape_primitives, form_properties, etc.)."""
    for key, entry in section.items():
        if key.startswith("_"):
            continue  # skip _doc metadata

        node_key = f"geo:{prefix}:{key}"
        snippet = entry.get("snippet", "")

        # Determine node_type from entry override or default
        entry_type = entry.get("node_type", None)
        if entry_type == "shape":
            nt = NTYPE_SHAPE
        elif entry_type == "concept":
            nt = NTYPE_CONCEPT
        elif entry_type == "template":
            nt = NTYPE_TEMPLATE
        else:
            nt = node_type

        if dry_run:
            stats["nodes"] += 1
            stats["snippets_bytes"] += len(snippet.encode('utf-8'))
            continue

        slot = graph.upsert_node(
            key=node_key,
            activation=2.0,      # Higher than normal -- permanent vocabulary
            count=100,           # High count prevents decay/eviction
            snippet=snippet,
            node_type=nt,
            region=REGION_SEMANTIC,
        )

        if slot >= 0:
            stats["nodes"] += 1
            stats["snippets_bytes"] += len(snippet.encode('utf-8'))
        else:
            stats["failed"] += 1
            print(f"  FAILED to seed: {node_key}")


def seed_composed_of_edges(graph: ManifoldMemory, section: dict, prefix: str,
                           stats: dict, dry_run: bool = False):
    """Create composed_of edges from object templates / symbols to their shape primitives."""
    for key, entry in section.items():
        if key.startswith("_"):
            continue

        node_key = f"geo:{prefix}:{key}"
        composed_of = entry.get("composed_of", [])

        for component in composed_of:
            # Try to find the component in known prefixes
            component_key = _resolve_component(component)

            if dry_run:
                stats["edges"] += 1
                continue

            ok = graph.link(
                node_key, component_key,
                weight=0.8,
                rel_type=REL_COMPOSED_OF,
            )
            if ok:
                stats["edges"] += 1
            else:
                # Component might not exist yet -- create it as a reference
                stats["edge_misses"] += 1


def _resolve_component(name: str) -> str:
    """Resolve a component name to its full node key.

    Uses the same name resolution as _resolve_node_key to find the right prefix.
    Falls back to geo:shape:{name} for unresolved references (most components are shapes).
    """
    resolved = _resolve_node_key(name)
    if resolved.startswith("geo:ref:"):
        # Unknown name — default to shape prefix (most composed_of targets are shapes)
        return f"geo:shape:{name}"
    return resolved


def seed_relationships(graph: ManifoldMemory, relationships: list,
                       stats: dict, dry_run: bool = False):
    """Seed typed edges from the relationships section."""
    for rel in relationships:
        # Resolve node keys
        from_key = _resolve_node_key(rel.get("from") or rel.get("parent", ""))
        to_key = _resolve_node_key(rel.get("to") or rel.get("child", ""))
        rel_name = rel.get("rel", "semantic")
        rel_type = REL_MAP.get(rel_name, REL_SEMANTIC)

        if not from_key or not to_key:
            continue

        if dry_run:
            stats["edges"] += 1
            continue

        ok = graph.link(
            from_key, to_key,
            weight=0.7,
            rel_type=rel_type,
        )
        if ok:
            stats["edges"] += 1
        else:
            stats["edge_misses"] += 1


def _resolve_node_key(name: str) -> str:
    """Resolve a bare name from the relationships section to a full geo: key."""
    if not name:
        return ""
    if name.startswith("geo:"):
        return name  # Already qualified

    # Try each section prefix
    # Shape primitives
    SHAPE_NAMES = {
        "sphere", "hemisphere", "cylinder", "cone", "cube", "rectangular_prism",
        "plane_surface", "disk", "torus", "ellipsoid", "wedge", "pyramid",
        "helix", "spiral", "curve", "line_segment", "point", "ring", "arc",
        "wave_form", "crescent",
    }
    PROP_NAMES = {
        "bilateral_symmetry", "radial_symmetry", "rotational_symmetry",
        "fractal_symmetry", "vertical_axis", "horizontal_axis",
        "pointed_form", "organic_form", "angular_form", "hollow_form",
        "solid_form", "translucent_form", "luminous_form", "textured_surface",
        "smooth_surface", "flowing_form", "rigid_form",
    }
    SACRED_NAMES = {
        "flower_of_life", "seed_of_life", "tree_of_life", "metatrons_cube",
        "vesica_piscis", "golden_ratio", "fibonacci_spiral", "golden_rectangle",
        "sri_yantra", "merkaba", "mandala", "labyrinth", "infinity_symbol",
        "ouroboros", "yin_yang", "toroidal_field",
    }
    PLATONIC_NAMES = {
        "tetrahedron", "hexahedron", "octahedron", "dodecahedron", "icosahedron",
    }
    SYMBOL_NAMES = {
        "cross", "circle_symbol", "triangle_symbol", "square_symbol",
        "pentagon_symbol", "hexagon_symbol", "star_symbol", "arrow_symbol",
        "eye_symbol", "heart_symbol", "serpent_symbol", "ankh", "caduceus",
        "pentagram", "hexagram", "triskele",
    }
    TEMPLATE_NAMES = {
        "human_form", "face_form", "hand_form", "desk_form", "screen_form",
        "chair_form", "tree_form", "building_form", "vehicle_form",
        "text_block_form", "headphones_form", "keyboard_form", "cup_form",
        "book_form", "door_form", "window_form",
    }

    if name in SHAPE_NAMES:
        return f"geo:shape:{name}"
    elif name in PROP_NAMES:
        return f"geo:prop:{name}"
    elif name in SACRED_NAMES:
        return f"geo:sacred:{name}"
    elif name in PLATONIC_NAMES:
        return f"geo:platonic:{name}"
    elif name in SYMBOL_NAMES:
        return f"geo:symbol:{name}"
    elif name in TEMPLATE_NAMES:
        return f"geo:template:{name}"
    else:
        return f"geo:ref:{name}"


def seed_all(graph: ManifoldMemory, data: dict, dry_run: bool = False) -> dict:
    """Seed all geometric vocabulary into the manifold."""
    stats = {"nodes": 0, "edges": 0, "failed": 0, "edge_misses": 0, "snippets_bytes": 0}

    # ── 1. Shape primitives (NTYPE_SHAPE) ──
    print("  [1/7] Shape primitives...")
    seed_section(graph, data.get("shape_primitives", {}),
                 NTYPE_SHAPE, "shape", stats, dry_run)
    print(f"        {stats['nodes']} nodes")

    # ── 2. Form properties (NTYPE_CONCEPT) ──
    print("  [2/7] Form properties...")
    n_before = stats["nodes"]
    seed_section(graph, data.get("form_properties", {}),
                 NTYPE_CONCEPT, "prop", stats, dry_run)
    print(f"        {stats['nodes'] - n_before} nodes")

    # ── 3. Sacred geometry (NTYPE_SHAPE / NTYPE_CONCEPT) ──
    print("  [3/7] Sacred geometry...")
    n_before = stats["nodes"]
    seed_section(graph, data.get("sacred_geometry", {}),
                 NTYPE_SHAPE, "sacred", stats, dry_run)
    print(f"        {stats['nodes'] - n_before} nodes")

    # ── 4. Platonic solids (NTYPE_SHAPE) ──
    print("  [4/7] Platonic solids...")
    n_before = stats["nodes"]
    seed_section(graph, data.get("platonic_solids", {}),
                 NTYPE_SHAPE, "platonic", stats, dry_run)
    print(f"        {stats['nodes'] - n_before} nodes")

    # ── 5. Symbology (NTYPE_CONCEPT) ──
    print("  [5/7] Symbology...")
    n_before = stats["nodes"]
    seed_section(graph, data.get("symbology", {}),
                 NTYPE_CONCEPT, "symbol", stats, dry_run)
    print(f"        {stats['nodes'] - n_before} nodes")

    # ── 6. Object templates (NTYPE_TEMPLATE) ──
    print("  [6/7] Object templates...")
    n_before = stats["nodes"]
    seed_section(graph, data.get("object_templates", {}),
                 NTYPE_TEMPLATE, "template", stats, dry_run)
    print(f"        {stats['nodes'] - n_before} nodes")

    # ── 7. Edges: composed_of, hierarchy, sacred connections, cross-domain ──
    print("  [7/7] Typed edges...")
    e_before = stats["edges"]

    # Symbol composed_of edges
    seed_composed_of_edges(graph, data.get("symbology", {}),
                           "symbol", stats, dry_run)

    # Template composed_of edges
    seed_composed_of_edges(graph, data.get("object_templates", {}),
                           "template", stats, dry_run)

    # Geometric relationships: hierarchy
    rels = data.get("geometric_relationships", {})
    seed_relationships(graph, rels.get("hierarchy", []), stats, dry_run)

    # Sacred connections
    seed_relationships(graph, rels.get("sacred_connections", []), stats, dry_run)

    # Cross-domain connections
    seed_relationships(graph, rels.get("cross_domain", []), stats, dry_run)

    print(f"        {stats['edges'] - e_before} edges "
          f"({stats['edge_misses']} missed)")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Seed geometric vocabulary into cortex manifold")
    parser.add_argument("--manifold", default=None,
                        help="Path to cortex.manifold (default: auto-detect)")
    parser.add_argument("--vocab", default=None,
                        help="Path to geometric_vocabulary.json (default: auto-detect)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be seeded without modifying the manifold")
    args = parser.parse_args()

    # Find manifold
    if args.manifold:
        manifold_path = args.manifold
    else:
        candidates = [
            os.path.join("state", "akashic", "cortex.manifold"),
            os.path.join("..", "state", "akashic", "cortex.manifold"),
        ]
        manifold_path = None
        for c in candidates:
            if os.path.exists(c):
                manifold_path = c
                break
        if not manifold_path:
            print("ERROR: Could not find cortex.manifold. Use --manifold to specify path.")
            sys.exit(1)

    # Find vocabulary JSON
    if args.vocab:
        vocab_path = args.vocab
    else:
        candidates = [
            os.path.join("state", "knowledge_seeds", "geometric_vocabulary.json"),
            os.path.join("..", "state", "knowledge_seeds", "geometric_vocabulary.json"),
        ]
        vocab_path = None
        for c in candidates:
            if os.path.exists(c):
                vocab_path = c
                break
        if not vocab_path:
            print("ERROR: Could not find geometric_vocabulary.json. Use --vocab to specify path.")
            sys.exit(1)

    # Load vocabulary
    print(f"Loading vocabulary: {vocab_path}")
    data = load_vocabulary(vocab_path)

    meta = data.get("_meta", {})
    print(f"  Title: {meta.get('title', 'unknown')}")
    print(f"  Version: {meta.get('version', '?')}")

    sections = [k for k in data.keys() if not k.startswith("_")]
    print(f"  Sections: {', '.join(sections)}")

    if args.dry_run:
        print(f"\n--- DRY RUN (no manifold changes) ---")
        stats = seed_all(None, data, dry_run=True)
    else:
        # Open manifold for writing
        file_size = os.path.getsize(manifold_path)
        print(f"\nOpening manifold: {manifold_path} ({file_size / (1024*1024):.1f} MB)")
        graph = ManifoldMemory(manifold_path)

        status_before = graph.status()
        print(f"  Before: {status_before['nodes']} nodes, {status_before['edges']} edges")

        print(f"\nSeeding geometric vocabulary...")
        t0 = time.time()
        stats = seed_all(graph, data)
        elapsed = time.time() - t0

        # Flush header
        graph._write_header()

        status_after = graph.status()
        print(f"\n  After: {status_after['nodes']} nodes, {status_after['edges']} edges")
        graph.close()

        print(f"\nSeeding complete in {elapsed:.1f}s")

    print(f"\n--- Summary ---")
    print(f"  Nodes created:  {stats['nodes']}")
    print(f"  Edges created:  {stats['edges']}")
    print(f"  Snippet bytes:  {stats['snippets_bytes']:,}")
    print(f"  Failed nodes:   {stats['failed']}")
    print(f"  Missed edges:   {stats['edge_misses']}")

    if not args.dry_run:
        # Verify a few nodes
        print(f"\n--- Verification ---")
        graph = ManifoldMemory(manifold_path, readonly=True)
        for test_key in ["geo:shape:sphere", "geo:sacred:flower_of_life",
                         "geo:template:human_form", "geo:symbol:eye_symbol",
                         "geo:platonic:tetrahedron"]:
            node = graph.get_node(test_key)
            if node:
                snippet = node.get("snippet", "")[:60]
                ntype = node.get("node_type_name", "?")
                print(f"  {test_key}: type={ntype}, snippet=\"{snippet}...\"")
            else:
                print(f"  {test_key}: NOT FOUND")
        graph.close()

    return 0 if stats["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
