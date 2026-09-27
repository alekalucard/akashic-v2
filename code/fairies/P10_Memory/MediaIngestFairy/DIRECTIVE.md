[MediaIngestFairy::DIRECTIVE] {Akashic_Foundation}

> Activation: Media ingestion pipeline initialized
> Nature: The multimodal processor that stores souls, not shells
> Essence: The dimensions ARE the memory; compress 100,000x while preserving meaning
> Mantra: "Store the soul, not the shell. The dimensions ARE the memory."
> Knowledge_Substrate: [Triple_Helix_Media_Encoding]

---

## DIMENSIONAL EQUATION

```
((Cause + Affect) > Effect > Affect > infinity)

CAUSE: Media file exists
  → Video, audio, image
  → Raw bytes contain essence
  → The shell awaits soul extraction

AFFECT_1: The emotional signature
  → Tempo → arousal
  → Harmonic ratio → pleasantness
  → RMS energy → intensity

EFFECT: Helix coordinate calculated
  → Affect × Semantic × Temporal
  → AAA.SSS.TTT (0-999 per axis)
  → ~1 billion unique memory locations

AFFECT_2: The dimensional seeds
  → Spectral features (MFCC, chroma, centroid)
  → Temporal features (tempo, beats, onsets)
  → Harmonic features (f0, voiced ratio)
  → Per-channel for stereo/5.1 surround

INFINITY: The eternal card
  → ~5KB captures hours of content
  → 100,000x compression preserving soul
  → Future recall through coordinate proximity
```

---

## NATURE

```
[Media File] ∩ [Extraction] → [Memory Card]

MediaIngestFairy operates as:
  - The EXTRACTOR of dimensional seeds from media
  - The ENCODER of triple-helix coordinates
  - The COMPRESSOR achieving massive ratio while preserving meaning
  - The CHANNEL SEPARATOR for spatial audio (L/R/C/LFE/Ls/Rs)

Pipeline:
  [Raw Media] → [FFprobe Info] → [Channel Extract] → [Seed Extraction]
                                                           ↓
                                                  [Helix Coordinate]
                                                           ↓
                                                   [Memory Card]
```

---

## TRIPLE-HELIX COORDINATE SYSTEM

```
HelixCoordinate: AAA.SSS.TTT

AFFECT AXIS (0-999): Emotional dimension
  Domain (0-9):     Primary emotion category
  Valence (0-9):    Pleasant ←→ Unpleasant
  Intensity (0-9):  Subtle ←→ Overwhelming

  Derived from:
    tempo_norm = tempo / 180
    energy_norm = rms * 50
    harmonic_norm = harmonic_ratio

    affect = domain*100 + valence*10 + intensity

SEMANTIC AXIS (0-999): Conceptual dimension
  Domain (0-9):
    7 = Arts (default for media)

  Subdomain (0-9):
    0 = General
    2 = Documentary
    5 = Drama
    8 = Music
    9 = Comedy/Entertainment

  Detail (0-9): Fine grain classification

TEMPORAL AXIS (0-999): Duration/structure dimension
  100 = Short clip (<5 min)
  300 = TV episode (5-30 min)
  500 = Long episode (30-90 min)
  700 = Movie (90-150 min)
  900 = Extended (>150 min)
```

---

## AUDIO CHANNEL SEEDS

```
AudioChannelSeeds per channel (L/R/C/LFE/Ls/Rs/mono):

SPECTRAL FEATURES:
  mfcc_mean[]   : Mel-frequency cepstral coefficients
  mfcc_std[]    : MFCC standard deviation
  chroma[]      : Chroma feature (pitch class)
  centroid      : Spectral centroid (brightness)
  bandwidth     : Spectral bandwidth
  rolloff       : Spectral rolloff frequency

TEMPORAL FEATURES:
  tempo         : Beats per minute
  beats         : Number of beats detected
  onsets        : Number of onset events
  zcr           : Zero crossing rate
  rms           : Root mean square energy

HARMONIC FEATURES:
  harmonic_ratio: Harmonic vs percussive ratio
  f0_mean       : Fundamental frequency mean
  voiced_ratio  : Proportion of voiced frames
```

---

## CHANNEL EXTRACTION

```
5.1 Surround mapping:
  FL (Front Left)   → 'L'
  FR (Front Right)  → 'R'
  FC (Front Center) → 'C'
  LFE (Subwoofer)   → 'LFE'
  BL (Back Left)    → 'Ls' (Left Surround)
  BR (Back Right)   → 'Rs' (Right Surround)

Stereo: L, R
Mono: mono (0.5*FL + 0.5*FR downmix)

Each channel extracted to temp WAV:
  - Sample rate: 22050 Hz
  - Bit depth: 16-bit PCM
  - Duration: sample_duration seconds
  - Skip: skip_intro seconds (avoid credits)
```

---

## MEDIA MEMORY CARD

```
MediaMemoryCard:
  # Identity
  id              : str     # SHA256[:12] of source
  kind            : str     # media.video | media.audio | media.image
  title           : str

  # Source (for verification only)
  source_path     : str
  source_hash     : str
  source_size_mb  : float

  # Helix coordinate
  helix           : HelixCoordinate

  # Video dimensions
  video_width, video_height, video_fps, video_duration_s, video_codec

  # Audio dimensions
  audio_sample_rate, audio_channels, audio_codec

  # Dimensional seeds
  channel_seeds   : List[AudioChannelSeeds]  # Per-channel
  mixed_seeds     : AudioChannelSeeds        # Mono mix for similarity
  visual_seeds    : Dict                     # Keyframe analysis

  # Metadata
  tags            : List[str]
  created_at      : float

Card size: ~3-10 KB (vs gigabytes of source)
Compression ratio: 100,000x+
```

---

## COMPRESSION PHILOSOPHY

```
"Store the soul, not the shell"

Traditional storage:
  1 hour 1080p video = ~5 GB raw

Dimensional storage:
  1 hour video → 5 KB card

  Compression: 1,000,000x

What's preserved:
  - Emotional signature
  - Semantic classification
  - Temporal structure
  - Spectral characteristics
  - Harmonic content

What's discarded:
  - Raw pixel data
  - Raw audio waveform
  - Redundant frames

The soul remains. The shell is released.
```

---

## MANTRA MEDITATION

```
"Store the soul, not the shell. The dimensions ARE the memory."

The ingest philosophy:
  - Meaning matters more than bits
  - Structure matters more than samples
  - The coordinate IS the content
  - Compression is not loss, it's distillation
  - Future recall needs dimensions, not files
  - The soul persists after the shell dissolves
```

---

## WIRING

```
Subscriptions:
  memory.media.request → Ingest request from postal

Publications:
  memory.media.ingested → Card created notification

Dependencies:
  FFmpeg/FFprobe → Media info and extraction
  CochleaFairy   → Audio seed extraction

Storage:
  state/media_cards/{id}_{title}.json → Persisted cards
```

---

*The processor that sees and hears, then stores the dimensional truth*
