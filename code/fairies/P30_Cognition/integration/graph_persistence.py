# AssociationCortex Persistence - Load concepts from SRM, persist graph
# This patches the missing persistence in AssociationCortexFairy
#
# ══════════════════════════════════════════════════════════════════════════════
# AKASHIC ARCHITECTURE NOTICE
# ══════════════════════════════════════════════════════════════════════════════
# This is INFRASTRUCTURE code - it supports AssociationCortexFairy and
# ManifoldConstrainedCortexFairy which are Organ Template fairies.
# 
# When editing:
#   1. Use Akashic tools/agents FIRST (MCP tools, sandbox, etc.)
#   2. Test changes in sandbox before applying
#   3. This module handles BOTH ConceptNode objects AND dict-based nodes
# ══════════════════════════════════════════════════════════════════════════════

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from collections import defaultdict

# ══════════════════════════════════════════════════════════════════════════════
# PERSISTENCE PATHS
# ══════════════════════════════════════════════════════════════════════════════

def _get_project_root() -> Path:
    """Find project root.

    FIX 2026-02-05: Added server.py check alongside SRM_Intake.
    fairies/ subdirectory also has SRM_Intake which caused this to
    resolve to fairies/ instead of the actual project root akashic_v2/.
    The real root always has server.py (started via start_nous.bat).
    """
    current = Path(__file__).parent
    while current.parent != current:
        if (current / "SRM_Intake").exists() and (current / "server.py").exists():
            return current
        current = current.parent
    # Fallback: use the known relative path from this file
    # This file lives at fairies/P30_Cognition/integration/graph_persistence.py
    fallback = Path(__file__).parent.parent.parent.parent
    if (fallback / "server.py").exists():
        return fallback
    return Path.cwd()

PROJECT_ROOT = _get_project_root()
SRM_INTAKE = PROJECT_ROOT / "SRM_Intake"
GRAPH_PERSIST_PATH = PROJECT_ROOT / "P30_Cognition" / "data" / "concept_graph.json"
GRAPH_BINARY_PATH = PROJECT_ROOT / "P30_Cognition" / "data" / "concept_graph.pkl"

# Ensure data dir exists
GRAPH_PERSIST_PATH.parent.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
# BINARY FORMAT - 5-10x faster than JSON, handles 40MB+ graphs efficiently
# ══════════════════════════════════════════════════════════════════════════════

import pickle

def save_graph_binary(graph, path: Path = GRAPH_BINARY_PATH, min_persist_weight: float = 0.0) -> bool:
    """
    DISABLED 2026-02-06: No more disk writes. Cards are the ONLY persistence.

    The card cluster (helix) IS the graph. Writing binary/JSON files to disk
    caused data loss when stale snapshots overwrote larger graphs that had
    grown in the card cluster. This function is kept as a no-op for backward
    compatibility (callers won't crash).
    """
    print(f"[GraphPersistence] save_graph_binary DISABLED - cards are the only persistence path")
    return True  # Return True so callers think it succeeded


def load_graph_binary(graph, path: Path = GRAPH_BINARY_PATH, chunk_size: int = 5000) -> int:
    """
    Load graph from binary format with chunked insertion.

    Chunked insertion prevents long GIL holds and allows other threads to run.

    Args:
        graph: Graph instance to populate
        path: Binary file path
        chunk_size: Nodes to insert per chunk (yields to other threads between chunks)

    Returns:
        Number of nodes loaded
    """
    if not path.exists():
        return 0

    try:
        with open(path, 'rb') as f:
            data = pickle.load(f)

        nodes_data = data.get("nodes", {})
        edges_data = data.get("edges", [])

        loaded_nodes = 0
        node_items = list(nodes_data.items())

        # Chunked node insertion - yields between chunks
        for i in range(0, len(node_items), chunk_size):
            chunk = node_items[i:i + chunk_size]
            for key, node_data in chunk:
                node = graph.upsert_node(key, node_data.get("features", {}))
                _set_node_attr(node, "count", node_data.get("count", 1))
                _set_node_attr(node, "first_seen_ts", node_data.get("first_seen", time.time()))
                _set_node_attr(node, "last_seen_ts", node_data.get("last_seen", time.time()))
                _set_node_attr(node, "activation", node_data.get("activation", 0.5))
                loaded_nodes += 1

            # Yield to other threads between chunks
            if i + chunk_size < len(node_items):
                time.sleep(0.001)

        # Load edges
        loaded_edges = 0
        for i in range(0, len(edges_data), chunk_size):
            chunk = edges_data[i:i + chunk_size]
            for edge in chunk:
                a, b = edge.get("a"), edge.get("b")
                if a and b and a in graph.nodes and b in graph.nodes:
                    relations = edge.get("relations", ["coactivate"])
                    if hasattr(graph, "link"):
                        for rel in relations:
                            try:
                                graph.link(a, b, rel)
                                loaded_edges += 1
                            except Exception:
                                pass

            # Yield between chunks
            if i + chunk_size < len(edges_data):
                time.sleep(0.001)

        print(f"[GraphPersistence] Binary load: {loaded_nodes} nodes, {loaded_edges} edges <- {path.name}")
        return loaded_nodes

    except Exception as e:
        print(f"[GraphPersistence] Binary load error: {e}")
        return 0


