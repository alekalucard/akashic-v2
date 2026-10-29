import os, subprocess, sys, tempfile
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GATE = os.path.join(ROOT, "code/infrastructure/coma_gate.py")
SERVER = os.path.join(ROOT, "code/server.py")
TEST = os.path.join(ROOT, "code/tests/test_w13_coma_gate.py")
MUT = [
    ("M1 gate switch ON when unset", GATE, 'os.environ.get(SWITCH, "0") == "1"', 'os.environ.get(SWITCH, "1") == "1"'),
    ("M2 gate switch != '0'", GATE, 'os.environ.get(SWITCH, "0") == "1"', 'os.environ.get(SWITCH, "0") != "0"'),
    ("M3 drop the asleep check", GATE, '        if not getattr(inst, "_comatose", False):\n            return "awake"\n', ''),
    ("M4 owner sweep ignores gate:/owner split", GATE, 'allowed = owner_open if owner_only else gate_open', 'allowed = gate_open'),
    ("M5 allow-list not read live (cached)", GATE, 'def read_allow_list(path: str = None):\n',
     '_CACHE = []\ndef read_allow_list(path: str = None):\n    if _CACHE:\n        return _CACHE[0]\n    _CACHE.append(_read_allow_list(path))\n    return _CACHE[0]\ndef _read_allow_list(path: str = None):\n'),
    ("M6 wake bypassed: on_boot called directly", GATE, 'wake(reason="coma_gate:%s" % source)', 'inst.on_boot()'),
    ("S1 server switch ON when unset", SERVER, 'os.environ.get("AKASHIC_COMA_GATE", "0") == "1"', 'os.environ.get("AKASHIC_COMA_GATE", "1") == "1"'),
    ("S2 server: drop the post-build hook", SERVER,
     '                    if _coma_gate is not None:\n                        _coma_gate.on_boot_request(payload, instance=instance)\n',
     '                    pass\n'),
    ("S3 server: early hook does not return (falls through)", SERVER,
     '== "woke"):\n                    return\n', '== "woke"):\n                    pass\n'),
]
tmp = tempfile.mkdtemp()
for label, path, old, new in MUT:
    src = open(path, newline="").read()
    assert src.count(old) == 1, label
    out = os.path.join(tmp, os.path.basename(path))
    open(out, "w", newline="").write(src.replace(old, new))
    env = dict(os.environ)
    env["COMA_GATE_SRC" if path == GATE else "SERVER_SRC"] = out
    r = subprocess.run([sys.executable, TEST], env=env, capture_output=True, text=True)
    fails = [l for l in r.stderr.splitlines() if l.startswith(("FAIL:", "ERROR:"))]
    print("%-50s %s  %s" % (label, "KILLED" if r.returncode else "SURVIVED", "; ".join(f.split(" (")[0] for f in fails)))
