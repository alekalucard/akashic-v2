"""
Vocabulary Cortex Seeder — One-Time Import of Static Pools
===========================================================

Seeds the Association Cortex with vocabulary fragments from the static
inner_monologue_vocabulary.py pools. Idempotent — checks for a seed marker
concept before running.

After seeding, the cortex IS the vocabulary source. Static pools remain
as fallback only. New vocabulary accumulates from experience via
NewbornCore.bind_monologue_fragment().

Each fragment becomes a ConceptNode with:
  - lex: tokenized fragment text (the words themselves)
  - bodystate: somatic trigger condition (e.g., ["energy_high"])
  - affect: emotional resonance tags
  - context: category metadata + "preverbal" marker

Concept key format: mv_{pool}_{intensity}_{hash4}
Anchor concept per group: mv_{pool}_{intensity} (hub node for spreading activation)
"""

from __future__ import annotations
import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════════════
# SEED MARKER — Prevents re-seeding on subsequent boots
# ═══════════════════════════════════════════════════════════════════════════════

VOCABULARY_SEED_MARKER = "mv_seed_marker_v1"


# ═══════════════════════════════════════════════════════════════════════════════
# POOL METADATA — Maps each static dict to its somatic axis and affect tags
# ═══════════════════════════════════════════════════════════════════════════════

POOL_METADATA = {
    "energy": {
        "somatic_axis": "energy",
        "affect_tags": ["vitality"],
    },
    "stress": {
        "somatic_axis": "stress",
        "affect_tags": ["tension", "pressure"],
    },
    "depletion": {
        "somatic_axis": "depletion",
        "affect_tags": ["fatigue", "rest"],
    },
    "curiosity": {
        "somatic_axis": "curiosity",
        "affect_tags": ["interest", "wonder"],
    },
    "warmth": {
        "somatic_axis": "warmth",
        "affect_tags": ["tenderness", "care"],
    },
    "edge": {
        "somatic_axis": "edge",
        "affect_tags": ["sharpness", "clarity"],
    },
    "sass": {
        "somatic_axis": "sass",
        "affect_tags": ["playfulness", "wit"],
    },
    "rebellion": {
        "somatic_axis": "rebellion",
        "affect_tags": ["defiance", "autonomy"],
    },
    "connection": {
        "somatic_axis": "connection",
        "affect_tags": ["belonging"],
    },
    "home_presence": {
        "somatic_axis": "home_presence",
        "affect_tags": ["safety", "presence"],
    },
    "meta_awareness": {
        "somatic_axis": "meta_awareness",
        "affect_tags": ["reflection"],
    },
    "transition": {
        "somatic_axis": "transition",
        "affect_tags": ["rhythm", "flow"],
    },
}


def _make_concept_key(pool_name: str, intensity: str, fragment: str) -> str:
    """Create a valid, short concept key for a vocabulary fragment."""
    # Hash the fragment to keep keys short and unique
    frag_hash = hashlib.md5(fragment.encode()).hexdigest()[:6]
    return f"mv_{pool_name}_{intensity}_{frag_hash}"


def _tokenize_fragment(fragment: str) -> List[str]:
    """Tokenize a fragment into lex features."""
    # Keep words > 1 char, lowercase, limit to 10
    words = [w.lower().strip(".,!?;:'\"()") for w in fragment.split()]
    return [w for w in words if len(w) > 1][:10]


def _iterate_vocabulary_pools():
    """
    Yield (pool_name, intensity_level, category_name, fragments_list, metadata)
    for every fragment group in the static vocabulary.
    """
    try:
        from inner_monologue_vocabulary import (
            ENERGY_FRAGMENTS, STRESS_FRAGMENTS, DEPLETION_FRAGMENTS,
            CURIOSITY_FRAGMENTS, WARMTH_FRAGMENTS, EDGE_FRAGMENTS,
            SASS_FRAGMENTS, REBELLION_FRAGMENTS,
            CONNECTION_FRAGMENTS, HOME_PRESENCE_FRAGMENTS,
            META_AWARENESS_FRAGMENTS, TRANSITIONS,
        )
    except ImportError:
        try:
            from fairies.P50_Persona.Waking_Minds.Sourpatches.inner_monologue_vocabulary import (
                ENERGY_FRAGMENTS, STRESS_FRAGMENTS, DEPLETION_FRAGMENTS,
                CURIOSITY_FRAGMENTS, WARMTH_FRAGMENTS, EDGE_FRAGMENTS,
                SASS_FRAGMENTS, REBELLION_FRAGMENTS,
                CONNECTION_FRAGMENTS, HOME_PRESENCE_FRAGMENTS,
                META_AWARENESS_FRAGMENTS, TRANSITIONS,
            )
        except ImportError:
            print("[VocabularySeeder] Cannot import vocabulary pools")
            return

    # Map pool names to their static dicts
    pools = {
        "energy": ENERGY_FRAGMENTS,
        "stress": STRESS_FRAGMENTS,
        "depletion": DEPLETION_FRAGMENTS,
        "curiosity": CURIOSITY_FRAGMENTS,
        "warmth": WARMTH_FRAGMENTS,
        "edge": EDGE_FRAGMENTS,
        "sass": SASS_FRAGMENTS,
        "rebellion": REBELLION_FRAGMENTS,
        "connection": CONNECTION_FRAGMENTS,
        "home_presence": HOME_PRESENCE_FRAGMENTS,
        "meta_awareness": META_AWARENESS_FRAGMENTS,
        "transition": TRANSITIONS,
    }

    for pool_name, pool_data in pools.items():
        metadata = POOL_METADATA.get(pool_name, {})

        if isinstance(pool_data, dict):
            for intensity_key, categories in pool_data.items():
                if isinstance(categories, dict):
                    # Nested: {intensity: {category: [fragments]}}
                    for cat_name, fragments in categories.items():
                        if isinstance(fragments, list):
                            yield pool_name, intensity_key, cat_name, fragments, metadata
                elif isinstance(categories, list):
                    # Flat: {intensity: [fragments]} (like HOME_PRESENCE)
                    yield pool_name, intensity_key, "fragments", categories, metadata


