"""W9 test matrix: the same suite against (1) this branch, (2) origin/main's version of every changed file, (3) mutants.

Each variant gets its own minimal code root in a temp dir (infrastructure/__init__.py, manifold_memory.py, portal_gate.py and
the cortex fairy.py, which the suite only reads as text). Nothing outside the temp dir is written.

    python docs/nous/W9/run_w9_matrix.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
SUITE = os.path.join(HERE, "test_w9_writer_decay.py")
FILES = ["code/infrastructure/__init__.py", "code/infrastructure/manifold_memory.py", "code/infrastructure/portal_gate.py",
         "code/infrastructure/portal_interior.py",      # copied, never imported or run: PortalGate() checks it exists
         "code/fairies/P30_Cognition/AssociationCortexFairy/fairy.py"]
CONTROL = "test_control_writer_decays_when_on"

MUTANTS = {
    # name: (file, old, new) -- each a near miss of the change
    "M1_switch_default_on": ("code/infrastructure/portal_gate.py",
                             'return os.environ.get(_WD_SWITCH, "0") == "1"',
                             'return os.environ.get(_WD_SWITCH, "1") == "1"'),
    "M2_interior_check_ignores_tunnels": ("code/infrastructure/portal_gate.py",
                                          '            if getattr(g, "_tunnels", None):\n                return True\n',
                                          ''),
    "M3_no_mid_pass_recheck": ("code/infrastructure/portal_gate.py",
                               "if not writer_decay_on() or cortex_interior_alive():",
                               "if not writer_decay_on():"),
    "M4_exemption_dropped": ("code/infrastructure/manifold_memory.py",
                             "                    if self._AFFECT_DECAY > 0.0 and record[12] not in self._AFFECT_DECAY_TRACER_EXEMPT:\n"
                             "                        _ac = self.read_affect_coupling(slot)\n"
                             "                        if _ac != 1.0:\n"
                             "                            self.write_affect_coupling(slot, _ac + (1.0 - _ac) * self._AFFECT_DECAY)\n"
                             "                        _pr = self.read_paradox_residue(slot)\n"
                             "                        if _pr > 0.0:\n"
                             "                            self.write_paradox_residue(slot, max(0.0, _pr - _pr * self._AFFECT_DECAY))\n"
                             "        return n",
                             "                    if self._AFFECT_DECAY > 0.0:\n"
                             "                        _ac = self.read_affect_coupling(slot)\n"
                             "                        if _ac != 1.0:\n"
                             "                            self.write_affect_coupling(slot, _ac + (1.0 - _ac) * self._AFFECT_DECAY)\n"
                             "                        _pr = self.read_paradox_residue(slot)\n"
                             "                        if _pr > 0.0:\n"
                             "                            self.write_paradox_residue(slot, max(0.0, _pr - _pr * self._AFFECT_DECAY))\n"
                             "        return n"),
    "M5_cadence_wall_clock_tau1": ("code/infrastructure/portal_gate.py",
                                   "    return _WD_TICK_BEATS * interior_decay_interval(tau)",
                                   "    return interior_decay_interval(tau)"),
    "M6_floor_changed": ("code/infrastructure/manifold_memory.py",
                         "                if record[5] > 0.01:  # Only decay active nodes (same floor as decay_all)",
                         "                if record[5] > 0.0:  # Only decay active nodes (same floor as decay_all)"),
    "M7_fairy_hook_ungated": ("code/fairies/P30_Cognition/AssociationCortexFairy/fairy.py",
                              'if os.environ.get("AKASHIC_DECAY_IN_WRITER", "0") == "1":',
                              'if os.environ.get("AKASHIC_DECAY_IN_WRITER", "0") != "0":'),
}


def _root(tmp, name, source):
    root = os.path.join(tmp, name)
    for f in FILES:
        dst = os.path.join(root, f[len("code/"):])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if source == "main":
            data = subprocess.run(["git", "-C", REPO, "show", "origin/main:" + f], capture_output=True, check=True).stdout
        else:
            with open(os.path.join(REPO, f), "rb") as fh:
                data = fh.read()
        with open(dst, "wb") as fh:
            fh.write(data)
    return root


def _run(root):
    env = dict(os.environ, W9_CODE_ROOT=root, PYTHONDONTWRITEBYTECODE="1")
    env.pop("AKASHIC_DECAY_IN_WRITER", None)
    p = subprocess.run([sys.executable, SUITE], capture_output=True, text=True, env=env,
                       cwd=tempfile.gettempdir(), timeout=600)
    res = {}
    for line in p.stderr.splitlines():
        m = re.match(r"^(test_\w+) \(", line)
        if m:
            res.setdefault(m.group(1), "ok")
    for line in p.stderr.splitlines():
        m = re.match(r"^(FAIL|ERROR): (test_\w+) \(", line)
        if m:
            res[m.group(2)] = m.group(1)
    if os.environ.get("W9_DEBUG"):
        print(p.stderr[-4000:])
    tail = [l for l in p.stderr.splitlines() if l.startswith(("Ran ", "OK", "FAILED"))]
    return res, " ".join(tail)


def main():
    tmp = tempfile.mkdtemp(prefix="w9_matrix_")
    try:
        rows = []
        br, br_t = _run(_root(tmp, "branch", "branch"))
        rows.append(("branch", br, br_t))
        mn, mn_t = _run(_root(tmp, "main", "main"))
        rows.append(("origin/main", mn, mn_t))
        for name, (f, old, new) in MUTANTS.items():
            root = _root(tmp, name, "branch")
            p = os.path.join(root, f[len("code/"):])
            with open(p, "rb") as fh:
                s = fh.read().decode("utf-8")
            assert s.count(old) == 1, (name, s.count(old))
            with open(p, "wb") as fh:
                fh.write(s.replace(old, new).encode("utf-8"))
            r, t = _run(root)
            rows.append((name, r, t))
        for name, r, t in rows:
            bad = sorted(k for k, v in r.items() if v != "ok")
            print("%-36s %s | control=%s | not-ok: %s" % (name, t, r.get(CONTROL, "?"), ", ".join(bad) or "-"))
        ok = (all(v == "ok" for v in br.values()) and len(br) > 0 and mn.get(CONTROL) != "ok"
              and all(any(v != "ok" for v in r.values()) for n, r, _ in rows[2:]))
        print("MATRIX:", "PASS" if ok else "FAIL")
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
