"""W8 tests: stranded letters (misspelled publishers, literal-wildcard ears). Static (ast) only.

Nothing under code/ is imported or run. Topic expressions at subscribe/publish sites are read
with ast and evaluated with eval() in a namespace that holds only the file's own `_prefix_ear`
helper (a pure function, exec'd alone) and `os`. Delivery is checked with the router rules of
tools/dead_letters.py (Rust: rust_match, Python fallback: python_match).

    python3 -m unittest tools/tests/test_w8_ears.py

W8_CODE_ROOT=<dir> runs the same tests against another copy of the 7 files (laid out under
<dir>/code/...); used by tools/tests/run_w8_control_and_mutants.py for control and mutants.
"""
import ast
import importlib.util
import os
import subprocess
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
ROOT = Path(os.environ.get("W8_CODE_ROOT", REPO))
BASE_REF = os.environ.get("W8_BASE_REF", "origin/nous/w3-dead-letter-triage")

EMB = "code/fairies/P00_Autonomic/EmbodimentFairy/fairy.py"
FOR = "code/fairies/P10_Memory/ForensicScribeFairy/fairy.py"
SEN = "code/fairies/P40_Sensory/sensory_integration.py"
CAR = "code/fairies/P20_Somatic/SomaticMindFairy/mixins/cardinal.py"
SOM = "code/fairies/P00_Autonomic/SomaticMind/somatic_mind.py"
NOU = "code/fairies/P30_Cognition/cognition/nous_trainer.py"
PRO = "code/fairies/P20_Somatic/SomaticMindFairy/mixins/profile.py"
FILES = [EMB, FOR, SEN, CAR, SOM, NOU, PRO]

# ear (as written today) -> (files holding it, letters from docs/nous/W3/TRIAGE.md rows 3-21)
EARS = {
    "umf.signal.*": ([EMB], ["umf.signal.chemistry", "umf.signal.body_state", "umf.signal.visual",
                             "umf.signal.novelty", "umf.signal.sensory", "umf.signal.urgent"]),
    "tracer.*": ([FOR], ["tracer"]),
    "sensory.window.*": ([SEN], ["sensory.window.intent", "sensory.window.fairy"]),
    "shadow.*": ([FOR], ["shadow.error", "shadow.metrics"]),
    "blueprint.*": ([CAR, SOM], ["blueprint.reload.starting", "blueprint.reload.success",
                                 "blueprint.reload.failed", "blueprint.watcher.baseline",
                                 "blueprint.watcher.boot_diff", "blueprint.fairy.added",
                                 "blueprint.contract"]),
    "diary.*": ([CAR, SOM], ["diary.entry"]),
}
# literal-wildcard ears in the same files that W8 must NOT touch (out of scope)
UNTOUCHED = {FOR: ["telemetry.*"], EMB: ["goal.feeling.*", "system.health.*"],
             CAR: ["health.*"], SOM: ["health.*", "consciousness.*"]}
SPELL = {NOU: ("goal_scheduler.inject", "goal.scheduler.inject"),
         PRO: ("skill.levelup", "skill.level_up")}

SUB = {"subscribe", "receive", "subscribe_cross_plane"}
PUB = {"publish", "route", "send", "emit"}
LISTS = {"SUBSCRIPTIONS", "CARDINAL_SUBSCRIPTIONS"}


