"""W5 boot fixes: static / AST-driven tests (no import of her modules with side effects).

Run:  python3 -I -m unittest discover -s tests_nous/w5 -v
Point NOUS_W5_ROOT at another checkout (original / mutant copy) to run the same
tests against it; defaults to this repo root.
"""
import ast
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(os.environ.get("NOUS_W5_ROOT") or Path(__file__).resolve().parents[2])
CODE = ROOT / "code"

BOOT_ORCH = CODE / "tracer_pool" / "boot_orchestrator.py"
SERVER = CODE / "server.py"
WAKE_CASCADE = CODE / "fairies" / "P20_Somatic" / "SomaticMindFairy" / "wake_cascade.py"
DREAM_SEED = CODE / "fairies" / "P00_Autonomic" / "nervous_system" / "dream_seed_fairy.py"
HARMONIC = CODE / "fairies" / "P30_Cognition" / "HarmonicCortexFairy" / "fairy.py"
TEMPLATE = CODE / "fairies" / "P00_Autonomic" / "organ_template" / "Organ_Template_0_3_0.py"
AUTONOMY = CODE / "fairies" / "P00_Autonomic" / "AutonomyFairy" / "fairy.py"


def _parse(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _find_func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"function {name} not found")


def _find_class(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"class {name} not found")


# ─────────────────────────────────────────────────────────────────────────────
# B2: Shadow suffix exclude must be case-insensitive
# ─────────────────────────────────────────────────────────────────────────────
class _B2Excluder:
    """Evaluates the REAL exclude `if` expression from _build_fairy_specs."""

    def __init__(self):
        fn = _find_func(_parse(BOOT_ORCH), "_build_fairy_specs")
        env = {}
        test_expr = None
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                    and node.targets[0].id in ("_BOOT_EXCLUDE_NAMES", "_BOOT_EXCLUDE_SUFFIXES"):
                env[node.targets[0].id] = eval(compile(ast.Expression(node.value), "b2", "eval"))
            if isinstance(node, ast.If) and test_expr is None:
                names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
                if "_BOOT_EXCLUDE_NAMES" in names:
                    test_expr = node.test
        assert test_expr is not None and len(env) == 2
        self.env = env
        self.code = compile(ast.Expression(test_expr), "b2_test", "eval")

    def excluded(self, name):
        return bool(eval(self.code, dict(self.env), {"fairy": types.SimpleNamespace(name=name)}))


class TestB2ShadowSuffix(unittest.TestCase):
    def setUp(self):
        self.x = _B2Excluder()

    def test_lowercase_shadow_actor_name_is_excluded(self):
        # 'organ.shadow' is registered by FairyScanner from the organ template
        self.assertTrue(self.x.excluded("organ.shadow"))
        self.assertTrue(self.x.excluded("SomeFairy.SHADOW"))

    def test_camelcase_shadow_still_excluded(self):
        self.assertTrue(self.x.excluded("ManifoldConstrainedCortexShadow"))

    def test_names_list_still_excluded(self):
        self.assertTrue(self.x.excluded("my_organ"))
        self.assertTrue(self.x.excluded("MockRecallFairy"))

    def test_real_fairies_not_excluded(self):
        for n in ("HarmonicCortexFairy", "DreamSeedFairy", "shadowboxer.fairy",
                  "fairy_citizens.reg.michael", "ShadowCasterFairy"):
            self.assertFalse(self.x.excluded(n), n)


# ─────────────────────────────────────────────────────────────────────────────
# B4: cascade name for the dream seed fairy must be its real directory name
# ─────────────────────────────────────────────────────────────────────────────
def _actor_name(path, cls_name):
    cls = _find_class(_parse(path), cls_name)
    for node in cls.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == "ACTOR_NAME":
            return node.value.value
    raise AssertionError("ACTOR_NAME not found")


