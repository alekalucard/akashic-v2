"""Run tools/tests/test_dead_letters.py against: the fixed tool, the CONTROL (the tool as it was on
origin/nous/dead-letters-1028, read with `git show`), and near-miss MUTANTS of the fix.
Expected: fixed passes; control and every mutant fail.

    python3 tools/tests/run_control_and_mutants.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "tools" / "dead_letters.py"
TEST = REPO / "tools" / "tests" / "test_dead_letters.py"
BASE = "origin/nous/dead-letters-1028"

MUTANTS = {
    # receive dropped, route kept
    "M1 no receive alias": [('SUBSCRIBE_METHODS = {"subscribe", "subscribe_cross_plane", "receive"}',
                             'SUBSCRIBE_METHODS = {"subscribe", "subscribe_cross_plane"}')],
    # reached copies found but not added to the scanned set
    "M2 reached twins not scanned": [("return live + [p for p, _ in reached], tests, shadowed, reached",
                                      "return live, tests, shadowed, reached")],
    # method wrapper: forget to skip `self` when mapping the parameter to a call argument
    "M3 method arg index not shifted": [("        if pos is not None and is_method:\n            pos -= 1\n",
                                         "")],
    # twin rule inverted to 'any import at all' (bare import of the twin counts too)
    "M4 twin rule counts bare imports": [('pats = [re.compile(r"(?:from|import)\\s+" + re.escape(full) + r"\\b"),',
                                          'pats = [re.compile(r"(?:from|import)\\s+(?:fairies\\.)?" + re.escape(full.split(".", 1)[1]) + r"\\b"),')],
}


def run(path: Path) -> tuple[bool, str]:
    env = dict(os.environ, DEAD_LETTERS_PATH=str(path))
    r = subprocess.run([sys.executable, "-W", "ignore", "-m", "unittest", str(TEST)], env=env,
                       capture_output=True, text=True, cwd=REPO)
    last = [l for l in r.stderr.strip().splitlines() if l.strip()][-1]
    return r.returncode == 0, last


def main():
    src = TOOL.read_text()
    results = []
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        results.append(("FIXED", True) + run(TOOL))
        ctrl = td / "control_dead_letters.py"
        ctrl.write_text(subprocess.run(["git", "show", f"{BASE}:tools/dead_letters.py"], cwd=REPO,
                                       capture_output=True, text=True, check=True).stdout)
        results.append(("CONTROL (base branch tool)", False) + run(ctrl))
        for name, edits in MUTANTS.items():
            m = src
            for a, b in edits:
                assert m.count(a) == 1, f"{name}: anchor not found once: {a!r}"
                m = m.replace(a, b)
            p = td / f"mutant_{name.split()[0]}.py"
            p.write_text(m)
            results.append((name, False) + run(p))
    ok_all = True
    for name, want, passed, last in results:
        good = passed == want
        ok_all &= good
        print(f"{'OK ' if good else 'BAD'} {name:36s} tests {'PASS' if passed else 'FAIL'}  ({last})")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
