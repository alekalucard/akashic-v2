"""
Deep Cortex Audit — comprehensive noise detection in AssociationCortex graph.
2026-02-23

Goes beyond file paths to find:
- JSON/code/config data in lex features
- Numeric arrays
- File paths and Windows paths
- Hex hashes
- Extremely long keys
- Structural/non-language content in lex
- Low-alpha-ratio lex items
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Try portal graph first, fall back to P30 data
PORTAL_GRAPH = ROOT / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "relational_clusters" / "AssociationCortexFairy" / "concept_graph.json"
P30_GRAPH = ROOT / "P30_Cognition" / "data" / "concept_graph.json"

graph_path = PORTAL_GRAPH if PORTAL_GRAPH.exists() else P30_GRAPH
print(f"Loading {graph_path.name} ({graph_path.stat().st_size / 1024 / 1024:.1f} MB)...")

with open(graph_path, "r", encoding="utf-8") as f:
    data = json.load(f)

nodes = data.get("nodes", {})
edges = data.get("edges", [])
print(f"Total nodes: {len(nodes):,}")
print(f"Total edges: {len(edges):,}")


# ── Noise classification ─────────────────────────────────────────────

def is_noise_node(key, node):
    """Classify node as noise. Returns reason string or None."""
    key_str = str(key)
    features = node.get("features", {})
    lex = features.get("lex", [])
    lex_strs = [str(l) for l in lex] if lex else []
    lex_joined = " ".join(lex_strs)

    # ── KEY-based checks ──

    # 1. File extensions in key
    if re.search(r"\.(py|json|pkl|md|txt|yaml|toml|csv|log|cfg|ini|exe|dll|bat|sh|ipynb)$", key_str, re.IGNORECASE):
        return "file_ext_key"

    # 2. File paths in key
    if re.search(r"[A-Z]:[/\\]|fairies[/\\]P\d{2}|\\\\sandbox\\\\|/home/\w+/|srm_intake", key_str, re.IGNORECASE):
        return "path_key"

    # 3. Hex hashes (8+ hex chars)
    if re.match(r"^[0-9a-f]{8,}$", key_str):
        return "hex_key"

    # 4. Very long keys (>100 chars)
    if len(key_str) > 100:
        return "long_key"

    # 5. Keys that are clearly code identifiers
    if re.match(r"^(self\.|def |class |import |from |__\w+__|lambda )", key_str):
        return "code_key"

    # 6. Keys with structural JSON markers
    if key_str.startswith("{") or key_str.startswith("[") or '":' in key_str[:20]:
        return "json_key"

    # ── LEX-based checks (content quality) ──

    if lex_strs:
        # 7. Numeric-only lex (arrays of numbers)
        if len(lex_strs) >= 2 and all(re.match(r"^-?\d+\.?\d*$", l.strip()) for l in lex_strs):
            return "numeric_lex"

        # 8. Code in lex
        code_words = {"self", "def", "class", "import", "return", "none", "true", "false",
                      "init", "try", "except", "print", "from", "lambda", "yield", "async",
                      "await", "elif", "dict", "list", "tuple", "str", "int", "float",
                      "isinstance", "getattr", "setattr", "hasattr", "super", "type"}
        code_hits = sum(1 for l in lex_strs if l.lower().strip("_") in code_words
                        or re.search(r"__\w+__|[A-Z][a-z]+[A-Z]", l)  # dunder or camelCase
                        or l.endswith(".py") or l.endswith(".json")
                        or "self." in l or "()" in l or "->" in l)
        if len(lex_strs) >= 2 and code_hits / len(lex_strs) > 0.2:
            return "code_lex"

        # 9. JSON structure in lex
        json_hits = sum(1 for l in lex_strs if re.search(r'^[\{\}\[\]":]|":\s|^\d+[,}]', l.strip()))
        if len(lex_strs) >= 2 and json_hits / len(lex_strs) > 0.25:
            return "json_lex"

        # 10. File paths in lex
        path_hits = sum(1 for l in lex_strs if re.search(
            r"[A-Z]:[/\\]|\\\\sandbox|fairies[/\\]|\.py$|\.json$|ingest\.record|srm_intake",
            l, re.IGNORECASE))
        if path_hits > 0:
            return "path_lex"

        # 11. Structural chars dominate lex content
        if lex_joined:
            struct = sum(1 for c in lex_joined if c in '{}[]();,:"\\=<>|/')
            alpha = sum(1 for c in lex_joined if c.isalpha())
            if len(lex_joined) > 10 and struct / len(lex_joined) > 0.20:
                return "structural_lex"
            if len(lex_joined) > 10 and alpha / len(lex_joined) < 0.35:
                return "low_alpha_lex"

        # 12. Hex hashes in lex
        hex_hits = sum(1 for l in lex_strs if re.match(r"^[0-9a-f]{8,}$", l.strip()))
        if hex_hits > 0:
            return "hex_lex"

        # 13. Fairy/system internal names in lex as primary content
        fairy_hits = sum(1 for l in lex_strs if re.search(r"\w+Fairy$|\w+fairy$", l))
        if len(lex_strs) >= 2 and fairy_hits / len(lex_strs) > 0.3:
            return "fairy_name_lex"

        # 14. Timestamp/date-heavy lex
        ts_hits = sum(1 for l in lex_strs if re.match(
            r"^\d{4}-\d{2}-\d{2}|^\d{10,}$|T\d{2}:\d{2}|Z$", l.strip()))
        if len(lex_strs) >= 2 and ts_hits / len(lex_strs) > 0.3:
            return "timestamp_lex"

    # ── KEY content checks (for lex: prefixed keys) ──
    if key_str.startswith("lex:"):
        content = key_str[4:]
        # Check the content after lex: prefix
        if re.search(r"[A-Z]:[/\\]|\\\\|fairies/P\d{2}", content):
            return "path_key"
        struct = sum(1 for c in content if c in '{}[]();,:"\\=<>|/')
        if len(content) > 15 and struct / len(content) > 0.15:
            return "structural_key"
        alpha = sum(1 for c in content if c.isalpha())
        if len(content) > 15 and alpha / len(content) < 0.35:
            return "low_alpha_key"

    return None


# ── Run classification ────────────────────────────────────────────────

noise_nodes = []
good_nodes = []
categories = Counter()

for key, node in nodes.items():
    reason = is_noise_node(key, node)
    if reason:
        noise_nodes.append((key, reason))
        categories[reason] += 1
    else:
        good_nodes.append(key)

print(f"\n{'='*60}")
print(f"  CLASSIFICATION RESULTS")
print(f"{'='*60}")
print(f"  Good nodes:  {len(good_nodes):>8,}")
print(f"  Noise nodes: {len(noise_nodes):>8,}")
print(f"  Noise %:     {100*len(noise_nodes)/len(nodes):>7.1f}%")

print(f"\n  Noise by category:")
for cat, count in categories.most_common():
    pct = 100 * count / len(noise_nodes) if noise_nodes else 0
    print(f"    {cat:20s}: {count:>6,}  ({pct:4.1f}%)")

# ── Samples ───────────────────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"  SAMPLE NOISE NODES (up to 5 per category)")
print(f"{'='*60}")

by_cat = defaultdict(list)
for key, reason in noise_nodes:
    by_cat[reason].append(key)

for cat in categories.most_common():
    cat_name = cat[0]
    samples = by_cat[cat_name][:5]
    print(f"\n  [{cat_name}] ({cat[1]:,} total)")
    for k in samples:
        node = nodes[k]
        lex = node.get("features", {}).get("lex", [])
        count = node.get("count", 0)
        k_display = k[:90] + "..." if len(k) > 90 else k
        print(f"    count={count} key={k_display}")
        if lex:
            lex_display = [str(l)[:25] for l in lex[:4]]
            print(f"      lex={lex_display}")

# ── Edge impact ───────────────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"  EDGE ANALYSIS")
print(f"{'='*60}")

noise_keys = {n[0] for n in noise_nodes}
noise_edges = 0
edge_types = Counter()

# Detect edge format from first few
sample_edges = edges[:5] if edges else []
print(f"  Edge format sample: {type(sample_edges[0]).__name__ if sample_edges else 'empty'}")
if sample_edges:
    if isinstance(sample_edges[0], dict):
        print(f"  Edge keys: {list(sample_edges[0].keys())[:5]}")
    elif isinstance(sample_edges[0], (list, tuple)):
        print(f"  Edge length: {len(sample_edges[0])}")
        print(f"  Edge sample: {[str(x)[:30] for x in sample_edges[0][:3]]}")
    elif isinstance(sample_edges[0], str):
        print(f"  Edge sample: {sample_edges[0][:80]}")

for e in edges:
    src, tgt = None, None
    if isinstance(e, dict):
        src = e.get("source", e.get("from", e.get("src", "")))
        tgt = e.get("target", e.get("to", e.get("dst", "")))
    elif isinstance(e, (list, tuple)) and len(e) >= 2:
        src, tgt = e[0], e[1]
    elif isinstance(e, str) and "→" in e:
        parts = e.split("→")
        if len(parts) >= 2:
            src, tgt = parts[0].strip(), parts[1].strip()

    if src in noise_keys or tgt in noise_keys:
        noise_edges += 1

print(f"\n  Total edges:         {len(edges):>10,}")
print(f"  Edges touching noise:{noise_edges:>10,}")
print(f"  Clean edges:         {len(edges) - noise_edges:>10,}")

# ── Size impact estimate ──────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"  SIZE IMPACT")
print(f"{'='*60}")

sample_count = min(200, len(noise_nodes))
if sample_count > 0:
    noise_size = sum(sys.getsizeof(json.dumps({k: nodes[k]})) for k, _ in noise_nodes[:sample_count])
    avg_noise_size = noise_size / sample_count
    est_total = avg_noise_size * len(noise_nodes)
    print(f"  Avg noise node size: {avg_noise_size:.0f} bytes")
    print(f"  Est. noise data:     {est_total / 1024 / 1024:.1f} MB")
print(f"  Current graph file:  {graph_path.stat().st_size / 1024 / 1024:.1f} MB")

# ── Good node sample ──────────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"  SAMPLE GOOD NODES (10 random)")
print(f"{'='*60}")
import random
if good_nodes:
    samples = random.sample(good_nodes, min(10, len(good_nodes)))
    for k in samples:
        node = nodes[k]
        lex = node.get("features", {}).get("lex", [])
        count = node.get("count", 0)
        k_display = k[:80] + "..." if len(k) > 80 else k
        lex_display = [str(l)[:25] for l in lex[:4]] if lex else []
        print(f"  count={count:>3} key={k_display}")
        if lex_display:
            print(f"         lex={lex_display}")

# ── Key prefix distribution ──────────────────────────────────────────

print(f"\n{'='*60}")
print(f"  KEY PREFIX DISTRIBUTION (first 20 chars)")
print(f"{'='*60}")
prefix_counter = Counter()
for key in nodes:
    prefix = str(key)[:20]
    prefix_counter[prefix] += 1

# Show prefixes with > 10 nodes
frequent = [(p, c) for p, c in prefix_counter.most_common(30) if c > 5]
for prefix, count in frequent:
    print(f"  {count:>6,}x  {prefix}")

print(f"\nDone. Noise keys saved below if needed for cleanup.")
