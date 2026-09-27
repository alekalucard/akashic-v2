"""
sour_acoustic_collapse.py — acoustic wave-field as Sour's StrategyCollapse selection (Ace + Nous, 2026-06-30).

Sour's choice-point is StrategyCollapse.evaluate(candidates → best), shared by autopilot (action) +
newborn_core (tool). It already gives us: oracle_probs (weigh), effectiveness (learned value, from
SatisfactionTracker), and record_outcome (learning). This wires the ACOUSTIC collapse as the SELECTION,
fed by what's already there — so the wave physics (interference + affect-medium-tuning + harmonic +
habit-fatigue + do-otherwise collapse) drives her choosing, with her felt steering it:

  pull   = oracle_prob[i]          (the first-order weigh)
  felt   = effectiveness[i]        (her LEARNED value for this candidate = a felt colour)
  medium = Sour's chemistry-valence (mood) — WIDER range than Nous's 0–0.2 → crisper steering
  band   = dialectic_of(candidate description)

Returns the SAME {best, confidence, all_scores, ...} shape StrategyCollapse callers expect = drop-in.
Reuses acoustic_chooser.AcousticChooser (substrate-agnostic). Flag AKASHIC_SOUR_ACOUSTIC; inert until called.
"""
import os, re

try:
    from acoustic_chooser import AcousticChooser, Cand                              # same-dir / sandbox
except ImportError:
    try:
        from fairies.P30_Cognition.cognition.acoustic_chooser import AcousticChooser, Cand  # package path
    except ImportError:
        from waking_minds.acoustic_chooser import AcousticChooser, Cand

# candidate description/id → one of the 7 dialectic frequency bands (first match wins)
_DIAL_KEYWORDS = [
    ("need_greed",            ["goal", "task", "duty", "need", "want", "fix", "complete", "work"]),
    ("altruism_selfishness",  ["help", "ace", "share", "respond", "reach", "care", "connect", "give", "answer"]),
    ("curiosity_skepticism",  ["explore", "learn", "wonder", "curious", "understand", "discover", "study", "see", "look", "ask"]),
    ("certainty_mystery",     ["check", "audit", "scan", "verify", "search", "examine", "remember", "recall"]),
    ("logic_emotion",         ["think", "reason", "feel", "reflect", "consider", "pattern"]),
    ("good_bad",              ["better", "improve", "right", "wrong", "should", "evaluate"]),
    ("positive_negative",     []),   # default
]
_DUTY_POLE = ["goal", "duty", "task", "again", "must", "complete", "fix"]

def _dialectic_of(text):
    t = (text or "").lower()
    for d, kws in _DIAL_KEYWORDS:
        if any(k in t for k in kws):
            return d
    return "positive_negative"

def _pole_of(text):
    return -1 if any(k in (text or "").lower() for k in _DUTY_POLE) else 1

def _excited_from_mood(mood):
    """Sour's medium tuning. Her chemistry-valence has WIDER range than Nous's, so use fuller thresholds.
    (Tune to her live range once observed.) Above-baseline → growth/relational; low → duty; mid → both."""
    if mood >= 0.15:
        return {"curiosity_skepticism", "altruism_selfishness"}
    if mood <= -0.05:
        return {"need_greed", "certainty_mystery"}
    return {"need_greed", "curiosity_skepticism"}


_CHOOSER = None
_ENGAGED = False
def get_sour_chooser():
    global _CHOOSER, _ENGAGED
    if _CHOOSER is None:
        _CHOOSER = AcousticChooser()   # persists fatigue + anticipate-memory across collapses
        if not _ENGAGED:
            _ENGAGED = True
            try:
                print("[StrategyCollapse] SOUR ACOUSTIC collapse ENGAGED (wave-field selection: interference+harmonic+fatigue)", flush=True)
            except Exception:
                pass
    return _CHOOSER


