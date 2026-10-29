"""W11: run test_w11_bind_carryover.py against main, this branch, and near-miss mutants of this branch. Synthetic temp dirs only.

    python3 -I code/tests/w11_mutation_run.py <main_dir>

<main_dir> holds main's copies: infrastructure/{tardis_fix,tardis_backlog,tardis_timing,manifold_memory}.py and server.py
(export them with `git show origin/main:code/<path> > <main_dir>/<path>`). Expected: main FAILS the CONTROL tests, the branch
passes all, every mutant fails at least one test.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
FILES = ["infrastructure/__init__.py", "infrastructure/tardis_fix.py", "infrastructure/tardis_backlog.py",
         "infrastructure/tardis_timing.py", "infrastructure/manifold_memory.py", "server.py"]
TEST = os.path.join(HERE, "test_w11_bind_carryover.py")

MUTANTS = {
    "M1 env switch default flipped (ON when unset)": [
        ("infrastructure/tardis_fix.py", 'os.environ.get(name, "0") == "1"', 'os.environ.get(name, "1") == "1"')],
    "M2 verbatim without the exact round-trip check": [
        ("infrastructure/tardis_backlog.py", "if json.loads(json.dumps(keep, ensure_ascii=True)) != keep:", "if False:")],
    "M3 never-delete gate inverted": [
        ("infrastructure/tardis_backlog.py", "            if _carry():\n                return                                  # W11",
         "            if not _carry():\n                return                                  # W11")],
    "M4 eviction laps without the env gate": [
        ("infrastructure/manifold_memory.py", "_tfl0 if (_tfl0 is not None and _w11_timing()) else None", "_tfl0")],
    "M5 server hook default flipped (ON when unset)": [
        ("server.py", 'os.environ.get("AKASHIC_BIND_CARRYOVER", "0") == "1"', 'os.environ.get("AKASHIC_BIND_CARRYOVER", "1") == "1"')],
    "M6 persist_owner without its switch": [
        ("infrastructure/tardis_backlog.py", "        if not _carry():\n            return False\n        with _OWNER_LOCK:",
         "        with _OWNER_LOCK:")],
    "M7 verbatim keeps the _tf_ bookkeeping keys": [
        ("infrastructure/tardis_backlog.py", 'if not (isinstance(k, str) and k.startswith("_tf_"))', "")],
    "M8 ledger trimmed even with carryover ON": [
        ("infrastructure/tardis_backlog.py", "    if not _carry():                                    # W11: done-*", "    if True:                                    # W11: done-*")],
    "M9 reboot hook moved after os._exit (unreachable)": [
        ("server.py", '                _w11_bind_carryover("reboot")   # W11: OFF (AKASHIC_BIND_CARRYOVER unset) = no-op\n', ""),
        ("server.py", '                    os._exit(0)\n            threading.Thread(target=_do_reboot',
         '                    os._exit(0)\n                    _w11_bind_carryover("reboot")\n            threading.Thread(target=_do_reboot')],
    "M10 ctrl_c hook moved after shutdown_system()": [
        ("server.py", '        _w11_bind_carryover("ctrl_c")   # W11: OFF (AKASHIC_BIND_CARRYOVER unset) = no-op\n', ""),
        ("server.py", '            SYSTEM.shutdown_fairy.wait_for_completion(timeout=8.0)\n        shutdown_system()\n',
         '            SYSTEM.shutdown_fairy.wait_for_completion(timeout=8.0)\n        shutdown_system()\n        _w11_bind_carryover("ctrl_c")\n')],
}


def build(src_dir, dst):
    for f in FILES:
        os.makedirs(os.path.dirname(os.path.join(dst, f)), exist_ok=True)
        s = os.path.join(src_dir, f)
        if os.path.exists(s):
            shutil.copyfile(s, os.path.join(dst, f))
        else:
            open(os.path.join(dst, f), "w").close()


def run(tree):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AKASHIC_")}
    env["W11_TREE"] = tree
    p = subprocess.run([sys.executable, "-I", "-W", "ignore", TEST], env=env, capture_output=True, text=True, timeout=600)
    out = p.stdout + p.stderr
    bad = sorted(set(re.findall(r"^(?:FAIL|ERROR): (\S+) \(__main__\.(\S+)\)", out, re.M)))
    m = re.search(r"Ran (\d+) test", out)
    return (int(m.group(1)) if m else -1), bad, p.returncode


def main():
    main_dir = sys.argv[1]
    root = tempfile.mkdtemp(prefix="w11_mut_")
    try:
        rows = []
        for label, src in (("main", main_dir), ("branch", CODE)):
            t = os.path.join(root, label)
            build(src, t)
            rows.append((label, run(t)))
        for label, edits in MUTANTS.items():
            t = os.path.join(root, "mut%d" % len(rows))
            build(CODE, t)
            for f, old, new in edits:
                p = os.path.join(t, f)
                s = open(p, encoding="utf-8").read()
                assert s.count(old) >= 1, (label, old)
                open(p, "w", encoding="utf-8").write(s.replace(old, new))
            rows.append((label, run(t)))
        for label, (n, bad, rc) in rows:
            print("%-50s ran=%d failed=%d rc=%d" % (label, n, len(bad), rc))
            for name, cls in bad:
                print("      FAILED %s" % cls)
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
