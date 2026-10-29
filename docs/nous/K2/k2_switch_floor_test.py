"""Synthetic K2 checks. Imports infrastructure/one_cortex.py (stdlib only, no top-level side effects). Temp dir only."""
import importlib.util, json, os, sys, tempfile, io, contextlib

SRC = sys.argv[1]


def fresh():
    spec = importlib.util.spec_from_file_location("one_cortex_t", SRC)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


tmp = tempfile.mkdtemp(prefix="k2t_")
cases = {
    "absent": None,
    "empty": b"",
    "on_true": b'{"on": true}',
    "on_true_BOM": b'\xef\xbb\xbf{"on": true}',
    "on_string_true": b'{"on": "true"}',
    "on_1": b'{"on": 1}',
    "on_false": b'{"on": false}',
    "list": b'[{"on": true}]',
    "trailing_garbage": b'{"on": true} x',
    "utf16": '{"on": true}'.encode("utf-16"),
    "names_ok": b'{"on": true, "names": ["AssociationCortexFairy"]}',
    "names_other": b'{"on": true, "names": ["SomethingElse"]}',
    "names_str": b'{"on": true, "names": "AssociationCortexFairy"}',
    "names_empty": b'{"on": true, "names": []}',
    "dup_key_last_true": b'{"on": false, "on": true}',
    "true_caps": b'{"on": True}',
}
m = fresh()
print("== switch parse ==")
for k, v in cases.items():
    p = os.path.join(tmp, k + ".json")
    if v is not None:
        with open(p, "wb") as f:
            f.write(v)
    print("%-20s -> %s" % (k, sorted(m._read_switch(p))))
d = os.path.join(tmp, "a_directory")
os.mkdir(d)
print("%-20s -> %s" % ("path_is_dir", sorted(m._read_switch(d))))

# default SWITCH_FILE resolution
print("SWITCH_FILE =", m.SWITCH_FILE)


class Rec:
    def __init__(self):
        self.status = "booting"
        self.metadata = {}


class Dir:
    def __init__(self, rec):
        self.rec = rec

    def get_fairy(self, n):
        return self.rec


def run(label, steps):
    mm = fresh()
    mm._OWNED = frozenset({"AssociationCortexFairy"})  # simulate ON
    pubs = []
    pub = lambda t, p: pubs.append((t, p))
    out = io.StringIO()
    res = []
    with contextlib.redirect_stdout(out):
        for s in steps:
            res.append(s(mm, pub))
    print("--", label)
    print("   results:", res)
    print("   published:", pubs)
    print("   stats:", mm.stats())
    for line in out.getvalue().splitlines():
        print("   log:", line)
    return mm, pubs


N = "AssociationCortexFairy"
print("\n== floor scenarios (ON) ==")
run("cascade before serial start", [lambda m, p: m.cascade_should_skip(N, {}), lambda m, p: m.serial_started(N)])
run("start, skip, success", [lambda m, p: m.serial_started(N), lambda m, p: m.cascade_should_skip(N, {}),
                             lambda m, p: m.serial_succeeded(N, Dir(Rec()), object(), True, p)])
mm, pubs = run("start, skip, FAIL -> fallback; fallback not skipped; second fail no 2nd fallback",
               [lambda m, p: m.serial_started(N), lambda m, p: m.cascade_should_skip(N, {}),
                lambda m, p: m.serial_failed(N, p),
                lambda m, p: m.is_fallback(N, {"k2_fallback": True}),
                lambda m, p: m.cascade_should_skip(N, {"k2_fallback": True}),
                lambda m, p: m.cascade_should_skip(N, {}),
                lambda m, p: m.serial_failed(N, p)])
run("start, FAIL before any skip -> no fallback; later cascade not skipped",
    [lambda m, p: m.serial_started(N), lambda m, p: m.serial_failed(N, p), lambda m, p: m.cascade_should_skip(N, {})])
run("start, skip, success then serial_failed (raise after register)",
    [lambda m, p: m.serial_started(N), lambda m, p: m.cascade_should_skip(N, {}),
     lambda m, p: m.serial_succeeded(N, Dir(Rec()), object(), True, p), lambda m, p: m.serial_failed(N, p)])
run("start, skip, boot()->False", [lambda m, p: m.serial_started(N), lambda m, p: m.cascade_should_skip(N, {}),
                                   lambda m, p: m.serial_succeeded(N, Dir(Rec()), object(), False, p)])
run("start, skip, success with coma-style boot()->True, no record", [lambda m, p: m.serial_started(N),
    lambda m, p: m.cascade_should_skip(N, {}), lambda m, p: m.serial_succeeded(N, Dir(None), object(), True, p)])
run("forged fallback payload before any fallback was sent", [lambda m, p: m.serial_started(N),
    lambda m, p: m.is_fallback(N, {"k2_fallback": True}), lambda m, p: m.cascade_should_skip(N, {"k2_fallback": True})])
run("publish raises", [lambda m, p: m.serial_started(N), lambda m, p: m.cascade_should_skip(N, {}),
                       lambda m, p: m.serial_failed(N, lambda *a: 1 / 0)])

print("\n== OFF (no file) ==")
mm = fresh()
mm.SWITCH_FILE = os.path.join(tmp, "nope.json")
with contextlib.redirect_stdout(io.StringIO()):
    mm.serial_started(N)
    r = mm.cascade_should_skip(N, {})
    f = mm.serial_failed(N, lambda *a: (_ for _ in ()).throw(AssertionError("published while OFF")))
print("describe:", mm.describe(), "| skip:", r, "| fallback:", f, "| stats:", mm.stats())

print("\n== read-once: file appears after first read ==")
mm = fresh()
p = os.path.join(tmp, "late.json")
mm.SWITCH_FILE = p
a = mm.owned()
with open(p, "wb") as fh:
    fh.write(b'{"on": true}')
b = mm.owned()
print("before:", sorted(a), "after file written:", sorted(b))
