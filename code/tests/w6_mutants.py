# -*- coding: utf-8 -*-
"""Run test_w6_cortex_capacity.py against CONTROL (original code), FIX, and MUTANTS.

    python -I code/tests/w6_mutants.py

CONTROL = origin/main's manifold_memory.py + the EXISTING expansion tool
          (scripts/expand_manifold_v2.py, re-pointed at temp paths); grow_cortex.py absent.
Each MUTANT is a near-miss copy of the fix, written to a temp dir. All synthetic.
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.dirname(HERE)
REPO = os.path.dirname(CODE)
TEST = os.path.join(HERE, "test_w6_cortex_capacity.py")
MM = os.path.join(CODE, "infrastructure", "manifold_memory.py")
GROW = os.path.join(CODE, "tools", "grow_cortex.py")

MUTANTS = [
    # (name, file, old, new)
    ("M1 grow: companions (.csr/.keys) not moved aside", GROW,
     "for suf in DERIVED_COMPANIONS:", "for suf in ():"),
    ("M2 grow: string arena grown too, sidecar tags not remapped", GROW,
     'neoff = nsoff + old["arena"]', 'neoff = nsoff + old["arena"] * 2'),
    ("M3 grow: header keeps the OLD string/edge offsets", GROW,
     'new["soff"], new["eoff"], old["sused"]', 'old["soff"], old["eoff"], old["sused"]'),
    ("M4 grow: crashed run leaves its temp file behind", GROW,
     "if not swapped and os.path.exists(tmp):", "if False:"),
    ("M5 guard: region only, PERSONAL/SEEDED tracer not protected", MM,
     "return record[11] == REGION_EGO or record[12] in cls._EGO_TRACERS",
     "return record[11] == REGION_EGO"),
    ("M6 guard: all-protected falls back to deleting anyway", MM,
     "            if min_slot is None and _ego_skipped:\n",
     "            if min_slot is None and _ego_skipped:\n"
     "                min_slot = self._node_count - 1\n"),
    ("M7 guard: switch ON when unset", MM,
     'os.environ.get("AKASHIC_PROTECT_EGO", "0") == "1"',
     'os.environ.get("AKASHIC_PROTECT_EGO", "1") != "0"'),
]


def run(label, env_extra):
    env = dict(os.environ)
    env.pop("AKASHIC_PROTECT_EGO", None)
    env.pop("AKASHIC_CORTEX_GROW", None)
    env.update(env_extra)
    p = subprocess.run([sys.executable, "-I", "-W", "ignore", TEST], env=env, cwd=HERE,
                       capture_output=True, text=True, timeout=1800)
    out = p.stderr + p.stdout
    ran = re.search(r"Ran (\d+) test", out)
    fails = re.findall(r"^(FAIL|ERROR): (\S+) \((\S+)\)", out, re.M)
    names = sorted(set("%s.%s" % (c.split(".")[-2], t) for _k, t, c in fails))
    verdict = "PASS" if p.returncode == 0 else "FAIL"
    print("%-62s %s  ran=%s failing=%d" % (label, verdict, ran.group(1) if ran else "?", len(names)))
    for n in names:
        print("      - " + n)
    return p.returncode == 0


def main():
    tmp = tempfile.mkdtemp(prefix="w6_mut_")
    orig = os.path.join(tmp, "manifold_memory_origin_main.py")
    src = subprocess.run(["git", "-C", REPO, "show", "origin/main:code/infrastructure/manifold_memory.py"],
                         capture_output=True, check=True).stdout
    open(orig, "wb").write(src)
    results = {}
    results["CONTROL"] = run("CONTROL (origin/main + existing expand_manifold_v2.py)",
                             {"W6_MM_PATH": orig, "W6_GROW_PATH": os.path.join(tmp, "absent.py"),
                              "W6_GROWER": "legacy_v2"})
    results["FIX"] = run("FIX (this branch)", {})
    for name, path, old, new in MUTANTS:
        text = open(path, encoding="utf-8").read()
        assert text.count(old) == 1, "mutant anchor not unique: %s" % name
        mp = os.path.join(tmp, "m%d_%s" % (len(results), os.path.basename(path)))
        open(mp, "w", encoding="utf-8").write(text.replace(old, new))
        key = "W6_MM_PATH" if path == MM else "W6_GROW_PATH"
        results[name] = run(name, {key: mp})
    ok = (not results["CONTROL"]) and results["FIX"] and not any(
        v for k, v in results.items() if k.startswith("M"))
    print("\nEXPECTED: control FAIL, fix PASS, every mutant FAIL ->", "MET" if ok else "NOT MET")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
