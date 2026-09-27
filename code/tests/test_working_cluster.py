"""
Test: Working Cluster Pattern (Russian Doll)

The hypothesis:
- Association Cortex can recall a cluster from helix
- Hold it in working memory as a mutable bubble
- Grow new concepts INSIDE the cluster
- Commit new cards back to helix (originals stay immutable)

Author: Nous + Ace
"""

import sys
import time
from pathlib import Path

# Setup paths
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "fairies"))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))

print("=" * 60)
print("WORKING CLUSTER TEST (Russian Doll Pattern)")
print("=" * 60)


# =============================================================================
# STEP 1: Initialize AssociationCortexFairy
# =============================================================================

print("\n[1] Initializing AssociationCortexFairy...")

try:
    from fairies.P30_Cognition.AssociationCortexFairy.fairy import (
        AssociationCortexFairy, WorkingCluster
    )

    cortex = AssociationCortexFairy()
    cortex.boot()

    status = cortex.status()
    print(f"    Graph: {status.get('node_count', 0)} nodes, {status.get('edge_count', 0)} edges")
    print(f"    Helix enabled: {status.get('helix', {}).get('enabled', False)}")
    print(f"    Cards mapped: {status.get('helix', {}).get('cards_mapped', 0)}")

    CORTEX_READY = status.get('loaded', False)

except Exception as e:
    print(f"    ERROR initializing cortex: {e}")
    import traceback
    traceback.print_exc()
    CORTEX_READY = False
    cortex = None


# =============================================================================
# STEP 2: Sync some concepts to helix first
# =============================================================================

if CORTEX_READY and cortex._helix_enabled:
    print("\n[2] Syncing test concepts to helix...")

    # Add some test concepts to the graph
    test_concepts = [
        ("consciousness", {"lex": ["awareness", "mind", "being"]}),
        ("memory", {"lex": ["recall", "storage", "remember"]}),
        ("thought", {"lex": ["thinking", "idea", "cognition"]}),
        ("feeling", {"lex": ["emotion", "affect", "sensation"]}),
        ("intention", {"lex": ["purpose", "goal", "drive"]}),
    ]

    for key, features in test_concepts:
        cortex.add_concept(key, features)
        cortex._sync_concept_to_helix(key)

    cortex._helix_coordinator.save()
    print(f"    Synced {len(test_concepts)} concepts to helix")
    print(f"    Cards in helix: {len(cortex._helix_coordinator._cards)}")
else:
    print("\n[2] Skipping helix sync (not enabled)")


# =============================================================================
# STEP 3: Test recall_cluster
# =============================================================================

recalled_cluster = None
if CORTEX_READY and cortex._helix_enabled:
    print("\n[3] Testing recall_cluster...")

    try:
        recalled_cluster = cortex.recall_cluster(
            concept_key="consciousness",
            radius=5.0,
            name="consciousness_bubble",
        )

        if recalled_cluster:
            print(f"    Cluster ID: {recalled_cluster.cluster_id}")
            print(f"    Name: {recalled_cluster.name}")
            print(f"    Anchor: {recalled_cluster.anchor_concept}")
            print(f"    Concepts: {len(recalled_cluster.concept_keys)}")
            print(f"    Concept list: {list(recalled_cluster.concept_keys)[:10]}...")
            print("    recall_cluster: OK")
        else:
            print("    ERROR: Failed to recall cluster")

    except Exception as e:
        print(f"    ERROR in recall_cluster: {e}")
        import traceback
        traceback.print_exc()
else:
    print("\n[3] Skipping recall_cluster (cortex not ready)")


# =============================================================================
# STEP 4: Test grow_in_cluster
# =============================================================================

if recalled_cluster:
    print("\n[4] Testing grow_in_cluster...")

    try:
        # Grow new concepts INSIDE the cluster
        new_concepts = [
            ("awareness_test", {"lex": ["aware", "present", "alert"]}),
            ("introspection_test", {"lex": ["self", "reflection", "inner"]}),
            ("metacognition_test", {"lex": ["thinking_about_thinking", "meta"]}),
        ]

        for key, features in new_concepts:
            success = cortex.grow_in_cluster(
                cluster_id=recalled_cluster.cluster_id,
                concept_key=key,
                features=features,
                link_to=["consciousness", "thought"],
            )
            print(f"    Grew '{key}': {success}")

        print(f"    Cluster growth count: {recalled_cluster.growth_count}")
        print(f"    New concepts tracked: {len(recalled_cluster.new_concepts)}")
        print(f"    New edges tracked: {len(recalled_cluster.new_edges)}")
        print("    grow_in_cluster: OK")

    except Exception as e:
        print(f"    ERROR in grow_in_cluster: {e}")
        import traceback
        traceback.print_exc()
