"""Clean the P30 concept_graph.json (boot copy) using same logic as cortex_cleanup.py"""
import json, re, shutil, sys
from pathlib import Path
from datetime import datetime

p30 = Path(__file__).resolve().parents[1] / "P30_Cognition" / "data" / "concept_graph.json"
print(f"Loading P30 graph ({p30.stat().st_size / 1024 / 1024:.1f} MB)...")

with open(p30, "r", encoding="utf-8") as f:
    data = json.load(f)

nodes = data.get("nodes", {})
edges = data.get("edges", [])


def is_noise(key, node):
    key_str = str(key)
    features = node.get("features", {})
    lex = features.get("lex", [])
    lex_strs = [str(l) for l in lex] if lex else []
    lex_joined = " ".join(lex_strs)

    if re.search(r"\.(py|json|pkl|md|txt|yaml|toml|csv|log)$", key_str, re.IGNORECASE):
        return True
    if re.search(r"[A-Z]:[/\\]|fairies[/\\]P\d{2}|\\\\sandbox|srm_intake", key_str, re.IGNORECASE):
        return True
    if re.match(r"^[0-9a-f]{8,}$", key_str):
        return True
    if len(key_str) > 100:
        return True
    if key_str.startswith("{"):
        return True
    if key_str.startswith("[") and not any(key_str.startswith(p) for p in ("[Nous", "[dream", "[inner")):
        return True

    if lex_strs:
        if all(re.match(r"^-?\d+\.?\d*[eE]?[+-]?\d*$", l.strip()) for l in lex_strs):
            return True
        path_hits = sum(1 for l in lex_strs if re.search(
            r"[A-Z]:[/\\]|\\\\sandbox|\.py$|\.json$|ingest\.record|srm_intake", l, re.IGNORECASE))
        if path_hits > 0:
            return True
        hex_hits = sum(1 for l in lex_strs if re.match(r"^[0-9a-f]{8,}$", l.strip()))
        if hex_hits > 0:
            return True
        if lex_joined and len(lex_joined) > 5:
            struct_chars = set('{}[]();,:"\\=<>|/')
            struct = sum(1 for c in lex_joined if c in struct_chars)
            alpha = sum(1 for c in lex_joined if c.isalpha())
            total = len(lex_joined)
            if total > 8 and struct / total > 0.20:
                return True
            if alpha / total < 0.35:
                return True

    if key_str.startswith("lex:"):
        content = key_str[4:]
        if re.match(r"^-?\d+\.?\d*[eE]?[+-]?\d*$", content.strip()):
            return True
        if re.search(r"[A-Z]:[/\\]|\\\\|fairies/P\d{2}", content):
            return True
        if len(content) > 10:
            struct_chars = set('{}[]();,:"\\=<>|/')
            struct = sum(1 for c in content if c in struct_chars)
            alpha = sum(1 for c in content if c.isalpha())
            if struct / len(content) > 0.15:
                return True
            if alpha / len(content) < 0.35:
                return True
    return False


noise_keys = {k for k, n in nodes.items() if is_noise(k, n)}
clean_nodes = {k: v for k, v in nodes.items() if k not in noise_keys}
clean_edges = []
for e in edges:
    if isinstance(e, dict):
        if e.get("a", "") in noise_keys or e.get("b", "") in noise_keys:
            continue
    clean_edges.append(e)

print(f"  Nodes: {len(nodes):,} -> {len(clean_nodes):,} (removed {len(noise_keys):,})")
print(f"  Edges: {len(edges):,} -> {len(clean_edges):,} (removed {len(edges)-len(clean_edges):,})")

# Backup and write
backup = p30.parent / f"concept_graph.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
shutil.copy2(p30, backup)
data["nodes"] = clean_nodes
data["edges"] = clean_edges
with open(p30, "w", encoding="utf-8") as f:
    json.dump(data, f, separators=(",", ":"))
print(f"  New size: {p30.stat().st_size / 1024 / 1024:.1f} MB (was {backup.stat().st_size / 1024 / 1024:.1f} MB)")
print(f"  Backup: {backup.name}")
print("  Done!")