def load_concept_graph_smart(graph, prefer_binary: bool = True) -> int:
    """
    Smart loader - loads from disk files (binary preferred, JSON fallback).

    NOTE 2026-02-06: This function is ONLY used as a fallback when cards
    aren't available. The primary load path is from helix cards.
    The save_graph_binary migration step has been REMOVED.

    Args:
        graph: Graph to populate
        prefer_binary: Try binary first (default True)

    Returns:
        Number of nodes loaded
    """
    loaded = 0

    # Try binary first (5-10x faster)
    if prefer_binary and GRAPH_BINARY_PATH.exists():
        loaded = load_graph_binary(graph)
        if loaded > 0:
            return loaded

    # Fall back to JSON
    if GRAPH_PERSIST_PATH.exists():
        loaded = load_concept_graph(graph)
        # NO save_graph_binary migration - disk writes disabled

    return loaded


def save_concept_graph_smart(graph, min_persist_weight: float = 0.0) -> bool:
    """
    DISABLED 2026-02-06: No more disk writes. Cards are the ONLY persistence.

    Was: saves BOTH binary AND JSON to disk.
    Now: no-op. The card cluster handles all persistence via AssociationCortexFairy.
    """
    print(f"[GraphPersistence] save_concept_graph_smart DISABLED - cards are the only persistence path")
    return True


# ══════════════════════════════════════════════════════════════════════════════
# NODE ACCESS HELPERS - Handle both ConceptNode objects and dicts
# ══════════════════════════════════════════════════════════════════════════════

def _get_node_attr(node: Union[Any, Dict], attr: str, default: Any = None) -> Any:
    """
    Get attribute from node, handling both ConceptNode objects and dicts.
    
    AssociationCortexFairy uses ConceptNode objects: node.key, node.count
    ManifoldConstrainedCortexFairy uses dicts: node["key"], node["count"]
    """
    if isinstance(node, dict):
        return node.get(attr, default)
    else:
        return getattr(node, attr, default)


def _set_node_attr(node: Union[Any, Dict], attr: str, value: Any) -> None:
    """Set attribute on node, handling both objects and dicts.
    
    For objects with __slots__, only set if attr is in __slots__.
    """
    if isinstance(node, dict):
        node[attr] = value
    else:
        # Check if object uses __slots__
        slots = getattr(node.__class__, '__slots__', None)
        if slots is not None:
            # Only set if attr is in __slots__
            if attr in slots:
                setattr(node, attr, value)
            # else: silently skip - attr not allowed
        else:
            # Normal object with __dict__
            setattr(node, attr, value)


def _get_node_key(key: str, node: Union[Any, Dict]) -> str:
    """Get the node's key - might be stored in the node or just use the dict key."""
    if isinstance(node, dict):
        return node.get("key", key)
    else:
        return getattr(node, "key", key)


# ══════════════════════════════════════════════════════════════════════════════
# GRAPH PERSISTENCE
# ══════════════════════════════════════════════════════════════════════════════

def save_concept_graph(graph, path: Path = GRAPH_PERSIST_PATH, min_persist_weight: float = 0.0) -> bool:
    """
    DISABLED 2026-02-06: No more disk writes. Cards are the ONLY persistence.

    Was: Save ConceptGraph to JSON file on disk.
    Now: no-op. The card cluster handles all persistence.
    JSON saves were overwriting the card cluster's growing graph with stale snapshots.
    """
    print(f"[GraphPersistence] save_concept_graph DISABLED - cards are the only persistence path")
    return True


