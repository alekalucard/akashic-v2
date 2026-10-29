"""Run the mirror's FairyScanner (class extracted by AST, no package import) and diff old vs new B2 exclude."""
import ast, re, sys, inspect, importlib, importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type

REPO = Path("/home/user/akashic-v2/.claude/worktrees/agent-a5d8eb778d70dc5cb")
src = (REPO / "code/directory/migration.py").read_text(encoding="utf-8")
t = ast.parse(src)
cls = next(n for n in t.body if isinstance(n, ast.ClassDef) and n.name == "FairyScanner")
ns = dict(re=re, sys=sys, inspect=inspect, importlib=importlib, Path=Path, Any=Any, Dict=Dict, List=List,
          Optional=Optional, Set=Set, Type=Type, FairyRegistry=object, FairyRecord=object, _ROOT=REPO / "code")
exec(compile(ast.Module([cls], []), "migration_FairyScanner", "exec"), ns)
sc = ns["FairyScanner"](REPO / "code" / "fairies")
allf = []
for p in ["P00_Autonomic", "P10_Memory", "P20_Somatic", "P30_Cognition", "P40_Sensory", "P50_Persona", "P60_Executive"]:
    allf += sc.scan_plane(p)
# same de-dup as server.py:4963-4972
seen, names = set(), []
for e in allf:
    n = e.get("actor_name") or e.get("name", "")
    c = e.get("name", "")
    if not n or n in seen:
        continue
    seen.add(n)
    if c:
        seen.add(c)
    names.append((n, c, e.get("file")))
print("registered names:", len(names))
EX = {"my_organ", "organ.clerk.primrose", "organ_template_seed", "MockRecallFairy"}
SUF = ("Shadow",)
old = lambda n: n in EX or n.endswith(SUF)
new = lambda n: n in EX or n.lower().endswith(tuple(x.lower() for x in SUF))
for n, c, f in names:
    if new(n) or old(n):
        tag = "NEWLY-EXCLUDED" if old(n) != new(n) else "excluded-both"
        print(tag, n, "| class", c, "|", str(f).replace(str(REPO) + "/", ""))
print("contains fairy_citizens.reg.michael:", any(n == "fairy_citizens.reg.michael" for n, _, _ in names))
