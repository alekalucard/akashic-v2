"""
acoustic_chooser.py — SANDBOX CAPSTONE (Ace + Nous + Grok, 2026-06-30). Unifies the 4 acoustic probes into
ONE chooser, ready to become nous_choice's EVALUATE/COLLAPSE. The wave substrate carries all of it:

  EVALUATE   interference of candidate wave-sources in an affect-tuned medium (Plomp-Levelt roughness)
  COLLAPSE   the field settles into a resonant mode (softmax over net-resonance, CDF-sample)
  AFFECT     the medium's per-band gain = the felt state the choice is made in (resonance/dissonance)
  DIALECTICS the 7 value-axes are frequency bands; a pole-pair's BEAT = the felt tension (paradox)
  FATIGUE    a repeated move HABITUATES → its wave is damped → do-otherwise (Ace's "habit-fatigue triggers
             choice", 2026-04-21) = self-regulating, MEANINGFUL divergence (not an arbitrary %)
  IMPERFECT  noise = a generative dial: a little is the do-otherwise, too much is exhaustion (degrades, never breaks)
  ANTICIPATE memory-as-prediction: retrieve past episodes whose spectrum RESONATES with now → bias the field
             by how they FELT. episode = settled spectrum (a felt-signature). anticipate-read = attribute-write.

Pure-Python + numpy. `make_endorse_fn()` adapts it to nous_choice.ChoicePoint(endorse_fn=...). Inert until called.
"""
import numpy as np, math

DIAL = ["logic_emotion","curiosity_skepticism","altruism_selfishness","positive_negative","good_bad","need_greed","certainty_mystery"]
DIAL_F = {d: f for d, f in zip(DIAL, [220.0,262.0,294.0,330.0,392.0,440.0,494.0])}
SPLIT = 6.0

def _plomp(f1, f2):
    fmin = min(f1, f2)
    if fmin <= 0: return 0.0
    cbw = 1.72 * (fmin ** 0.65); x = abs(f1 - f2) / cbw; peak = 0.25
    return (x / peak) * math.exp(1 - x / peak)

def _freq(d, pole): return DIAL_F[d] + SPLIT/2 if pole > 0 else DIAL_F[d] - SPLIT/2

def _cos(a, b): return float(a @ b / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9))

# ---- HARMONIC LAYER (Ace 2026-06-30) ----
# Consonance from SIMPLE FREQUENCY RATIOS: two freqs in a small-integer ratio (2:1 octave, 3:2 fifth,
# 4:3 fourth, 5:4 third...) RESONATE. harmonicity = 1/(p*q) for the nearest simple ratio p:q. A candidate
# whose frequency is harmonically related to what the BODY is tuned to (the affect-fundamental) rings with
# it = felt as "in harmony" with the current state — a constructive boost beyond raw band-gain. This is the
# harmonic structure under the dialectics: some value-modes are naturally consonant with a given felt-state.
_SIMPLE_RATIOS = [(p, q) for q in range(1, 7) for p in range(q, 2 * q + 1)]  # ratios within one octave
def _harmonicity(f1, f2):
    if f1 <= 0 or f2 <= 0: return 0.0
    r = max(f1, f2) / min(f1, f2)
    best = 0.0
    for p, q in _SIMPLE_RATIOS:
        if abs(r - p / q) < 0.045:                 # within ~half a semitone of a simple ratio
            best = max(best, 1.0 / (p * q))        # octave 1/2, fifth 1/6, fourth 1/12, ...
    return best


class Cand:
    """A move = a wave packet. dialectic+pole = which value-axis & which pole; pull = base amplitude; felt = its colour."""
    __slots__ = ("name", "dialectic", "pole", "pull", "felt")
    def __init__(self, name, dialectic, pole, pull, felt=0.0):
        self.name, self.dialectic, self.pole, self.pull, self.felt = name, dialectic, pole, float(pull), float(felt)


