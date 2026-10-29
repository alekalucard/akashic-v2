"""Run test_w2_return_to_sender.py against ORIGINAL (pre-W2), FIX, and MUTANTS of _python_fallback.py.

    python3 code/postal_core/python/tests_nous/run_w2_matrix.py

ORIGINAL is taken from git (origin/main) into a temp dir. Expected: ORIGINAL fails (CONTROL),
FIX passes, every MUTANT fails. Prints one line per variant.
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(os.path.dirname(HERE), "postal_core", "_python_fallback.py")
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
GIT_PATH = "code/postal_core/python/postal_core/_python_fallback.py"

MUTANTS = {
    # near-misses of the change; each must make at least one test fail
    "M1 switch ON when unset": ('os.environ.get("AKASHIC_RETURN_TO_SENDER", "0") == "1"',
                                'os.environ.get("AKASHIC_RETURN_TO_SENDER", "1") != "0"'),
    "M2 no return-of-return guard": ("        if is_return:\n",
                                     "        if False:\n"),
    "M3 prefix range includes intent": ("for _k in range(3, len(parts)):",
                                        "for _k in range(3, len(parts) + 1):"),
    "M4 rate floor dropped": ("self.rate = max(RETURN_RATE_FLOOR, rate_per_intent if rate_per_intent is not None",
                              "self.rate = max(0, rate_per_intent if rate_per_intent is not None"),
    "M5 returned letter also counted published": (
        """        if not subs and self._return_office is not None:
            self._return_to_sender(intent, payload, envelope.source, priority)
            return

        self._metrics["messages_published"] += 1""",
        """        self._metrics["messages_published"] += 1
        if not subs and self._return_office is not None:
            self._return_to_sender(intent, payload, envelope.source, priority)
            return"""),
}


def run(path, original):
    env = dict(os.environ, W2_FALLBACK=path, W2_ORIGINAL=original)
    p = subprocess.run([sys.executable, "-m", "unittest", "-q", "test_w2_return_to_sender"],
                       cwd=HERE, env=env, capture_output=True, text=True, timeout=600)
    tail = [l for l in p.stderr.splitlines() if l.startswith(("Ran ", "OK", "FAILED"))]
    m = re.search(r"failures=(\d+)", p.stderr)
    e = re.search(r"errors=(\d+)", p.stderr)
    bad = int(m.group(1)) if m else 0
    bad += int(e.group(1)) if e else 0
    if not any(l.startswith("Ran ") for l in tail):
        return None, bad, "INVALID RUN (no unittest summary): " + p.stderr.strip().splitlines()[-1][:120]
    return p.returncode == 0, bad, " ".join(tail)


def main():
    tmp = tempfile.mkdtemp(prefix="w2_matrix_")
    original = os.path.join(tmp, "original.py")
    with open(original, "w", encoding="utf-8") as f:
        f.write(subprocess.run(["git", "show", "origin/main:" + GIT_PATH], cwd=REPO,
                               capture_output=True, text=True, check=True).stdout)
    fix_src = open(FIX, encoding="utf-8").read()
    rows = [("CONTROL original", original, False), ("FIX", FIX, True)]
    for name, (old, new) in MUTANTS.items():
        assert fix_src.count(old) == 1, name
        mp = os.path.join(tmp, re.sub(r"\W+", "_", name) + ".py")
        with open(mp, "w", encoding="utf-8") as f:
            f.write(fix_src.replace(old, new))
        rows.append((name, mp, False))
    ok_all = True
    for name, path, want_pass in rows:
        passed, bad, tail = run(path, original)
        verdict = "as expected" if passed == want_pass else "UNEXPECTED"
        ok_all &= passed == want_pass
        state = "PASS" if passed else ("FAIL" if passed is False else "ERROR")
        print("%-42s %-5s failing=%-2d %s  [%s]" % (name, state, bad, verdict, tail))
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
