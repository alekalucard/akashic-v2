#!/usr/bin/env python3
"""Dead-letter list for the postal system under code/.

Static reading only (ast, stdlib). Nothing under code/ is imported or run.

    python tools/dead_letters.py            # writes docs/DEAD_LETTERS.md
    python tools/dead_letters.py --stdout   # prints the report instead

Model (see section D of the report for the evidence):
  * Delivery rule used for A/B is the Rust TopicBus rule, which is what runs when
    postal_core is compiled: a subscription S receives intent P when
    P == S or P.startswith(S + ".")   (code/postal_core/src/topic_bus.rs:86-91).
  * The Python fallback is stricter: S receives P only when S is P itself, its
    first two segments, or its first segment (_python_fallback.py:986-1004).
    Topics that are live only under the Rust rule are listed separately.
  * Neither router has wildcards. A subscription on "x.*" or "*" is a literal string.
  * f-string {...} pieces are treated as one wildcard segment (no dots inside).
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CODE = REPO / "code"
OUT = REPO / "docs" / "DEAD_LETTERS.md"

# sys.path order at runtime (code/server.py:1525-1527): ROOT first, then
# postal_core/python, then fairies.
IMPORT_ROOTS = [CODE, CODE / "postal_core" / "python", CODE / "fairies"]
PLANE_DIRS = ("P00_", "P10_", "P20_", "P30_", "P40_", "P50_", "P60_")
SKIP_DIRS = {"__pycache__", ".git", "node_modules", "target", "venv", ".venv",
             "site-packages", "dist", "build"}

PUBLISH_METHODS = {"publish", "send", "emit", "post"}
SUBSCRIBE_METHODS = {"subscribe", "subscribe_cross_plane"}  # the latter wraps fabric.subscribe
UNSUBSCRIBE_METHODS = {"unsubscribe"}
ALWAYS_METHODS = {"publish", "subscribe", "unsubscribe", "subscribe_cross_plane"}   # any receiver
GATED_METHODS = {"send", "emit", "post"}                   # postal-ish receiver only
POSTAL_RECEIVER = re.compile(r"(post|postal|hub|bus|fabric)", re.I)
POSTAL_CLASS = re.compile(r"(postal|hub|bus|fabric|shim)", re.I)
TOPIC_KWARGS = ("topic", "intent", "channel")

WILD = "\x00"           # one wildcard segment piece inside a pattern
MAX_EXPAND = 64         # cap on combinations from one expression

CONTROLS_A = ["cortex.multimodal_bind", "sensory.audio.cochlea", "harmonic.audio_received",
              "cortex.harmonic_result", "cortex.multimodal_percept"]
CONTROLS_B = ["harmonic.query", "harmonic.perspectives", "cortex.harmonic_query",
              "cortex.harmonic_bind"]


# ─────────────────────────────────────────────────────────────── file census

def rel(p: Path) -> str:
    return p.relative_to(REPO).as_posix()


def is_test(p: Path) -> bool:
    parts = p.relative_to(CODE).parts
    name = p.name
    return ("tests" in parts[:-1] or "test" in parts[:-1]
            or name.startswith("test_") or name.endswith("_test.py"))


def census():
    files = []
    for dirpath, dirnames, filenames in os.walk(CODE):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            if fn.endswith(".py"):
                files.append(Path(dirpath) / fn)
    tests, shadowed, live = [], [], []
    for p in files:
        if is_test(p):
            tests.append(p)
            continue
        r = p.relative_to(CODE)
        if r.parts[0] == "fairies" and len(r.parts) > 2 and r.parts[1].startswith(PLANE_DIRS):
            winner = CODE.joinpath(*r.parts[1:])
            if winner.exists():
                shadowed.append((p, winner))
                continue
        live.append(p)
    return live, tests, shadowed


# ─────────────────────────────────────────────────────────────── module index

class Module:
    def __init__(self, path: Path, tree: ast.Module):
        self.path = path
        self.tree = tree
        self.consts: dict[str, list[ast.AST]] = defaultdict(list)
        self.classes: dict[str, ast.ClassDef] = {}
        self.imports: dict[str, tuple[str, str | None, int]] = {}  # name -> (module, attr, level)
        for node in tree.body:
            self._index_top(node)

    def _index_top(self, node):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    self.consts[t.id].append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value:
            self.consts[node.target.id].append(node.value)
        elif isinstance(node, ast.ClassDef):
            self.classes[node.name] = node
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                self.imports[a.asname or a.name] = (node.module or "", a.name, node.level)
        elif isinstance(node, ast.Import):
            for a in node.names:
                self.imports[a.asname or a.name.split(".")[0]] = (
                    a.name if a.asname else a.name.split(".")[0], None, 0)
        elif isinstance(node, (ast.If, ast.Try)):
            for sub in ast.iter_child_nodes(node):
                if isinstance(sub, ast.stmt):
                    self._index_top(sub)
            for h in getattr(node, "handlers", []):
                for sub in h.body:
                    self._index_top(sub)

    def class_attr(self, cls: str, name: str, seen=None) -> list[ast.AST]:
        seen = seen or set()
        if cls in seen or cls not in self.classes:
            return []
        seen.add(cls)
        c = self.classes[cls]
        vals = []
        for node in c.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == name:
                        vals.append(node.value)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                    and node.target.id == name and node.value:
                vals.append(node.value)
        if vals:
            return vals
        for b in c.bases:
            if isinstance(b, ast.Name):
                v = self.class_attr(b.id, name, seen)
                if v:
                    return v
        return []


_MODULES: dict[Path, Module | None] = {}
PARSE_ERRORS: list[tuple[Path, str]] = []


def load(path: Path) -> Module | None:
    if path in _MODULES:
        return _MODULES[path]
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src, filename=str(path))
        mod = Module(path, tree)
    except (SyntaxError, ValueError) as e:
        PARSE_ERRORS.append((path, f"{type(e).__name__}: {e}"))
        mod = None
    _MODULES[path] = mod
    return mod


def find_module(name: str, level: int, from_file: Path) -> Path | None:
    if level:
        base = from_file.parent
        for _ in range(level - 1):
            base = base.parent
        roots = [base]
    else:
        roots = IMPORT_ROOTS
    parts = name.split(".") if name else []
    for root in roots:
        cand = root.joinpath(*parts) if parts else root
        if cand.with_suffix(".py").is_file():
            return cand.with_suffix(".py")
        if (cand / "__init__.py").is_file():
            return cand / "__init__.py"
    return None


# ─────────────────────────────────────────────────────────────── resolver

class Unresolved(Exception):
    pass


class Ctx:
    def __init__(self, mod: Module, cls: ast.ClassDef | None, funcs: list):
        self.mod, self.cls, self.funcs = mod, cls, funcs


def _cat(a: list[str], b: list[str]) -> list[str]:
    out = [x + y for x in a for y in b]
    if len(out) > MAX_EXPAND:
        raise Unresolved("too many combinations")
    return out


def fmt_to_pattern(s: str, style: str) -> str:
    if style == "%":
        return re.sub(r"%(\([^)]*\))?[-#0 +]*\d*(\.\d+)?[sdifr]", WILD, s)
    return re.sub(r"\{[^{}]*\}", WILD, s)


def func_params(fn) -> set[str]:
    a = fn.args
    names = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs]
    if a.vararg:
        names.append(a.vararg.arg)
    if a.kwarg:
        names.append(a.kwarg.arg)
    return set(names)


def local_bindings(fn, name: str):
    """Assignments and for-loop bindings of `name` inside fn (not nested defs)."""
    assigns, loops = [], []
    stack = list(fn.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    assigns.append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.target.id == name and node.value:
            assigns.append(node.value)
        elif isinstance(node, ast.NamedExpr) and node.target.id == name:
            assigns.append(node.value)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            t = node.target
            if isinstance(t, ast.Name) and t.id == name:
                loops.append((node.iter, None))
            elif isinstance(t, ast.Tuple):
                for i, e in enumerate(t.elts):
                    if isinstance(e, ast.Name) and e.id == name:
                        loops.append((node.iter, i))
        elif isinstance(node, (ast.AugAssign,)) and isinstance(node.target, ast.Name) \
                and node.target.id == name:
            assigns.append(None)  # mutated -> give up
        stack.extend(ast.iter_child_nodes(node))
    return assigns, loops


class Resolver:
    def __init__(self):
        self.depth = 0

    # value: list[str] of topics (WILD marks wildcard pieces)
    def value(self, node, ctx: Ctx, in_fstring=False) -> list[str]:
        self.depth += 1
        try:
            if self.depth > 25:
                raise Unresolved("resolution too deep")
            return self._value(node, ctx, in_fstring)
        finally:
            self.depth -= 1

    def _value(self, node, ctx, in_fstring):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        if isinstance(node, ast.JoinedStr):
            outs = [""]
            for v in node.values:
                if isinstance(v, ast.Constant):
                    outs = _cat(outs, [str(v.value)])
                else:
                    inner = v.value
                    piece = [WILD]
                    # Substitute only true module/imported constants; self.X stays a
                    # wildcard because subclasses override it (e.g. ACTOR_NAME).
                    if isinstance(inner, ast.Name) and not self._is_local(inner.id, ctx):
                        try:
                            got = self.name(inner.id, ctx)
                            if len(got) == 1 and WILD not in got[0]:
                                piece = got
                        except Unresolved:
                            pass
                    outs = _cat(outs, piece)
            return outs
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return _cat(self.value(node.left, ctx), self.value(node.right, ctx))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) \
                and isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
            return [fmt_to_pattern(node.left.value, "%")]
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "format" and isinstance(node.func.value, ast.Constant) \
                and isinstance(node.func.value.value, str):
            return [fmt_to_pattern(node.func.value.value, "{}")]
        if isinstance(node, ast.IfExp):
            return self.value(node.body, ctx) + self.value(node.orelse, ctx)
        if isinstance(node, ast.Name):
            return self.name(node.id, ctx)
        if isinstance(node, ast.Attribute):
            return self.attr(node, ctx)
        raise Unresolved("expression")

    def _is_local(self, name, ctx):
        for fn in reversed(ctx.funcs):
            if name in func_params(fn):
                return True
            a, l = local_bindings(fn, name)
            if a or l:
                return True
        return False

    def name(self, name: str, ctx: Ctx) -> list[str]:
        for fn in reversed(ctx.funcs):
            assigns, loops = local_bindings(fn, name)
            if assigns or loops:
                out = []
                for a in assigns:
                    if a is None:
                        raise Unresolved("reassigned with +=")
                    out += self.value(a, ctx)
                for it, idx in loops:
                    out += self.iterate(it, idx, ctx)
                return out
            if name in func_params(fn):
                raise Unresolved("parameter")
        return self.module_name(ctx.mod, name)

    def module_name(self, mod: Module, name: str, hops=0) -> list[str]:
        if name in mod.consts:
            out = []
            sub = Ctx(mod, None, [])
            for v in mod.consts[name]:
                out += self.value(v, sub)
            return out
        if name in mod.imports and hops < 4:
            modname, attr, level = mod.imports[name]
            if attr is None:
                raise Unresolved("module object")
            target = find_module(modname, level, mod.path)
            other = load(target) if target else None
            if other is None:
                raise Unresolved("import outside repo")
            return self.module_name(other, attr, hops + 1)
        raise Unresolved("undefined name")

    def attr(self, node: ast.Attribute, ctx: Ctx) -> list[str]:
        base = node.value
        if isinstance(base, ast.Name):
            if base.id in ("self", "cls") and ctx.cls is not None:
                vals = ctx.mod.class_attr(ctx.cls.name, node.attr)
                if vals:
                    out = []
                    for v in vals:
                        out += self.value(v, Ctx(ctx.mod, ctx.cls, []))
                    return out
                raise Unresolved("instance attribute")
            if base.id in ctx.mod.classes:
                vals = ctx.mod.class_attr(base.id, node.attr)
                if vals:
                    out = []
                    for v in vals:
                        out += self.value(v, Ctx(ctx.mod, ctx.mod.classes[base.id], []))
                    return out
            if base.id in ctx.mod.imports:
                modname, attr, level = ctx.mod.imports[base.id]
                full = modname if attr is None else f"{modname}.{attr}" if modname else attr
                target = find_module(full, level, ctx.mod.path)
                other = load(target) if target else None
                if other is not None:
                    return self.module_name(other, node.attr)
                # imported class: from x import Cls; Cls.ATTR
                if attr is not None:
                    target = find_module(modname, level, ctx.mod.path)
                    other = load(target) if target else None
                    if other is not None and attr in other.classes:
                        vals = other.class_attr(attr, node.attr)
                        out = []
                        for v in vals:
                            out += self.value(v, Ctx(other, other.classes[attr], []))
                        if out:
                            return out
        raise Unresolved("attribute")

    def iterate(self, it, idx, ctx: Ctx) -> list[str]:
        # dict.items()/keys()
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Attribute) \
                and it.func.attr in ("items", "keys") and not it.args:
            if it.func.attr == "items" and idx not in (0,):
                raise Unresolved("loop over dict values")
            return self.iterate(it.func.value, None, ctx)
        elems = self.container(it, ctx)
        out = []
        for e in elems:
            if idx is not None:
                if isinstance(e, (ast.Tuple, ast.List)) and len(e.elts) > idx:
                    e = e.elts[idx]
                else:
                    raise Unresolved("loop element shape")
            out += self.value(e, ctx)
        return out

    def container(self, node, ctx: Ctx, hops=0) -> list[ast.AST]:
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return list(node.elts)
        if isinstance(node, ast.Dict):
            return [k for k in node.keys if k is not None]
        if hops > 4:
            raise Unresolved("container too deep")
        if isinstance(node, ast.Name):
            for fn in reversed(ctx.funcs):
                assigns, loops = local_bindings(fn, node.id)
                if assigns and not loops and all(a is not None for a in assigns):
                    out = []
                    for a in assigns:
                        out += self.container(a, ctx, hops + 1)
                    return out
                if assigns or loops or node.id in func_params(fn):
                    raise Unresolved("loop iterable")
            if node.id in ctx.mod.consts:
                out = []
                for v in ctx.mod.consts[node.id]:
                    out += self.container(v, Ctx(ctx.mod, None, []), hops + 1)
                return out
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id in ("self", "cls") and ctx.cls is not None:
            vals = ctx.mod.class_attr(ctx.cls.name, node.attr)
            if vals:
                out = []
                for v in vals:
                    out += self.container(v, Ctx(ctx.mod, ctx.cls, []), hops + 1)
                return out
        raise Unresolved("loop iterable")


# ─────────────────────────────────────────────────────────────── site scan

class Site:
    __slots__ = ("kind", "file", "line", "expr", "topics", "reason", "cls", "actor", "method")

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    @property
    def loc(self):
        return f"{rel(self.file)}:{self.line}"


def receiver_name(func: ast.Attribute) -> str:
    v = func.value
    while isinstance(v, ast.Call):
        v = v.func
    if isinstance(v, ast.Attribute):
        return v.attr
    if isinstance(v, ast.Name):
        return v.id
    return ""


def actor_name(mod: Module, cls: ast.ClassDef | None) -> str:
    if cls is None:
        return ""
    for v in mod.class_attr(cls.name, "ACTOR_NAME"):
        try:
            got = Resolver().value(v, Ctx(mod, None, []))
        except Unresolved:
            continue
        if len(got) == 1 and WILD not in got[0]:
            return got[0]
    return ""


def topic_arg(call: ast.Call):
    if call.args and not isinstance(call.args[0], ast.Starred):
        return call.args[0]
    for kw in call.keywords:
        if kw.arg in TOPIC_KWARGS:
            return kw.value
    return None


class Scanner(ast.NodeVisitor):
    def __init__(self, mod: Module, sites: list):
        self.mod, self.sites = mod, sites
        self.cls_stack, self.fn_stack = [], []
        self.res = Resolver()

    def visit_ClassDef(self, node):
        self.cls_stack.append(node)
        saved, self.fn_stack = self.fn_stack, []
        self.generic_visit(node)
        self.fn_stack = saved
        self.cls_stack.pop()

    def visit_FunctionDef(self, node):
        self.fn_stack.append(node)
        self.generic_visit(node)
        self.fn_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node):
        self.generic_visit(node)
        f = node.func
        if not isinstance(f, ast.Attribute):
            return
        m = f.attr
        if m not in ALWAYS_METHODS and m not in GATED_METHODS:
            return
        cls = self.cls_stack[-1] if self.cls_stack else None
        recv = receiver_name(f)
        if m in GATED_METHODS:
            if recv in ("self", "cls"):
                if cls is None or not (POSTAL_CLASS.search(cls.name) or actor_name(self.mod, cls)):
                    return
            elif not POSTAL_RECEIVER.search(recv) or recv.lower() in ("requests",):
                return
        arg = topic_arg(node)
        if arg is None:
            return  # e.g. bus.subscribe() with no topic -> not a topic site
        kind = ("pub" if m in PUBLISH_METHODS else "sub" if m in SUBSCRIBE_METHODS else "unsub")
        ctx = Ctx(self.mod, cls, list(self.fn_stack))
        try:
            topics = sorted(set(self.res.value(arg, ctx)))
            reason = ""
        except Unresolved as e:
            topics, reason = [], str(e)
        if topics and all(t.replace(WILD, "").strip(".") == "" for t in topics):
            topics, reason = [], "pure wildcard"
        if not topics and not reason:
            reason = "empty class-level list (subclasses fill it)"
        self.sites.append(Site(kind=kind, file=self.mod.path, line=node.lineno,
                               expr=ast.unparse(arg), topics=topics, reason=reason,
                               cls=cls.name if cls else "", actor=actor_name(self.mod, cls),
                               method=f"{recv}.{m}"))


def declared_subscriptions(paths):
    """Classes that declare SUBSCRIPTIONS = [...] and whether anything in reach reads it."""
    out = []
    for p in paths:
        mod = load(p)
        if mod is None:
            continue
        reads = "self.SUBSCRIPTIONS" in p.read_text(encoding="utf-8", errors="replace")
        for c in mod.classes.values():
            for node in c.body:
                tgt = node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else \
                    node.target if isinstance(node, ast.AnnAssign) else None
                if isinstance(tgt, ast.Name) and tgt.id == "SUBSCRIPTIONS" and \
                        isinstance(getattr(node, "value", None), (ast.List, ast.Tuple)) and node.value.elts:
                    bases = [ast.unparse(b) for b in c.bases]
                    out.append((p, node.lineno, c.name, bases, len(node.value.elts), reads))
    return out


def scan(paths) -> list[Site]:
    sites = []
    for p in paths:
        mod = load(p)
        if mod is not None:
            Scanner(mod, sites).visit(mod.tree)
    return sites


# ─────────────────────────────────────────────────────────────── matching

def _seg_re(seg: str):
    return re.compile("^" + "[^.]+".join(re.escape(x) for x in seg.split(WILD)) + "$")


def seg_overlap(a: str, b: str) -> bool:
    wa, wb = WILD in a, WILD in b
    if not wa and not wb:
        return a == b
    if wa and wb:
        return True  # two patterns: possible overlap
    pat, lit = (a, b) if wa else (b, a)
    if "*" in lit:
        return False  # a literal "*" is just a character to the router, never a match target
    return bool(_seg_re(pat).match(lit))


def segs(t: str):
    return t.split(".")


def rust_match(sub: str, pub: str) -> bool:
    s, p = segs(sub), segs(pub)
    return len(s) <= len(p) and all(seg_overlap(x, y) for x, y in zip(s, p))


def python_match(sub: str, pub: str) -> bool:
    s, p = segs(sub), segs(pub)
    if len(s) == len(p):
        return all(seg_overlap(x, y) for x, y in zip(s, p))
    return len(s) in (1, 2) and len(s) < len(p) and all(seg_overlap(x, y) for x, y in zip(s, p))


def show(t: str) -> str:
    return t.replace(WILD, "{*}")


# ─────────────────────────────────────────────────────────────── report

def md_escape(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def dead_and_deaf(sites):
    pubs, subs = set(), set()
    for x in sites:
        if x.kind == "pub":
            pubs.update(x.topics)
        elif x.kind == "sub":
            subs.update(x.topics)
    dead = {p for p in pubs if not any(rust_match(s, p) for s in subs)}
    deaf = {s for s in subs if not any(rust_match(s, p) for p in pubs)}
    return dead, deaf


def import_counts(shadowed):
    """How often each shadowed module is imported bare (winner) vs as fairies.X (the copy)."""
    texts = []
    for p in CODE.rglob("*.py"):
        if not any(d in SKIP_DIRS for d in p.parts):
            texts.append(p.read_text(encoding="utf-8", errors="replace"))
    out = {}
    for p, win in shadowed:
        parts = list(win.relative_to(CODE).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        mod = re.escape(".".join(parts))
        bare = re.compile(r"(?:from|import)\s+" + mod + r"\b")
        fq = re.compile(r"(?:from|import)\s+fairies\." + mod + r"\b")
        out[p] = (sum(len(bare.findall(t)) for t in texts), sum(len(fq.findall(t)) for t in texts))
    return out


def build_report(live, tests, shadowed, sites, test_sites, shadow_sites, declared) -> str:
    pubs = [s for s in sites if s.kind == "pub"]
    subs = [s for s in sites if s.kind == "sub"]
    unsubs = [s for s in sites if s.kind == "unsub"]
    pub_topics = defaultdict(list)
    sub_topics = defaultdict(list)
    for s in pubs:
        for t in s.topics:
            pub_topics[t].append(s)
    for s in subs:
        for t in s.topics:
            sub_topics[t].append(s)
    sub_keys, pub_keys = list(sub_topics), list(pub_topics)

    rust_live, py_live = {}, {}
    for p in pub_keys:
        rust_live[p] = [s for s in sub_keys if rust_match(s, p)]
        py_live[p] = [s for s in sub_keys if python_match(s, p)]
    dead = sorted(p for p in pub_keys if not rust_live[p])
    def is_catchall(sub):
        return "." not in sub and WILD not in sub
    catchall_only = sorted(p for p in pub_keys if rust_live[p] and "." in p
                           and all(is_catchall(x) for x in rust_live[p]))
    rust_only = sorted(p for p in pub_keys if rust_live[p] and not py_live[p])
    deaf = sorted(s for s in sub_keys if not any(rust_match(s, p) for p in pub_keys))
    unresolved = [s for s in sites if not s.topics and s.kind in ("pub", "sub")]

    dead_sites = [s for p in dead for s in pub_topics[p]]
    L = []
    w = L.append
    w("# DEAD LETTERS: the postal system under code/")
    w("")
    w("Generated by `python tools/dead_letters.py` (stdlib only, static `ast` read; nothing under")
    w("code/ is imported or run). Regenerate after any change to publish or subscribe sites.")
    w("")
    w("## Summary")
    w("")
    w(f"* Python files scanned (live): **{len(live)}**. Excluded tests: {len(tests)}. "
      f"Shadowed copies: {len(shadowed)}. Unparseable: {len(PARSE_ERRORS)}.")
    w(f"* Sites: {len(pubs)} publish, {len(subs)} subscribe, {len(unsubs)} unsubscribe.")
    w(f"* Distinct resolved topics: {len(pub_topics)} published, {len(sub_topics)} subscribed.")
    w(f"* **A. Dead letters: {len(dead)} topics** ({len(dead_sites)} publish sites).")
    w(f"* **B. Deaf ears: {len(deaf)} topics.**")
    n_unres_pub = sum(1 for s in unresolved if s.kind == 'pub')
    w(f"* **C. Unresolved: {len(unresolved)} sites** ({n_unres_pub} publish, "
      f"{len(unresolved) - n_unres_pub} subscribe).")
    w(f"* Live only under the Rust rule, dead on the Python fallback: {len(rust_only)} topics (A2).")
    w(f"* Delivered ONLY to a base-topic catch-all (e.g. `cortex`), no purpose-built ear: "
      f"{len(catchall_only)} topics (A3).")
    w("")
    w("Caveats: an UNRESOLVED subscriber (section C) may be the missing ear for a letter in A, and an")
    w("UNRESOLVED publisher may be the missing voice for an ear in B. Treat A and B as \"no *static*")
    w("partner found\", then check C for the topic's prefix before calling it dead.")
    w("")

    # ── A
    w("## A. DEAD LETTERS: published, no matching subscriber")
    w("")
    w("Grouped by sender file and class. Matching uses the Rust prefix rule (the more permissive one),")
    w("so everything here is also dead on the Python fallback.")
    w("")
    groups = defaultdict(lambda: defaultdict(list))
    for p in dead:
        for s in pub_topics[p]:
            groups[(rel(s.file), s.cls, s.actor)][p].append(s)
    for (f, cls, actor) in sorted(groups):
        label = f"`{f}`"
        if cls:
            label += f": class `{cls}`"
        if actor:
            label += f" (ACTOR_NAME `{actor}`)"
        w(f"### {label}")
        w("")
        w("| topic | sites | file:line |")
        w("|---|---|---|")
        for p, ss in sorted(groups[(f, cls, actor)].items()):
            locs = ", ".join(f":{s.line}" for s in sorted(ss, key=lambda x: x.line))
            w(f"| `{md_escape(show(p))}` | {len(ss)} | {locs} |")
        w("")

    w("### A2. Live only under the Rust rule (deep prefix, 3+ segments)")
    w("")
    w("A subscriber at depth >= 3 receives deeper intents in Rust (`starts_with(S + \".\")`) but not in")
    w("the Python fallback, which only checks the exact intent, its first two segments and its first.")
    w("If postal_core falls back to Python, these become dead letters.")
    w("")
    if rust_only:
        w("| published topic | Rust-only subscriber(s) | publish sites |")
        w("|---|---|---|")
        for p in rust_only:
            locs = ", ".join(s.loc for s in pub_topics[p][:4]) + (" ..." if len(pub_topics[p]) > 4 else "")
            w(f"| `{md_escape(show(p))}` | {', '.join('`'+md_escape(show(x))+'`' for x in rust_live[p][:4])} | {locs} |")
    else:
        w("None.")
    w("")

    w("### A3. Heard only by a base-topic catch-all")
    w("")
    w("These letters are delivered, but only to a subscriber on the bare first segment (e.g. `cortex`,")
    w("`memory`), which receives every intent in that namespace under both routers. No subscriber")
    w("asked for the topic itself. Most come from AttentionControllerFairy's \"squirrel mode\"")
    w("(`code/fairies/P30_Cognition/AttentionControllerFairy/fairy.py:383-403`), which listens to whole")
    w("namespaces to score salience. The letter is read, but only as a generic attention ping.")
    w("Without that catch-all, every row below would be a dead letter.")
    w("")
    w("| topic | only ear(s) | publish sites |")
    w("|---|---|---|")
    for p in catchall_only:
        ears = "; ".join(f"`{x}` ({', '.join(s.loc for s in sub_topics[x])})" for x in rust_live[p])
        locs = ", ".join(s.loc for s in pub_topics[p][:3]) + (" ..." if len(pub_topics[p]) > 3 else "")
        w(f"| `{md_escape(show(p))}` | {ears} | {locs} |")
    w("")

    # ── B
    w("## B. DEAF EARS: subscribed, no matching publisher")
    w("")
    w("| topic | subscriber file:line | class (ACTOR_NAME) |")
    w("|---|---|---|")
    for t in deaf:
        for s in sorted(sub_topics[t], key=lambda x: (rel(x.file), x.line)):
            who = s.cls + (f" ({s.actor})" if s.actor else "")
            w(f"| `{md_escape(show(t))}` | {s.loc} | {md_escape(who)} |")
    w("")

    # ── C
    w("## C. UNRESOLVED: topic expressions that cannot be decided statically")
    w("")
    w("Never guessed. `reason` says why: `parameter` means the topic is forwarded from a caller")
    w("(plumbing: hubs, shims, wrappers); `instance attribute` means it is set at runtime.")
    w("")
    by_reason = defaultdict(int)
    for s in unresolved:
        by_reason[s.reason] += 1
    w("Counts by reason: " + ", ".join(f"{k}: {v}" for k, v in sorted(by_reason.items(), key=lambda x: -x[1])) + ".")
    w("")
    w("| side | file:line | call | topic expression | reason |")
    w("|---|---|---|---|---|")
    for s in sorted(unresolved, key=lambda x: (rel(x.file), x.line)):
        w(f"| {s.kind} | {s.loc} | `{md_escape(s.method)}` | `{md_escape(s.expr[:90])}` | {s.reason} |")
    w("")

    # ── D
    w("## D. Router rules (step 1) and the Python-vs-Rust difference")
    w("")
    w(ROUTER_RULES.strip())
    w("")

    # ── E
    w("## E. CONTROL")
    w("")
    w("| expected | topic | result | evidence |")
    w("|---|---|---|---|")
    ctrl_ok = True
    for t in CONTROLS_A:
        if t in dead:
            ev = ", ".join(s.loc for s in pub_topics[t])
            w(f"| A | `{t}` | PASS (in A) | published at {ev} |")
        elif t in catchall_only:
            ctrl_ok = False
            ev = "; ".join(f"`{show(x)}` at {', '.join(s.loc for s in sub_topics[x])}" for x in rust_live[t])
            w(f"| A | `{t}` | MAP CORRECTION: catch-all ear only (A3) | {ev} |")
        elif t in pub_topics:
            ctrl_ok = False
            ev = "; ".join(f"`{show(x)}` at {', '.join(s.loc for s in sub_topics[x])}" for x in rust_live[t])
            w(f"| A | `{t}` | FAIL: has subscriber | {ev} |")
        else:
            ctrl_ok = False
            w(f"| A | `{t}` | FAIL: no publish site found | scan missed it |")
    for t in CONTROLS_B:
        if t in deaf:
            ev = ", ".join(s.loc for s in sub_topics[t])
            w(f"| B | `{t}` | PASS (in B) | subscribed at {ev} |")
        elif t in sub_topics:
            ctrl_ok = False
            ev = "; ".join(f"`{show(p)}` at {', '.join(s.loc for s in pub_topics[p])}"
                           for p in pub_keys if rust_match(t, p))
            w(f"| B | `{t}` | FAIL: has publisher | {ev} |")
        else:
            ctrl_ok = False
            w(f"| B | `{t}` | FAIL: no subscribe site found | scan missed it |")
    w("")
    if ctrl_ok:
        w("Control verdict: **all 9 pass**.")
    else:
        w("Control verdict: **not all in A/B; see rows.** A MAP CORRECTION row is not a scan failure: the")
        w("scan found a real subscriber, shown with file:line. It is a base-topic catch-all, so the router")
        w("delivers the letter even though no fairy asked for that topic (see A3).")
    w("")

    # ── F
    w("## F. HOW TO CHECK: three rows to verify by hand")
    w("")
    w("Run from the repo root. Each publish line should appear; no subscribe line should (for A),")
    w("or no publish line should (for B). Remember a subscriber on a PREFIX also counts: for")
    w("`a.b.c` also grep `subscribe(\"a.b\"` and `subscribe(\"a\"`.")
    w("")
    samples = [("A", "sensory.audio.cochlea"), ("A", "harmonic.audio_received"), ("B", "cortex.harmonic_query")]
    for i, (sec, t) in enumerate(samples, 1):
        if sec == "A":
            rows = pub_topics.get(t, [])
            w(f"{i}. **{sec}: `{t}`**, published at {', '.join(s.loc for s in rows)}.")
            w("")
            w("```bash")
            w(f"grep -rn --include='*.py' '{t}' code/ | grep -v '/tests/'")
            prefixes = "|".join(re.escape(".".join(t.split(".")[:k])) for k in range(1, len(t.split("."))))
            w(f"grep -rnE --include='*.py' \"subscribe\\(\\s*f?[\\\"']({prefixes})[\\\"']\" code/")
            w(f"grep -rnE --include='*.py' \"\\([\\\"']({prefixes})[\\\"'],\" code/   # tuple lists fed to a subscribe loop")
            w("```")
            w("")
            w("   Expected: the first grep shows only `.publish(` lines (and comments or docstrings). The other two")
            w("   show no subscriber on a prefix of the topic.")
        else:
            rows = sub_topics.get(t, [])
            w(f"{i}. **{sec}: `{t}`**, subscribed at {', '.join(s.loc for s in rows)}.")
            w("")
            w("```bash")
            w(f"grep -rn --include='*.py' '{t}' code/ | grep -v '/tests/'")
            w("```")
            w("")
            w("   Expected: only the `.subscribe(` call, its log string and the handler docstring; no `.publish(`.")
        w("")

    w("## Declared but never wired: SUBSCRIPTIONS class lists")
    w("")
    w("`fairy_template/unified.py:253` subscribes every entry of `self.SUBSCRIPTIONS`. The organ template")
    w("(`fairies.P00_Autonomic.organ_template.MyFairy`) has no such loop. A fairy that inherits the organ")
    w("template and declares `SUBSCRIPTIONS` without reading it itself gets no subscription from that list.")
    w("Those entries are NOT counted as subscribers above.")
    w("")
    w("| class | file:line | bases | entries | file reads self.SUBSCRIPTIONS |")
    w("|---|---|---|---|---|")
    for p, line, cname, bases, n, reads in declared:
        w(f"| {cname} | {rel(p)}:{line} | {md_escape(', '.join(bases))} | {n} | {'yes' if reads else '**no**'} |")
    w("")

    w("To see an A3 case by hand: `grep -n '(\"cortex\",' code/fairies/P30_Cognition/AttentionControllerFairy/fairy.py`")
    w("shows the bare `cortex` entry that line 403 subscribes in a loop. That entry is why")
    w("`cortex.multimodal_bind` is delivered.")
    w("")

    # ── listings
    w("## Excluded and shadowed files")
    w("")
    w("### Shadowed copies (code/fairies/P*/X loses to code/P*/X, first on sys.path)")
    w("")
    w("Sites inside shadowed copies are NOT counted above. Caveat: this applies to `import P00_Autonomic.x`")
    w("style imports. A module loaded by file path (`spec_from_file_location`) is not shadowed.")
    w("")
    w("**Surprise: the rule above holds only for bare imports.** Most code imports these modules as")
    w("`fairies.P00_Autonomic...`, a different package name, which always resolves to the code/fairies/ copy.")
    w("The two right-hand columns count import statements (whole code/ tree, tests included) of each form.")
    w("Where `fairies.X` imports outnumber bare ones, the \"shadowed\" copy is the one most callers run.")
    w("")
    ic = import_counts(shadowed)
    w("| shadowed copy | winning copy | pub/sub sites in shadowed copy | bare imports (winner) | `fairies.` imports (copy) |")
    w("|---|---|---|---|---|")
    for p, win in shadowed:
        n = sum(1 for s in shadow_sites if s.file == p)
        nb, nf = ic[p]
        w(f"| {rel(p)} | {rel(win)} | {n} | {nb} | {nf} |")
    w("")
    w("### Sensitivity: counting the code/fairies/ copies as live too")
    w("")
    d0, f0 = dead_and_deaf(sites)
    d1, f1 = dead_and_deaf(sites + shadow_sites)
    w(f"With the {len(shadow_sites)} sites from the shadowed copies added: A = {len(d1)} "
      f"(was {len(d0)}), B = {len(f1)} (was {len(f0)}).")
    w("")
    for title, a, b in (("Dead letters that gain a subscriber", d0 - d1, None),
                        ("New dead letters (published only in a shadowed copy)", d1 - d0, None),
                        ("Deaf ears that gain a publisher", f0 - f1, None),
                        ("New deaf ears (subscribed only in a shadowed copy)", f1 - f0, None)):
        w(f"* {title}: " + (", ".join(f"`{md_escape(show(x))}`" for x in sorted(a)) or "none") + ".")
    w("")
    w(f"### Test files excluded ({len(tests)} files, {len(test_sites)} sites)")
    w("")
    w("<details><summary>list</summary>")
    w("")
    for p in tests:
        n = sum(1 for s in test_sites if s.file == p)
        w(f"* {rel(p)}" + (f" ({n} sites)" if n else ""))
    w("")
    w("</details>")
    w("")
    if PARSE_ERRORS:
        w("### Unparseable files (not scanned)")
        w("")
        for p, e in PARSE_ERRORS:
            w(f"* {rel(p)}: {md_escape(e)}")
        w("")
    return "\n".join(L) + "\n", dict(dead=len(dead), deaf=len(deaf), unresolved=len(unresolved),
                                     rust_only=len(rust_only), catchall=len(catchall_only),
                                     controls_ok=ctrl_ok)


ROUTER_RULES = r"""
Nothing in either router understands wildcards (`*`, `#`, `>`). Subscribing to `cortex.*` subscribes to the
literal string `cortex.*`, which no publish ever equals. Prefix behaviour comes only from the dot rules below.

