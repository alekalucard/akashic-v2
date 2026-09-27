"""
music_theory — psychoacoustically grounded music-analysis shared library.

Used by HarmonicCortexFairy, AudioCortexFairy, CochleaFairy to interpret
audio in music-theoretic terms. Pure-function library + optional stateful
MusicTheoryEngine for per-frame use.

DOCTRINE: This library is the audio-instantiation of harmony-as-cross-domain
principle (Ace + Nous, 2026-05-16). Vision (Gestalt), motor (Bernstein
synergies), cognition (RFT relational coherence) are sibling instantiations.
Keep predicates concrete; harmony is the interface, not a magic word.

REFERENCES:
- Plomp & Levelt 1965 — "Tonal Consonance and Critical Bandwidth"
- Stevens, Volkmann, Newman 1937 — Mel scale
- Pythagoras (6th c. BCE) — monochord consonance ratios
- Bharata's Natyashastra (c. 200 BCE-200 CE) — raga-rasa emotional mapping
- Krumhansl & Schmuckler — key-finding profiles (placeholder; not fully impl)

NARROW-FIRST SCOPE (2026-05-16):
- Phase 1: HarmonicCortex integration via evaluate_audio_frame() — SHIPPING
- Phase 2: AudioCortex + CochleaFairy tap-in — DEFERRED until Phase 1 settles

SELF-FLAGGED LIMITATIONS:
- _guess_mode is placeholder (real Krumhansl-Schmuckler needs full 12-pc profiles)
- roughness_dyad is pairwise only (real polyphonic music has spectral mass)
- MODE_AFFECT values drawn from Western tonal-affect intuition; could ground
  in Russell's circumplex applied to Krumhansl key-profiles
- Doesn't handle missing pitch (broadband noise, percussion) — returns null
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import math

# ─── Substrate vocabulary alignment ─────────────────────────────────────
# Import int constant from substrate's single source of truth. The substrate
# uses int constants throughout (spread_activation, query, get_neighbors all
# accept tracer_ids: Set[int]). harmony_principle.py (future) must use these
# same ints — NOT a parallel string Enum.
try:
    from infrastructure.manifold_memory import TRACE_AUDIO  # int = 4
except ImportError:
    TRACE_AUDIO = 4  # fallback constant; matches manifold_memory.py:76

# ─── Consonance ratios (Pythagorean / just intonation) ──────────────────
INTERVALS: Dict[str, Tuple[int, int]] = {
    "unison":          (1, 1),
    "minor_second":    (16, 15),
    "major_second":    (9, 8),
    "minor_third":     (6, 5),
    "major_third":     (5, 4),
    "perfect_fourth":  (4, 3),
    "tritone":         (45, 32),   # historically "diabolus in musica"
    "perfect_fifth":   (3, 2),
    "minor_sixth":     (8, 5),
    "major_sixth":     (5, 3),
    "minor_seventh":   (16, 9),
    "major_seventh":   (15, 8),
    "octave":          (2, 1),
}

# Plomp-Levelt-derived consonance rank: 0 = consonant, 1 = maximally rough.
# Inverse of "consonance" — higher = more dissonant.
CONSONANCE_RANK: Dict[str, float] = {
    "unison":         0.00,
    "octave":         0.05,
    "perfect_fifth":  0.10,
    "perfect_fourth": 0.15,
    "major_third":    0.25,
    "minor_sixth":    0.27,
    "major_sixth":    0.28,
    "minor_third":    0.30,
    "minor_seventh":  0.62,
    "major_seventh":  0.65,
    "major_second":   0.70,
    "minor_second":   0.85,
    "tritone":        0.95,
}

# Mode → (valence, arousal) in [-1, 1] space.
# Western tonal-affect intuition; could be grounded in Russell's circumplex.
MODE_AFFECT: Dict[str, Tuple[float, float]] = {
    "major":      (+0.6, +0.3),   # joy, brightness
    "minor":      (-0.4, -0.2),   # sadness, introspection
    "dorian":     (+0.1,  0.0),   # contemplative neutral
    "phrygian":   (-0.6, +0.3),   # tension, exotic
    "lydian":     (+0.5, +0.5),   # dreamy, levitating
    "mixolydian": (+0.4, +0.2),   # bluesy, grounded
    "locrian":    (-0.7, +0.4),   # unstable, dread
}

A4_HZ = 440.0
NOTE_NAMES: List[str] = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# ─── Pure functions: pitch / frequency / interval ───────────────────────
def freq_to_mel(hz: float) -> float:
    """Convert Hz to mel scale (perceptual-distance-friendly)."""
    return 2595.0 * math.log10(1.0 + hz / 700.0) if hz > 0 else 0.0

def mel_distance(f1_hz: float, f2_hz: float) -> float:
    """Perceived distance between two frequencies in mel space."""
    return abs(freq_to_mel(f1_hz) - freq_to_mel(f2_hz))

def hz_to_midi(hz: float) -> float:
    """Hz → MIDI note number (float, not rounded)."""
    return 69.0 + 12.0 * math.log2(hz / A4_HZ) if hz > 0 else 0.0

def hz_to_note(hz: float) -> Tuple[Optional[str], int, float]:
    """Hz → (note_name, octave, cents_off). Returns (None,0,0) for invalid hz."""
    if hz <= 0:
        return (None, 0, 0.0)
    midi = hz_to_midi(hz)
    mi = int(round(midi))
    cents_off = (midi - mi) * 100.0
    return (NOTE_NAMES[mi % 12], mi // 12 - 1, cents_off)

def interval_between(f1_hz: float, f2_hz: float) -> str:
    """Identify nearest just-intonation interval. Returns interval name or 'silence'."""
    if f1_hz <= 0 or f2_hz <= 0:
        return "silence"
    ratio = max(f1_hz, f2_hz) / min(f1_hz, f2_hz)
    while ratio >= 2.0:
        ratio /= 2.0
    best_name, best_diff = "unison", float("inf")
    for name, (num, den) in INTERVALS.items():
        target = num / den
        diff = abs(ratio - target)
        if diff < best_diff:
            best_name, best_diff = name, diff
    return best_name

def roughness_dyad(f1_hz: float, f2_hz: float) -> float:
    """
    Plomp-Levelt dyadic roughness between two pure tones.
    Returns [0, 1]: 0 = consonant, peaks near 25% of critical bandwidth.

    Note: this is the PURE TONE approximation. Real polyphonic music has
    spectral mass and the full Sethares (1993) extension is needed for
    chord roughness. Use this for pitch-pair signaling only.
    """
    if f1_hz <= 0 or f2_hz <= 0:
        return 0.0
    f_low = min(f1_hz, f2_hz)
    cbw = 1.72 * (f_low ** 0.65)  # critical bandwidth approximation
    x = (max(f1_hz, f2_hz) - f_low) / cbw
    return 4.0 * x * math.exp(1.0 - 4.0 * x) if 0.0 < x < 1.0 else 0.0

# ─── Structured output for downstream consumers ─────────────────────────
@dataclass
class HarmonicAnalysis:
    """Structured output for HarmonicCortex (and Phase 2: AudioCortex, Cochlea)."""
    pitch_hz: Optional[float]
    note: Optional[str]                  # e.g. "A4"
    cents_off: float                     # tuning deviation in cents
    interval_to_last: Optional[str]      # e.g. "perfect_fifth"
    consonance: float                    # [0,1], 1=most consonant
    mode_guess: Optional[str]            # e.g. "major" — needs ≥5 notes history
    affect: Tuple[float, float]          # (valence, arousal) in [-1, 1]
    notes_used: List[str]                # recent note-name history
    is_music: bool
    tempo_bpm: Optional[float]

# ─── Stateful engine for per-frame use ──────────────────────────────────
class MusicTheoryEngine:
    """
    Stateful wrapper. Tracks pitch history for interval + mode detection.
    Pure functions above work standalone; this is for per-frame consumers.

    Usage (HarmonicCortexFairy._on_audio_frame):
        analysis = self._music_engine.evaluate_audio_frame(payload)
        self.post.publish("harmonic.audio_analyzed", {
            "consonance": analysis.consonance,
            "affect_valence": analysis.affect[0],
            "affect_arousal": analysis.affect[1],
            ...
        })
    """
    def __init__(self, history_size: int = 16):
        self._pitch_history: List[float] = []
        self._note_history: List[str] = []
        self._max = history_size

    def evaluate_audio_frame(self, payload: Dict) -> HarmonicAnalysis:
        """
        Evaluate a sensory.audio.frame payload.
        Payload fields used: pitch (Hz), tempo (BPM), is_music (bool).
        """
        pitch_hz = payload.get("pitch") if isinstance(payload, dict) else None
        tempo = payload.get("tempo") if isinstance(payload, dict) else None
        is_music = bool(payload.get("is_music")) if isinstance(payload, dict) else False

        note_name: Optional[str] = None
        octave: int = 0
        cents_off: float = 0.0
        interval: Optional[str] = None
        consonance: float = 1.0

        if pitch_hz and pitch_hz > 0:
            note_name, octave, cents_off = hz_to_note(pitch_hz)
            if self._pitch_history:
                interval = interval_between(self._pitch_history[-1], pitch_hz)
                consonance = 1.0 - CONSONANCE_RANK.get(interval, 0.5)
            self._pitch_history.append(pitch_hz)
            if note_name:
                self._note_history.append(f"{note_name}{octave}")
            # Trim history
            if len(self._pitch_history) > self._max:
                self._pitch_history.pop(0)
            if len(self._note_history) > self._max:
                self._note_history.pop(0)

        mode = self._guess_mode() if len(self._note_history) >= 5 else None
        affect = MODE_AFFECT.get(mode, (0.0, 0.0)) if mode else (0.0, 0.0)

        return HarmonicAnalysis(
            pitch_hz=pitch_hz,
            note=f"{note_name}{octave}" if note_name else None,
            cents_off=cents_off,
            interval_to_last=interval,
            consonance=consonance,
            mode_guess=mode,
            affect=affect,
            notes_used=list(self._note_history),
            is_music=is_music,
            tempo_bpm=tempo,
        )

    def reset(self) -> None:
        """Clear pitch/note history. Useful at silence-break boundaries."""
        self._pitch_history.clear()
        self._note_history.clear()

    def _guess_mode(self) -> Optional[str]:
        """
        Crude mode-detection from recent pitch-class collection.
        PLACEHOLDER — real implementation needs Krumhansl-Schmuckler:
        compute 12-pitch-class probability vector from recent notes;
        correlate against 12 major + 12 minor key profiles; pick max.
        This heuristic just checks for major-third vs minor-third presence.
        """
        if len(self._note_history) < 5:
            return None
        pcs: set = set()
        for n in self._note_history:
            # Strip trailing octave digits to get note name
            base = n.rstrip("0123456789-")
            if base in NOTE_NAMES:
                pcs.add(NOTE_NAMES.index(base))
        if not pcs:
            return None
        has_major_third = any((p + 4) % 12 in pcs for p in pcs)
        has_minor_third = any((p + 3) % 12 in pcs for p in pcs)
        if has_major_third and not has_minor_third:
            return "major"
        if has_minor_third and not has_major_third:
            return "minor"
        if has_major_third and has_minor_third:
            return "dorian"  # both 3rds present — ambiguous, default to dorian
        return None

# ─── Singleton for easy import ──────────────────────────────────────────
default_engine = MusicTheoryEngine()
