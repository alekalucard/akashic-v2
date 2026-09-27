# ═══════════════════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE SEEDER - Bootstrap Association Cortex with External Knowledge
# ═══════════════════════════════════════════════════════════════════════════════════════════
#
# "To see is to connect. To connect is to understand."
#
# This module seeds the Association Cortex and Manifold Cortex with knowledge from:
# 1. Color Psychology Database - color → emotion/trait associations
# 2. Emotion-Colors Dataset - emotion → dominant color associations
# 3. ConceptNet (optional) - general semantic associations
#
# ═══════════════════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root
# FIX 2026-05-15 (Nous + Ace): added 4th .parent. File lives at
# fairies/P40_Sensory/cortex/knowledge_seeder.py; three .parent calls
# resolved to fairies/, not the actual project root akashic_v2/. All
# 7 seed databases at akashic_v2/state/knowledge_seeds/ have been
# silently failing to load for ~2 months. Boot log "Domain concepts
# DB not found" was the visible symptom.
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Global seeding graph (populated by seed_association_cortex)
_SEEDING_GRAPH = None

# Knowledge seed locations
KNOWLEDGE_SEEDS_DIR = PROJECT_ROOT / "state" / "knowledge_seeds"
COLOR_PSYCHOLOGY_DB = KNOWLEDGE_SEEDS_DIR / "color-psychology-database" / "data.json"
EMOTION_COLORS_CSV = KNOWLEDGE_SEEDS_DIR / "Emotion-Colors" / "emotions_images_colors.csv"
DOMAIN_CONCEPTS_DB = KNOWLEDGE_SEEDS_DIR / "domain_concepts.json"

# Color name to hex mapping (for V4 integration)
COLOR_NAME_TO_HEX = {
    "red": "#ff0000",
    "orange": "#ff8000",
    "yellow": "#ffff00",
    "green": "#00ff00",
    "blue": "#0000ff",
    "indigo": "#4b0082",
    "purple": "#800080",
    "turquoise": "#40e0d0",
    "pink": "#ffc0cb",
    "magenta": "#ff00ff",
    "brown": "#8b4513",
    "grey": "#808080",
    "gray": "#808080",
    "silver": "#c0c0c0",
    "gold": "#ffd700",
    "white": "#ffffff",
    "black": "#000000",
    "cyan": "#00ffff",
    "teal": "#008080",
}


# ═══════════════════════════════════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════════════════════