**Who decides.** `code/postal_core/python/postal_core/__init__.py:23-29` imports the Rust `PostalCore` when the
extension is compiled, otherwise the Python fallback. Fairies don't call it directly: `TensorFabric`
wraps it in `_BaseTopicPostal` (`tensor_fabric.py:196`), which subscribes on the BASE topic pool with the
full intent as a filter (`:281`), and publishes the real intent routed into the base pool (`:363`).

**Rust (`code/postal_core/src/topic_bus.rs`).**
* Pools are keyed by the base topic (first segment). Subscribers carry `intent_filter`.
* `Subscriber::wants` (`:86-91`): `intent == filter || intent.starts_with(filter + ".")`. Any depth:
  a subscriber on `fairy.heartbeat` receives `fairy.heartbeat.routed.X`. `intent_filter = None` (a raw
  subscribe with no intent) receives everything in the pool.
* `publish_routed` (`:217-251`) increments `published` whether or not anyone wanted it (`:250`). An intent
  with no matching subscriber is counted as published and silently discarded; no drop is recorded.
* `_BaseTopicPostal._pool_dispatch` (`tensor_fabric.py:270`) applies the same `==` / `startswith(intent+'.')`
  test again on the Python side, so the two layers agree.

**Python fallback (`code/postal_core/python/postal_core/_python_fallback.py`).**
* `subscribe` (`:813-849`) stores the handler under the exact intent string in `_subscribers`.
* `publish` (`:934-1112`) collects subscribers from exactly three keys (`:986-1004`): the full intent, its
  first two segments, and its first segment. Nothing deeper. A subscriber on `a.b.c` receives `a.b.c` but
  NOT `a.b.c.d`.
