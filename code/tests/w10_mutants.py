"""W10 mutant runner: copies main's and mutated heartbeat_registry.py into a temp dir and
runs test_w10_liveness.py against each. Controls must fail on MAIN, every mutant must fail.

    python3 code/tests/w10_mutants.py            (repo root = two levels up; needs origin/main)
"""
import os, subprocess, sys, tempfile
SP = tempfile.mkdtemp(prefix="w10_mut_")
REPO = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(REPO, "code/consciousness/heartbeat_registry.py")
MAIN = os.path.join(SP, "hbr_main.py")
subprocess.run(["git", "-C", REPO, "show", "origin/main:code/consciousness/heartbeat_registry.py"],
               stdout=open(MAIN, "wb"), check=True)
src = open(SRC, "rb").read().decode()
MUT = {
    "M1_gated_still_stamps": ("if not _lfd:  # W10: ON -> a gated beat is not a delivery", "if True:  # mutant"),
    "M2_default_on": ('os.environ.get("AKASHIC_LIVENESS_FROM_DELIVERY", "0") == "1"',
                      'os.environ.get("AKASHIC_LIVENESS_FROM_DELIVERY", "1") == "1"'),
    "M3_ne_zero": ('os.environ.get("AKASHIC_LIVENESS_FROM_DELIVERY", "0") == "1"',
                   'os.environ.get("AKASHIC_LIVENESS_FROM_DELIVERY", "0") != "0"'),
    "M4_inflight_still_stamps": ("if not _lfd:  # W10: ON -> still busy with an older beat, not delivered",
                                 "if True:  # mutant"),
    "M5_obj_stamps_gated_too": ("                if _obj is not None:\r\n", "                if _obj is not None and not _lfd:\r\n"),
    "M6_no_beat_record": ("if self._liveness_from_delivery:  # W10: remember", "if False:  # W10: remember"),
}
runs = [("MAIN", MAIN), ("FIX", SRC)]
for k, (a, b) in MUT.items():
    assert src.count(a) == 1, k
    p = os.path.join(SP, f"hbr_{k}.py")
    open(p, "wb").write(src.replace(a, b).encode())
    runs.append((k, p))
for label, path in runs:
    env = dict(os.environ, W10_HBR_PATH=path, W10_REF_PATH=MAIN)
    env.pop("AKASHIC_LIVENESS_FROM_DELIVERY", None)
    r = subprocess.run([sys.executable, "-m", "unittest", "test_w10_liveness"], cwd=os.path.join(REPO, "code/tests"),
                       env=env, capture_output=True, text=True)
    failed = [l.split(" ")[1] for l in r.stderr.splitlines() if l.startswith(("FAIL:", "ERROR:"))]
    tail = [l for l in r.stderr.splitlines() if l.startswith(("Ran ", "OK", "FAILED"))]
    print(f"{label:26} {' '.join(tail):40} failing={failed}")
