# Memory Flow Tracer - Diagnose memory connectivity issues
# Shows what's connected and what's broken in the memory pipeline
#
# Run: python memory_tracer.py

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

# Add project root
# FIX 2026-05-15 (Nous + Ace): added 4th .parent — file at depth 4, 3-deep walked to fairies/ not akashic_v2/
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ══════════════════════════════════════════════════════════════════════════════
# MEMORY SOURCES TO TRACE
# ══════════════════════════════════════════════════════════════════════════════

MEMORY_SOURCES = {
    "SRM_Intake": {
        "path": PROJECT_ROOT / "SRM_Intake",
        "type": "disk",
        "description": "JSON memory files from fairies",
        "should_connect_to": ["SRMRecallFairy", "AssociationCortex"],
    },
    "AssociationCortex": {
        "type": "memory",
        "description": "In-memory concept graph for multi-modal binding",
        "should_load_from": ["SRM_Intake"],
        "should_persist_to": ["concept_graph.json"],
    },
    "ConceptGraph": {
        "type": "memory", 
        "description": "The actual graph structure inside AssociationCortex",
        "nodes": "ConceptNode instances",
        "edges": "Co-activation relationships",
    },
    "FairyExperiences": {
        "type": "memory",
        "description": "Each fairy's deque of recent experiences",
        "size": "maxlen=1000",
        "persisted": False,
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# TRACE SRM_INTAKE
# ══════════════════════════════════════════════════════════════════════════════

def trace_srm_intake():
    """Trace what's in SRM_Intake."""
    print("\n" + "═" * 60)
    print(" SRM_INTAKE TRACE")
    print("═" * 60)
    
    srm_path = PROJECT_ROOT / "SRM_Intake"
    
    if not srm_path.exists():
        print("[X] SRM_Intake directory not found!")
        return {}
    
    stats = {
        "total_files": 0,
        "total_size_kb": 0,
        "by_day": {},
        "by_type": {},
        "by_fairy": {},
    }
    
    for day_dir in sorted(srm_path.iterdir()):
        if not day_dir.is_dir():
            continue
        
        day_name = day_dir.name
        stats["by_day"][day_name] = 0
        
        for file in day_dir.glob("*.json"):
            stats["total_files"] += 1
            stats["total_size_kb"] += file.stat().st_size / 1024
            stats["by_day"][day_name] += 1
            
            # Parse filename: fairy.type-hash.json
            name = file.stem
            parts = name.split(".")
            if len(parts) >= 2:
                fairy = parts[0]
                rest = ".".join(parts[1:])
                type_part = rest.split("-")[0] if "-" in rest else rest
                
                stats["by_fairy"][fairy] = stats["by_fairy"].get(fairy, 0) + 1
                stats["by_type"][type_part] = stats["by_type"].get(type_part, 0) + 1
    
    print(f"\n Total files: {stats['total_files']}")
    print(f" Total size: {stats['total_size_kb']:.1f} KB")
    
    print(f"\n By Day:")
    for day, count in sorted(stats["by_day"].items())[-5:]:  # Last 5 days
        print(f"   {day}: {count} files")
    
    print(f"\n By Fairy:")
    for fairy, count in sorted(stats["by_fairy"].items(), key=lambda x: -x[1])[:10]:
        print(f"   {fairy}: {count} files")
    
    print(f"\n By Type:")
    for t, count in sorted(stats["by_type"].items(), key=lambda x: -x[1])[:15]:
        print(f"   {t}: {count} files")
    
    return stats


# ══════════════════════════════════════════════════════════════════════════════
# TRACE ASSOCIATION CORTEX
# ══════════════════════════════════════════════════════════════════════════════

def trace_association_cortex():
    """Check AssociationCortex state."""
    print("\n" + "═" * 60)
    print("[BRAIN] ASSOCIATION CORTEX TRACE")
    print("═" * 60)
    
    issues = []
    
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import (
            AssociationCortexFairy, ConceptGraph
        )
        print("[OK] AssociationCortexFairy importable")
        
        # Check if it has persistence
        import inspect
        source = inspect.getsource(AssociationCortexFairy)
        
        has_save = "save" in source.lower() and "disk" in source.lower()
        has_load = "load" in source.lower() and "disk" in source.lower()
        has_persist = "persist" in source.lower()
        
        print(f"\n Persistence check:")
        print(f"   Has save_to_disk: {'[OK]' if has_save else '[X] MISSING'}")
        print(f"   Has load_from_disk: {'[OK]' if has_load else '[X] MISSING'}")
        print(f"   Has persist method: {'[OK]' if has_persist else '[X] MISSING'}")
        
        if not has_save:
            issues.append("AssociationCortex has no save_to_disk method")
        if not has_load:
            issues.append("AssociationCortex has no load_from_disk method")
        
        # Check ConceptGraph
        graph_source = inspect.getsource(ConceptGraph)
        graph_has_persist = "save" in graph_source.lower() or "persist" in graph_source.lower()
        
        print(f"\n ConceptGraph check:")
        print(f"   Has persistence: {'[OK]' if graph_has_persist else '[X] IN-MEMORY ONLY'}")
        
        if not graph_has_persist:
            issues.append("ConceptGraph is in-memory only - loses all data on restart")
        
        # Check if it loads from SRM
        loads_srm = "SRM" in source or "srm_intake" in source.lower()
        print(f"   Loads from SRM: {'[OK]' if loads_srm else '[X] NO SRM INTEGRATION'}")
        
        if not loads_srm:
            issues.append("AssociationCortex doesn't load from SRM_Intake")
        
    except ImportError as e:
        print(f"[X] Cannot import AssociationCortexFairy: {e}")
        issues.append(f"Import error: {e}")
    except Exception as e:
        print(f"[WARN] Error checking AssociationCortex: {e}")
    
    return issues


# ══════════════════════════════════════════════════════════════════════════════
# TRACE SRM RECALL
# ══════════════════════════════════════════════════════════════════════════════

def trace_srm_recall():
    """Test SRMRecallFairy actually works."""
    print("\n" + "═" * 60)
    print(" SRM RECALL TRACE")
    print("═" * 60)
    
    try:
        from fairies.P10_Memory.SRMRecallFairy.fairy import SRMRecallFairy
        print("[OK] SRMRecallFairy importable")
        
        # Create instance and test query
        fairy = SRMRecallFairy()
        print("[OK] SRMRecallFairy instantiated")
        
        # Try a recall
        test_query = "thinking feeling consciousness"
        print(f"\n Test query: '{test_query}'")
        
        # Check if it has the search methods
        has_unified = hasattr(fairy, 'unified_search')
        has_recall = hasattr(fairy, 'handle_recall_query')
        
        print(f"   Has unified_search: {'[OK]' if has_unified else '[X]'}")
        print(f"   Has handle_recall_query: {'[OK]' if has_recall else '[X]'}")
        
        if has_unified:
            results = fairy.unified_search(test_query, horizon_days=1, max_results=5)
            print(f"\n Unified search results: {len(results.get('results', []))} matches")
            
            for i, r in enumerate(results.get('results', [])[:3]):
                what = r.get('what', r.get('content', ''))[:60]
                print(f"   {i+1}. {what}...")
        
        return True
        
    except ImportError as e:
        print(f"[X] Cannot import SRMRecallFairy: {e}")
        return False
    except Exception as e:
        print(f"[WARN] Error testing SRMRecallFairy: {e}")
        import traceback
        traceback.print_exc()
        return False


# ══════════════════════════════════════════════════════════════════════════════
# TRACE COGNITIVE CHAIN
# ══════════════════════════════════════════════════════════════════════════════

def trace_cognitive_chain():
    """Show what the cognitive chain tries to do."""
    print("\n" + "═" * 60)
    print(" COGNITIVE CHAIN TRACE")
    print("═" * 60)
    
    print("""
The cognitive chain in ClaudeFairy._run_cognitive_chain() does:

1. LogicFairy.analyze()
   └─ Returns: coherence score, hints, concepts
   └─ Status: ✅ Works (stateless analysis)

2. AssociationCortex.query()  
   └─ Should return: related concepts from graph
   └─ Status: ❌ ALWAYS EMPTY (no persistence, no SRM load)
   
3. IrrationalLogicFairy.find_paradoxes()
   └─ Returns: paradoxes, insights from content
   └─ Status: ✅ Works (stateless analysis)

4. Recent collisions (from consciousness loop)
   └─ Returns: last N collision events
   └─ Status: ✅ Works (in-memory deque)

5. Cognitive synthesis
   └─ Combines all above into response hints
   └─ Status: ⚠ Degraded (missing association data)
""")
    
    print(" TO FIX AssociationCortex:")
    print("""
   1. Add save_graph() / load_graph() to ConceptGraph
   2. On boot, scan SRM_Intake and build graph from JSON
   3. Periodically persist graph to disk
   4. OR: Query SRM directly instead of maintaining separate graph
""")


# ══════════════════════════════════════════════════════════════════════════════
# RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════

def generate_recommendations(srm_stats, assoc_issues):
    """Generate fix recommendations."""
    print("\n" + "═" * 60)
    print("[IDEA] RECOMMENDATIONS")
    print("═" * 60)
    
    recs = []
    
    # SRM is working but underutilized
    if srm_stats.get("total_files", 0) > 0:
        recs.append({
            "priority": "HIGH",
            "issue": "AssociationCortex doesn't use SRM data",
            "fix": "Add SRM loading on boot - scan JSON files, extract concepts, build graph",
        })
    
    # AssociationCortex issues
    for issue in assoc_issues:
        if "in-memory only" in issue.lower():
            recs.append({
                "priority": "HIGH", 
                "issue": "ConceptGraph loses all data on restart",
                "fix": "Add JSON persistence - save/load graph to concept_graph.json",
            })
        if "doesn't load" in issue.lower():
            recs.append({
                "priority": "HIGH",
                "issue": "No SRM → AssociationCortex integration",
                "fix": "On boot, parse SRM JSON files and upsert concepts into graph",
            })
    
    # Content diversity
    fairy_types = srm_stats.get("by_fairy", {})
    if "claudefairy" in fairy_types and fairy_types.get("gutenberg", 0) == 0:
        recs.append({
            "priority": "MEDIUM",
            "issue": "No external creative content in memory",
            "fix": "Ingest Gutenberg texts to add vocabulary/patterns diversity",
        })
    
    for i, rec in enumerate(recs, 1):
        print(f"\n{i}. [{rec['priority']}] {rec['issue']}")
        print(f"   → {rec['fix']}")
    
    return recs


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(" MEMORY FLOW TRACER")
    print("=" * 60)
    print(f"Project: {PROJECT_ROOT}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run traces
    srm_stats = trace_srm_intake()
    assoc_issues = trace_association_cortex()
    trace_srm_recall()
    trace_cognitive_chain()
    
    # Recommendations
    generate_recommendations(srm_stats, assoc_issues)
    
    print("\n" + "═" * 60)
    print("[OK] TRACE COMPLETE")
    print("═" * 60)


if __name__ == "__main__":
    main()
