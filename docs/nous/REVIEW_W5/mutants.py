"""Make reviewer-chosen near-miss mutants of the W5 head copy and run the shipped tests on each."""
import shutil, subprocess, os, re, sys
S = "/tmp/claude-0/-home-user-akashic-v2/154fc480-684e-5542-9a21-c27ca54b1276/scratchpad"
REPO = "/home/user/akashic-v2/.claude/worktrees/agent-a5d8eb778d70dc5cb"
HEAD = f"{S}/head"
BO = "code/tracer_pool/boot_orchestrator.py"
SV = "code/server.py"
HC = "code/fairies/P30_Cognition/HarmonicCortexFairy/fairy.py"
NEW_B2 = "fairy.name.lower().endswith(tuple(x.lower() for x in _BOOT_EXCLUDE_SUFFIXES))"

MUTANTS = {
    # B2
    "b2_substring": (BO, NEW_B2, '"shadow" in fairy.name.lower()'),
    "b2_dot_shadow_only": (BO, NEW_B2, 'fairy.name.endswith(_BOOT_EXCLUDE_SUFFIXES) or fairy.name.endswith(".shadow")'),
    "b2_upper_only": (BO, NEW_B2, "fairy.name.upper().endswith(_BOOT_EXCLUDE_SUFFIXES)"),
    "b2_equiv_casefold": (BO, NEW_B2, 'fairy.name.casefold().endswith("shadow")'),
    # B4
    "b4_both_keys": (SV, '"DreamSeedFairy": ("fairies.P00_Autonomic.nervous_system.dream_seed_fairy", "DreamSeedFairy"),',
                     '"DreamSeedFairy": ("fairies.P00_Autonomic.nervous_system.dream_seed_fairy", "DreamSeedFairy"),\n            "DreamSeedsFairy": ("fairies.P00_Autonomic.nervous_system.dream_seed_fairy", "DreamSeedFairy"),'),
    # B5
    "b5_names_dropped": (HC, None, None),
    "b5_bypass_bridge_private": (HC, "self.post.subscribe(", "self.post._fabric.subscribe("),
    "b5_one_left_on_fabric": (HC, 'self.post.subscribe(\n                    "sensory.audio.speech"', 'self.post.fabric.subscribe(\n                    "sensory.audio.speech"'),
}

def run(root):
    env = dict(os.environ, NOUS_W5_ROOT=root)
    p = subprocess.run([sys.executable, "-I", "-B", "-m", "unittest", "discover", "-s", "tests_nous/w5", "-v"],
                       cwd=REPO, env=env, capture_output=True, text=True)
    fails = re.findall(r"^(\w+) \(.*?\) \.\.\. (?:FAIL|ERROR)", p.stderr, re.M)
    return fails

for name, (rel, old, new) in MUTANTS.items():
    d = f"{S}/mut_{name}"
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(HEAD, d)
    path = f"{d}/{rel}"
    src = open(path, encoding="utf-8").read()
    if name == "b5_names_dropped":
        src2 = re.sub(r',\n\s*name=f"\{self\.ACTOR_NAME\}_\w+"\n', "\n", src)
    else:
        assert src.count(old) >= 1, name
        src2 = src.replace(old, new)
    assert src2 != src, name
    open(path, "w", encoding="utf-8").write(src2)
    f = run(d)
    print(f"{name}: {'KILLED by ' + ','.join(f) if f else 'SURVIVED (all 11 pass)'}")
