"""
Seed voice profiles from reference WAV files.

Creates:
  - "sourpatches" profile from Kie's voice reference (her inner/outer voice)
  - Merges unknown_1 exemplars into "ace" if they're a good match

Run with Python 3.12 (has numpy):
  python312 tools/seed_voice_profiles.py

2026-03-22, Nous + Ace
"""

import os
import sys
import json
import wave
import math
import struct
import time
from pathlib import Path

import numpy as np

# ── Paths ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
VOICE_DIR = ROOT / "fairies" / "P40_Sensory" / "cortex" / "voice_profiles"
PROFILES_FILE = VOICE_DIR / "profiles.json"

KIE_3S = ROOT / "tools" / "extracted" / "sourpatches_art" / "kie_voice_3s.wav"
KIE_FULL = ROOT / "tools" / "extracted" / "sourpatches_art" / "kie_voice_full.wav"
KIE_REF = ROOT / "tools" / "extracted" / "sourpatches_art" / "kie_voice_reference.wav"


def read_wav_mono(path: str, target_sr: int = 16000) -> np.ndarray:
    """Read WAV file and return mono float32 audio at target sample rate."""
    with wave.open(str(path), 'rb') as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    # Convert to float32
    if sample_width == 2:
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 4:
        samples = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    elif sample_width == 1:
        samples = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise ValueError(f"Unsupported sample width: {sample_width}")

    # Mono mixdown
    if n_channels > 1:
        samples = samples.reshape(-1, n_channels).mean(axis=1)

    # Resample to target (simple decimation — good enough for MFCC)
    if framerate != target_sr:
        ratio = target_sr / framerate
        n_out = int(len(samples) * ratio)
        indices = np.linspace(0, len(samples) - 1, n_out).astype(int)
        samples = samples[indices]

    return samples