* With zero subscribers the loop body never runs, `messages_published` is still incremented (`:1059`),
  `messages_dropped` is not. No error, no log: the void.
* `_BaseTopicPostal.publish` on the fallback (`tensor_fabric.py:367-436`) first looks on the bridge for exact
  and base-topic handlers only; if it finds any it dispatches to those and does NOT consult the core, so a
  2-level subscriber on the same bridge (e.g. `cortex.bind` for `cortex.bind.audio`) can be skipped when an
  exact or base handler also exists. If it finds none it calls core `publish` (rules above).
* Critical topics (`CRITICAL_VOLUME_TOPICS`) may go through `PoolRouter.publish` first (`pool_router.py:242`),
  which is EXACT-match only (`self._subs_by_topic.get(topic)`). If it dispatches to >=1 handler,
  the legacy path is skipped (`_python_fallback.py:957-960`), so base or 2-level subscribers miss it.

**The difference.**

| case | Rust | Python fallback |
|---|---|---|
| sub `a`, pub `a.b.c.d` | delivered | delivered (base) |
| sub `a.b`, pub `a.b.c.d` | delivered | delivered (2-level) |
| sub `a.b.c`, pub `a.b.c.d` | delivered | **dropped** |
| sub `a.b`, pub `a` | dropped | dropped |
| sub `a.*`, pub `a.x` | dropped | dropped |
| no subscriber | counted published, discarded | counted published (`:1059`), discarded |