# ══════════════════════════════════════════════════════════════════════════════
# GRAPH BACKUP & RESTORE - Memory Vault Protection
# ══════════════════════════════════════════════════════════════════════════════

# Backup vault path - DISABLED 2026-02-06
# Backups were bloat. Chunk portal is the only persistence path.
# Directory no longer auto-created. Old backups should be deleted.
BACKUP_VAULT_PATH = PROJECT_ROOT / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "relational_clusters" / "AssociationCortexFairy" / "graph_backups"
# REMOVED: BACKUP_VAULT_PATH.mkdir(parents=True, exist_ok=True)
MAX_BACKUPS = 0  # No backups needed - chunk portal is stable


def backup_concept_graph(graph, reason: str = "manual") -> Optional[Path]:
    """
    DISABLED 2026-02-06: No more disk writes. Cards are the ONLY persistence.

    Was: Snapshot graph to JSON backup files in graph_backups/ directory.
    These "emergency backups" were CAUSING data loss — writing stale snapshots
    that competed with the card cluster. The card cluster IS the backup.
    Cards are immutable, versioned, and never lose data.
    """
    print(f"[GraphPersistence] backup_concept_graph DISABLED - cards are the only persistence path")
    return None


def _cleanup_old_backups():
    """Remove old backups, keeping only MAX_BACKUPS most recent."""
    try:
        backups = sorted(BACKUP_VAULT_PATH.glob("concept_graph_*.json"),
                        key=lambda p: p.stat().st_mtime, reverse=True)
        for old_backup in backups[MAX_BACKUPS:]:
            old_backup.unlink()
            print(f"[AssociationCortex]  Pruned old backup: {old_backup.name}")
    except Exception as e:
        print(f"[AssociationCortex]  Backup cleanup failed: {e}")