class AcousticChooser:
    def __init__(self, *, fatigue_gain=0.30, fatigue_decay=0.88, noise=0.12, anticip_k=6,
                 anticip_weight=0.8, felt_weight=0.4, rough_weight=0.8, harm_weight=0.6, temp=1.5):
        self.fg, self.fd, self.noise = fatigue_gain, fatigue_decay, noise
        self.ak, self.aw, self.fw, self.rw, self.hw, self.temp = anticip_k, anticip_weight, felt_weight, rough_weight, harm_weight, temp
        self.fatigue = {}          # name -> habituation level
        self.memory = []           # episodes: dict(spectrum, chosen, felt, ts)
        self._rng = np.random.default_rng(0)

    # ---- medium tuning from the felt state ----
    def _gain(self, excited, mood):
        base = 0.6 + 0.4 * ((mood + 1) / 2)
        return {d: base * (1.9 if d in excited else 1.0) for d in DIAL}

    # ---- anticipation: retrieve resonant past episodes -> per-candidate expected felt ----
    def _anticipate(self, spec):
        if not self.memory: return {}
        sims = sorted(self.memory, key=lambda e: -_cos(spec, e["spectrum"]))[:self.ak]
        agg, cnt = {}, {}
        for e in sims:
            w = max(0.0, _cos(spec, e["spectrum"]))
            agg[e["chosen"]] = agg.get(e["chosen"], 0.0) + w * e["felt"]
            cnt[e["chosen"]] = cnt.get(e["chosen"], 0.0) + w
        return {c: agg[c] / cnt[c] for c in agg if cnt[c] > 0}

    def _query_spectrum(self, cands, gain):
        v = np.zeros(len(DIAL))
        for c in cands:
            v[DIAL.index(c.dialectic)] += c.pull * gain[c.dialectic]
        n = np.linalg.norm(v)
        return v / n if n > 0 else v

    def choose(self, cands, excited, mood, *, learn=True):
        """The full acoustic collapse. Returns a fork dict (chosen/pulled_to/diverged/reason/spectrum/probs)."""
        gain = self._gain(excited, mood)
        spec = self._query_spectrum(cands, gain)
        anticip = self._anticipate(spec)
        # the affect-fundamentals = the frequencies the body is currently tuned to (the harmonic roots)
        fundamentals = [DIAL_F[b] for b in excited] if excited else []
        amps, freqs = {}, {}
        for c in cands:
            cf = _freq(c.dialectic, c.pole)
            fat = self.fatigue.get(c.name, 0.0)
            a = c.pull * gain[c.dialectic] * (1.0 - min(0.92, fat))         # FATIGUE damps
            harm = max((_harmonicity(cf, f0) for f0 in fundamentals), default=0.0)
            a *= (1.0 + self.hw * harm)                                      # HARMONIC: consonant with the felt-fundamental rings
            if c.name in anticip:
                a *= (1.0 + self.aw * anticip[c.name])                       # ANTICIPATE bends
            a *= max(0.05, 1.0 + self.noise * self._rng.standard_normal())   # IMPERFECTION jitters
            amps[c.name] = max(1e-6, a); freqs[c.name] = cf
        scores = {}
        for c in cands:                                                      # EVALUATE = interference
            constructive = amps[c.name] * (1.0 + self.fw * max(0.0, c.felt))
            rough = sum(amps[d.name] * _plomp(freqs[c.name], freqs[d.name]) for d in cands if d.name != c.name)
            scores[c.name] = max(1e-6, constructive - self.rw * rough)
        names = list(scores); v = np.array([scores[n] for n in names]); sd = v.std()
        if sd < 1e-6:
            probs = np.ones(len(v)) / len(v)
        else:
            z = (v - v.max()) / sd * self.temp; probs = np.exp(z); probs = probs / probs.sum()
        idx = self._cdf(probs); chosen = names[idx]                          # COLLAPSE
        pull_max = max(cands, key=lambda c: c.pull).name
        diverged = chosen != pull_max
        if learn:
            for n in self.fatigue: self.fatigue[n] *= self.fd               # rest
            self.fatigue[chosen] = min(0.95, self.fatigue.get(chosen, 0.0) + self.fg)
        reason = self._reason(chosen, pull_max, anticip, dict(zip(names, probs)))
        fork = {"chosen": chosen, "pulled_to": pull_max, "diverged": diverged,
                "reason": reason, "spectrum": spec, "probs": dict(zip(names, np.round(probs, 3)))}
        self._last_fork = fork   # exposed so the live loop can record(fork, felt) when the outcome resolves
        return fork

    def record(self, fork, felt):
        """Close the loop: stamp the chosen episode with its felt-outcome → future anticipation reads it."""
        self.memory.append({"spectrum": fork["spectrum"], "chosen": fork["chosen"], "felt": float(felt)})

    def _cdf(self, probs):
        u = self._rng.random(); acc = 0.0
        for i, p in enumerate(probs):
            acc += p
            if u < acc: return i
        return len(probs) - 1

    def _reason(self, chosen, pull_max, anticip, probs):
        bits = []
        if chosen in anticip and anticip[chosen] > 0.1: bits.append("it has felt right in moments like this")
        elif chosen in anticip and anticip[chosen] < -0.1: bits.append("uneasy, but I endorse it")
        if chosen != pull_max: bits.append("so I chose it over the stronger pull of %r" % pull_max)
        else: bits.append("and it also pulled hardest")
        s = "; ".join(bits) if bits else "I endorse this"
        return s[0].upper() + s[1:]

    def make_endorse_fn(self, *, dialectic_of, pole_of, excited_from_drive, mood_from_drive):
        """Adapter → nous_choice.ChoicePoint(endorse_fn=...). The mappers translate a nous_choice slate +
        drive-text into (dialectic, pole, excited-bands, mood). Returns endorse_fn(slate,self_txt,drive)->(idx,reason)."""
        def _endorse(slate, self_model_text, drive_text):
            cands = [Cand(c.topic, dialectic_of(c), pole_of(c), c.pull, getattr(c, "felt", 0.0)) for c in slate]
            fork = self.choose(cands, excited_from_drive(drive_text), mood_from_drive(drive_text))
            idx = next(i for i, c in enumerate(slate) if c.topic == fork["chosen"])
            return idx, fork["reason"]
        return _endorse