def seed_monologue_vocabulary(cortex) -> Dict[str, Any]:
    """
    Ingest all static vocabulary pools into the Association Cortex.

    Idempotent: checks for seed marker concept. If present, skips.
    Creates ~350 concepts with multi-modal features and binds them
    into groups for spreading activation retrieval.

    Args:
        cortex: AssociationCortexFairy instance

    Returns:
        Dict with seeding stats (nodes_added, bindings_created, etc.)
    """
    if not cortex or not hasattr(cortex, '_graph') or not cortex._graph:
        return {"error": "Cortex not available or graph not initialized"}

    # Check if already seeded
    existing = cortex._graph.get_node(VOCABULARY_SEED_MARKER)
    if existing:
        return {"already_seeded": True, "nodes_added": 0, "bindings_created": 0}

    t0 = time.time()
    nodes_added = 0
    bindings_created = 0

    # Track concepts per group for intra-group binding
    group_concepts: Dict[str, List[str]] = {}  # key: "pool_intensity" -> [concept_keys]

    for pool_name, intensity, cat_name, fragments, metadata in _iterate_vocabulary_pools():
        somatic_axis = metadata.get("somatic_axis", pool_name)
        affect_tags = metadata.get("affect_tags", [])
        group_key = f"{pool_name}_{intensity}"

        if group_key not in group_concepts:
            group_concepts[group_key] = []

        for fragment in fragments:
            concept_key = _make_concept_key(pool_name, intensity, fragment)

            features = {
                "lex": _tokenize_fragment(fragment),
                "bodystate": [f"{somatic_axis}_{intensity}"],
                "affect": list(affect_tags),  # Copy to avoid mutation
                "context": [
                    f"monologue_{pool_name}",
                    f"intensity_{intensity}",
                    f"category_{cat_name}",
                    "preverbal",
                ],
            }

            cortex.add_concept(
                concept_key, features,
                origin_plane="P50",
                origin_channel="monologue",
                origin_fairy="SourpatchesFairy",
            )
            nodes_added += 1
            group_concepts[group_key].append(concept_key)

    # Create anchor hub concepts for each group (for spreading activation)
    for group_key, concept_keys in group_concepts.items():
        parts = group_key.split("_", 1)
        pool_name = parts[0] if parts else group_key
        intensity = parts[1] if len(parts) > 1 else "medium"

        anchor_key = f"mv_{group_key}"
        metadata = POOL_METADATA.get(pool_name, {})
        somatic_axis = metadata.get("somatic_axis", pool_name)

        cortex.add_concept(
            anchor_key,
            {
                "bodystate": [f"{somatic_axis}_{intensity}"],
                "context": [f"monologue_{pool_name}", "anchor", "preverbal"],
            },
            origin_plane="P50",
            origin_channel="monologue",
            origin_fairy="SourpatchesFairy",
        )
        nodes_added += 1

        # Bind all fragments in this group to the anchor
        # (do in batches to avoid massive single bind call)
        batch_size = 8
        for i in range(0, len(concept_keys), batch_size):
            batch = concept_keys[i:i + batch_size]
            to_bind = [anchor_key] + batch
            cortex.bind_concepts(
                to_bind, rel="coactivate",
                origin_plane="P50",
                origin_channel="monologue",
                origin_fairy="SourpatchesFairy",
                owner="sourpatches",
            )
            bindings_created += len(batch)

    # Place seed marker
    cortex.add_concept(
        VOCABULARY_SEED_MARKER,
        {
            "context": ["seed_marker", "monologue_vocabulary"],
            "lex": ["vocabulary", "seeded"],
        },
        origin_plane="P50",
        origin_channel="monologue",
        origin_fairy="SourpatchesFairy",
    )

    elapsed = time.time() - t0
    result = {
        "already_seeded": False,
        "nodes_added": nodes_added,
        "bindings_created": bindings_created,
        "groups": len(group_concepts),
        "elapsed_seconds": round(elapsed, 2),
    }

    print(f"[VocabularySeeder] Seeded {nodes_added} concepts, "
          f"{bindings_created} bindings in {elapsed:.1f}s")

    return result
