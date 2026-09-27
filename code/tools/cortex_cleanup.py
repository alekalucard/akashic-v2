"""
Cortex Cleanup — Remove noise nodes from AssociationCortex concept_graph.json
2026-02-23

Noise categories removed:
  - Timestamps (Unix epoch floats/ints leaked as concepts)
  - File paths (Windows paths, srm_intake records)
  - Numeric-only lex (arrays of numbers)
  - Structural formatting (=== separators, --- dividers, XML tags)
  - Hex hashes
  - Overly long keys (>100 chars)
  - Low-alpha lex content (< 35% alphabetic chars, min length 5)

Kept:
  - cluster:* nodes (SRM knowledge base)
  - consciousness_variant_* (auto-generated concept variants)
  - type:* (type annotations)
  - Regular words/phrases
  - Dream/thought entries [Nous], [dream memory], etc.
  - source:file:* references

Usage:
  python tools/cortex_cleanup.py          # Dry run (report only)
  python tools/cortex_cleanup.py --apply  # Actually write cleaned graph
"""
import json
import re
import sys
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRY_RUN = "--apply" not in sys.argv

# Locate graph
PORTAL_GRAPH = ROOT / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "relational_clusters" / "AssociationCortexFairy" / "concept_graph.json"
P30_GRAPH = ROOT / "P30_Cognition" / "data" / "concept_graph.json"
graph_path = PORTAL_GRAPH if PORTAL_GRAPH.exists() else P30_GRAPH

print(f"{'[DRY RUN]' if DRY_RUN else '[APPLYING]'} Loading {graph_path.name} ({graph_path.stat().st_size / 1024 / 1024:.1f} MB)...")

with open(graph_path, "r", encoding="utf-8") as f:
    data = json.load(f)

nodes = data.get("nodes", {})
edges = data.get("edges", [])
print(f"  Nodes: {len(nodes):,}  Edges: {len(edges):,}")


def is_noise_node(key, node):
    """Returns noise category string, or None if node is clean."""
    key_str = str(key)
    features = node.get("features", {})
    lex = features.get("lex", [])
    lex_strs = [str(l) for l in lex] if lex else []
    lex_joined = " ".join(lex_strs)

    # ── KEY checks ──

    # File extensions
    if re.search(r"\.(py|json|pkl|md|txt|yaml|toml|csv|log|cfg|ini|exe|dll|bat|sh|ipynb)$",
                 key_str, re.IGNORECASE):
        return "file_ext_key"

    # File paths
    if re.search(r"[A-Z]:[/\\]|fairies[/\\]P\d{2}|\\\\sandbox\\\\|/home/\w+/|srm_intake",
                 key_str, re.IGNORECASE):
        return "path_key"

    # Pure hex hash keys
    if re.match(r"^[0-9a-f]{8,}$", key_str):
        return "hex_key"

    # Very long keys
    if len(key_str) > 100:
        return "long_key"

    # Keys starting with JSON/array structures
    if key_str.startswith("{") or (key_str.startswith("[") and not key_str.startswith("[Nous")
                                    and not key_str.startswith("[dream")
                                    and not key_str.startswith("[inner")):
        return "json_key"

    # Code identifier keys
    if re.match(r"^(self\.|def |class |import |from |__\w+__|lambda )", key_str):
        return "code_key"

    # ── LEX checks ──

    if lex_strs:
        # Numeric-only lex
        if len(lex_strs) >= 1 and all(re.match(r"^-?\d+\.?\d*[eE]?[+-]?\d*$", l.strip()) for l in lex_strs):
            return "numeric_lex"

        # File paths in lex
        path_hits = sum(1 for l in lex_strs if re.search(
            r"[A-Z]:[/\\]|\\\\sandbox|fairies[/\\]|\.py$|\.json$|ingest\.record|srm_intake",
            l, re.IGNORECASE))
        if path_hits > 0:
            return "path_lex"

        # Code-heavy lex (but protect "self" as a philosophical concept)
        code_words = {"def", "class", "import", "return", "none", "true", "false",
                      "init", "try", "except", "print", "lambda", "yield", "async",
                      "await", "elif", "isinstance", "getattr", "setattr", "hasattr"}
        code_hits = sum(1 for l in lex_strs if l.lower().strip("_") in code_words
                        or re.search(r"__\w+__", l)
                        or l.endswith(".py") or l.endswith(".json")
                        or "self." in l or "()" in l)
        if len(lex_strs) >= 2 and code_hits / len(lex_strs) > 0.3:
            return "code_lex"

        # Hex hashes in lex
        hex_hits = sum(1 for l in lex_strs if re.match(r"^[0-9a-f]{8,}$", l.strip()))
        if hex_hits > 0:
            return "hex_lex"

        # Structural chars dominate lex
        if lex_joined and len(lex_joined) > 5:
            struct = sum(1 for c in lex_joined if c in '{}[]();,:"\\=<>|/')
            alpha = sum(1 for c in lex_joined if c.isalpha())
            total = len(lex_joined)
            if total > 8 and struct / total > 0.20:
                return "structural_lex"
            if total > 5 and alpha / total < 0.35:
                return "low_alpha_lex"

        # Fairy/system internal name spam
        fairy_hits = sum(1 for l in lex_strs if re.search(r"\w+Fairy$", l))
        if len(lex_strs) >= 3 and fairy_hits / len(lex_strs) > 0.4:
            return "fairy_name_lex"

        # Timestamp-heavy lex
        ts_hits = sum(1 for l in lex_strs if re.match(
            r"^\d{4}-\d{2}-\d{2}|^\d{10,}$|T\d{2}:\d{2}|Z$", l.strip()))
        if len(lex_strs) >= 2 and ts_hits / len(lex_strs) > 0.4:
            return "timestamp_lex"

    # ── lex: prefixed key content checks ──
    if key_str.startswith("lex:"):
        content = key_str[4:]
        # Pure number in lex: key
        if re.match(r"^-?\d+\.?\d*[eE]?[+-]?\d*$", content.strip()):
            return "numeric_key"
        # Path after lex:
        if re.search(r"[A-Z]:[/\\]|\\\\|fairies/P\d{2}", content):
            return "path_key"
        # Structural content after lex:
        if len(content) > 10:
            struct = sum(1 for c in content if c in '{}[]();,:"\\=<>|/')
            alpha = sum(1 for c in content if c.isalpha())
            if struct / len(content) > 0.15:
                return "structural_key"
            if alpha / len(content) < 0.35:
                return "low_alpha_key"

    return None


