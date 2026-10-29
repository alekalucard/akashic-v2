"""W15 runner: the test suite against (1) main's file = CONTROL, (2) this branch's
file = FIX, (3) each MUTANT. Temp dir only. Prints one line per target.

Run:  python code/tests/w15_mutants.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(REPO, "code", "infrastructure", "manifold_memory.py")
TEST = os.path.join(HERE, "test_w15_edge_slot.py")

FIX_LINE = 'if os.environ.get("AKASHIC_EDGE_SLOT_FIX", "0") == "1":'
MUTANTS = {
    # switch ON when unset
    "M1_default_on": [(FIX_LINE, 'if os.environ.get("AKASHIC_EDGE_SLOT_FIX", "1") == "1":')],
    # the "!= with default" trap: ON when unset
    "M2_ne_default": [(FIX_LINE, 'if os.environ.get("AKASHIC_EDGE_SLOT_FIX", "1") != "0":')],
    # wrong switch name: the fix never runs
    "M3_wrong_name": [(FIX_LINE, 'if os.environ.get("AKASHIC_EDGE_SLOT_FIXED", "0") == "1":')],
    # fix in _delete_edge instead: stops freeing genuinely deleted slots too
    "M4_never_free": [
        ("        self._free_edge_slots.append(slot)\n\n        # Update adjacency",
         "        if os.environ.get(\"AKASHIC_EDGE_SLOT_FIX\", \"0\") != \"1\":\n"
         "            self._free_edge_slots.append(slot)\n\n        # Update adjacency")],
    # removes the slot only when it is not the last entry (off by one)
    "M5_skip_last": [("                    while slot in self._free_edge_slots:\n"
                      "                        self._free_edge_slots.remove(slot)",
                      "                    while slot in self._free_edge_slots[:-1]:\n"
                      "                        self._free_edge_slots.remove(slot)")],
    # clears the whole free list (equivalent here: single-threaded, list == [slot])
    "M6_clear_all": [("                    while slot in self._free_edge_slots:\n"
                      "                        self._free_edge_slots.remove(slot)",
                      "                    self._free_edge_slots.clear()")],
    # node-evict guard checks only the deleted flag, not the endpoints
    "M7_guard_flag_only": [("                            (_er[0] == min_slot and _er[1] == neighbor_id) or",
                            "                            True or")],
    # node-evict guard checks only the endpoints, not the deleted flag
    "M8_guard_ends_only": [("                    if _er[4] == FLAG_DELETED or not (",
                            "                    if False or not (")],
}


def run(path, label):
    env = dict(os.environ, W15_MM_PATH=path)
    env.pop("AKASHIC_EDGE_SLOT_FIX", None)
    p = subprocess.run([sys.executable, "-W", "ignore", TEST], env=env,
                       capture_output=True, text=True, timeout=600)
    tail = [l for l in p.stderr.splitlines() if l.startswith(("Ran ", "OK", "FAILED"))]
    fails = [l.split(" (")[0].replace("FAIL: ", "").replace("ERROR: ", "")
             for l in p.stderr.splitlines() if l.startswith(("FAIL:", "ERROR:"))]
    print("%-16s rc=%d %s %s" % (label, p.returncode, " ".join(tail), fails))
    return p.returncode


def main():
    tmp = tempfile.mkdtemp(prefix="w15m_")
    main_src = subprocess.check_output(
        ["git", "-C", REPO, "show", "origin/main:code/infrastructure/manifold_memory.py"])
    mp = os.path.join(tmp, "main_mm.py")
    open(mp, "wb").write(main_src)
    os.environ["W15_MAIN_PATH"] = mp
    run(mp, "CONTROL(main)")
    run(SRC, "FIX(branch)")
    src = open(SRC, "rb").read().decode("utf-8")
    for name, subs in MUTANTS.items():
        s = src
        for old, new in subs:
            assert s.count(old) == 1, (name, old)
            s = s.replace(old, new)
        p = os.path.join(tmp, name + ".py")
        open(p, "wb").write(s.encode("utf-8"))
        run(p, name)


if __name__ == "__main__":
    main()
