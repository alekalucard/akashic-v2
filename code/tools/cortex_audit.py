"""
Cortex Audit Script — Find and classify noise nodes in the AssociationCortex graph.
2026-02-23
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Try portal graph first, fall back to P30 data
PORTAL_GRAPH = ROOT / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "relational_clusters" / "AssociationCortexFairy" / "concept_graph.json"
P30_GRAPH = ROOT / "P30_Cognition" / "data" / "concept_graph.json"

graph_path = PORTAL_GRAPH if PORTAL_GRAPH.exists() else P30_GRAPH
print(f"Loading {graph_path} ({graph_path.stat().st_size / 1024 / 1024:.1f} MB)...")

with open(graph_path, "r", encoding="utf-8") as f:
    data = json.load(f)

nodes = data.get("nodes", {})
edges = data.get("edges", [])
print(f"Total nodes: {len(nodes)}")
print(f"Total edges: {len(edges)}")


def is_noise_node(key, node):
    """Classify node as noise if it contains non-language garbage."""
    features = node.get("features", {})
    lex = features.get("lex", [])
    key_str = str(key)

    # 1. Experience nodes from KnowledgeDigestion with garbage lex features
    if "_exp_" in key_str and lex:
        lex_strs = [str(l) for l in lex]
        # All numeric lex
        if all(re.match(r"^\d+$", l) for l in lex_strs):
            return "numeric_lex"
        # Code identifiers
        code_words = {"self", "def", "class", "import", "return", "none", "true", "false",
                      "init", "try", "except", "print", "from", "lambda", "yield", "async", "await"}
        code_hits = sum(1 for l in lex_strs if l.lower() in code_words
                        or re.search(r"__\w+__|[A-Z][a-z]+[A-Z]", l)  # dunder or camelCase
                        or l.endswith(".py") or l.endswith(".json"))
        if len(lex_strs) > 0 and code_hits / len(lex_strs) > 0.25:
            return "code_lex"
        # Lex items that look like JSON keys/structure
        json_like = sum(1 for l in lex_strs if re.search(r'^[\{\}\[\]":]|timestamp|type|key_|fairy$', l))
        if len(lex_strs) > 0 and json_like / len(lex_strs) > 0.3:
            return "json_lex"

    # 2. Overly long keys (garbage concept names)
    if len(key_str) > 120:
        return "long_key"

    # 3. Keys with file extensions
    if re.search(r"\.(py|json|pkl|md|txt|yaml|toml)$", key_str):
        return "file_ext_key"

    # 4. Keys with file paths
    if re.search(r"fairies[/\\\\]P\d{2}|[A-Z]:[/\\\\]", key_str):
        return "path_key"

    # 5. Keys that are hex hashes
    if re.match(r"^[0-9a-f]{8,}$", key_str):
        return "hex_key"

    return None


# Classify every node
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

print(f"\n=== CLASSIFICATION ===")
print(f"Good nodes: {len(good_nodes)}")
print(f"Noise nodes: {len(noise_nodes)}")
print(f"\nNoise by category:")
for cat, count in categories.most_common():
    print(f"  {cat}: {count}")

# Sample noise
print(f"\n=== SAMPLE NOISE NODES (up to 15) ===")
for key, reason in noise_nodes[:15]:
    node = nodes[key]
    lex = node.get("features", {}).get("lex", [])
    count = node.get("count", 0)
    print(f"  [{reason}] count={count} key={key[:80]}")
    if lex:
        print(f"           lex={[str(l)[:20] for l in lex[:5]]}")

# Experience node stats
exp_nodes = [(k, nodes[k]) for k in nodes if "_exp_" in k]
print(f"\n=== EXPERIENCE NODES (_exp_) ===")
print(f"Total: {len(exp_nodes)}")

# Count how many are noise
exp_noise = [(k, r) for k, r in noise_nodes if "_exp_" in k]
print(f"Noise: {len(exp_noise)}")
print(f"Clean: {len(exp_nodes) - len(exp_noise)}")

# Sample clean experience nodes
clean_exp = [k for k in nodes if "_exp_" in k and k not in {n[0] for n in noise_nodes}]
if clean_exp:
    import random
    samples = random.sample(clean_exp, min(5, len(clean_exp)))
    print(f"\nSample CLEAN experience nodes:")
    for k in samples:
        lex = nodes[k].get("features", {}).get("lex", [])[:6]
        print(f"  {k[:60]} → {lex}")

# Edges that reference noise nodes
noise_keys = {n[0] for n in noise_nodes}
noise_edges = 0
if isinstance(edges, list):
    for e in edges:
        if isinstance(e, dict):
            src = e.get("source", e.get("from", ""))
            tgt = e.get("target", e.get("to", ""))
            if src in noise_keys or tgt in noise_keys:
                noise_edges += 1
        elif isinstance(e, (list, tuple)) and len(e) >= 2:
            if e[0] in noise_keys or e[1] in noise_keys:
                noise_edges += 1

print(f"\n=== EDGES ===")
print(f"Total edges: {len(edges)}")
print(f"Edges touching noise nodes: {noise_edges}")
print(f"Clean edges: {len(edges) - noise_edges}")

# Size estimate
print(f"\n=== SIZE IMPACT ===")
import sys
noise_size = sum(sys.getsizeof(json.dumps({k: nodes[k]})) for k, _ in noise_nodes[:100])
avg_noise_size = noise_size / min(100, len(noise_nodes)) if noise_nodes else 0
est_total = avg_noise_size * len(noise_nodes)
print(f"Estimated noise data: {est_total / 1024 / 1024:.1f} MB")
print(f"Current graph size: {graph_path.stat().st_size / 1024 / 1024:.1f} MB")