def _tool():
    spec = importlib.util.spec_from_file_location("dl_w8", REPO / "tools" / "dead_letters.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)   # top level only defines names
    return m


DL = _tool()


def topics(src: str, env: dict) -> dict:
    """{'sub': Counter, 'pub': Counter} of topic strings at the file's sites under `env`."""
    tree = ast.parse(src)
    ns = {"os": os}
    for node in tree.body:   # the file's own helper, alone (pure: imports os, reads environ)
        if isinstance(node, ast.FunctionDef) and node.name == "_prefix_ear":
            exec(compile(ast.Module([node], []), "<_prefix_ear>", "exec"), ns)
    out = {"sub": Counter(), "pub": Counter()}

    def ev(expr):
        try:
            v = eval(compile(ast.Expression(expr), "<topic>", "eval"), dict(ns))
        except Exception:
            return None
        return v if isinstance(v, str) else None

    with mock.patch.dict(os.environ, env, clear=False):
        for k in ("AKASHIC_PREFIX_EARS", "AKASHIC_TOPIC_SPELLFIX"):
            if k not in env:
                os.environ.pop(k, None)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.args:
                kind = "sub" if node.func.attr in SUB else "pub" if node.func.attr in PUB else None
                if kind:
                    t = ev(node.args[0])
                    if t:
                        out[kind][t] += 1
            elif isinstance(node, ast.Assign) and isinstance(node.value, ast.List):
                if any(isinstance(t, ast.Name) and t.id in LISTS for t in node.targets):
                    for e in node.value.elts:
                        t = ev(e)
                        if t:
                            out["sub"][t] += 1
    return out


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


OFF, ON, SPELL_ON = {}, {"AKASHIC_PREFIX_EARS": "1"}, {"AKASHIC_TOPIC_SPELLFIX": "1"}


class SwitchOff(unittest.TestCase):
    def test_off_strings_as_today(self):
        for ear, (files, _) in EARS.items():
            for f in files:
                self.assertIn(ear, topics(read(f), OFF)["sub"], f"{f}: {ear} missing with switch off")
        for f, (old, new) in SPELL.items():
            self.assertIn(old, topics(read(f), OFF)["pub"], f)
            self.assertNotIn(new, topics(read(f), OFF)["pub"], f)

    def test_off_identical_to_base(self):
        for f in FILES:
            r = subprocess.run(["git", "show", f"{BASE_REF}:{f}"], cwd=REPO, capture_output=True,
                               text=True, encoding="utf-8")
            if r.returncode != 0:
                self.skipTest(f"git show {BASE_REF} unavailable")
            self.assertEqual(topics(read(f), OFF), topics(r.stdout, OFF), f)

    def test_only_exact_1_turns_it_on(self):
        for v in ("0", "", "true", "yes", "on", " 1"):
            for ear, (files, _) in EARS.items():
                for f in files:
                    self.assertIn(ear, topics(read(f), {"AKASHIC_PREFIX_EARS": v})["sub"], (f, v))


class SwitchOn(unittest.TestCase):
    def test_on_subscribes_prefix(self):
        for ear, (files, _) in EARS.items():
            for f in files:
                subs = topics(read(f), ON)["sub"]
                self.assertIn(ear[:-2], subs, f"{f}: prefix {ear[:-2]} not subscribed")
                self.assertNotIn(ear, subs, f"{f}: literal {ear} still subscribed")

    def test_on_delivers_letters_both_routers(self):
        for ear, (files, letters) in EARS.items():
            for f in files:
                subs = topics(read(f), ON)["sub"]
                for p in letters:
                    self.assertTrue(any(DL.rust_match(s, p) for s in subs), (f, p, "rust"))
                    self.assertTrue(any(DL.python_match(s, p) for s in subs), (f, p, "python"))

    def test_off_delivers_nothing(self):   # documents the bug the switch fixes
        for ear, (files, letters) in EARS.items():
            for f in files:
                subs = topics(read(f), OFF)["sub"]
                for p in letters:
                    self.assertFalse(any(DL.rust_match(s, p) for s in subs), (f, p))

    def test_on_leaves_other_wildcards_alone(self):
        for f, ears in UNTOUCHED.items():
            subs = topics(read(f), ON)["sub"]
            for e in ears:
                self.assertIn(e, subs, f"{f}: out-of-scope ear {e} changed")

    def test_spellfix(self):
        for f, (old, new) in SPELL.items():
            pubs = topics(read(f), SPELL_ON)["pub"]
            self.assertIn(new, pubs, f)
            self.assertNotIn(old, pubs, f)

    def test_level_up_payload_carries_level_when_fixed(self):
        # EgoLearnerFairy._on_skill_level_up reads payload["level"] (fairy.py:594); profile.py sent
        # only "new_level", so every level-up on the fixed path would have counted as level 0.
        tree = ast.parse(read(PRO))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and n.args
                 and "skill.level_up" in ast.unparse(n.args[0])]
        self.assertEqual(len(calls), 1)
        payload = calls[0].args[1]
        from types import SimpleNamespace as NS
        ns = {"result": {"new_level": 3}, "skill_name": "s",
              "self": NS(_profile=NS(actor_name="A"))}
        for env, want in ((SPELL_ON, {"fairy": "A", "skill": "s", "new_level": 3, "level": 3}),
                          (OFF, {"fairy": "A", "skill": "s", "new_level": 3}),
                          (ON, {"fairy": "A", "skill": "s", "new_level": 3})):
            with mock.patch.dict(os.environ, env, clear=False):
                for k in ("AKASHIC_TOPIC_SPELLFIX", "AKASHIC_PREFIX_EARS"):
                    if k not in env:
                        os.environ.pop(k, None)
                got = eval(compile(ast.Expression(payload), PRO, "eval"), {"os": os, **ns})
            self.assertEqual(got, want, env)

    def test_switches_independent(self):
        for f, (old, new) in SPELL.items():
            self.assertIn(old, topics(read(f), ON)["pub"], f)
        for ear, (files, _) in EARS.items():
            for f in files:
                self.assertIn(ear, topics(read(f), SPELL_ON)["sub"], f)


if __name__ == "__main__":
    unittest.main()