# ── Classify all nodes ────────────────────────────────────────────────

noise_keys = set()
categories = Counter()

for key, node in nodes.items():
    reason = is_noise_node(key, node)
    if reason:
        noise_keys.add(key)
        categories[reason] += 1

good_count = len(nodes) - len(noise_keys)
print(f"\n  Noise: {len(noise_keys):,} ({100*len(noise_keys)/len(nodes):.1f}%)")
print(f"  Clean: {good_count:,} ({100*good_count/len(nodes):.1f}%)")
print(f"\n  By category:")
for cat, count in categories.most_common():
    print(f"    {cat:20s}: {count:>6,}")


# ── Remove noise nodes ───────────────────────────────────────────────

clean_nodes = {k: v for k, v in nodes.items() if k not in noise_keys}


# ── Remove edges touching noise nodes ────────────────────────────────

clean_edges = []
removed_edges = 0
for e in edges:
    src, tgt = None, None
    if isinstance(e, dict):
        src = e.get("a", e.get("source", e.get("from", "")))
        tgt = e.get("b", e.get("target", e.get("to", "")))
    elif isinstance(e, (list, tuple)) and len(e) >= 2:
        src, tgt = e[0], e[1]

    if src in noise_keys or tgt in noise_keys:
        removed_edges += 1
    else:
        clean_edges.append(e)

print(f"\n  Edges removed: {removed_edges:,}")
print(f"  Edges kept:    {len(clean_edges):,}")


# ── Build cleaned graph ──────────────────────────────────────────────

clean_data = dict(data)  # preserve any metadata keys
clean_data["nodes"] = clean_nodes
clean_data["edges"] = clean_edges

# Size comparison
import io
clean_json = json.dumps(clean_data, separators=(',', ':'))
clean_size_mb = len(clean_json.encode("utf-8")) / 1024 / 1024
orig_size_mb = graph_path.stat().st_size / 1024 / 1024

print(f"\n{'='*60}")
print(f"  SUMMARY")
print(f"{'='*60}")
print(f"  Nodes:  {len(nodes):>8,} -> {len(clean_nodes):>8,}  (removed {len(noise_keys):,})")
print(f"  Edges:  {len(edges):>8,} -> {len(clean_edges):>8,}  (removed {removed_edges:,})")
print(f"  Size:   {orig_size_mb:>7.1f} MB -> {clean_size_mb:>7.1f} MB  (saved {orig_size_mb - clean_size_mb:.1f} MB)")

if DRY_RUN:
    print(f"\n  [DRY RUN] No changes written. Use --apply to write.")
else:
    # Backup original
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = graph_path.parent / f"concept_graph.backup_{timestamp}.json"
    print(f"\n  Backing up to {backup_path.name}...")
    shutil.copy2(graph_path, backup_path)

    # Write cleaned graph (pretty-printed for readability)
    print(f"  Writing cleaned graph...")
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump(clean_data, f, separators=(',', ':'))

    final_size = graph_path.stat().st_size / 1024 / 1024
    print(f"  Done! New size: {final_size:.1f} MB")
    print(f"  Backup at: {backup_path}")

print(f"\n  Cleanup complete.")
