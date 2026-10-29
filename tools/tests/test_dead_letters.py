"""Unit tests for tools/dead_letters.py (W3 fixes). Synthetic code/ tree in a temp dir only.

    python3 -m unittest tools/tests/test_dead_letters.py

DEAD_LETTERS_PATH=<file> runs the same tests against another copy of the tool (used by
run_control_and_mutants.py for the control and the mutants).
"""
import importlib.util
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = Path(os.environ.get("DEAD_LETTERS_PATH", HERE.parent / "dead_letters.py"))


def load_tool():
    spec = importlib.util.spec_from_file_location("dead_letters_under_test", TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)   # top level only defines names; main() is not run
    return mod


FILES = {
    # 1. route/receive aliases
    "fairies/P30_Alpha/Sender/fairy.py": '''
        class SenderFairy:
            ACTOR_NAME = "SenderFairy"
            def go(self):
                self.post.route("alias.ping", {})
                self.post.publish("lonely.letter", {})
    ''',
    "fairies/P30_Alpha/Ear/fairy.py": '''
        class EarFairy:
            ACTOR_NAME = "EarFairy"
            def boot(self):
                self.post.receive("alias.ping", self.on_ping)
                self.post.subscribe("lonely.ear", self.on_ping)
            def on_ping(self, env):
                pass
    ''',
    # 2. twin copies: code/P30_Alpha/hub.py is a re-export shim of the code/fairies copy
    "P30_Alpha/__init__.py": "",
    "P30_Alpha/hub.py": '''
        from fairies.P30_Alpha.hub import Hub  # re-export
    ''',
    "fairies/__init__.py": "",
    "fairies/P30_Alpha/__init__.py": "",
    "fairies/P30_Alpha/hub.py": '''
        class Hub:
            ACTOR_NAME = "Hub"
            def boot(self):
                self.post.subscribe("twin.event", self.on_evt)
            def on_evt(self, env):
                pass
    ''',
    "fairies/P30_Alpha/Twin/fairy.py": '''
        from fairies.P30_Alpha.hub import Hub
        class TwinUser:
            ACTOR_NAME = "TwinUser"
            def go(self):
                self.post.publish("twin.event", {})
    ''',
    # a twin copy imported only by its BARE name (which loads code/P30_Alpha/orphan.py) stays excluded
    "P30_Alpha/orphan.py": "X = 1\n",
    "fairies/P30_Alpha/Bare/fairy.py": "from P30_Alpha.orphan import X\n",
    "fairies/P30_Alpha/orphan.py": '''
        class Orphan:
            ACTOR_NAME = "Orphan"
            def go(self):
                self.post.publish("orphan.only", {})
    ''',
    # 3. wrappers: module function and method (method arg index shifts past self)
    "fairies/P30_Alpha/Wrap/fairy.py": '''
        def _emit(topic, payload):
            hub = get_hub()
            hub.publish(topic, payload)

        class WrapFairy:
            ACTOR_NAME = "WrapFairy"
            def _pub(self, topic, data=None):
                self.post.publish(topic, data or {})
            def go(self):
                _emit("wrap.func", {})
                self._pub("wrap.method", {"k": 1})
                self._pub(topic="wrap.kw")
    ''',
    "fairies/P30_Alpha/WrapEar/fairy.py": '''
        class WrapEar:
            ACTOR_NAME = "WrapEar"
            def boot(self):
                for t in ("wrap.func", "wrap.method", "wrap.kw"):
                    self.post.subscribe(t, self.h)
            def h(self, env):
                pass
    ''',
}


class DeadLettersW3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        code = root / "code"
        for rel, src in FILES.items():
            p = code / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(textwrap.dedent(src))
        dl = load_tool()
        dl.REPO, dl.CODE = root, code
        dl.OUT = root / "out.md"
        dl.IMPORT_ROOTS = [code, code / "postal_core" / "python", code / "fairies"]
        dl._MODULES.clear()
        res = dl.census()
        live = res[0]
        cls.dl = dl
        cls.live = {p.relative_to(code).as_posix() for p in live}
        cls.sites = dl.scan(live)
        dead, deaf = dl.dead_and_deaf(cls.sites)
        cls.dead = {dl.show(x) for x in dead}
        cls.deaf = {dl.show(x) for x in deaf}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    # sanity: true dead letter / deaf ear still reported (guards against "match everything")
    def test_true_dead_and_deaf_kept(self):
        self.assertIn("lonely.letter", self.dead)
        self.assertIn("lonely.ear", self.deaf)

    def test_route_is_publish_and_receive_is_subscribe(self):
        self.assertNotIn("alias.ping", self.dead)
        self.assertNotIn("alias.ping", self.deaf)

    def test_twin_copy_imported_as_fairies_is_live(self):
        self.assertIn("fairies/P30_Alpha/hub.py", self.live)
        self.assertNotIn("twin.event", self.dead)

    def test_unimported_twin_copy_stays_excluded(self):
        self.assertNotIn("fairies/P30_Alpha/orphan.py", self.live)
        self.assertNotIn("orphan.only", self.dead)

    def test_wrapper_function_call_is_publish(self):
        self.assertNotIn("wrap.func", self.deaf)

    def test_wrapper_method_positional_and_keyword(self):
        self.assertNotIn("wrap.method", self.deaf)
        self.assertNotIn("wrap.kw", self.deaf)

    def test_wrapper_sites_carry_caller_location(self):
        locs = {s.loc for s in self.sites if s.kind == "pub" and "wrap.method" in s.topics}
        self.assertEqual(locs, {"code/fairies/P30_Alpha/Wrap/fairy.py:12"})


if __name__ == "__main__":
    unittest.main()