This report uses the Rust rule for A and B, and lists the third row's victims in A2.

**Other buses with their own rules (NOT the postal router, not used for A/B):**
`postal_core/python/postal_core/akp_server.py:193-209` (segment `*` wildcards, AKP websocket server),
`fairies/P00_Autonomic/postal_bridge/sqlite_channel.py:529` (`.*` suffix), `fairies/P00_Autonomic/mini_stubs/mini_cognition.py:161-165`
(`*` and `.*`), `fairies/P20_Somatic/SomaticMindFairy/boot_monitor_system.py:176` (`*`). A `*` subscription sent
to the real postal router through one of these is still a literal string there.
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()
    live, tests, shadowed = census()
    sites = scan(live)
    test_sites = scan(tests)
    shadow_sites = scan([p for p, _ in shadowed])
    text, counts = build_report(live, tests, shadowed, sites, test_sites, shadow_sites,
                                declared_subscriptions(live))
    if args.stdout:
        sys.stdout.write(text)
    else:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {rel(OUT)}")
    print("A dead letters: {dead}  B deaf ears: {deaf}  C unresolved: {unresolved}  "
          "A2 rust-only: {rust_only}  A3 catch-all only: {catchall}  controls ok: {controls_ok}".format(**counts), file=sys.stderr)


if __name__ == "__main__":
    main()
