"""Run tools/tests/test_w8_ears.py against: the fixed files, the CONTROL (the 7 files as they are on
origin/nous/w3-dead-letter-triage, read with `git show`), and near-miss MUTANTS of the fix.
Expected: fixed passes; control and every mutant fail. Copies live in a temp dir only.

    python3 tools/tests/run_w8_control_and_mutants.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TEST = HERE / "test_w8_ears.py"
BASE = "origin/nous/w3-dead-letter-triage"
sys.path.insert(0, str(HERE))
from test_w8_ears import FILES, EMB, CAR, PRO, FOR  # noqa: E402  (test module imports no code/)

MUTANTS = {
    # switch defaults to ON when unset
    "M1 default on": [(EMB, 'os.environ.get("AKASHIC_PREFIX_EARS", "0") == "1"',
                       'os.environ.get("AKASHIC_PREFIX_EARS", "1") == "1"')],
    # strips only the '*', leaving a trailing dot: "umf.signal." never matches anything
    "M2 strip only '*'": [(EMB, "return topic[:-2]", "return topic[:-1]")],
    # one site of a two-site ear forgotten (diary.* in the Cardinal list)
    "M3 diary site missed": [(CAR, '        _prefix_ear("diary.*"),', '        "diary.*",')],
    # spelling fix gone one character wrong
    "M4 near-miss spellfix": [(PRO, '"skill.level_up" if', '"skill.levelup_" if')],
    # helper also strips any ".*" switch-independent ('!=' instead of '==' on "0")
    "M5 inverted test": [(FOR, 'os.environ.get("AKASHIC_PREFIX_EARS", "0") == "1"',
                          'os.environ.get("AKASHIC_PREFIX_EARS", "0") != "1"')],
}


def run(root: Path):
    env = dict(os.environ, W8_CODE_ROOT=str(root))
    env.pop("AKASHIC_PREFIX_EARS", None)
    env.pop("AKASHIC_TOPIC_SPELLFIX", None)
    r = subprocess.run([sys.executable, "-W", "ignore", "-m", "unittest", str(TEST)], env=env,
                       capture_output=True, text=True, cwd=REPO)
    last = [l for l in r.stderr.strip().splitlines() if l.strip()][-1]
    return r.returncode == 0, last


def tree(td: Path, name: str, getter) -> Path:
    root = td / name
    for f in FILES:
        p = root / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(getter(f))
    return root


def main():
    results = [("FIXED", True) + run(REPO)]
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        base = lambda f: subprocess.run(["git", "show", f"{BASE}:{f}"], cwd=REPO, capture_output=True,
                                        check=True).stdout
        results.append(("CONTROL (base branch files)", False) + run(tree(td, "control", base)))
        for name, edits in MUTANTS.items():
            def get(f, edits=edits):
                b = (REPO / f).read_bytes()
                for ef, a, c in edits:
                    if ef == f:
                        assert b.count(a.encode()) == 1, f"{name}: anchor not once in {f}: {a!r}"
                        b = b.replace(a.encode(), c.encode())
                return b
            results.append((name, False) + run(tree(td, name.split()[0], get)))
    ok_all = True
    for name, want, passed, last in results:
        good = passed == want
        ok_all &= good
        print(f"{'OK ' if good else 'BAD'} {name:30s} tests {'PASS' if passed else 'FAIL'}  ({last})")
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
