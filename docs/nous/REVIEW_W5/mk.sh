#!/bin/bash
# Build main/head copies of the files the W5 tests read, then run the tests on each.
set -e
REPO=/home/user/akashic-v2/.claude/worktrees/agent-a5d8eb778d70dc5cb
S=/tmp/claude-0/-home-user-akashic-v2/154fc480-684e-5542-9a21-c27ca54b1276/scratchpad
FILES="code/tracer_pool/boot_orchestrator.py code/server.py code/fairies/P20_Somatic/SomaticMindFairy/wake_cascade.py code/fairies/P00_Autonomic/nervous_system/dream_seed_fairy.py code/fairies/P30_Cognition/HarmonicCortexFairy/fairy.py code/fairies/P00_Autonomic/organ_template/Organ_Template_0_3_0.py code/fairies/P00_Autonomic/AutonomyFairy/fairy.py"
cd "$REPO"
for pair in main:origin/main head:HEAD; do
  d=${pair%%:*}; ref=${pair#*:}
  rm -rf "$S/$d"; mkdir -p "$S/$d"
  git archive "$ref" $FILES | tar -x -C "$S/$d"
done