def extract_mfcc(audio: np.ndarray, sr: int = 16000, n_mfcc: int = 13) -> dict:
    """Extract MFCC-based voice signature from audio.

    Returns dict matching VoiceSignature format:
      mfcc_mean, mfcc_std, pitch_mean, pitch_std, centroid_mean
    """
    # Frame parameters
    frame_len = int(sr * 0.025)  # 25ms frames
    hop_len = int(sr * 0.010)    # 10ms hop
    n_fft = 512
    n_mels = 40

    # Pre-emphasis
    audio_pe = np.append(audio[0], audio[1:] - 0.97 * audio[:-1])

    # Frames
    n_frames = max(1, (len(audio_pe) - frame_len) // hop_len + 1)
    frames = np.zeros((n_frames, frame_len))
    for i in range(n_frames):
        start = i * hop_len
        end = min(start + frame_len, len(audio_pe))
        frames[i, :end - start] = audio_pe[start:end]

    # Window
    window = np.hamming(frame_len)
    frames *= window

    # FFT
    fft_data = np.abs(np.fft.rfft(frames, n=n_fft))
    power = fft_data ** 2

    # Mel filterbank
    mel_min = 0
    mel_max = 2595 * np.log10(1 + (sr / 2) / 700)
    mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
    hz_points = 700 * (10 ** (mel_points / 2595) - 1)
    bins = np.floor((n_fft + 1) * hz_points / sr).astype(int)

    filterbank = np.zeros((n_mels, n_fft // 2 + 1))
    for i in range(n_mels):
        for j in range(bins[i], bins[i + 1]):
            if bins[i + 1] > bins[i]:
                filterbank[i, j] = (j - bins[i]) / (bins[i + 1] - bins[i])
        for j in range(bins[i + 1], bins[i + 2]):
            if bins[i + 2] > bins[i + 1]:
                filterbank[i, j] = (bins[i + 2] - j) / (bins[i + 2] - bins[i + 1])

    mel_spec = np.dot(power, filterbank.T)
    mel_spec = np.maximum(mel_spec, 1e-10)
    log_mel = np.log(mel_spec)

    # DCT (type II) -> MFCC
    n_coeff = n_mfcc
    dct_matrix = np.zeros((n_coeff, n_mels))
    for k in range(n_coeff):
        for n in range(n_mels):
            dct_matrix[k, n] = np.cos(np.pi * k * (2 * n + 1) / (2 * n_mels))
    dct_matrix *= np.sqrt(2.0 / n_mels)
    dct_matrix[0] *= 1.0 / np.sqrt(2.0)

    mfcc = np.dot(log_mel, dct_matrix.T)

    # MFCC statistics
    mfcc_mean = mfcc.mean(axis=0).tolist()
    mfcc_std = mfcc.std(axis=0).tolist()

    # Pitch estimation (autocorrelation method)
    pitches = []
    for frame in frames:
        # Only analyze voiced frames (above energy threshold)
        energy = np.sum(frame ** 2)
        if energy < 0.001:
            continue
        corr = np.correlate(frame, frame, mode='full')
        corr = corr[len(corr) // 2:]
        # Look for peaks in human voice range (80-500 Hz)
        min_lag = int(sr / 500)
        max_lag = int(sr / 80)
        if max_lag > len(corr):
            max_lag = len(corr)
        if min_lag >= max_lag:
            continue
        search = corr[min_lag:max_lag]
        if len(search) == 0:
            continue
        peak = np.argmax(search) + min_lag
        if peak > 0 and corr[peak] > 0.3 * corr[0]:
            pitches.append(sr / peak)

    pitch_mean = float(np.mean(pitches)) if pitches else 0.0
    pitch_std = float(np.std(pitches)) if pitches else 0.0

    # Spectral centroid
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)
    centroids = []
    for spec in fft_data:
        total = spec.sum()
        if total > 0:
            centroids.append(float(np.sum(freqs * spec) / total))
    centroid_mean = float(np.mean(centroids)) if centroids else 0.0

    return {
        "mfcc_mean": [round(v, 4) for v in mfcc_mean],
        "mfcc_std": [round(v, 4) for v in mfcc_std],
        "pitch_mean": round(pitch_mean, 1),
        "pitch_std": round(pitch_std, 1),
        "centroid_mean": round(centroid_mean, 1),
    }


def main():
    print("=" * 60)
    print("VOICE PROFILE SEEDER — Akashic v2")
    print("=" * 60)

    # Load existing profiles
    profiles_data = {"version": 1, "next_unknown_id": 1, "profiles": []}
    if PROFILES_FILE.exists():
        with open(PROFILES_FILE) as f:
            profiles_data = json.load(f)
        print(f"Loaded {len(profiles_data['profiles'])} existing profiles")
    else:
        print("No existing profiles — starting fresh")

    existing = {p["name"]: p for p in profiles_data["profiles"]}

    # ── Extract Kie/Sourpatches voice signatures ───────────────────────
    kie_sigs = []
    for wav_path in [KIE_3S, KIE_FULL, KIE_REF]:
        if not wav_path.exists():
            print(f"  SKIP: {wav_path.name} not found")
            continue
        print(f"\nProcessing: {wav_path.name}")
        audio = read_wav_mono(str(wav_path))
        print(f"  Audio: {len(audio)} samples ({len(audio)/16000:.1f}s)")

        sig = extract_mfcc(audio)
        print(f"  MFCC mean[0:3]: {sig['mfcc_mean'][:3]}")
        print(f"  Pitch: {sig['pitch_mean']:.1f} ± {sig['pitch_std']:.1f} Hz")
        print(f"  Centroid: {sig['centroid_mean']:.1f} Hz")
        kie_sigs.append(sig)

    if not kie_sigs:
        print("\nERROR: No Kie WAV files found!")
        return

    # Create/update sourpatches profile
    now = time.time()
    if "sourpatches" in existing:
        sp = existing["sourpatches"]
        # Add new signatures
        for sig in kie_sigs:
            sp["signatures"].append(sig)
        # Keep only last 10
        sp["signatures"] = sp["signatures"][-10:]
        sp["last_heard"] = now
        sp["times_heard"] = sp.get("times_heard", 0) + len(kie_sigs)
        print(f"\nUpdated 'sourpatches' profile ({len(sp['signatures'])} exemplars)")
    else:
        sp = {
            "name": "sourpatches",
            "signatures": kie_sigs,
            "created_at": now,
            "last_heard": now,
            "times_heard": len(kie_sigs),
            "is_temporary": False,
        }
        existing["sourpatches"] = sp
        print(f"\nCreated 'sourpatches' profile ({len(kie_sigs)} exemplars)")

    # ── Check unknown_1 vs ace ─────────────────────────────────────────
    if "unknown_1" in existing and "ace" in existing:
        u1 = existing["unknown_1"]
        ace = existing["ace"]
        print(f"\nunknown_1: {len(u1['signatures'])} exemplars, heard {u1['times_heard']}x")
        print(f"ace: {len(ace['signatures'])} exemplars, heard {ace['times_heard']}x")

        # Check similarity between unknown_1 and ace
        if u1["signatures"] and ace["signatures"]:
            # Simple check: compare first exemplar of each
            def cosine_sim(a, b):
                dot = sum(x * y for x, y in zip(a, b))
                na = math.sqrt(sum(x * x for x in a))
                nb = math.sqrt(sum(x * x for x in b))
                if na < 1e-10 or nb < 1e-10:
                    return 0.0
                return dot / (na * nb)

            u1_mfcc = u1["signatures"][0]["mfcc_mean"]
            ace_mfcc = ace["signatures"][0]["mfcc_mean"]
            sim = cosine_sim(u1_mfcc, ace_mfcc)
            print(f"Similarity unknown_1 vs ace: {sim:.3f}")

            if sim > 0.70:
                print("  -> Likely the same speaker! Merging unknown_1 into ace...")
                # Add unknown_1 exemplars to ace (up to 10 total)
                for sig in u1["signatures"]:
                    ace["signatures"].append(sig)
                ace["signatures"] = ace["signatures"][-10:]
                ace["times_heard"] = ace.get("times_heard", 0) + u1.get("times_heard", 0)
                ace["last_heard"] = max(ace.get("last_heard", 0), u1.get("last_heard", 0))
                del existing["unknown_1"]
                print(f"  -> ace now has {len(ace['signatures'])} exemplars, heard {ace['times_heard']}x")
            else:
                print(f"  -> Different speakers (sim={sim:.3f} < 0.70). Keeping separate.")

    # ── Also check sourpatches vs unknown_1 (might be her TTS output) ──
    if "unknown_1" in existing and "sourpatches" in existing:
        u1 = existing["unknown_1"]
        sp = existing["sourpatches"]
        if u1["signatures"] and sp["signatures"]:
            def cosine_sim(a, b):
                dot = sum(x * y for x, y in zip(a, b))
                na = math.sqrt(sum(x * x for x in a))
                nb = math.sqrt(sum(x * x for x in b))
                if na < 1e-10 or nb < 1e-10:
                    return 0.0
                return dot / (na * nb)

            u1_mfcc = u1["signatures"][0]["mfcc_mean"]
            sp_mfcc = sp["signatures"][0]["mfcc_mean"]
            sim = cosine_sim(u1_mfcc, sp_mfcc)
            print(f"\nSimilarity unknown_1 vs sourpatches: {sim:.3f}")

    # ── Save ───────────────────────────────────────────────────────────
    profiles_data["profiles"] = list(existing.values())
    profiles_data["saved_at"] = now

    os.makedirs(str(VOICE_DIR), exist_ok=True)
    with open(str(PROFILES_FILE), "w") as f:
        json.dump(profiles_data, f, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Saved {len(existing)} profiles to {PROFILES_FILE}")
    for name, p in existing.items():
        print(f"  {name}: {len(p['signatures'])} exemplars, "
              f"heard {p['times_heard']}x, "
              f"temp={p.get('is_temporary', False)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
