#!/bin/bash
# Run the shipped W5 tests against a given root copy; print per-test outcome lines.
REPO=/home/user/akashic-v2/.claude/worktrees/agent-a5d8eb778d70dc5cb
cd "$REPO"
for r in "$@"; do
  echo "== $r"
  NOUS_W5_ROOT="$r" python3 -I -B -m unittest discover -s tests_nous/w5 -v 2>&1 | grep -E " \.\.\. |^Ran|^OK|^FAILED" | grep -vE "WIRED"
done
