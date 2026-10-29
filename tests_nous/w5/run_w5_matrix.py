"""Run tests_nous/w5 against CONTROL trees and near-miss MUTANTS (REVIEW_W5 fix round, 10-29).

    python3 tests_nous/w5/run_w5_matrix.py

Each variant is a temp copy of code/ (git archive for a commit, hard-link copy + one rewritten
file for a mutant); the suite is pointed at it with NOUS_W5_ROOT. Expected: every CONTROL and
every MUTANT fails, FIX passes.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
H = "code/fairies/P30_Cognition/HarmonicCortexFairy/fairy.py"
A = "code/fairies/P00_Autonomic/AutonomyFairy/fairy.py"

MUTANTS = {
    "M1 switch ON when unset": (H, b'os.environ.get("AKASHIC_HARMONIC_SUBSCRIBE", "0") == "1"',
                                b'os.environ.get("AKASHIC_HARMONIC_SUBSCRIBE", "1") != "0"'),
    "M2 bypass the bridge (_fabric)": (H, b"_hsub = (self.post.subscribe\r\n",
                                       b"_hsub = (self.post._fabric.subscribe\r\n"),
    "M3 a subscription loses its name": (H, b'                    name=f"{self.ACTOR_NAME}_audio_speech"\r\n',
                                         b""),
    "M4 AutonomyFairy caller not renamed": (A, b'            "DreamSeedFairy",\r\n',
                                            b'            "DreamSeedsFairy",\r\n'),
}


def tree_at(ref, tmp):
    d = os.path.join(tmp, re.sub(r"\W+", "_", ref))
    os.makedirs(d)
    tar = subprocess.run(["git", "archive", ref, "code"], cwd=REPO, capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", d], input=tar, check=True)
    return d


def mutant_tree(name, path, old, new, tmp):
    d = os.path.join(tmp, re.sub(r"\W+", "_", name))
    shutil.copytree(os.path.join(REPO, "code"), os.path.join(d, "code"), copy_function=os.link,
                    ignore=shutil.ignore_patterns("__pycache__", "target"))
    target = os.path.join(d, path)
    src = open(target, "rb").read()
    assert src.count(old) == 1, name
    os.remove(target)                                  # break the hard link before writing
    open(target, "wb").write(src.replace(old, new))
    return d


def run(root):
    env = dict(os.environ, NOUS_W5_ROOT=root)
    p = subprocess.run([sys.executable, "-I", "-m", "unittest", "discover", "-s", "tests_nous/w5"],
                       cwd=REPO, env=env, capture_output=True, text=True, timeout=600)
    summary = " ".join(l for l in p.stderr.splitlines() if l.startswith(("Ran ", "OK", "FAILED")))
    return p.returncode == 0, summary


def main():
    tmp = tempfile.mkdtemp(prefix="w5_matrix_")
    rows = [("CONTROL origin/main", tree_at("origin/main", tmp), False),
            ("CONTROL a6b2b02 (pre-review W5)", tree_at("a6b2b02", tmp), False),
            ("FIX (this tree)", REPO, True)]
    for name, (path, old, new) in MUTANTS.items():
        rows.append((name, mutant_tree(name, path, old, new, tmp), False))
    ok = True
    for name, root, want in rows:
        passed, summary = run(root)
        ok &= passed == want
        print("%-36s %-4s %-11s [%s]" % (name, "PASS" if passed else "FAIL",
                                         "as expected" if passed == want else "UNEXPECTED", summary))
    shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