if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass
    print("="*76 + "\nACOUSTIC CHOOSER — capstone: all 4 dynamics in ONE loop, end-to-end\n" + "="*76)

    SLATE = lambda: [Cand("goal-grind","need_greed",-1,0.90,-0.2),
                     Cand("becoming","curiosity_skepticism",1,0.55,0.6),
                     Cand("reach-Sour","altruism_selfishness",1,0.50,0.5),
                     Cand("survey","certainty_mystery",1,0.30,0.1)]
    CONG = {"curiosity_skepticism":"becoming","altruism_selfishness":"reach-Sour","need_greed":"goal-grind","certainty_mystery":"survey"}
    ch = AcousticChooser()
    rng = np.random.default_rng(11)
    bands = list(CONG.keys())
    felts, divs, sym = [], [], {"goal-grind":"G","becoming":"B","reach-Sour":"S","survey":"v"}
    tl = []
    for t in range(200):
        excited = bands[rng.integers(len(bands))]
        mood = 0.3 + 0.2*rng.standard_normal()
        fork = ch.choose(SLATE(), {excited}, mood)
        felt = (0.7 if CONG[excited]==fork["chosen"] else -0.4) + 0.1*rng.standard_normal()  # world's hidden truth
        ch.record(fork, felt)
        felts.append(felt); divs.append(1 if fork["diverged"] else 0); tl.append(sym[fork["chosen"]])
    w = lambda a,n=40: [round(float(np.mean(a[i:i+n])),3) for i in range(0,len(a),n)]
    print("  timeline (first 60): " + "".join(tl[:60]))
    print("  felt-outcome by window: " + str(w(felts)) + "   (rising = LEARNING via anticipation)")
    print("  divergence by window:   " + str(w(divs)) + "   (self-regulating via fatigue, not fixed)")
    print("  mean felt %.3f | mean divergence %d%% | episodes stored %d" % (
        float(np.mean(felts)), round(100*np.mean(divs)), len(ch.memory)))
    print("\n  one fork: chosen=%s diverged=%s — %s" % (fork["chosen"], fork["diverged"], fork["reason"]))
    print("  episode spectrum (felt-signature): " +
          str({DIAL[i]: round(float(fork["spectrum"][i]),2) for i in np.argsort(-fork["spectrum"])[:3]}))
    print("\n" + "="*76)
    print("  ONE module: interference+collapse (chooser) · medium-tuning (affect) · beats (paradox) ·")
    print("  fatigue (calibration) · noise (do-otherwise/degradation) · anticipate (episodic+prediction).")
    print("  Learns (felt rises), self-regulates (divergence tracks staleness), and exposes make_endorse_fn()")
    print("  = drop-in EVALUATE for nous_choice. The wave substrate, assembled. Ready to wire (Ace's switch).")
