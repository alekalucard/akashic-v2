# -*- coding: utf-8 -*-
"""Run test_w6_cortex_capacity.py against CONTROLS (original code), FIX, and MUTANTS.

    python -I code/tests/w6_mutants.py            # all runs, 4 in parallel

CONTROL   = origin/main's manifold_memory.py + the EXISTING expansion tool
            (scripts/expand_manifold_v2.py, re-pointed at temp paths); grow_cortex.py absent.
CONTROL-B = the pre-fix grow_cortex.py (branch tip 0f49669, before the fix round after
            REVIEW_W6) with this tree's manifold_memory.py: the F1/F2/F3 tests must fail on it.
Each MUTANT is a near-miss copy of the fix, written to a temp dir. All synthetic.
  M1-M7   the original W6 mutants
  R1-R18  the reviewer's mutants (docs/nous/REVIEW_W6/VERDICT.md, r6_mutants.py); R7 and
          R18 re-anchored onto the fixed code, same semantics
  N1-N7   near-misses of the fix round itself
"""
import concurrent.futures
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
PRE_FIX = "0f49669"

_COMP = ('        _step("move_companions")\n        moved = []\n        for suf in DERIVED_COMPANIONS:\n'
         '            c = path + suf\n            if os.path.exists(c):\n'
         '                os.replace(c, "%s.pre_grow.%s" % (c, stamp))\n                moved.append(c)\n'
         '        report["companions_moved_aside"] = moved\n')

