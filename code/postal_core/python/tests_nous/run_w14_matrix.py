"""Run test_w14_no_double.py against the ORIGINALS, the FIX and MUTANTS of _python_fallback.py.

    python3 code/postal_core/python/tests_nous/run_w14_matrix.py

Originals come from git into a temp dir: origin/nous/w2-return-to-sender (the base this change is made on;
also used as W14_ORIGINAL for the switch-OFF equivalence test) and origin/main.
Expected: both CONTROLs fail, FIX passes, every MUTANT fails. One line per variant.
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
BASE_REF = "origin/nous/w2-return-to-sender"

MUTANTS = {
    # near-misses of the change; each must make at least one test fail
    "M1 switch ON when unset": ('os.environ.get("AKASHIC_POSTAL_NO_DOUBLE", "0") == "1"',
                                'os.environ.get("AKASHIC_POSTAL_NO_DOUBLE", "1") != "0"'),
    "M2 drops the FIRST add instead (order changes)": (
        "                if len(parts) >= 2 and not self._no_double:\n",
        "                if len(parts) >= 2:\n",
        "                if parent != intent:\n",
        "                if parent != intent and not self._no_double:\n"),
    "M3 only for 4+ segments": ("                if len(parts) >= 2 and not self._no_double:\n",
                                "                if len(parts) >= 2 and not (self._no_double and len(parts) >= 4):\n"),
    "M4 accepts ' 1' / 'true'": ('os.environ.get("AKASHIC_POSTAL_NO_DOUBLE", "0") == "1"',
                                 'os.environ.get("AKASHIC_POSTAL_NO_DOUBLE", "0").strip().lower() in ("1", "true")'),
    "M5 block removed even when OFF": ("                if len(parts) >= 2 and not self._no_double:\n",
                                       "                if False:\n"),
    "M6 condition inverted": ("                if len(parts) >= 2 and not self._no_double:\n",
                              "                if len(parts) >= 2 and self._no_double:\n"),
    # added after the REVIEW (X4-X7 there): each passed the first version of the suite
    "M7 ON drops base subs for 5+ segments": (
        "                subs.extend(self._subscribers.get(topic, []))\n",
        "                if not (self._no_double and len(parts) >= 5):\n"
        "                    subs.extend(self._subscribers.get(topic, []))\n"),
    "M8 new line written with LF": "RAW",
    "M9 extra metrics key on the OFF path": (
        '        self._no_double = os.environ.get("AKASHIC_POSTAL_NO_DOUBLE", "0") == "1"\n',
        '        self._no_double = os.environ.get("AKASHIC_POSTAL_NO_DOUBLE", "0") == "1"\n'
        '        self._metrics["w14_no_double"] = 0\n'),
    "M10 prefix-any-depth stops at depth 4": ("for _k in range(3, len(parts)):",
                                              "for _k in range(3, min(len(parts), 5)):"),
}
RAW = {
    "M8 new line written with LF": (b'        self._no_double = os.environ.get("AKASHIC_POSTAL_NO_DOUBLE", "0") == "1"\r\n',
                                    b'        self._no_double = os.environ.get("AKASHIC_POSTAL_NO_DOUBLE", "0") == "1"\n'),
}


def run(path, original):
    env = dict(os.environ, W14_FALLBACK=path, W14_ORIGINAL=original)
    for k in ("AKASHIC_RETURN_TO_SENDER", "AKASHIC_POSTAL_PREFIX_ANY_DEPTH", "AKASHIC_POSTAL_NO_DOUBLE",
              "AKASHIC_RETURN_RATE", "AKASHIC_RETURN_RING", "AKASHIC_RETURN_GLOBAL_RATE"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-m", "unittest", "-q", "test_w14_no_double"],
                       cwd=HERE, env=env, capture_output=True, text=True, timeout=900)
    tail = [l for l in p.stderr.splitlines() if l.startswith(("Ran ", "OK", "FAILED"))]
    m = re.search(r"failures=(\d+)", p.stderr)
    e = re.search(r"errors=(\d+)", p.stderr)
    bad = (int(m.group(1)) if m else 0) + (int(e.group(1)) if e else 0)
    if not any(l.startswith("Ran ") for l in tail):
        return None, bad, "INVALID RUN (no unittest summary): " + p.stderr.strip().splitlines()[-1][:120]
    return p.returncode == 0, bad, " ".join(tail)


def git_show(ref):
    return subprocess.run(["git", "show", ref + ":" + GIT_PATH], cwd=REPO,
                          capture_output=True, check=True).stdout


def mutate(src: bytes, pairs, name: str) -> bytes:
    """Apply text anchors to bytes, matching the file's own line endings (CRLF or LF)."""
    crlf = b"\r\n" in src
    conv = (lambda t: t.replace("\r\n", "\n").replace("\n", "\r\n")) if crlf else (lambda t: t)
    for old, new in zip(pairs[0::2], pairs[1::2]):
        o, n = conv(old).encode(), conv(new).encode()
        assert src.count(o) == 1, (name, old, src.count(o))
        src = src.replace(o, n)
    return src


def main():
    tmp = tempfile.mkdtemp(prefix="w14_matrix_")
    base = os.path.join(tmp, "base_w2.py")
    main_ = os.path.join(tmp, "main.py")
    open(base, "wb").write(git_show(BASE_REF))
    open(main_, "wb").write(git_show("origin/main"))
    fix_src = open(FIX, "rb").read()
    rows = [("CONTROL base (" + BASE_REF + ")", base, False),
            ("CONTROL origin/main", main_, False),
            ("FIX", FIX, True)]
    for name, pairs in MUTANTS.items():
        mp = os.path.join(tmp, re.sub(r"\W+", "_", name) + ".py")
        if pairs == "RAW":                                        # byte-level, no line-ending conversion
            o, n = RAW[name]
            assert fix_src.count(o) == 1, name
            out = fix_src.replace(o, n)
        else:
            out = mutate(fix_src, pairs, name)
        open(mp, "wb").write(out)
        rows.append((name, mp, False))
    ok_all = True
    for name, path, want_pass in rows:
        passed, bad, tail = run(path, base)
        verdict = "as expected" if passed == want_pass else "UNEXPECTED"
        ok_all &= passed == want_pass
        state = "PASS" if passed else ("FAIL" if passed is False else "ERROR")
        print("%-50s %-5s failing=%-2d %s  [%s]" % (name, state, bad, verdict, tail), flush=True)
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