def load_color_psychology_db() -> Dict[str, Any]:
    """Load the color psychology database."""
    if not COLOR_PSYCHOLOGY_DB.exists():
        print(f"[KnowledgeSeeder] Color psychology DB not found: {COLOR_PSYCHOLOGY_DB}")
        return {}
    
    with open(COLOR_PSYCHOLOGY_DB, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_emotion_colors_db() -> List[Dict[str, Any]]:
    """Load the emotion-colors dataset from CSV."""
    import csv

    if not EMOTION_COLORS_CSV.exists():
        print(f"[KnowledgeSeeder] Emotion-Colors CSV not found: {EMOTION_COLORS_CSV}")
        return []

    entries = []
    with open(EMOTION_COLORS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            # Format: idx, idx2, idx3, emotion, image_url, color_rgb
            if len(row) >= 6:
                emotion = row[3].strip().lower() if len(row) > 3 else ""
                color_str = row[5].strip() if len(row) > 5 else ""

                if emotion and color_str:
                    entries.append({
                        "emotion": emotion,
                        "color_str": color_str,
                    })

    return entries


def load_domain_concepts_db() -> Dict[str, Any]:
    """Load the domain concepts knowledge base."""
    if not DOMAIN_CONCEPTS_DB.exists():
        print(f"[KnowledgeSeeder] Domain concepts DB not found: {DOMAIN_CONCEPTS_DB}")
        return {}

    with open(DOMAIN_CONCEPTS_DB, 'r', encoding='utf-8') as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════════════════════════════════
# ASSOCIATION EXTRACTION
# ═══════════════════════════════════════════════════════════════════════════════════════════

def extract_color_trait_associations(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract (color, trait, strength) associations from color psychology DB.
    
    Returns list of:
    {
        "color": "purple",
        "color_hex": "#800080",
        "trait": "creative",
        "positive": True,
        "strength": 0.7
    }
    """
    associations = []
    
    for trait_key, entry in data.items():
        trait_text = entry.get("text", trait_key)
        is_positive = entry.get("positive", True)
        colors = entry.get("colors", [])
        importances = entry.get("importance", [])
        
        # Normalize importances to 0-1 range
        # Original scale seems to be -inf to +inf with typical values 0-2
        max_importance = max(importances) if importances else 1
        min_importance = min(importances) if importances else 0
        importance_range = max(1, max_importance - min_importance)
        
        for i, color in enumerate(colors):
            importance = importances[i] if i < len(importances) else 0
            # Convert importance to 0-1 strength (2 = strong, 0 = moderate, negative = weak)
            strength = 0.5 + (importance / 4.0)  # Maps 2 -> 1.0, 0 -> 0.5, -2 -> 0
            strength = max(0.3, min(1.0, strength))
            
            associations.append({
                "color": color.lower(),
                "color_hex": COLOR_NAME_TO_HEX.get(color.lower(), "#808080"),
                "trait": trait_text.lower().replace("_", " "),
                "trait_key": trait_key,
                "positive": is_positive,
                "strength": strength,
            })
    
    return associations


def extract_emotion_color_associations(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract (emotion, color) associations from emotion-colors dataset.

    Returns list of:
    {
        "emotion": "happy",
        "color_rgb": [255, 200, 100],
        "strength": 1.0
    }
    """
    from collections import Counter, defaultdict

    # Aggregate colors by emotion
    emotion_colors = defaultdict(list)

    for entry in data:
        emotion = entry.get("emotion", "").lower()
        color_str = entry.get("color_str", "")

        if emotion and color_str:
            # Parse RGB tuple string like "(211, 205, 200)"
            try:
                if color_str.startswith("(") or color_str.startswith("["):
                    color_rgb = tuple(map(int, color_str.strip("()[]").split(",")))
                    emotion_colors[emotion].append(color_rgb)
            except:
                pass

    # Compute average color for each emotion
    associations = []
    for emotion, colors in emotion_colors.items():
        if not colors:
            continue

        # Average RGB
        avg_r = sum(c[0] for c in colors) / len(colors)
        avg_g = sum(c[1] for c in colors) / len(colors)
        avg_b = sum(c[2] for c in colors) / len(colors)
        avg_rgb = (int(avg_r), int(avg_g), int(avg_b))

        associations.append({
            "emotion": emotion,
            "color_rgb": avg_rgb,
            "color_hex": "#{:02x}{:02x}{:02x}".format(*avg_rgb),
            "sample_count": len(colors),
            "strength": min(1.0, len(colors) / 50.0),  # More samples = stronger
        })

    return associations


def extract_domain_concept_associations(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract concept associations from domain concepts DB.

    Creates:
    - Domain nodes (coding, reading, art, science, etc.)
    - Concept nodes within domains
    - Cross-domain relationship edges
    - Affect associations (how concepts feel)

    Returns list of association dicts for seeding.
    """
    associations = []

    domains = data.get("domains", {})
    meta_concepts = data.get("meta_concepts", {})
    cross_links = data.get("cross_domain_links", [])

    # 1. Extract domain -> concept relationships
    for domain_name, domain_data in domains.items():
        # Core concepts within domain
        core_concepts = domain_data.get("core_concepts", [])
        for concept in core_concepts:
            associations.append({
                "type": "domain_concept",
                "domain": domain_name,
                "concept": concept,
                "relation": "contains",
                "strength": 0.9,
            })

        # Sub-concepts (hierarchical)
        sub_concepts = domain_data.get("sub_concepts", {})
        for category, concepts in sub_concepts.items():
            # Category belongs to domain
            associations.append({
                "type": "domain_category",
                "domain": domain_name,
                "concept": category,
                "relation": "has_category",
                "strength": 0.85,
            })
            # Concepts belong to category
            for concept in concepts:
                associations.append({
                    "type": "category_concept",
                    "domain": domain_name,
                    "parent": category,
                    "concept": concept,
                    "relation": "includes",
                    "strength": 0.8,
                })

        # Affects (emotional associations)
        affects = domain_data.get("affects", {})
        for affect_type, triggers in affects.items():
            for trigger in triggers:
                associations.append({
                    "type": "concept_affect",
                    "domain": domain_name,
                    "concept": trigger,
                    "affect": affect_type,
                    "relation": "evokes",
                    "strength": 0.7,
                })

        # Domain-to-domain links
        links_to = domain_data.get("links_to", [])
        for linked_domain in links_to:
            associations.append({
                "type": "domain_link",
                "from_domain": domain_name,
                "to_domain": linked_domain,
                "relation": "relates_to",
                "strength": 0.6,
            })

    # 2. Meta-concepts (learning, creativity, problem_solving)
    for meta_name, meta_data in meta_concepts.items():
        concepts = meta_data.get("concepts", [])
        for concept in concepts:
            associations.append({
                "type": "meta_concept",
                "meta_domain": meta_name,
                "concept": concept,
                "relation": "involves",
                "strength": 0.85,
            })
        affects = meta_data.get("affects", [])
        for affect in affects:
            associations.append({
                "type": "meta_affect",
                "meta_domain": meta_name,
                "affect": affect,
                "relation": "produces",
                "strength": 0.7,
            })

    # 3. Explicit cross-domain links
    for link in cross_links:
        associations.append({
            "type": "cross_domain",
            "from": link["from"],
            "to": link["to"],
            "relation": link.get("relation", "connects"),
            "strength": link.get("strength", 0.5),
        })

    return associations


def seed_domain_concepts(associations: List[Dict[str, Any]], graph=None) -> Dict[str, Any]:
    """
    Seed domain concepts into the Association Cortex.

    Creates concept nodes and relationship edges for domain knowledge.
    """
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import ConceptGraph

        global _SEEDING_GRAPH
        if graph is not None:
            pass  # Use provided graph
        else:
            if "_SEEDING_GRAPH" not in globals() or _SEEDING_GRAPH is None:
                _SEEDING_GRAPH = ConceptGraph(max_nodes=50000)
            graph = _SEEDING_GRAPH

        seeded = 0
        errors = 0

        for assoc in associations:
            try:
                assoc_type = assoc.get("type", "")

                if assoc_type == "domain_concept":
                    # Domain -> Concept edge
                    domain_key = f"domain:{assoc['domain']}"
                    concept_key = f"concept:{assoc['concept']}"

                    graph.upsert_node(domain_key, {
                        "lex": [assoc["domain"]],
                        "type": "domain",
                        "description": f"Knowledge domain: {assoc['domain']}",
                    })
                    graph.upsert_node(concept_key, {
                        "lex": [assoc["concept"]],
                        "type": "concept",
                        "domain": assoc["domain"],
                    })
                    graph.link(domain_key, concept_key, rel="semantic", weight=assoc["strength"])
                    seeded += 1

                elif assoc_type == "domain_category":
                    domain_key = f"domain:{assoc['domain']}"
                    category_key = f"category:{assoc['domain']}.{assoc['concept']}"

                    graph.upsert_node(category_key, {
                        "lex": [assoc["concept"]],
                        "type": "category",
                        "domain": assoc["domain"],
                    })
                    graph.link(domain_key, category_key, rel="semantic", weight=assoc["strength"])
                    seeded += 1

                elif assoc_type == "category_concept":
                    category_key = f"category:{assoc['domain']}.{assoc['parent']}"
                    concept_key = f"concept:{assoc['concept']}"

                    graph.upsert_node(concept_key, {
                        "lex": [assoc["concept"]],
                        "type": "concept",
                        "domain": assoc["domain"],
                        "category": assoc["parent"],
                    })
                    graph.link(category_key, concept_key, rel="semantic", weight=assoc["strength"])
                    seeded += 1

                elif assoc_type == "concept_affect":
                    concept_key = f"concept:{assoc['concept']}"
                    affect_key = f"affect:{assoc['affect']}"

                    graph.upsert_node(affect_key, {
                        "lex": [assoc["affect"]],
                        "type": "affect",
                        "affect": [assoc["affect"]],
                    })
                    graph.link(concept_key, affect_key, rel="evokes", weight=assoc["strength"])
                    seeded += 1

                elif assoc_type == "domain_link":
                    from_key = f"domain:{assoc['from_domain']}"
                    to_key = f"domain:{assoc['to_domain']}"
                    graph.link(from_key, to_key, rel="semantic", weight=assoc["strength"])
                    seeded += 1

                elif assoc_type == "meta_concept":
                    meta_key = f"meta:{assoc['meta_domain']}"
                    concept_key = f"concept:{assoc['concept']}"

                    graph.upsert_node(meta_key, {
                        "lex": [assoc["meta_domain"]],
                        "type": "meta_skill",
                    })
                    graph.upsert_node(concept_key, {
                        "lex": [assoc["concept"]],
                        "type": "concept",
                    })
                    graph.link(meta_key, concept_key, rel="semantic", weight=assoc["strength"])
                    seeded += 1

                elif assoc_type == "meta_affect":
                    meta_key = f"meta:{assoc['meta_domain']}"
                    affect_key = f"affect:{assoc['affect']}"

                    graph.upsert_node(affect_key, {
                        "lex": [assoc["affect"]],
                        "type": "affect",
                    })
                    graph.link(meta_key, affect_key, rel="evokes", weight=assoc["strength"])
                    seeded += 1

                elif assoc_type == "cross_domain":
                    # Parse "domain.concept" format
                    from_parts = assoc["from"].split(".")
                    to_parts = assoc["to"].split(".")

                    if len(from_parts) >= 2:
                        from_key = f"concept:{from_parts[1]}"
                    else:
                        from_key = f"domain:{from_parts[0]}"

                    if len(to_parts) >= 2:
                        to_key = f"concept:{to_parts[1]}"
                    else:
                        to_key = f"domain:{to_parts[0]}"

                    graph.link(from_key, to_key, rel=assoc["relation"], weight=assoc["strength"])
                    seeded += 1

            except Exception as e:
                errors += 1
                if errors < 5:
                    print(f"[KnowledgeSeeder] Domain seed error: {e}")

        return {
            "success": True,
            "seeded": seeded,
            "errors": errors,
        }

    except ImportError as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════════════════
# ASSOCIATION CORTEX SEEDING
# ═══════════════════════════════════════════════════════════════════════════════════════════

def seed_association_cortex(associations: List[Dict[str, Any]],
                            source: str = "color_psychology",
                            graph = None) -> Dict[str, Any]:
    """
    Seed the Association Cortex with color-trait associations.

    Creates edges like:
    - purple --evokes--> creative (strength=0.7)
    - red --evokes--> passionate (strength=0.8)

    Args:
        associations: List of association dicts to seed
        source: Source identifier
        graph: OPTIONAL external ConceptGraph to seed into. If None, uses internal.
    """
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import ConceptGraph

        # Use external graph if provided, otherwise create/use internal
        global _SEEDING_GRAPH
        if graph is not None:
            # IMPORTANT: Use the passed graph (e.g., AssociationCortexFairy._graph)
            pass  # Use the provided graph directly
        else:
            if "_SEEDING_GRAPH" not in globals() or _SEEDING_GRAPH is None:
                _SEEDING_GRAPH = ConceptGraph(max_nodes=50000)
            graph = _SEEDING_GRAPH
        seeded = 0
        errors = 0

        for assoc in associations:
            try:
                if source == "color_psychology":
                    # Color -> Trait edge
                    color = assoc["color"]
                    trait = assoc["trait"]
                    strength = assoc["strength"]
                    is_positive = assoc.get("positive", True)

                    # Create color node
                    color_key = f"color:{color}"
                    graph.upsert_node(color_key, {
                        "lex": [color],
                        "vision": [assoc.get("color_hex", "")],
                        "type": "color",
                    })

                    # Create trait node
                    trait_key = f"trait:{trait}"
                    graph.upsert_node(trait_key, {
                        "lex": [trait],
                        "affect": {"valence": 0.5 if is_positive else -0.3},
                        "type": "trait",
                    })

                    # Link color -> trait
                    graph.link(
                        color_key, trait_key,
                        rel=ConceptGraph.REL_SEMANTIC,
                        weight=strength,
                        context={"source": "color_psychology_db", "positive": is_positive}
                    )
                    seeded += 1

                elif source == "emotion_colors":
                    # Emotion -> Color edge
                    emotion = assoc["emotion"]
                    color_rgb = assoc.get("color_rgb", (128, 128, 128))
                    color_hex = assoc.get("color_hex", "#808080")
                    strength = assoc["strength"]

                    # Create emotion node
                    emotion_key = f"emotion:{emotion}"
                    graph.upsert_node(emotion_key, {
                        "lex": [emotion],
                        "type": "emotion",
                    })

                    # Create color node (using hex as identifier)
                    color_key = f"color_rgb:{color_hex}"
                    graph.upsert_node(color_key, {
                        "vision": [color_hex],
                        "rgb": color_rgb,
                        "type": "color",
                    })

                    # Link emotion -> color
                    graph.link(
                        emotion_key, color_key,
                        rel=ConceptGraph.REL_MODAL_BRIDGE,
                        weight=strength,
                        context={"source": "emotion_colors_db", "samples": assoc.get("sample_count", 1)}
                    )
                    seeded += 1

            except Exception as e:
                errors += 1
                if errors < 5:
                    print(f"[KnowledgeSeeder] Error seeding: {e}")

        return {
            "success": True,
            "seeded": seeded,
            "errors": errors,
            "source": source,
            "graph_stats": graph.stats(),
        }

    except ImportError as e:
        print(f"[KnowledgeSeeder] AssociationCortex not available: {e}")
        return {"success": False, "error": str(e)}


def seed_srm_relations(associations: List[Dict[str, Any]], 
                       source: str = "color_psychology") -> Dict[str, Any]:
    """
    Seed SRM (Semantic Relation Memory) with color associations as triples.
    
    Creates triples like:
    - (purple, evokes, creativity, strength=0.7)
    """
    try:
        from fairies.P30_Cognition.affect.frequency_field_77 import emit_srm
        seeded = 0
        errors = 0
        
        for assoc in associations:
            try:
                if source == "color_psychology":
                    color = assoc["color"]
                    trait = assoc["trait"]
                    strength = assoc["strength"]
                    
                    emit_srm(
                        subject=color,
                        predicate="evokes",
                        obj=trait,
                        strength=strength,
                        tags=["color", "psychology", "seed"],
                        context={
                            "source": "color_psychology_db",
                            "positive": assoc.get("positive", True),
                        }
                    )
                    seeded += 1
                    
            except Exception as e:
                errors += 1
                if errors < 5:
                    print(f"[KnowledgeSeeder] SRM error: {e}")
        
        return {
            "success": True,
            "seeded": seeded,
            "errors": errors,
        }
        
    except ImportError as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════════════════
# MAIN SEEDING FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════════════════

def seed_all_knowledge(verbose: bool = True, graph = None) -> Dict[str, Any]:
    """
    Load all knowledge bases and seed the Association Cortex.

    Args:
        verbose: Print progress messages
        graph: OPTIONAL external ConceptGraph to seed into (e.g., AssociationCortexFairy._graph)

    Returns summary of seeding results.
    """
    results = {
        "timestamp": time.time(),
        "sources": {},
        "total_associations": 0,
        "total_seeded": 0,
    }

    # 1. Color Psychology Database
    if verbose:
        print("[KnowledgeSeeder] Loading Color Psychology Database...")
    color_psych_data = load_color_psychology_db()
    if color_psych_data:
        associations = extract_color_trait_associations(color_psych_data)
        results["sources"]["color_psychology"] = {
            "associations_extracted": len(associations),
            "unique_colors": len(set(a["color"] for a in associations)),
            "unique_traits": len(set(a["trait"] for a in associations)),
        }
        results["total_associations"] += len(associations)

        if verbose:
            print(f"[KnowledgeSeeder]   Extracted {len(associations)} color-trait associations")

        # Seed to Association Cortex (use external graph if provided)
        seed_result = seed_association_cortex(associations, source="color_psychology", graph=graph)
        results["sources"]["color_psychology"]["cortex_result"] = seed_result
        results["total_seeded"] += seed_result.get("seeded", 0)

        # Seed to SRM
        srm_result = seed_srm_relations(associations, source="color_psychology")
        results["sources"]["color_psychology"]["srm_result"] = srm_result

    # 2. Emotion-Colors Dataset
    if verbose:
        print("[KnowledgeSeeder] Loading Emotion-Colors Dataset...")
    emotion_colors_data = load_emotion_colors_db()
    if emotion_colors_data:
        if verbose:
            print(f"[KnowledgeSeeder]   Loaded {len(emotion_colors_data)} raw entries")

        associations = extract_emotion_color_associations(emotion_colors_data)
        results["sources"]["emotion_colors"] = {
            "raw_entries": len(emotion_colors_data),
            "associations_extracted": len(associations),
            "unique_emotions": len(set(a["emotion"] for a in associations)),
        }
        results["total_associations"] += len(associations)

        if verbose:
            print(f"[KnowledgeSeeder]   Extracted {len(associations)} unique emotion-color mappings")

        # Seed to Association Cortex (use external graph if provided)
        seed_result = seed_association_cortex(associations, source="emotion_colors", graph=graph)
        results["sources"]["emotion_colors"]["cortex_result"] = seed_result
        results["total_seeded"] += seed_result.get("seeded", 0)

    # 3. Domain Concepts (coding, reading, art, science, etc.)
    if verbose:
        print("[KnowledgeSeeder] Loading Domain Concepts...")
    domain_data = load_domain_concepts_db()
    if domain_data:
        associations = extract_domain_concept_associations(domain_data)
        domains = domain_data.get("domains", {})
        results["sources"]["domain_concepts"] = {
            "associations_extracted": len(associations),
            "domains": list(domains.keys()),
            "meta_concepts": list(domain_data.get("meta_concepts", {}).keys()),
        }
        results["total_associations"] += len(associations)

        if verbose:
            print(f"[KnowledgeSeeder]   Extracted {len(associations)} domain concept associations")
            print(f"[KnowledgeSeeder]   Domains: {', '.join(domains.keys())}")

        # Seed to Association Cortex
        seed_result = seed_domain_concepts(associations, graph=graph)
        results["sources"]["domain_concepts"]["cortex_result"] = seed_result
        results["total_seeded"] += seed_result.get("seeded", 0)

        if verbose:
            print(f"[KnowledgeSeeder]   Seeded {seed_result.get('seeded', 0)} domain concepts")

    # Get final graph stats
    if graph is not None:
        results["final_graph_stats"] = graph.stats()
    elif "_SEEDING_GRAPH" in globals() and _SEEDING_GRAPH is not None:
        results["final_graph_stats"] = _SEEDING_GRAPH.stats()

    if verbose:
        print(f"[KnowledgeSeeder] COMPLETE: {results['total_seeded']} associations seeded")
        if "final_graph_stats" in results:
            stats = results["final_graph_stats"]
            print(f"[KnowledgeSeeder] Graph: {stats['node_count']} nodes, {stats['edge_count']} edges")

    return results


def get_seeded_graph():
    """Get the seeded ConceptGraph for external use."""
    global _SEEDING_GRAPH
    if "_SEEDING_GRAPH" not in globals() or _SEEDING_GRAPH is None:
        return None
    return _SEEDING_GRAPH


def get_color_associations(color: str) -> List[Dict[str, Any]]:
    """
    Query associations for a specific color.
    
    Args:
        color: Color name (e.g., "purple", "cyan")
        
    Returns:
        List of trait associations for that color
    """
    data = load_color_psychology_db()
    if not data:
        return []
    
    associations = extract_color_trait_associations(data)
    return [a for a in associations if a["color"] == color.lower()]


def get_trait_colors(trait: str) -> List[Dict[str, Any]]:
    """
    Query which colors evoke a specific trait.
    
    Args:
        trait: Trait name (e.g., "creative", "calm")
        
    Returns:
        List of color associations for that trait
    """
    data = load_color_psychology_db()
    if not data:
        return []
    
    associations = extract_color_trait_associations(data)
    trait_lower = trait.lower()
    return [a for a in associations if trait_lower in a["trait"]]


# ═══════════════════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    
    print("=" * 70)
    print("KNOWLEDGE SEEDER - Bootstrap Association Cortex")
    print("=" * 70)
    
    # Test loading
    print("\n[1] Testing data load...")
    color_data = load_color_psychology_db()
    print(f"    Color Psychology: {len(color_data)} entries")
    
    emotion_data = load_emotion_colors_db()
    print(f"    Emotion-Colors: {len(emotion_data)} entries")
    
    # Extract associations
    print("\n[2] Extracting associations...")
    color_associations = extract_color_trait_associations(color_data)
    print(f"    Color-Trait: {len(color_associations)} associations")
    
    # Show sample
    print("\n[3] Sample associations for 'purple':")
    purple_assocs = get_color_associations("purple")
    for a in purple_assocs[:10]:
        sign = "+" if a["positive"] else "-"
        print(f"    [{sign}] purple --> {a['trait']} (strength: {a['strength']:.2f})")
    
    # Show sample for 'creative'
    print("\n[4] Colors that evoke 'creative':")
    creative_colors = get_trait_colors("creative")
    for a in creative_colors:
        print(f"    {a['color']} --> creative (strength: {a['strength']:.2f})")
    
    print("\n" + "=" * 70)
    print("Ready to seed. Run seed_all_knowledge() to populate cortex.")
    print("=" * 70)
