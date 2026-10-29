"""W13 coma gate tests. Synthetic data in a temp dir only; nothing boots, no server, no fairy, no organ template import.

Run:  python3 code/tests/test_w13_coma_gate.py
Overrides (used to run the CONTROL against main and the MUTANTS):
  COMA_GATE_SRC  path of the coma_gate.py to test      (default code/infrastructure/coma_gate.py)
  SERVER_SRC     path of the server.py whose boot.fairy.request handler is exercised (default code/server.py)
"""
import ast
import importlib.util
import os
import sys
import tempfile
import threading
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
COMA_GATE_SRC = os.environ.get("COMA_GATE_SRC") or os.path.join(CODE, "infrastructure", "coma_gate.py")
SERVER_SRC = os.environ.get("SERVER_SRC") or os.path.join(CODE, "server.py")
TEMPLATE_SRC = os.path.join(CODE, "fairies", "P00_Autonomic", "organ_template", "Organ_Template_0_3_0.py")
REG_KEY = "fairy_template.citizen_registry"


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def load_gate():
    spec = importlib.util.spec_from_file_location("coma_gate_under_test", COMA_GATE_SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeFairy:
    """Mirrors the template's wake() contract (Organ_Template_0_3_0.py:3487-3509): idempotent on _comatose, runs on_boot."""
    built = 0

    def __init__(self, name="PainDriveFairy", asleep=True):
        FakeFairy.built += 1
        self.ACTOR_NAME = name
        self._comatose = asleep
        self.on_boot_calls = 0

    def on_boot(self):
        self.on_boot_calls += 1

    def wake(self, reason="explicit"):
        if not getattr(self, "_comatose", False):
            return True
        self._comatose = False
        self.on_boot()
        return True


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = os.path.join(self.tmp.name, "coma_gate_open.txt")
        self._env = {k: os.environ.get(k) for k in ("AKASHIC_COMA_GATE", "AKASHIC_COMA_GATE_FILE")}
        os.environ.pop("AKASHIC_COMA_GATE", None)
        os.environ["AKASHIC_COMA_GATE_FILE"] = self.file
        self._reg_prev = sys.modules.get(REG_KEY)
        reg = types.ModuleType(REG_KEY)
        reg.CITIZEN_OBJECTS = {}
        reg._CITIZEN_OBJECTS = reg.CITIZEN_OBJECTS
        sys.modules[REG_KEY] = reg
        self.citizens = reg.CITIZEN_OBJECTS
        self.logs = []
        FakeFairy.built = 0

    def tearDown(self):
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if self._reg_prev is None:
            sys.modules.pop(REG_KEY, None)
        else:
            sys.modules[REG_KEY] = self._reg_prev
        self.tmp.cleanup()

    def write(self, text):
        with open(self.file, "w", encoding="utf-8") as fh:
            fh.write(text)

    def log(self, msg):
        self.logs.append(msg)


class GateModule(Base):
    def setUp(self):
        super().setUp()
        self.g = load_gate()

    def test_off_when_unset_or_not_exactly_1(self):
        f = FakeFairy()
        self.citizens[f.ACTOR_NAME] = f
        self.write("PainDriveFairy\ngate:PainDriveFairy\n")
        for val in (None, "", "0", "true", "yes", " 1", "1 ", "on"):
            if val is None:
                os.environ.pop("AKASHIC_COMA_GATE", None)
            else:
                os.environ["AKASHIC_COMA_GATE"] = val
            self.assertFalse(self.g.enabled(), repr(val))
            self.assertEqual(self.g.on_boot_request({"fairy_name": "PainDriveFairy", "gate": "embodiment"}, log=self.log), "off")
            self.assertEqual(self.g.sweep(log=self.log), {})
            self.assertIsNone(self.g.start_owner_watch(log=self.log))
        self.assertTrue(f._comatose)
        self.assertEqual(f.on_boot_calls, 0)
        self.assertEqual(self.logs, [])

    def test_on_listed_wakes_exactly_once_no_duplicate(self):
        os.environ["AKASHIC_COMA_GATE"] = "1"
        f = FakeFairy()
        self.citizens[f.ACTOR_NAME] = f
        self.write("gate:PainDriveFairy\n")
        results = []
        lock = threading.Lock()

        def ask():
            r = self.g.on_boot_request({"payload": {"fairy_name": "PainDriveFairy", "gate": "embodiment"}}, log=self.log)
            with lock:
                results.append(r)

        ts = [threading.Thread(target=ask) for _ in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        ask()
        self.assertFalse(f._comatose)
        self.assertEqual(f.on_boot_calls, 1)
        self.assertEqual(results.count("woke"), 1, results)
        self.assertEqual(results.count("awake"), 8, results)
        self.assertEqual(FakeFairy.built, 1)
        self.assertIs(self.citizens["PainDriveFairy"], f)

    def test_not_listed_refusal_names_fairy_and_reason(self):
        os.environ["AKASHIC_COMA_GATE"] = "1"
        f = FakeFairy("SomaticAvatarFairy")
        self.citizens[f.ACTOR_NAME] = f
        self.write("gate:PainDriveFairy\n")
        r = self.g.on_boot_request({"fairy_name": "SomaticAvatarFairy", "gate": "embodiment"}, log=self.log)
        self.assertEqual(r, "refused:not-listed")
        self.assertTrue(f._comatose)
        self.assertEqual(len(self.logs), 1)
        self.assertIn("SomaticAvatarFairy", self.logs[0])
        self.assertIn("not on the allow-list", self.logs[0])
        self.assertIn("gate:embodiment", self.logs[0])

    def test_gate_line_does_not_let_owner_sweep_wake_but_owner_line_does(self):
        os.environ["AKASHIC_COMA_GATE"] = "1"
        f = FakeFairy()
        self.citizens[f.ACTOR_NAME] = f
        self.write("# comment\ngate:PainDriveFairy\n")
        self.assertEqual(self.g.sweep(log=self.log), {})
        self.assertEqual(self.g.open_for("PainDriveFairy", "owner", log=self.log, owner_only=True), "refused:not-listed")
        self.assertTrue(f._comatose)
        self.write("PainDriveFairy   # owner opens it\n")
        self.assertEqual(self.g.sweep(log=self.log), {"PainDriveFairy": "woke"})
        self.assertEqual(self.g.sweep(log=self.log), {"PainDriveFairy": "awake"})
        self.assertEqual(f.on_boot_calls, 1)

    def test_file_is_read_live(self):
        os.environ["AKASHIC_COMA_GATE"] = "1"
        f = FakeFairy()
        self.citizens[f.ACTOR_NAME] = f
        self.write("")
        self.assertEqual(self.g.on_boot_request({"fairy_name": "PainDriveFairy", "gate": "autonomy"}, log=self.log),
                         "refused:not-listed")
        self.write("gate:PainDriveFairy\n")
        self.assertEqual(self.g.on_boot_request({"fairy_name": "PainDriveFairy", "gate": "autonomy"}, log=self.log), "woke")

    def test_missing_file_opens_nothing(self):
        os.environ["AKASHIC_COMA_GATE"] = "1"
        f = FakeFairy()
        self.citizens[f.ACTOR_NAME] = f
        self.assertEqual(self.g.on_boot_request({"fairy_name": "PainDriveFairy", "gate": "autonomy"}, log=self.log),
                         "refused:not-listed")
        self.assertTrue(f._comatose)

    def test_only_her_three_gates_may_open(self):
        os.environ["AKASHIC_COMA_GATE"] = "1"
        f = FakeFairy()
        self.citizens[f.ACTOR_NAME] = f
        self.write("gate:PainDriveFairy\n")
        for g in ("k2_fallback", "anybody", "unknown", None):
            p = {"fairy_name": "PainDriveFairy"}
            if g is not None:
                p["gate"] = g
            self.assertEqual(self.g.on_boot_request(p, log=self.log), "refused:not-a-gate", g)
        self.assertTrue(f._comatose)
        self.assertIn("not one of her three gates", self.logs[0])
        for g in ("autonomy", "autopilot", "embodiment"):
            self.assertIn(self.g.on_boot_request({"fairy_name": "PainDriveFairy", "gate": g}, log=self.log), ("woke", "awake"))
        self.assertEqual(f.on_boot_calls, 1)

    def test_owner_line_is_also_open_to_her_gates_and_prefix_is_case_insensitive(self):
        os.environ["AKASHIC_COMA_GATE"] = "1"
        a, b = FakeFairy("PainDriveFairy"), FakeFairy("SomaticAvatarFairy")
        self.citizens.update({a.ACTOR_NAME: a, b.ACTOR_NAME: b})
        self.write("PainDriveFairy\nGATE: SomaticAvatarFairy\n")
        self.assertEqual(self.g.on_boot_request({"fairy_name": "PainDriveFairy", "gate": "embodiment"}, log=self.log), "woke")
        self.assertEqual(self.g.on_boot_request({"fairy_name": "SomaticAvatarFairy", "gate": "embodiment"}, log=self.log), "woke")

    def test_slow_wake_still_once_and_lock_not_held_across_wake(self):
        os.environ["AKASHIC_COMA_GATE"] = "1"
        release = threading.Event()

        class Slow(FakeFairy):
            def wake(inner, reason="explicit"):       # worst case: clears _comatose only AFTER a slow on_boot
                if not inner._comatose:
                    return True
                inner.on_boot()
                release.wait(5)
                inner._comatose = False
                return True

        a, b = Slow("PainDriveFairy"), FakeFairy("SomaticAvatarFairy")
        self.citizens.update({a.ACTOR_NAME: a, b.ACTOR_NAME: b})
        self.write("gate:PainDriveFairy\ngate:SomaticAvatarFairy\n")
        out = []
        t1 = threading.Thread(target=lambda: out.append(self.g.on_boot_request(
            {"fairy_name": "PainDriveFairy", "gate": "autonomy"}, log=self.log)))
        t1.start()
        for _ in range(200):
            if a.on_boot_calls:
                break
            threading.Event().wait(0.01)
        r2 = []
        t2 = threading.Thread(target=lambda: r2.append(self.g.on_boot_request(
            {"fairy_name": "SomaticAvatarFairy", "gate": "autonomy"}, log=self.log)))
        t2.start()
        t2.join(2)
        self.assertEqual(r2, ["woke"], "another fairy's wake was blocked by a slow on_boot")
        self.assertEqual(self.g.on_boot_request({"fairy_name": "PainDriveFairy", "gate": "autopilot"}, log=self.log), "waking")
        release.set()
        t1.join(5)
        self.assertEqual(out, ["woke"])
        self.assertEqual(a.on_boot_calls, 1)

    def test_second_copy_is_not_woken(self):
        os.environ["AKASHIC_COMA_GATE"] = "1"
        one, copy = FakeFairy(), FakeFairy()
        self.citizens["PainDriveFairy"] = one
        self.write("gate:PainDriveFairy\n")
        self.assertEqual(self.g.on_boot_request({"fairy_name": "PainDriveFairy", "gate": "autonomy"}, instance=copy,
                                                log=self.log), "refused:not-the-one")
        self.assertTrue(copy._comatose)
        self.assertEqual(self.g.on_boot_request({"fairy_name": "PainDriveFairy", "gate": "autonomy"}, instance=one,
                                                log=self.log), "woke")

    def test_wake_marks_directory_record_running(self):
        os.environ["AKASHIC_COMA_GATE"] = "1"
        f = FakeFairy("SRMIngestFairy")
        self.citizens[f.ACTOR_NAME] = f
        rec = types.SimpleNamespace(metadata={"fairy_instance": f}, status="sleeping")
        directory = types.SimpleNamespace(get_fairy=lambda n: rec if n == "SRMIngestFairy" else None)
        self.write("gate:SRMIngestFairy\n")
        self.g.on_boot_request({"fairy_name": "SRMIngestFairy", "gate": "autonomy"}, directory=directory, log=self.log)
        self.assertEqual(rec.status, "running")

    def test_never_builds_an_instance(self):
        os.environ["AKASHIC_COMA_GATE"] = "1"
        self.write("PainDriveFairy\n")
        self.assertEqual(self.g.sweep(log=self.log), {"PainDriveFairy": "refused:no-instance"})
        self.assertEqual(self.citizens, {})
        self.assertEqual(FakeFairy.built, 0)
        self.assertIn("no existing instance", self.logs[0])

    def test_directory_record_fallback(self):
        os.environ["AKASHIC_COMA_GATE"] = "1"
        f = FakeFairy("SRMIngestFairy")
        rec = types.SimpleNamespace(metadata={"fairy_instance": f}, status="sleeping")
        directory = types.SimpleNamespace(get_fairy=lambda n: rec if n == "SRMIngestFairy" else None)
        self.write("gate:SRMIngestFairy\n")
        self.assertEqual(self.g.on_boot_request({"fairy_name": "SRMIngestFairy", "gate": "autonomy"},
                                                directory=directory, log=self.log), "woke")
        self.assertEqual(f.on_boot_calls, 1)


def extract_handler():
    src = _read(SERVER_SRC)
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.FunctionDef) and n.name == "_handle_fairy_boot_request":
            return ast.get_source_segment(src, n)
    raise AssertionError("handler not found in %s" % SERVER_SRC)


class ServerHandler(Base):
    """Runs server.py's REAL _handle_fairy_boot_request source against stubs (no server, no fabric)."""

    def make(self, gate_on):
        import textwrap
        self.published = []
        self.resolves = 0
        self.boot_hook = getattr(self, "boot_hook", None)
        self.init_hook = getattr(self, "init_hook", None)
        self.registered = []
        citizens = self.citizens

        class SleepyFairy(FakeFairy):
            def __init__(inner, fabric=None):
                FakeFairy.__init__(inner, "PainDriveFairy", asleep=False)
                inner._booted = False
                if self.init_hook:
                    self.init_hook()
                ex = citizens.get(inner.ACTOR_NAME)         # template __init__ :1212-1248: register unless a booted
                if not (ex is not None and getattr(ex, "_booted", False) and ex is not inner):   # other copy exists
                    citizens[inner.ACTOR_NAME] = inner

            def boot(inner):
                inner._booted = True
                inner._comatose = True                      # AKASHIC_COMA=1: boot() returns asleep (:3572-3583)
                if self.boot_hook:
                    self.boot_hook()
                return True

        def resolve(name):
            self.resolves += 1
            return SleepyFairy, "test"

        fabric = types.SimpleNamespace(publish=lambda t, p: self.published.append((t, p)))
        system = types.SimpleNamespace(fabric=fabric, directory=None)
        if gate_on:
            os.environ["AKASHIC_COMA_GATE"] = "1"
        ns = {"SYSTEM": system, "registered_fairies": self.registered, "_one_cortex": None,
              "_fairy_goes_to_portal": lambda n: False, "_resolve_fairy_class": resolve, "_skip_registry": None,
              "_coma_gate": load_gate() if gate_on else None, "print": lambda *a, **k: None}
        exec(textwrap.dedent(extract_handler()), ns)
        return ns["_handle_fairy_boot_request"]

    def test_off_gate_requested_fairy_stays_asleep(self):
        self.write("gate:PainDriveFairy\nPainDriveFairy\n")
        h = self.make(gate_on=False)
        h({"fairy_name": "PainDriveFairy", "gate": "embodiment", "boot_id": "b"})
        h({"fairy_name": "PainDriveFairy", "gate": "embodiment", "boot_id": "b"})
        f = self.citizens["PainDriveFairy"]
        self.assertTrue(f._comatose)
        self.assertEqual(f.on_boot_calls, 0)
        self.assertEqual(FakeFairy.built, 1)

    def test_on_listed_new_build_wakes_once_no_duplicate(self):     # CONTROL: fails on main's server.py
        self.write("gate:PainDriveFairy\n")
        h = self.make(gate_on=True)
        for _ in range(3):
            h({"fairy_name": "PainDriveFairy", "gate": "embodiment", "boot_id": "b"})
        f = self.citizens["PainDriveFairy"]
        self.assertFalse(f._comatose)
        self.assertEqual(f.on_boot_calls, 1)
        self.assertEqual(FakeFairy.built, 1)
        self.assertEqual(self.resolves, 1)

    def test_on_listed_existing_registered_instance_wakes_in_place(self):   # CONTROL: fails on main's server.py
        self.write("gate:PainDriveFairy\n")
        h = self.make(gate_on=True)
        f = FakeFairy("PainDriveFairy", asleep=True)    # built by the serial block, already in registered_fairies
        self.citizens["PainDriveFairy"] = f
        self.registered.append("PainDriveFairy")
        h({"fairy_name": "PainDriveFairy", "gate": "embodiment", "boot_id": "b"})
        h({"fairy_name": "PainDriveFairy", "gate": "embodiment", "boot_id": "b"})
        self.assertFalse(f._comatose)
        self.assertEqual(f.on_boot_calls, 1)
        self.assertEqual(FakeFairy.built, 1)
        self.assertEqual(self.resolves, 0)

    def test_on_listed_existing_unregistered_instance_is_not_rebuilt(self):   # CONTROL: fails on main's server.py
        self.write("gate:PainDriveFairy\n")
        h = self.make(gate_on=True)
        f = FakeFairy("PainDriveFairy", asleep=True)    # in CITIZEN_OBJECTS but NOT in registered_fairies / directory
        self.citizens["PainDriveFairy"] = f
        h({"fairy_name": "PainDriveFairy", "gate": "autonomy", "boot_id": "b"})
        self.assertIs(self.citizens["PainDriveFairy"], f)
        self.assertFalse(f._comatose)
        self.assertEqual(f.on_boot_calls, 1)
        self.assertEqual(FakeFairy.built, 1)
        self.assertEqual(self.resolves, 0)

    def test_on_listed_awake_unregistered_instance_is_not_rebuilt(self):
        self.write("gate:PainDriveFairy\n")
        h = self.make(gate_on=True)
        f = FakeFairy("PainDriveFairy", asleep=False)
        self.citizens["PainDriveFairy"] = f
        h({"fairy_name": "PainDriveFairy", "gate": "autonomy", "boot_id": "b"})
        self.assertEqual(FakeFairy.built, 1)
        self.assertEqual(self.resolves, 0)

    def test_on_listed_wake_error_does_not_rebuild(self):
        self.write("gate:PainDriveFairy\n")
        h = self.make(gate_on=True)

        class Bad(FakeFairy):
            def wake(inner, reason="explicit"):
                raise RuntimeError("boom")

        f = Bad("PainDriveFairy", asleep=True)
        self.citizens["PainDriveFairy"] = f
        h({"fairy_name": "PainDriveFairy", "gate": "autonomy", "boot_id": "b"})
        self.assertEqual(FakeFairy.built, 1)
        self.assertEqual(self.resolves, 0)

    def test_on_concurrent_double_build_wakes_only_one(self):
        """Main already double-builds when two requests race before registered_fairies is appended; the gate must
        wake only ONE of the copies (any interleaving of the two __init__/boot calls)."""
        self.write("gate:PainDriveFairy\n")
        expect_built = {"in_init": 2, "in_boot": 1, "after": 1}
        for stagger in ("in_init", "in_boot", "after"):
            FakeFairy.built = 0
            self.citizens.clear()
            self.registered.clear() if hasattr(self, "registered") else None
            h = self.make(gate_on=True)
            gm = h.__globals__["_coma_gate"]
            req = {"fairy_name": "PainDriveFairy", "gate": "autonomy", "boot_id": "b"}
            fired = []

            def hook():
                if not fired:
                    fired.append(1)
                    h(dict(req, gate="embodiment"))
            self.init_hook = hook if stagger == "in_init" else None
            self.boot_hook = hook if stagger == "in_boot" else None
            h(req)
            if stagger == "after":      # 2nd request after the 1st finished, before registered_fairies saw it
                self.registered.clear()
                h(dict(req, gate="embodiment"))
            self.init_hook = self.boot_hook = None
            self.assertEqual(FakeFairy.built, expect_built[stagger], stagger)
            woken = [o() for o in gm._opened.values() if o() is not None]
            self.assertEqual(len(woken), 1, stagger)
            self.assertEqual(woken[0].on_boot_calls, 1, stagger)
            self.assertIs(self.citizens["PainDriveFairy"], woken[0], stagger)

    def test_on_registry_overwritten_by_a_copy_after_a_wake_never_wakes_or_builds_again(self):
        """Defence for a registry that a later copy overwrites (template :1248 when the first copy is not yet _booted)."""
        self.write("gate:PainDriveFairy\n")
        h = self.make(gate_on=True)
        gm = h.__globals__["_coma_gate"]
        a = FakeFairy("PainDriveFairy", asleep=True)
        self.citizens["PainDriveFairy"] = a
        h({"fairy_name": "PainDriveFairy", "gate": "autonomy", "boot_id": "b"})
        self.assertFalse(a._comatose)
        b = FakeFairy("PainDriveFairy", asleep=True)       # a copy took the registry slot, asleep, not registered
        self.citizens["PainDriveFairy"] = b
        self.assertEqual(gm.on_boot_request({"fairy_name": "PainDriveFairy", "gate": "autopilot"}, log=self.log),
                         "refused:already-opened")
        h({"fairy_name": "PainDriveFairy", "gate": "embodiment", "boot_id": "b"})
        self.assertTrue(b._comatose)
        self.assertEqual(self.resolves, 0)
        self.assertEqual(FakeFairy.built, 2)

    def test_on_listed_instance_without_wake_is_not_rebuilt(self):
        self.write("gate:PainDriveFairy\n")
        h = self.make(gate_on=True)
        f = types.SimpleNamespace(ACTOR_NAME="PainDriveFairy", _comatose=True)
        self.citizens["PainDriveFairy"] = f
        h({"fairy_name": "PainDriveFairy", "gate": "autonomy", "boot_id": "b"})
        self.assertEqual(self.resolves, 0)

    def test_on_not_a_gate_falls_through_to_todays_path(self):
        self.write("gate:PainDriveFairy\n")
        h = self.make(gate_on=True)
        h({"fairy_name": "PainDriveFairy", "gate": "k2_fallback", "boot_id": "b"})
        self.assertEqual(self.resolves, 1)
        self.assertTrue(self.citizens["PainDriveFairy"]._comatose)

    def test_on_not_listed_stays_asleep(self):
        self.write("gate:SomeOtherFairy\n")
        h = self.make(gate_on=True)
        h({"fairy_name": "PainDriveFairy", "gate": "embodiment", "boot_id": "b"})
        self.assertTrue(self.citizens["PainDriveFairy"]._comatose)


class Structure(unittest.TestCase):
    def test_server_switch_is_off_when_unset_and_every_use_is_guarded(self):    # CONTROL: fails on main
        src = _read(SERVER_SRC)
        self.assertIn('if os.environ.get("AKASHIC_COMA_GATE", "0") == "1":\n'
                      '                from infrastructure import coma_gate as _coma_gate', src)
        self.assertIn("        _coma_gate = None\n", src)
        uses = [ln for ln in src.splitlines() if "_coma_gate." in ln]
        self.assertEqual(len(uses), 4, uses)
        lines = src.splitlines()
        for i, ln in enumerate(lines):
            if "_coma_gate." in ln:
                window = "\n".join(lines[max(0, i - 2):i + 1])
                self.assertIn("_coma_gate is not None", window, ln)
        self.assertEqual(src.count("import coma_gate"), 1)

    def test_template_wake_contract_matches_fake(self):
        src = _read(TEMPLATE_SRC)
        i = src.index("    def wake(self, reason: str = \"explicit\") -> bool:")
        body = src[i:i + 600]
        self.assertIn('if not getattr(self, "_comatose", False):', body)
        self.assertIn("self._comatose = False", body)
        self.assertIn("self.on_boot()", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