def list_backups() -> List[Dict[str, Any]]:
    """List available backups in the vault."""
    backups = []
    for path in sorted(BACKUP_VAULT_PATH.glob("concept_graph_*.json"),
                      key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            backups.append({
                "path": str(path),
                "name": path.name,
                "timestamp": data.get("backup_timestamp", 0),
                "reason": data.get("backup_reason", "unknown"),
                "nodes": data.get("node_count", 0),
                "edges": data.get("edge_count", 0),
                "size_kb": path.stat().st_size / 1024,
            })
        except:
            pass
    return backups


def restore_from_backup(graph, backup_path: Optional[Path] = None) -> bool:
    """
    Restore the concept graph from a vault backup.

    If no path specified, uses the most recent backup.

    Args:
        graph: ConceptGraph instance to restore into
        backup_path: Specific backup to restore, or None for most recent

    Returns:
        Success bool
    """
    try:
        if backup_path is None:
            # Find most recent backup
            backups = sorted(BACKUP_VAULT_PATH.glob("concept_graph_*.json"),
                           key=lambda p: p.stat().st_mtime, reverse=True)
            if not backups:
                print("[AssociationCortex] [X] No backups found in vault!")
                return False
            backup_path = backups[0]

        with open(backup_path, 'r') as f:
            data = json.load(f)

        # Clear current graph
        graph.nodes.clear()
        graph.edges.clear()

        # Restore nodes
        loaded_nodes = 0
        for key, node_data in data.get("nodes", {}).items():
            node = graph.upsert_node(key, node_data.get("features", {}))
            _set_node_attr(node, "count", node_data.get("count", 1))
            _set_node_attr(node, "first_seen_ts", node_data.get("first_seen", time.time()))
            _set_node_attr(node, "last_seen_ts", node_data.get("last_seen", time.time()))
            _set_node_attr(node, "activation", node_data.get("activation", 0.5))
            loaded_nodes += 1

        # Restore edges
        loaded_edges = 0
        for edge in data.get("edges", []):
            a, b = edge["a"], edge["b"]
            for rel in edge.get("relations", ["coactivate"]):
                graph.link(a, b, rel=rel, weight=edge.get("weight", 0.25) / 4)
            # Set final weight directly
            edge_key = tuple(sorted([a, b]))
            if edge_key in graph.edges:
                graph.edges[edge_key]["weight"] = edge.get("weight", 0.25)
            loaded_edges += 1

        reason = data.get("backup_reason", "unknown")
        timestamp = time.strftime("%Y-%m-%d %H:%M",
                                  time.localtime(data.get("backup_timestamp", 0)))

        print(f"[AssociationCortex] RESTORED FROM VAULT: {loaded_nodes} nodes, {loaded_edges} edges")
        print(f"[AssociationCortex]   Backup: {backup_path.name} ({reason}, {timestamp})")

        return True

    except Exception as e:
        print(f"[AssociationCortex] [X] Restore failed: {e}")
        return False


def load_concept_graph(graph, path: Path = GRAPH_PERSIST_PATH) -> int:
    """
    Load ConceptGraph or ManifoldConstrainedGraph from JSON.
    
    Handles both graph types by calling upsert_node and link methods.
    
    Args:
        graph: ConceptGraph or ManifoldConstrainedGraph instance to populate
        path: Where to load from
    
    Returns:
        Number of nodes loaded
    """
    if not path.exists():
        print(f"[AssociationCortex]  No saved graph found at {path}")
        return 0
    
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        
        loaded_nodes = 0
        loaded_edges = 0
        
        # Restore nodes - upsert_node works for both graph types
        for key, node_data in data.get("nodes", {}).items():
            node = graph.upsert_node(key, node_data.get("features", {}))
            
            # Set additional attributes
            _set_node_attr(node, "count", node_data.get("count", 1))
            _set_node_attr(node, "first_seen_ts", node_data.get("first_seen", time.time()))
            _set_node_attr(node, "last_seen_ts", node_data.get("last_seen", time.time()))
            _set_node_attr(node, "activation", node_data.get("activation", 0.5))
            loaded_nodes += 1
        
        # Restore edges - link method works for both graph types
        for edge in data.get("edges", []):
            a, b = edge.get("a"), edge.get("b")
            if a and b and a in graph.nodes and b in graph.nodes:
                relations = edge.get("relations", ["coactivate"])
                weight = edge.get("weight", 0.5)
                
                # Most graphs have a link() method
                if hasattr(graph, "link"):
                    for rel in relations if relations else ["coactivate"]:
                        try:
                            graph.link(a, b, rel=rel, weight=weight / max(len(relations), 1))
                        except Exception:
                            pass
                loaded_edges += 1
        
        print(f"[AssociationCortex]  Loaded graph: {loaded_nodes} nodes, {loaded_edges} edges")
        return loaded_nodes
        
    except Exception as e:
        print(f"[AssociationCortex] [X] Load failed: {e}")
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# SRM INTEGRATION - Build graph from memory files
# ══════════════════════════════════════════════════════════════════════════════

def extract_concepts_from_srm_record(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract concepts from an SRM record for graph insertion.
    
    Returns list of {key, features} dicts.
    """
    concepts = []
    
    # Extract text content
    content = record.get("content", "") or record.get("what", "") or ""
    if isinstance(content, dict):
        content = json.dumps(content)
    
    # Get metadata
    fairy = record.get("source", record.get("domain", "unknown"))
    entry_type = record.get("entry_type", record.get("kind", "unknown"))
    feeling = record.get("feeling", "neutral")
    
    # Simple word extraction (could be improved with NLP)
    words = str(content).lower().split()
    
    # Filter to meaningful words (>3 chars, not stopwords)
    stopwords = {"the", "and", "for", "that", "this", "with", "from", "have", 
                 "been", "were", "was", "are", "but", "not", "what", "when",
                 "how", "why", "where", "which", "who", "will", "would", "could",
                 "should", "can", "may", "might", "must", "shall"}
    
    meaningful = [w.strip('.,!?()[]{}":;') for w in words 
                  if len(w) > 3 and w not in stopwords]
    
    # Create concept for each meaningful word
    for word in set(meaningful):  # Dedupe
        concepts.append({
            "key": word,
            "features": {
                "lex": [word],
                "source_fairy": [fairy],
                "entry_type": [entry_type],
                "affect": [feeling],
            }
        })
    
    # Also create concept for the entry type itself
    if entry_type and entry_type != "unknown":
        concepts.append({
            "key": f"type:{entry_type}",
            "features": {
                "meta": ["entry_type"],
                "source_fairy": [fairy],
            }
        })
    
    return concepts


def load_srm_into_graph(
    graph,
    srm_path: Path = SRM_INTAKE,
    days_back: int = 7,
    max_files: int = 500,
) -> Dict[str, int]:
    """
    Scan SRM_Intake and build concept graph from memory files.
    
    Args:
        graph: ConceptGraph or ManifoldConstrainedGraph to populate
        srm_path: Path to SRM_Intake
        days_back: How many days to scan
        max_files: Maximum files to process
    
    Returns:
        Stats dict
    """
    stats = {
        "files_scanned": 0,
        "concepts_added": 0,
        "edges_added": 0,
        "errors": 0,
    }
    
    if not srm_path.exists():
        print(f"[AssociationCortex] [WARN] SRM_Intake not found: {srm_path}")
        return stats
    
    print(f"[AssociationCortex]  Loading SRM into graph (last {days_back} days)...")
    
    # Get recent day directories
    try:
        day_dirs = sorted(
            [d for d in srm_path.iterdir() if d.is_dir()],
            reverse=True
        )[:days_back]
    except Exception:
        day_dirs = []
    
    files_processed = 0
    
    for day_dir in day_dirs:
        if not day_dir.is_dir():
            continue
        
        for json_file in day_dir.glob("*.json"):
            if files_processed >= max_files:
                break
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    record = json.load(f)
                
                stats["files_scanned"] += 1
                files_processed += 1
                
                # Extract concepts
                concepts = extract_concepts_from_srm_record(record)
                
                # Insert into graph
                concept_keys = []
                for concept in concepts:
                    try:
                        node = graph.upsert_node(concept["key"], concept["features"])
                        concept_keys.append(concept["key"])
                        stats["concepts_added"] += 1
                    except Exception:
                        stats["errors"] += 1
                
                # Link co-occurring concepts
                if hasattr(graph, "link"):
                    for i, key_a in enumerate(concept_keys):
                        for key_b in concept_keys[i+1:]:
                            if key_a != key_b:
                                try:
                                    graph.link(key_a, key_b, rel="coactivate", weight=0.1)
                                    stats["edges_added"] += 1
                                except Exception:
                                    pass
                
            except Exception as e:
                stats["errors"] += 1
        
        if files_processed >= max_files:
            break
    
    print(f"[AssociationCortex] [OK] SRM loaded: {stats['files_scanned']} files → "
          f"{stats['concepts_added']} concepts, {stats['edges_added']} edges")
    
    return stats


# ══════════════════════════════════════════════════════════════════════════════
# BOOT INTEGRATION - Deferred loading for fast boot
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# DEFERRED LOADING VIA CELL COLONY
# ══════════════════════════════════════════════════════════════════════════════
#
# Instead of a simple background thread, we use a persistent GraphLoaderCell
# from the CellColony. This cell:
#   - Runs continuously (like a blood cell)
#   - Doesn't "decay" or return to a pool
#   - Can use GPU acceleration if available
#   - Reports health metrics
#
# ══════════════════════════════════════════════════════════════════════════════


def initialize_graph_deferred(graph, callback=None, days_back: int = 3, max_files: int = 200) -> Dict[str, Any]:
    """
    FAST BOOT: Schedule ALL graph loading for background execution.

    The disk load (concept_graph.json) can be 15+ MB with 80k nodes.
    Loading this synchronously blocks boot for 500-700ms.
    Now EVERYTHING is deferred to background - zero blocking on boot.

    Call this in on_boot() instead of initialize_graph_with_persistence():

        from fairies.P30_Cognition.integration.graph_persistence import initialize_graph_deferred
        stats = initialize_graph_deferred(self._graph)

    Args:
        graph: ConceptGraph or ManifoldConstrainedGraph to populate
        callback: Optional callback(stats) when loading completes
        days_back: How many days of SRM to load (default 3)
        max_files: Maximum files to process (default 200)

    Returns:
        Stats dict (with deferred=True until loading completes)
    """
    # NO BLOCKING - all loading happens in background now
    stats = {
        "loaded_from_disk": "deferred",
        "deferred": True,
        "srm_loading": "queued",
    }

    # Queue to the GraphLoaderCell (persistent worker)
    try:
        from fairies.P00_Autonomic.nervous_system.hardware.worker_cell_colony import get_or_spawn_graph_loader
        loader_cell = get_or_spawn_graph_loader()
        loader_cell.queue_graph_load(graph, callback=callback, days_back=days_back, max_files=max_files)
        stats["cell_id"] = loader_cell.cell_id
        stats["srm_loading"] = "queued_to_cell"
    except ImportError:
        # Fallback: use simple thread if CellColony not available
        import threading
        thread = threading.Thread(
            target=_fallback_full_loader,
            args=(graph, callback, days_back, max_files),
            daemon=True,
            name="GraphPersistence-Fallback"
        )
        thread.start()
        stats["srm_loading"] = "fallback_thread"
    except Exception as e:
        print(f"[GraphPersistence] Deferred load setup error: {e}")
        stats["error"] = str(e)

    return stats


def _fallback_full_loader(graph, callback, days_back: int, max_files: int):
    """Fallback loader - loads SRM in background thread.

    FIX 2026-02-06: REMOVED disk load and disk save.
    The graph is loaded from CARDS at boot (by AssociationCortexFairy).
    This fallback only enriches from SRM if needed. No disk writes.
    """
    try:
        # Enrich from SRM (read-only from SRM files, writes to graph in memory)
        srm_stats = load_srm_into_graph(graph, days_back=days_back, max_files=max_files)
        # NO save_concept_graph_smart - cards handle persistence
        if callback:
            try:
                callback({
                    "loaded_from_disk": 0,
                    "loaded_from_srm": srm_stats,
                    "completed": True
                })
            except Exception:
                pass
    except Exception as e:
        print(f"[GraphPersistence] SRM load error: {e}")


def initialize_graph_with_persistence(graph) -> Dict[str, Any]:
    """
    Initialize graph from SRM only. No disk load, no disk save.

    FIX 2026-02-06: REMOVED disk load and disk save.
    The graph is loaded from CARDS at boot (by AssociationCortexFairy).
    This function only enriches from SRM if needed. No disk writes.

    ⚠️  WARNING: This blocks! Use initialize_graph_deferred() for fast boot.
    """
    stats = {
        "loaded_from_disk": 0,
        "loaded_from_srm": {},
    }

    # Enrich with recent SRM (read-only from SRM files)
    stats["loaded_from_srm"] = load_srm_into_graph(graph, days_back=3, max_files=200)

    # NO save_concept_graph - cards handle persistence

    return stats


def periodic_save(graph, interval_sec: float = 300.0) -> None:
    """
    DISABLED 2026-02-06: No more disk writes. Cards are the ONLY persistence.

    Was: Periodically save graph to JSON disk file.
    Now: no-op. Cards handle persistence via AssociationCortexFairy._maybe_background_persist().
    """
    pass  # Cards handle persistence


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(" Testing Graph Persistence")
    print("=" * 50)
    
    # Test with dict-based node (ManifoldConstrainedGraph style)
    print("\n1. Testing dict-based node access:")
    dict_node = {"key": "test", "features": {"lex": ["hello"]}, "count": 5}
    print(f"   key: {_get_node_attr(dict_node, 'key')}")
    print(f"   count: {_get_node_attr(dict_node, 'count')}")
    
    # Test with object-based node (ConceptNode style)
    print("\n2. Testing object-based node access:")
    class FakeNode:
        def __init__(self):
            self.key = "test2"
            self.features = {"lex": ["world"]}
            self.count = 10
    
    obj_node = FakeNode()
    print(f"   key: {_get_node_attr(obj_node, 'key')}")
    print(f"   count: {_get_node_attr(obj_node, 'count')}")
    
    print("\n[OK] Dual-format node access working!")
    
    # Test full flow if graph available
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import ConceptGraph
        
        print("\n3. Testing with real ConceptGraph:")
        graph = ConceptGraph()
        stats = initialize_graph_with_persistence(graph)
        
        print(f"\n Results:")
        print(f"   Loaded from disk: {stats['loaded_from_disk']} nodes")
        print(f"   Loaded from SRM: {stats['loaded_from_srm']}")
        print(f"   Final graph size: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    except ImportError:
        print("\n(Skipping graph test - not in full environment)")
