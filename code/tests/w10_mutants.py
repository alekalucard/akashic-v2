"""W10 mutant runner: copies main's and mutated heartbeat_registry.py / break_room.py into a
temp dir and runs test_w10_liveness.py against each. MAIN (controls) must fail, FIX must pass,
every mutant must fail. Exits 1 on anything unexpected.

    python3 code/tests/w10_mutants.py [repo_root]      (needs origin/main fetched)
"""
import os, subprocess, sys, tempfile
SP = tempfile.mkdtemp(prefix="w10_mut_")
REPO = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HBR = os.path.join(REPO, "code/consciousness/heartbeat_registry.py")
BR = os.path.join(REPO, "code/consciousness/break_room.py")
MAIN = os.path.join(SP, "hbr_main.py")
with open(MAIN, "wb") as f:
    subprocess.run(["git", "-C", REPO, "show", "origin/main:code/consciousness/heartbeat_registry.py"],
                   stdout=f, check=True)
FLAGEXPR = 'os.environ.get("AKASHIC_LIVENESS_FROM_DELIVERY", "0") == "1"'
MUT = {  # name: (file, old, new)
    "M1_default_on": (HBR, FLAGEXPR, FLAGEXPR.replace('"0") == "1"', '"1") == "1"')),
    "M2_ne_zero": (HBR, FLAGEXPR, FLAGEXPR.replace('== "1"', '!= "0"')),
    "M3_handled_not_recorded": (HBR, "if self._liveness_from_delivery:  # W10 watch-only", "if False:  # W10 watch-only"),
    "M4_handled_ignores_switch": (HBR, "if self._liveness_from_delivery:  # W10 watch-only", "if True:  # W10 watch-only"),
    "M5_old_design_gates_watchdog_stamp": (HBR, "                self._last_delivered_ts[_name] = _now_liveness\r\n",
                                           "                if not _lfd:\r\n                    self._last_delivered_ts[_name] = _now_liveness\r\n"),
    "M6_handled_on_raise_too": (HBR, "            self._total_errors += 1\r\n",
                                "            self._total_errors += 1\r\n            if self._liveness_from_delivery:\r\n                self._last_handled_ts[name] = time.time()\r\n"),
    "M7_report_reads_wrong_field": (BR, 'snap.get("last_handled_beat", {})', 'snap.get("last_delivered_beat", {})'),
}
runs = [("MAIN", {"W10_HBR_PATH": MAIN}), ("FIX", {})]
for k, (path, a, b) in MUT.items():
    src = open(path, "rb").read().decode()
    assert src.count(a) == 1, k
    p = os.path.join(SP, f"{k}_{os.path.basename(path)}")
    with open(p, "wb") as f:
        f.write(src.replace(a, b).encode())
    runs.append((k, {"W10_HBR_PATH" if path == HBR else "W10_BR_PATH": p}))
bad = []
for label, extra in runs:
    env = dict(os.environ, W10_REF_PATH=MAIN, **extra)
    env.pop("AKASHIC_LIVENESS_FROM_DELIVERY", None)
    r = subprocess.run([sys.executable, "-m", "unittest", "test_w10_liveness"], cwd=os.path.join(REPO, "code/tests"),
                       env=env, capture_output=True, text=True)
    failed = [l.split(" ")[1] for l in r.stderr.splitlines() if l.startswith(("FAIL:", "ERROR:"))]
    tail = [l for l in r.stderr.splitlines() if l.startswith(("Ran ", "OK", "FAILED"))]
    print(f"{label:36} {' '.join(tail):42} failing={failed}")
    if (label == "FIX") != (r.returncode == 0):
        bad.append(label)
print("UNEXPECTED: " + ", ".join(bad) if bad else "ALL AS EXPECTED (main fails, fix passes, all mutants killed)")
sys.exit(1 if bad else 0)
