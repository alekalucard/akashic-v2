# Memory Hydration - Populate AssociationCortex from SRM on boot
#
# Problem: AssociationCortex starts empty on each boot
# Solution: Load recent memories from SRM_Intake into the concept graph
#
# This should be called early in boot, before fairies start thinking

from __future__ import annotations

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict

# Add project root to path
# FIX 2026-05-15 (Nous + Ace): added 4th .parent — file at depth 4, 3-deep walked to fairies/ not akashic_v2/
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def hydrate_association_cortex(
    days_back: int = 3,
    max_memories: int = 500,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Load memories from SRM_Intake into AssociationCortex.
    
    This populates the concept graph with prior knowledge so fairies
    can make associations on boot instead of starting blank.
    
    Args:
        days_back: How many days of memories to load
        max_memories: Maximum memories to process
        verbose: Print progress
    
    Returns:
        Stats about what was loaded
    """
    
    stats = {
        "memories_loaded": 0,
        "concepts_created": 0,
        "links_created": 0,
        "errors": [],
        "by_kind": defaultdict(int),
    }
    
    # 1. Get AssociationCortex
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import (
            get_association_cortex_fairy
        )
        cortex = get_association_cortex_fairy()
        graph = cortex.graph
        
        if verbose:
            print(f"[Hydration] Got AssociationCortex, current nodes: {len(graph.nodes)}")
    except Exception as e:
        stats["errors"].append(f"Failed to get AssociationCortex: {e}")
        return stats
    
    # 2. Find SRM_Intake memories
    srm_root = PROJECT_ROOT / "SRM_Intake"
    if not srm_root.exists():
        stats["errors"].append(f"SRM_Intake not found at {srm_root}")
        return stats
    
    # Get recent date folders
    date_folders = sorted(srm_root.glob("2025-*"))[-days_back:]
    
    all_files = []
    for folder in date_folders:
        all_files.extend(folder.glob("*.json"))
    
    # Sort by modification time, newest first
    all_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    all_files = all_files[:max_memories]
    
    if verbose:
        print(f"[Hydration] Found {len(all_files)} memories to load")
    
    # 3. Process each memory
    for f in all_files:
        try:
            with open(f, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
            
            # Extract key fields
            domain = data.get("domain", "unknown")
            kind = data.get("kind", "unknown")
            source = data.get("source", "unknown")
            content = data.get("content", data.get("what", ""))
            
            if not content:
                continue
            
            # Create concept node for this memory
            concept_key = f"{kind}:{hash(content) % 100000}"
            
            # Extract features
            features = {
                "lex": _extract_keywords(str(content)),
                "domain": domain,
                "kind": kind,
                "source": source,
                "affect": data.get("feeling", "neutral"),
            }
            
            # Add to graph
            node = graph.upsert_node(concept_key, features)
            stats["concepts_created"] += 1
            stats["by_kind"][kind] += 1
            
            # Link to related concepts (by domain, source)
            domain_key = f"domain:{domain}"
            source_key = f"source:{source}"
            
            graph.upsert_node(domain_key, {"lex": [domain], "type": "domain"})
            graph.upsert_node(source_key, {"lex": [source], "type": "source"})
            
            graph.link(concept_key, domain_key, "semantic", 0.3)
            graph.link(concept_key, source_key, "semantic", 0.2)
            stats["links_created"] += 2
            
            # Link keywords to concept
            for keyword in features["lex"][:5]:  # Top 5 keywords
                kw_key = f"keyword:{keyword}"
                graph.upsert_node(kw_key, {"lex": [keyword], "type": "keyword"})
                graph.link(concept_key, kw_key, "semantic", 0.25)
                stats["links_created"] += 1
            
            stats["memories_loaded"] += 1
            
        except Exception as e:
            stats["errors"].append(f"{f.name}: {e}")
    
    if verbose:
        print(f"[Hydration] Complete!")
        print(f"   Memories loaded: {stats['memories_loaded']}")
        print(f"   Concepts created: {stats['concepts_created']}")
        print(f"   Links created: {stats['links_created']}")
        print(f"   Graph now has: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
        if stats["errors"]:
            print(f"   Errors: {len(stats['errors'])}")
    
    return stats


def _extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """Extract meaningful keywords from text."""
    
    # Simple keyword extraction - split and filter
    words = text.lower().split()
    
    # Remove stop words and short words
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "into", "through",
        "and", "but", "or", "if", "then", "than", "this", "that", "these",
        "those", "i", "you", "he", "she", "it", "we", "they", "my", "your",
        "his", "her", "its", "our", "their", "what", "which", "who", "whom",
    }
    
    keywords = []
    for word in words:
        # Clean word
        word = ''.join(c for c in word if c.isalnum())
        
        if len(word) > 3 and word not in stop_words:
            keywords.append(word)
    
    # Dedupe while preserving order
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)
    
    return unique[:max_keywords]


def hydrate_fairy_memories(fairy_name: str, days_back: int = 3) -> Dict[str, Any]:
    """
    Hydrate a specific fairy's local accumulator from SRM.
    
    This loads memories created BY this fairy back into their
    experiences/reflections deques.
    """
    
    stats = {
        "loaded": 0,
        "experiences": 0,
        "reflections": 0,
        "errors": [],
    }
    
    # Get fairy
    fairy = None
    try:
        if fairy_name == "ClaudeFairy":
            from fairies.P60_Executive.system_managment.claude_fairy import get_claude_fairy
            fairy = get_claude_fairy()
        elif fairy_name == "SourpatchesFairy":
            from fairies.P60_Executive.system_managment.sourpatches_fairy import get_sourpatches_fairy
            fairy = get_sourpatches_fairy()
    except Exception as e:
        stats["errors"].append(f"Failed to get {fairy_name}: {e}")
        return stats
    
    if fairy is None:
        stats["errors"].append(f"Fairy {fairy_name} not found")
        return stats
    
    # Find memories from this fairy
    srm_root = PROJECT_ROOT / "SRM_Intake"
    date_folders = sorted(srm_root.glob("2025-*"))[-days_back:]
    
    for folder in date_folders:
        # Pattern: claudefairy.* or sourpatchesfairy.*
        pattern = f"{fairy_name.lower()}.*"
        for f in folder.glob(pattern + "*.json"):
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                
                kind = data.get("kind", "")
                content = data.get("content", data.get("what", ""))
                
                # Add to appropriate accumulator
                if hasattr(fairy, "experiences") and "experience" in kind:
                    fairy.experiences.append({
                        "type": kind,
                        "content": content,
                        "ts": data.get("ts", time.time()),
                        "hydrated": True,
                    })
                    stats["experiences"] += 1
                
                elif hasattr(fairy, "reflections") and "insight" in kind:
                    fairy.reflections.append({
                        "type": kind,
                        "content": content,
                        "ts": data.get("ts", time.time()),
                        "hydrated": True,
                    })
                    stats["reflections"] += 1
                
                stats["loaded"] += 1
                
            except Exception as e:
                stats["errors"].append(f"{f.name}: {e}")
    
    return stats


# ══════════════════════════════════════════════════════════════════════════════
# BOOT INTEGRATION
# ══════════════════════════════════════════════════════════════════════════════

def full_hydration(verbose: bool = True) -> Dict[str, Any]:
    """
    Run full memory hydration on boot.
    
    Call this early in the boot sequence before fairies start thinking.
    """
    
    results = {}
    
    if verbose:
        print("=" * 50)
        print(" MEMORY HYDRATION")
        print("=" * 50)
    
    # 1. Hydrate AssociationCortex
    if verbose:
        print("\n1. Hydrating AssociationCortex from SRM...")
    results["association_cortex"] = hydrate_association_cortex(
        days_back=3,
        max_memories=300,
        verbose=verbose
    )
    
    # 2. Hydrate ClaudeFairy
    if verbose:
        print("\n2. Hydrating ClaudeFairy memories...")
    results["claude_fairy"] = hydrate_fairy_memories("ClaudeFairy", days_back=2)
    if verbose:
        print(f"   Loaded: {results['claude_fairy']['loaded']}")
    
    # 3. Hydrate SourpatchesFairy
    if verbose:
        print("\n3. Hydrating SourpatchesFairy memories...")
    results["sourpatches_fairy"] = hydrate_fairy_memories("SourpatchesFairy", days_back=2)
    if verbose:
        print(f"   Loaded: {results['sourpatches_fairy']['loaded']}")
    
    if verbose:
        print("\n" + "=" * 50)
        print(" Hydration complete!")
        print("=" * 50)
    
    return results


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    results = full_hydration(verbose=True)
    print(f"\nResults: {json.dumps(results, indent=2, default=str)}")
