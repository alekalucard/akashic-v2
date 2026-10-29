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
TF = os.path.join(os.path.dirname(HERE), "postal_core", "tensor_fabric.py")
TF_GIT_PATH = "code/postal_core/python/postal_core/tensor_fabric.py"

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
    "M6 accepts ' 1' / 'true'": ('os.environ.get("AKASHIC_RETURN_TO_SENDER", "0") == "1"',
                                 'os.environ.get("AKASHIC_RETURN_TO_SENDER", "0").strip().lower() in ("1", "true")'),
    "M7 source before _sender": ('for _k in ("_sender", "source"):', 'for _k in ("source", "_sender"):'),
    "M8 global floor dropped": ("self.global_rate = max(RETURN_GLOBAL_FLOOR, global_rate",
                                "self.global_rate = max(0, global_rate"),
    "M9 rate table never cleared": ("                    self._window.clear()\n",
                                    "                    pass\n"),
    "M10 fan-out order reversed (OFF path)": ("        _pools_touched = set()\n",
                                              "        subs = subs[::-1]\n        _pools_touched = set()\n"),
    "M11 tensor_fabric stamp ON when unset": ('_STAMP_SENDER = os.environ.get("AKASHIC_RETURN_TO_SENDER", "0") == "1"',
                                               '_STAMP_SENDER = os.environ.get("AKASHIC_RETURN_TO_SENDER", "1") != "0"', "tf"),
    "M12 tensor_fabric stamp overwrites _sender": ('and "_sender" not in payload:', ':', "tf"),
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


def run(path, original, tf):
    env = dict(os.environ, W2_FALLBACK=path, W2_ORIGINAL=original, W2_TENSOR_FABRIC=tf)
    for k in ("AKASHIC_RETURN_TO_SENDER", "AKASHIC_POSTAL_PREFIX_ANY_DEPTH", "AKASHIC_RETURN_RATE",
              "AKASHIC_RETURN_RING", "AKASHIC_RETURN_GLOBAL_RATE"):
        env.pop(k, None)
    p = subprocess.run([sys.executable, "-m", "unittest", "-q", "test_w2_return_to_sender"],
                       cwd=HERE, env=env, capture_output=True, text=True, timeout=900)
    tail = [l for l in p.stderr.splitlines() if l.startswith(("Ran ", "OK", "FAILED"))]
    m = re.search(r"failures=(\d+)", p.stderr)
    e = re.search(r"errors=(\d+)", p.stderr)
    bad = (int(m.group(1)) if m else 0) + (int(e.group(1)) if e else 0)
    if not any(l.startswith("Ran ") for l in tail):
        return None, bad, "INVALID RUN (no unittest summary): " + p.stderr.strip().splitlines()[-1][:120]
    return p.returncode == 0, bad, " ".join(tail)


def git_show(path):
    return subprocess.run(["git", "show", "origin/main:" + path], cwd=REPO,
                          capture_output=True, check=True).stdout


def mutate(src: bytes, old: str, new: str, name: str) -> bytes:
    """Apply a text anchor to bytes, matching the file's own line endings (CRLF or LF)."""
    crlf = b"\r\n" in src
    conv = (lambda t: t.replace("\r\n", "\n").replace("\n", "\r\n")) if crlf else (lambda t: t)
    o, n = conv(old).encode(), conv(new).encode()
    assert src.count(o) == 1, (name, src.count(o))
    return src.replace(o, n)


def main():
    tmp = tempfile.mkdtemp(prefix="w2_matrix_")
    original = os.path.join(tmp, "original.py")
    original_tf = os.path.join(tmp, "original_tensor_fabric.py")
    open(original, "wb").write(git_show(GIT_PATH))
    open(original_tf, "wb").write(git_show(TF_GIT_PATH))
    fix_src = open(FIX, "rb").read()
    tf_src = open(TF, "rb").read()
    rows = [("CONTROL original (main fallback + main tensor_fabric)", original, original_tf, False),
            ("FIX", FIX, TF, True)]
    for name, spec in MUTANTS.items():
        old, new = spec[0], spec[1]
        on_tf = len(spec) > 2 and spec[2] == "tf"
        mp = os.path.join(tmp, re.sub(r"\W+", "_", name) + ".py")
        open(mp, "wb").write(mutate(tf_src if on_tf else fix_src, old, new, name))
        rows.append((name, FIX if on_tf else mp, mp if on_tf else TF, False))
    ok_all = True
    for name, path, tf, want_pass in rows:
        passed, bad, tail = run(path, original, tf)
        verdict = "as expected" if passed == want_pass else "UNEXPECTED"
        ok_all &= passed == want_pass
        state = "PASS" if passed else ("FAIL" if passed is False else "ERROR")
        print("%-52s %-5s failing=%-2d %s  [%s]" % (name, state, bad, verdict, tail))
    sys.exit(0 if ok_all else 1)


if __name__ == "__main__":
    main()