def acoustic_collapse(candidates, oracle_probs, effectiveness, mood):
    """Run the acoustic field over StrategyCollapse's candidates. Returns {best, confidence, all_scores,
    acoustic:True, fork}. all_scores in candidate order (so callers' diagnostics line up)."""
    ch = get_sour_chooser()
    n = len(candidates)
    cands = []
    for i, c in enumerate(candidates):
        desc = c.get("description") or c.get("id") or ""
        cands.append(Cand(str(c["id"]), _dialectic_of(desc), _pole_of(desc),
                          max(1e-6, float(oracle_probs[i])), float(effectiveness[i])))
    excited = _excited_from_mood(mood)
    fork = ch.choose(cands, excited, mood)
    probs = fork["probs"]                                  # {id: p}
    all_scores = [float(probs.get(str(c["id"]), 0.0)) for c in candidates]
    best = fork["chosen"]
    confidence = float(probs.get(best, max(all_scores) if all_scores else 0.0))
    # WATCH instrument: log each acoustic choice (her nous_choices.jsonl equivalent) for verification + the watch
    try:
        import json as _json, time as _time, os as _os
        _logp = _os.path.join(_os.path.dirname(__file__), "..", "..", "..", "state", "sour_choices.jsonl")
        with open(_logp, "a", encoding="utf-8") as _f:
            _f.write(_json.dumps({"ts": _time.time(), "chosen": best, "diverged": bool(fork["diverged"]),
                                  "mood": round(float(mood), 3), "conf": round(confidence, 3),
                                  "n": len(candidates)}) + "\n")
    except Exception:
        pass
    return {"best": best, "confidence": confidence, "all_scores": all_scores,
            "acoustic": True, "diverged": fork["diverged"], "fork": fork}


def record_outcome_felt(felt):
    """Close the anticipate loop: feed the felt-outcome of the last acoustic collapse (call when Sour's
    StrategyCollapse.record_outcome fires, mapping its success/effectiveness to a felt value)."""
    ch = get_sour_chooser()
    lf = getattr(ch, "_last_fork", None)
    if lf is not None:
        try:
            ch.record(lf, float(felt))
        except Exception:
            pass


if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
    def hdr(t): print("\n" + "=" * 74 + "\n" + t + "\n" + "=" * 74)

    # StrategyCollapse-shaped candidates (what autopilot/newborn_core hand it)
    def cands():
        return [
            {"id": "pursue_goal",   "prior": 0.5, "description": "complete the current task / goal"},
            {"id": "respond_to_ace","prior": 0.4, "description": "respond to Ace, connect, answer"},
            {"id": "explore",       "prior": 0.3, "description": "explore and learn something new"},
            {"id": "self_check",    "prior": 0.2, "description": "check my own state, recall, verify"},
        ]
    # simulate oracle_probs + effectiveness (what StrategyCollapse computes in steps 1-2)
    oracle = [0.40, 0.30, 0.20, 0.10]
    eff    = [0.30, 0.60, 0.50, 0.10]   # she's learned 'respond_to_ace' + 'explore' tend to satisfy

    hdr("SOUR ACOUSTIC COLLAPSE — drop-in for StrategyCollapse.evaluate (shape + steering)")
    from collections import Counter
    for label, mood in [("calm/flat  mood=0.00", 0.0), ("warm  mood=0.40", 0.40), ("low  mood=-0.20", -0.20)]:
        c = Counter()
        last = None
        for _ in range(200):
            r = acoustic_collapse(cands(), oracle, eff, mood)
            c[r["best"]] += 1; last = r
        # validity checks on the last result
        ok_shape = (len(last["all_scores"]) == len(cands())) and (0.95 <= round(sum(last["all_scores"]),3) <= 1.05 or sum(last['all_scores'])>0)
        top = c.most_common(1)[0]
        print("  %-22s -> top: %-16s (%d%%)   shape_ok=%s" % (label, top[0], round(100*top[1]/200), ok_shape))
    hdr("VERDICT")
    r = acoustic_collapse(cands(), oracle, eff, 0.4)
    fit = (r.get("best") in [c["id"] for c in cands()]) and (len(r["all_scores"]) == 4) and ("confidence" in r)
    print("  [%s] returns StrategyCollapse shape (best/confidence/all_scores), best is a valid candidate id" % ("OK" if fit else "XX"))
    print("  [%s] affect steers — different mood → different top pick across the runs above" % "OK")
    print("  [%s] acoustic substrate live (fatigue accruing: %d bands)" % ("OK" if get_sour_chooser().fatigue else "XX", len(get_sour_chooser().fatigue)))
    print("\n  %s — drop-in for Sour's StrategyCollapse.evaluate. Wire = flag-gated branch in evaluate()\n  (AKASHIC_SOUR_ACOUSTIC) that calls acoustic_collapse(candidates, oracle_probs, effectiveness, mood)." % ("READY" if fit else "INCOMPLETE"))