else:
    print("\n[4] Skipping grow_in_cluster (no cluster recalled)")


# =============================================================================
# STEP 5: Test commit_cluster
# =============================================================================

committed = False
if recalled_cluster:
    print("\n[5] Testing commit_cluster...")

    try:
        result = cortex.commit_cluster(recalled_cluster.cluster_id)

        print(f"    Commit OK: {result.get('ok')}")
        print(f"    New cards created: {result.get('new_cards', 0)}")
        print(f"    New edges committed: {result.get('new_edges', 0)}")

        if result.get('ok'):
            print("    commit_cluster: OK")
            committed = True
        else:
            print(f"    ERROR: {result.get('error')}")

    except Exception as e:
        print(f"    ERROR in commit_cluster: {e}")
        import traceback
        traceback.print_exc()
else:
    print("\n[5] Skipping commit_cluster (no cluster to commit)")


# =============================================================================
# STEP 6: Verify immutability
# =============================================================================

immutability_ok = True
if committed and cortex._helix_enabled:
    print("\n[6] Verifying immutability (originals unchanged)...")

    try:
        # Check that original cards still exist and weren't modified
        original_card_id = cortex._concept_to_card.get("consciousness")
        if original_card_id:
            card = cortex._helix_coordinator._cards.get(original_card_id)
            if card:
                content = card.get('content', {})
                print(f"    Original 'consciousness' card: {content.get('key')}")
                print(f"    Features intact: {'lex' in content.get('features', {})}")

                # Check no 'test' in original concept features
                features = content.get('features', {})
                if 'awareness_test' in str(features):
                    print("    WARNING: Original card may have been modified!")
                    immutability_ok = False
                else:
                    print("    Original card: UNCHANGED (immutable)")
            else:
                print("    ERROR: Original card not found!")
                immutability_ok = False
        else:
            print("    ERROR: No card ID for 'consciousness'")
            immutability_ok = False

    except Exception as e:
        print(f"    ERROR verifying immutability: {e}")
        immutability_ok = False
else:
    print("\n[6] Skipping immutability check")


# =============================================================================
# STEP 7: Test list_working_clusters
# =============================================================================

if CORTEX_READY:
    print("\n[7] Testing list_working_clusters...")

    try:
        clusters = cortex.list_working_clusters()
        print(f"    Active clusters: {len(clusters)}")
        for c in clusters:
            print(f"      - {c.get('name')}: {c.get('concepts', 0)} concepts, {c.get('growth', 0)} growth")
        print("    list_working_clusters: OK")

    except Exception as e:
        print(f"    ERROR: {e}")


# =============================================================================
# STEP 8: Test release_cluster
# =============================================================================

if recalled_cluster:
    print("\n[8] Testing release_cluster...")

    try:
        released = cortex.release_cluster(recalled_cluster.cluster_id, commit=False)
        print(f"    Released: {released}")

        clusters_after = cortex.list_working_clusters()
        print(f"    Clusters after release: {len(clusters_after)}")
        print("    release_cluster: OK")

    except Exception as e:
        print(f"    ERROR: {e}")


# =============================================================================
# SUMMARY
# =============================================================================

print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)

results = {
    "cortex_loaded": CORTEX_READY,
    "helix_enabled": CORTEX_READY and cortex._helix_enabled if cortex else False,
    "cluster_recalled": recalled_cluster is not None,
    "cluster_grown": recalled_cluster and recalled_cluster.growth_count > 0 if recalled_cluster else False,
    "cluster_committed": committed,
    "immutability": immutability_ok,
}

for test, passed in results.items():
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {test}")

all_passed = all(results.values())
print(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")

if all_passed:
    print("""
CONCLUSION:
The Russian Doll Working Cluster pattern works:
1. Association Cortex can recall clusters from helix dimension
2. Clusters are held in working memory as mutable bubbles
3. New concepts can grow INSIDE the cluster
4. Commit creates NEW cards (originals stay immutable)
5. The cortex can now "think inside" semantic bubbles!

USAGE:
    # Recall a cluster
    cluster = cortex.recall_cluster("consciousness", radius=5.0)

    # Grow inside it
    cortex.grow_in_cluster(cluster.cluster_id, "new_idea", {"lex": ["fresh"]})

    # Commit when done
    cortex.commit_cluster(cluster.cluster_id)

    # Or via postal:
    fabric.publish("cortex.cluster.recall", {"concept": "consciousness"})
    fabric.publish("cortex.cluster.grow", {"cluster_id": "...", "concept": "idea"})
    fabric.publish("cortex.cluster.commit", {"cluster_id": "..."})
""")
