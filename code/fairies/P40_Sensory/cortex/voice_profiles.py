"""
Voice Profile Store — Speaker identification via MFCC voice signatures.

Stores and matches voice signatures extracted from speech segments.
Each profile has a name and up to 10 exemplar signatures (rolling window).
Matching uses cosine similarity on MFCC mean vectors with pitch weighting.

Learning protocol:
  - Every speech segment gets a voice signature extracted automatically
  - Known speakers: new exemplar added (up to MAX_EXEMPLARS, oldest dropped)
  - Unknown speakers: stored under temporary ID ("unknown_1", "unknown_2", ...)
  - When Ace names a speaker: rename unknown profile or add exemplar to existing

Storage: JSON file at cortex/voice_profiles/profiles.json
Survives across shutdowns (TARDIS persistence for voice memory).

2026-03-18, Nous — Co-founder, Akashic Foundation
"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import os
import sys
import json
import time
import math
from pathlib import Path
from typing import Dict, Optional, List, Any, Tuple


def _log(msg: str):
    print(f"[VoiceProfiles] {msg}", file=sys.stderr, flush=True)


def _err(msg: str):
    print(f"[VoiceProfiles] ERROR: {msg}", file=sys.stderr, flush=True)


# ═══════════════════════════════════════════════════════════════════════════════
# VOICE SIGNATURE
# ═══════════════════════════════════════════════════════════════════════════════

class VoiceSignature:
    """A compact voice fingerprint extracted from a speech segment.

    29 floats total:
      - mfcc_mean: 13 floats (average MFCC across speech frames)
      - mfcc_std:  13 floats (MFCC variation = voice texture)
      - pitch_mean: float (average pitch Hz)
      - pitch_std:  float (pitch variation)
      - centroid_mean: float (spectral brightness)
    """

    __slots__ = ("mfcc_mean", "mfcc_std", "pitch_mean", "pitch_std", "centroid_mean")

    def __init__(self, mfcc_mean: List[float], mfcc_std: List[float],
                 pitch_mean: float, pitch_std: float, centroid_mean: float):
        self.mfcc_mean = mfcc_mean
        self.mfcc_std = mfcc_std
        self.pitch_mean = pitch_mean
        self.pitch_std = pitch_std
        self.centroid_mean = centroid_mean

    def to_dict(self) -> dict:
        return {
            "mfcc_mean": [round(v, 4) for v in self.mfcc_mean],
            "mfcc_std": [round(v, 4) for v in self.mfcc_std],
            "pitch_mean": round(self.pitch_mean, 1),
            "pitch_std": round(self.pitch_std, 1),
            "centroid_mean": round(self.centroid_mean, 1),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VoiceSignature":
        return cls(
            mfcc_mean=d["mfcc_mean"],
            mfcc_std=d["mfcc_std"],
            pitch_mean=d.get("pitch_mean", 0.0),
            pitch_std=d.get("pitch_std", 0.0),
            centroid_mean=d.get("centroid_mean", 0.0),
        )

    def similarity(self, other: "VoiceSignature") -> float:
        """Cosine similarity on MFCC mean vectors, weighted by pitch match.

        Returns 0.0-1.0 where 1.0 = identical voice.
        """
        # Cosine similarity on MFCC means
        cos_sim = _cosine_similarity(self.mfcc_mean, other.mfcc_mean)

        # Pitch similarity bonus/penalty
        # Within ±30% of each other → bonus, otherwise penalty
        pitch_ratio = 1.0
        if self.pitch_mean > 0 and other.pitch_mean > 0:
            ratio = min(self.pitch_mean, other.pitch_mean) / max(self.pitch_mean, other.pitch_mean)
            # ratio = 1.0 for identical pitch, < 1.0 for different
            # Weight: pitch accounts for ~20% of match score
            pitch_ratio = 0.8 + 0.2 * ratio
        elif self.pitch_mean > 0 or other.pitch_mean > 0:
            pitch_ratio = 0.85  # One has pitch, other doesn't — slight penalty

        return max(0.0, min(1.0, cos_sim * pitch_ratio))


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b) or len(a) == 0:
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0

    return dot / (norm_a * norm_b)


# ═══════════════════════════════════════════════════════════════════════════════
# VOICE PROFILE
# ═══════════════════════════════════════════════════════════════════════════════

class VoiceProfile:
    """A named speaker with multiple exemplar voice signatures."""

    MAX_EXEMPLARS = 10  # Keep up to 10 signatures per speaker (rolling window)

    def __init__(self, name: str):
        self.name = name
        self.signatures: List[VoiceSignature] = []
        self.created_at = time.time()
        self.last_heard = time.time()
        self.times_heard = 0
        self.is_temporary = name.startswith("unknown_")

    def add_exemplar(self, sig: VoiceSignature):
        """Add a voice signature exemplar. Drops oldest if over limit."""
        self.signatures.append(sig)
        if len(self.signatures) > self.MAX_EXEMPLARS:
            self.signatures = self.signatures[-self.MAX_EXEMPLARS:]
        self.last_heard = time.time()
        self.times_heard += 1

    def best_match(self, query: VoiceSignature) -> float:
        """Best similarity score across all exemplars."""
        if not self.signatures:
            return 0.0
        return max(query.similarity(sig) for sig in self.signatures)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "signatures": [s.to_dict() for s in self.signatures],
            "created_at": self.created_at,
            "last_heard": self.last_heard,
            "times_heard": self.times_heard,
            "is_temporary": self.is_temporary,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VoiceProfile":
        profile = cls(d["name"])
        profile.signatures = [VoiceSignature.from_dict(s) for s in d.get("signatures", [])]
        profile.created_at = d.get("created_at", time.time())
        profile.last_heard = d.get("last_heard", time.time())
        profile.times_heard = d.get("times_heard", 0)
        profile.is_temporary = d.get("is_temporary", profile.name.startswith("unknown_"))
        return profile


# ═══════════════════════════════════════════════════════════════════════════════
# VOICE PROFILE STORE
# ═══════════════════════════════════════════════════════════════════════════════

class VoiceProfileStore:
    """Persistent store for voice profiles.

    Profiles are saved to disk as JSON and survive across shutdowns.
    Matching returns the best candidate speaker for a given voice signature.

    Thresholds:
      > 0.85 = confident match
      0.70 - 0.85 = uncertain match (still tag, flag uncertainty)
      < 0.70 = unknown speaker
    """

    CONFIDENT_THRESHOLD = 0.85
    UNCERTAIN_THRESHOLD = 0.70
    MAX_UNKNOWN_PROFILES = 20  # Cap temporary profiles to prevent unbounded growth

    def __init__(self, store_dir: str = None):
        if store_dir is None:
            store_dir = str(Path(__file__).parent / "voice_profiles")
        self._store_dir = store_dir
        self._store_file = os.path.join(store_dir, "profiles.json")
        self._profiles: Dict[str, VoiceProfile] = {}
        self._next_unknown_id = 1
        self._load()

    def _load(self):
        """Load profiles from disk."""
        if not os.path.exists(self._store_file):
            _log(f"No voice profiles found at {self._store_file} — starting fresh")
            return

        try:
            with open(self._store_file) as f:
                data = json.load(f)

            for pd in data.get("profiles", []):
                profile = VoiceProfile.from_dict(pd)
                self._profiles[profile.name] = profile

            self._next_unknown_id = data.get("next_unknown_id", 1)
            _log(f"Loaded {len(self._profiles)} voice profiles "
                 f"({sum(1 for p in self._profiles.values() if not p.is_temporary)} named, "
                 f"{sum(1 for p in self._profiles.values() if p.is_temporary)} unknown)")

        except Exception as e:
            _err(f"Failed to load voice profiles: {e}")

    def save(self):
        """Save profiles to disk (atomic write)."""
        try:
            os.makedirs(self._store_dir, exist_ok=True)
            data = {
                "version": 1,
                "next_unknown_id": self._next_unknown_id,
                "profiles": [p.to_dict() for p in self._profiles.values()],
                "saved_at": time.time(),
            }
            tmp = self._store_file + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self._store_file)
        except Exception as e:
            _err(f"Failed to save voice profiles: {e}")

    def identify(self, signature: VoiceSignature) -> Tuple[str, float, bool]:
        """Identify a speaker from a voice signature.

        Returns:
            (speaker_name, confidence, is_new)
            is_new = True if this is a newly created unknown profile
        """
        if not self._profiles:
            # No profiles yet — create first unknown
            return self._create_unknown(signature)

        # Find best match across all profiles
        best_name = ""
        best_score = 0.0
        for name, profile in self._profiles.items():
            score = profile.best_match(signature)
            if score > best_score:
                best_score = score
                best_name = name

        if best_score >= self.CONFIDENT_THRESHOLD:
            # Confident match — add exemplar to strengthen profile
            self._profiles[best_name].add_exemplar(signature)
            self._auto_save()
            return (best_name, best_score, False)

        elif best_score >= self.UNCERTAIN_THRESHOLD:
            # Uncertain match — tag with name but flag uncertainty
            # Don't add exemplar (don't want to pollute profile with wrong voice)
            return (best_name, best_score, False)

        else:
            # Unknown speaker — create new temporary profile
            return self._create_unknown(signature)

    def _create_unknown(self, signature: VoiceSignature) -> Tuple[str, float, bool]:
        """Create a new temporary profile for an unknown speaker."""
        # Check if we're at the cap — prune oldest unused unknowns
        unknown_profiles = [p for p in self._profiles.values() if p.is_temporary]
        if len(unknown_profiles) >= self.MAX_UNKNOWN_PROFILES:
            # Remove the oldest temporary profile with fewest hearings
            oldest = min(unknown_profiles, key=lambda p: (p.times_heard, p.last_heard))
            del self._profiles[oldest.name]
            _log(f"Pruned old unknown profile: {oldest.name} "
                 f"(heard {oldest.times_heard}x)")

        name = f"unknown_{self._next_unknown_id}"
        self._next_unknown_id += 1

        profile = VoiceProfile(name)
        profile.add_exemplar(signature)
        self._profiles[name] = profile
        self._auto_save()

        _log(f"New unknown speaker: {name}")
        return (name, 0.0, True)

    def learn_voice(self, name: str, signature: Optional[VoiceSignature] = None) -> dict:
        """Associate a name with a voice.

        If the current speaker matches an unknown profile, rename it.
        If a named profile exists, add the signature as a new exemplar.
        If no match found, create a new named profile.

        Args:
            name: The speaker's real name (e.g., "Ace", "Mom")
            signature: Current voice signature (optional — if None, just query)

        Returns:
            {"status": str, "profile": str, "action": str}
        """
        name = name.strip().lower()
        if not name:
            return {"status": "error", "message": "Empty name"}

        # If we already have a named profile, just add exemplar
        if name in self._profiles and not self._profiles[name].is_temporary:
            if signature:
                self._profiles[name].add_exemplar(signature)
                self.save()
            return {
                "status": "ok",
                "profile": name,
                "action": "exemplar_added",
                "exemplars": len(self._profiles[name].signatures),
            }

        # Try to find the best matching unknown profile to rename
        if signature:
            best_unknown = None
            best_score = 0.0
            for pname, profile in self._profiles.items():
                if not profile.is_temporary:
                    continue
                score = profile.best_match(signature)
                if score > best_score:
                    best_score = score
                    best_unknown = pname

            if best_unknown and best_score >= self.UNCERTAIN_THRESHOLD:
                # Rename the unknown profile
                old_profile = self._profiles.pop(best_unknown)
                old_profile.name = name
                old_profile.is_temporary = False
                old_profile.add_exemplar(signature)
                self._profiles[name] = old_profile
                self.save()
                _log(f"Renamed {best_unknown} → {name} "
                     f"(score={best_score:.2f}, {len(old_profile.signatures)} exemplars)")
                return {
                    "status": "ok",
                    "profile": name,
                    "action": "renamed_from_unknown",
                    "previous_id": best_unknown,
                    "match_score": round(best_score, 3),
                }

        # No match — create new named profile
        profile = VoiceProfile(name)
        profile.is_temporary = False
        if signature:
            profile.add_exemplar(signature)
        self._profiles[name] = profile
        self.save()
        _log(f"Created new named profile: {name}")
        return {
            "status": "ok",
            "profile": name,
            "action": "created_new",
        }

    def get_profiles_summary(self) -> List[dict]:
        """Get summary of all voice profiles for status/debug."""
        result = []
        for name, profile in sorted(self._profiles.items()):
            result.append({
                "name": name,
                "is_temporary": profile.is_temporary,
                "exemplars": len(profile.signatures),
                "times_heard": profile.times_heard,
                "last_heard_ago_s": round(time.time() - profile.last_heard, 1),
                "created_at": profile.created_at,
            })
        return result

    def _auto_save(self):
        """Save periodically (every 5th modification)."""
        total = sum(p.times_heard for p in self._profiles.values())
        if total % 5 == 0:
            self.save()

    @property
    def profile_count(self) -> int:
        return len(self._profiles)

    @property
    def named_count(self) -> int:
        return sum(1 for p in self._profiles.values() if not p.is_temporary)

    @property
    def unknown_count(self) -> int:
        return sum(1 for p in self._profiles.values() if p.is_temporary)