MUTANTS = [
    # (name, file, [(old, new), ...]); every `old` must occur exactly once
    ("M1 grow: companions (.csr/.keys) not moved aside", GROW,
     [("for suf in DERIVED_COMPANIONS:", "for suf in ():")]),
    ("M2 grow: string arena grown too, sidecar tags not remapped", GROW,
     [('neoff = nsoff + old["arena"]', 'neoff = nsoff + old["arena"] * 2')]),
    ("M3 grow: header keeps the OLD string/edge offsets", GROW,
     [('new["soff"], new["eoff"], old["sused"]', 'old["soff"], old["eoff"], old["sused"]')]),
    ("M4 grow: crashed run leaves its temp file behind", GROW,
     [("if not swapped and os.path.exists(tmp):", "if False:")]),
    ("M5 guard: region only, PERSONAL/SEEDED tracer not protected", MM,
     [("return record[11] == REGION_EGO or record[12] in cls._EGO_TRACERS",
       "return record[11] == REGION_EGO")]),
    ("M6 guard: all-protected falls back to deleting anyway", MM,
     [("            if min_slot is None and _ego_skipped:\n",
       "            if min_slot is None and _ego_skipped:\n"
       "                min_slot = self._node_count - 1\n")]),
    ("M7 guard: switch ON when unset", MM,
     [('os.environ.get("AKASHIC_PROTECT_EGO", "0") == "1"',
       'os.environ.get("AKASHIC_PROTECT_EGO", "1") != "0"')]),
    # ---- reviewer's 18
    ("R1 skip fsync of tmp (both)", GROW,
     [("            fn.flush()\n            os.fsync(fn.fileno())\n", "            fn.flush()\n"),
      ('            _step("fsync_tmp")\n            os.fsync(fn.fileno())', '            _step("fsync_tmp")')]),
    ("R2 verify disabled (returns [])", GROW,
     [("    bad = []\n    if os.path.getsize(tmp)", "    return []\n    bad = []\n    if os.path.getsize(tmp)")]),
    ("R3 replace BEFORE verify", GROW,
     [('        _step("verify")\n        bad = verify(path, tmp, old, new)\n        if bad:\n'
       '            raise GrowRefused("verification FAILED, nothing swapped: " + "; ".join(bad))\n', ""),
      ('        _step("dirsync")',
       "        bad = verify(path + '.pre_grow.' + stamp, path, old, new)\n        if bad:\n"
       "            raise GrowRefused('late verify')\n        _step(\"verify\")\n        _step(\"dirsync\")")]),
    ("R4 edges written 24 B too far", GROW,
     [('_copy(fo, fn, old["eoff"], new["eoff"], old["ecap"] * EDGE_SIZE)',
       '_copy(fo, fn, old["eoff"], new["eoff"] + 24, old["ecap"] * EDGE_SIZE - 24)')]),
    ("R5 strings written 1 B too far", GROW,
     [('_copy(fo, fn, old["soff"], new["soff"], old["arena"])',
       '_copy(fo, fn, old["soff"], new["soff"] + 1, old["arena"] - 1)')]),
    ("R6 recheck_source removed", GROW,
     [("        if _src_ident(path) != ident0:", "        if False:")]),
    ("R7 companions moved AFTER replace", GROW,
     [(_COMP, "        moved = []\n"),
      ("        swapped = True\n", "        swapped = True\n" + _COMP)]),
    ("R8 no backup made", GROW,
     [("        try:\n            os.link(path, bak)\n        except OSError:\n            shutil.copy2(path, bak)\n"
       '            with open(bak, "rb+") as bf:\n                os.fsync(bf.fileno())\n', "")]),
    ("R9 in-use hits ignored", GROW,
     [('        if hits:\n            raise GrowRefused("file looks IN USE',
       '        if False:\n            raise GrowRefused("file looks IN USE')]),
    ("R10 /proc maps scan removed (fd only)", GROW,
     [('            with open("/proc/%s/maps" % pid, "r") as f:',
       '            with open("/nonexistent/%s" % pid, "r") as f:')]),
    ("R11 header tail 48..4095 zeroed", GROW,
     [('    h = bytearray(old["hdr"])', "    h = bytearray(4096)")]),
    ("R12 new node slots filled 0x01", GROW,
     [('    z = b"\\x00" * min(CHUNK, max(1, n))', '    z = b"\\x01" * min(CHUNK, max(1, n))')]),
    ("R13 lock not O_EXCL", GROW,
     [("os.O_CREAT | os.O_EXCL | os.O_WRONLY", "os.O_CREAT | os.O_WRONLY")]),
    ("R14 grow switch ON when unset", GROW,
     [('os.environ.get("AKASHIC_CORTEX_GROW", "0") != "1"', 'os.environ.get("AKASHIC_CORTEX_GROW", "1") == "0"')]),
    ("R15 guard: all-protected evicts slot 0 anyway", MM,
     [("        if min_slot is not None:\n            # Mark deleted",
       "        if min_slot is None and _protect_ego and _ego_skipped:\n            min_slot = 0\n"
       "        if min_slot is not None:\n            # Mark deleted")]),
    ("R16 guard: PERSONAL only (SEEDED dropped)", MM,
     [("record[12] in cls._EGO_TRACERS", "record[12] == TRACE_PERSONAL")]),
    ("R17 move_companions moves .names too", GROW,
     [('DERIVED_COMPANIONS = (".csr", ".keys")', 'DERIVED_COMPANIONS = (".csr", ".keys", ".names")')]),
    ("R18 assume-down gate removed", GROW,
     [('    if not (set(methods) - {"quiescence"}):\n        return ("no in-use',
       '    if False:\n        return ("no in-use')]),
    # ---- near-misses of the fix round
    ("N1 F1: blind processes ignored (fail-open again)", GROW,
     [("    if blind:\n        return (", "    if False:\n        return (")]),
    ("N2 F2: pre-swap in-use rescan removed", GROW,
     [('    if hits:\n        return "file looks IN USE right before',
       '    if False:\n        return "file looks IN USE right before')]),
    ("N3 F2: pre-swap full-hash check removed", GROW,
     [("    if _sha256(path) != sha0:", "    if False:")]),
    ("N4 F2: pre-swap scan ignores blindness (assume_down forced)", GROW,
     [("why = final_check(path, ident0, sha0, assume_down)", "why = final_check(path, ident0, sha0, True)")]),
    ("N5 F2: refusal leaves the companions moved aside", GROW,
     [("                    os.replace(aside, c)", "                    pass")]),
    ("N6 F3: no directory fsync before the swap", GROW,
     [("        _fsync_dir(d)                           # backup link", "        pass  # _fsync_dir(d) # backup link")]),
    ("N7 F1: /proc hidepid (invisible pids) ignored", GROW,
     [("        if _proc_hidden():\n            blind += 1", "        if False:\n            blind += 1")]),
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
    lines = ["%-62s %s  ran=%s failing=%d" % (label, verdict, ran.group(1) if ran else "?", len(names))]
    lines += ["      - " + n for n in names]
    return p.returncode == 0, "\n".join(lines)


def _git_show(rev, rel, dst):
    src = subprocess.run(["git", "-C", REPO, "show", "%s:%s" % (rev, rel)],
                         capture_output=True, check=True).stdout
    with open(dst, "wb") as f:
        f.write(src)
    return dst


def main():
    tmp = tempfile.mkdtemp(prefix="w6_mut_")
    jobs = [("CONTROL (origin/main + existing expand_manifold_v2.py)",
             {"W6_MM_PATH": _git_show("origin/main", "code/infrastructure/manifold_memory.py",
                                      os.path.join(tmp, "manifold_memory_origin_main.py")),
              "W6_GROW_PATH": os.path.join(tmp, "absent.py"), "W6_GROWER": "legacy_v2"}),
            ("CONTROL-B (pre-fix grow_cortex.py @ %s)" % PRE_FIX,
             {"W6_GROW_PATH": _git_show(PRE_FIX, "code/tools/grow_cortex.py",
                                        os.path.join(tmp, "grow_cortex_prefix.py"))}),
            ("FIX (this branch)", {})]
    for i, (name, path, edits) in enumerate(MUTANTS):
        with open(path, encoding="utf-8", newline="") as f:
            text = f.read()
        for old, new in edits:
            assert text.count(old) == 1, "mutant anchor not unique: %s (%r)" % (name, old[:60])
            text = text.replace(old, new)
        mp = os.path.join(tmp, "m%02d_%s" % (i, os.path.basename(path)))
        with open(mp, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        jobs.append((name, {("W6_MM_PATH" if path == MM else "W6_GROW_PATH"): mp}))
    with concurrent.futures.ThreadPoolExecutor(int(os.environ.get("W6_JOBS", "4"))) as ex:
        futs = [(name, ex.submit(run, name, env)) for name, env in jobs]
        results = {}
        for name, fu in futs:
            ok, text = fu.result()
            results[name] = ok
            print(text, flush=True)
    controls = [k for k in results if k.startswith("CONTROL")]
    survivors = [k for k in results if k[0] in "MRN" and results[k]]
    ok = (not any(results[k] for k in controls)) and results["FIX (this branch)"] and not survivors
    print("\nmutants: %d run, %d survive%s" % (len(MUTANTS), len(survivors),
                                              (": " + "; ".join(survivors)) if survivors else ""))
    print("EXPECTED: controls FAIL, fix PASS, every mutant FAIL ->", "MET" if ok else "NOT MET")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