def _cascade_fairy_paths():
    for node in ast.walk(_parse(SERVER)):
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id == "_CASCADE_FAIRY_PATHS":
            return ast.literal_eval(node.value)
    raise AssertionError("_CASCADE_FAIRY_PATHS not found")


def _load_wake_cascade():
    # wake_cascade.py top level is dataclasses/dicts only (main block guarded)
    spec = importlib.util.spec_from_file_location("_w5_wake_cascade", WAKE_CASCADE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(spec.name, None)
    return mod


class TestB4DreamSeedName(unittest.TestCase):
    def setUp(self):
        self.real = _actor_name(DREAM_SEED, "DreamSeedFairy")

    def test_real_name(self):
        self.assertEqual(self.real, "DreamSeedFairy")

    def test_server_fallback_key_matches_actor_name(self):
        paths = _cascade_fairy_paths()
        keys = [k for k, (mod, cls) in paths.items() if mod.endswith("dream_seed_fairy")]
        self.assertEqual(keys, [self.real])

    def test_cascade_requests_real_name(self):
        wc = _load_wake_cascade()
        requested = [n for d in wc.DOMAIN_SPECS.values() for tier in d.values() for n in tier]
        dream = [n for n in requested if n.lower().startswith("dreamseed")]
        self.assertEqual(dream, [self.real])
        self.assertNotIn("DreamSeedsFairy", requested)
        self.assertEqual(wc._get_fairy_description(self.real), "Dream seed generation")

    def test_autonomy_cascade_requests_real_name(self):
        # REVIEW_W5 (10-29): the live caller is AutonomyFairy's domain list, not wake_cascade.py
        # (which nothing imports). Its "deferred" tier asked for the misspelled name.
        src = AUTONOMY.read_text(encoding="utf-8")
        self.assertIn('"DreamSeedFairy",', src)
        self.assertNotIn("DreamSeedsFairy", src)

    def test_no_code_requests_misspelled_name(self):
        hits = [str(p.relative_to(CODE)) for p in CODE.rglob("*.py")
                if "DreamSeedsFairy" in p.read_text(encoding="utf-8", errors="replace")
                and "tests_nous" not in p.parts]
        self.assertEqual(hits, [])

    def test_server_registers_same_name_cascade_checks(self):
        # server.py registers name="DreamSeedFairy" and appends it to registered_fairies;
        # the cascade handler skips names already in that list.
        src = SERVER.read_text(encoding="utf-8")
        self.assertIn('registered_fairies.append("DreamSeedFairy")', src)


# ─────────────────────────────────────────────────────────────────────────────
# B5: HarmonicCortexFairy subscribes through the bridge it really has
# ─────────────────────────────────────────────────────────────────────────────
class _FakeFabric:
    def __init__(self):
        self.subs = []
        self.pubs = []

    def subscribe(self, topic, handler, name=None):
        self.subs.append((topic, name))

    def publish(self, topic, payload, source=None):
        self.pubs.append((topic, payload))


def _load_bridge_class():
    cls = _find_class(_parse(TEMPLATE), "_FabricPostalBridge")
    ns = {"Callable": object, "Dict": dict, "Any": object, "Optional": object, "List": list}
    exec(compile(ast.Module([cls], []), str(TEMPLATE), "exec"), ns)
    return ns["_FabricPostalBridge"]


def _harmonic_harness(method_names):
    """Build a class whose methods are the REAL HarmonicCortexFairy methods."""
    hcls = _find_class(_parse(HARMONIC), "HarmonicCortexFairy")
    funcs = [n for n in hcls.body if isinstance(n, ast.FunctionDef) and n.name in method_names]
    assert len(funcs) == len(method_names)
    base = ast.parse("class _Base:\n    def on_boot(self):\n        return {'ok': True}\n").body[0]
    harness = ast.ClassDef(name="H", bases=[ast.Name("_Base", ast.Load())], keywords=[],
                           body=funcs, decorator_list=[], type_params=[])
    mode_cls = _find_class(_parse(HARMONIC), "Mode")
    mod = ast.fix_missing_locations(ast.Module([mode_cls, base, harness], []))
    ns = {"Enum": __import__("enum").Enum, "_MUSIC_THEORY_AVAILABLE": False, "MusicTheoryEngine": None, "time": __import__("time"),
          "Dict": dict, "Any": object, "os": os}
    exec(compile(mod, str(HARMONIC), "exec"), ns)
    return ns["H"], ns


class TestB5HarmonicSubscribe(unittest.TestCase):
    TOPICS = ["harmonic.query", "harmonic.perspectives", "affect.changed",
              "sensory.audio.frame", "sensory.audio.observation", "sensory.audio.speech"]

    def setUp(self):
        # make the manifold import inside on_boot fail cleanly (ImportError branch)
        self._saved = {k: sys.modules.get(k) for k in
                       ("fairies", "fairies.P30_Cognition", "fairies.P30_Cognition.integration",
                        "fairies.P30_Cognition.integration.manifold_constrained_cortex_fairy")}
        sys.modules["fairies.P30_Cognition.integration.manifold_constrained_cortex_fairy"] = None

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    def _instance(self, H):
        fab = _FakeFabric()
        h = H()
        h.ACTOR_NAME = "HarmonicCortexFairy"
        h.post = _load_bridge_class()(fab, "HarmonicCortexFairy")
        h._current_mode = types.SimpleNamespace(value="ionian")
        for cb in ("_on_query", "_on_perspectives", "_on_affect_changed",
                   "_on_audio_frame", "_on_audio_observation", "_on_audio_speech"):
            setattr(h, cb, lambda *a, **k: None)
        return h, fab

    def test_bridge_has_no_public_fabric(self):
        fab = _FakeFabric()
        bridge = _load_bridge_class()(fab, "x")
        self.assertFalse(hasattr(bridge, "fabric"))
        self.assertTrue(callable(getattr(bridge, "subscribe", None)))

    NAMES = ["HarmonicCortexFairy_" + n for n in
             ("query", "perspectives", "affect", "audio_frame", "audio_observation", "audio_speech")]

    def _boot(self, switch):
        saved = os.environ.pop("AKASHIC_HARMONIC_SUBSCRIBE", None)
        if switch is not None:
            os.environ["AKASHIC_HARMONIC_SUBSCRIBE"] = switch
        try:
            H, _ = _harmonic_harness(["on_boot"])
            h, fab = self._instance(H)
            calls = []
            real = h.post.subscribe
            h.post.subscribe = lambda *a, **k: (calls.append(a[0]), real(*a, **k))[1]
            return h.on_boot(), fab, calls
        finally:
            os.environ.pop("AKASHIC_HARMONIC_SUBSCRIBE", None)
            if saved is not None:
                os.environ["AKASHIC_HARMONIC_SUBSCRIBE"] = saved

    def test_switch_off_is_todays_behaviour(self):
        # today: AttributeError on self.post.fabric -> swallowed -> nothing subscribed
        for switch in (None, "0", "", "true"):
            result, fab, calls = self._boot(switch)
            self.assertTrue(str(result.get("subscriptions", "")).startswith("error"), (switch, result))
            self.assertEqual(fab.subs, [], switch)
            self.assertEqual(calls, [], switch)

    def test_switch_on_wires_all_six_through_the_bridge(self):
        result, fab, calls = self._boot("1")
        self.assertEqual(result.get("subscriptions"), "ok", result)
        self.assertEqual(calls, self.TOPICS)                 # went through _FabricPostalBridge.subscribe
        self.assertEqual(fab.subs, list(zip(self.TOPICS, self.NAMES)))   # names kept
        self.assertEqual(result.get("affect_loop"), "subscribed")
        self.assertEqual(result.get("audio_wire"), "subscribed")


if __name__ == "__main__":
    unittest.main()
