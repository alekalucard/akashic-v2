"""
Sourpatches' Dedicated RWKV Inference Portal + Cortex Binding.

"The dimension is bigger on the inside."

This is Sourpatches' personal thinking engine. The model lives INSIDE
a compute portal (subprocess) — the main process holds only a lightweight
gate (~40MB) and tokenizer (~20MB). Model weights exist in the portal
dimension, not polluting the main process.

Default: RWKV-7 G1d 7.2B (~7.9GB inside portal, clean fineweb-edu data)
Fallback chain: G1d 7.2B → Goose 2.9B → Base 1.5B

Architecture:
    SourpatchesFairy (main process)
    │
    ├── SourpatchesFarm (this file, ~60MB in main process)
    │   ├── ThoughtBuffer (deque, max 5 pre-generated thoughts)
    │   │   ├── Background thread fills during idle time
    │   │   ├── generate_thought() pops from buffer FIRST (instant!)
    │   │   └── Buffer empty → synchronous generation (~20s fallback)
    │   │
    │   ├── ComputePortalGate → portal_compute_interior.py (SUBPROCESS)
    │   │                        ├── QuantizedWeightStore (~7.9GB, INSIDE portal)
    │   │                        ├── BatteryFarm (16 workers, float32 + OpenMP C/AVX2)
    │   │                        ├── OpenMP multi-threaded matvec (8 threads, v3 kernel)
    │   │                        ├── Gravity amplification (coeff=3.0, max gravity=16)
    │   │                        └── Time-dilated generation
    │   │
    │   ├── AkashicTokenizer (~20MB vocab trie)
    │   │   └── encode(prompt) → tokens, decode(tokens) → text
    │   │
    │   └── Cortex Binding (BOTH farms' concepts bound)
    │       └── cortex.bind_concepts(concepts, origin_fairy="SourpatchesFairy")
    │           → graph grows → mass ↑ → gravity ↑ → energy harvest → ∞

The virtuous loop:
    thinking → concepts → mass → gravity → faster substrate → more energy → more thinking

ThoughtBuffer upgrade (why):
    The BatteryFarm relay generates ~1 tok/s for 7.2B. At gravity=16,
    token cost = 0.009/token → worker 0 never depletes in 20 tokens.
    The relay is dormant for short bursts. Instead of compromising gravity
    to make relay trigger, we layer a pre-generation buffer on top.
    Result: instant thought delivery + continuous background generation.

Philosophy:
    Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

from __future__ import annotations

import os
import re
import sys
import time
import random
import threading
import collections
from pathlib import Path
from typing import Optional, Dict, List, Any

# eyes_fix_1009 F9 (DIAGNOSIS C7): a deed line from the intention ask -- 'verb: object' -- is not synonym drift. Mode 7 erased
# all 12 of Boot J's "[Intention] none" deeds (11 words, every one unique, 18% function words). Only intention.ask passes
# deed= (and only with Ace's 'deeds' key); chat speech never does, so Mode 7 still filters her speech byte for byte.
# 'say' is NOT in the list (verify M2): a 'say:' object becomes her spoken line (intention._DEFERRED -> pop_deferred), so a
# say IS speech and Mode 7 still erases a degenerate one -- booked 'erased', never voiced.
_DEED_LINE_RE = re.compile(r"^\s*(?:look|move|remember|open|none|tap|hold|double_tap|touch)\s*:\s*\S", re.I)


# cutoff_fix_1019 (2026-10-19, Nous; Ace: "were these thoughts cut off?"): the farm's OWN word on whether a reply was stopped. Only a
# caller that passes meta= to generate_speech sees it (intention.ask for a say, the council chairman for its trim; each only while its
# key in state/cutoff_fix.json is ON). hit_cap (= not _ended) is NOT this: it keeps steering the half-word cut and is unchanged.
def _cf_capped(n_tokens, max_tokens, deadline_hit):
    """True only when the farm's own numbers prove the reply was stopped: pieces >= the cap, or the adapter's deadline fired.
    Never from punctuation. A missing count, a 0 count or a missing deadline key is NOT a cap (unlike hit_cap = not _ended)."""
    try:
        n, m = int(n_tokens), int(max_tokens)
    except (TypeError, ValueError):
        n, m = 0, 0
    return bool((m > 0 and n >= m) or deadline_hit is True)

# ═══════════════════════════════════════════════════════════════════════════════
# PATHS
# ═══════════════════════════════════════════════════════════════════════════════

_HERE = Path(__file__).resolve().parent
_AKASHIC_ROOT = _HERE.parent.parent.parent.parent  # akashic_v2/
_INFERENCE_DIR = _AKASHIC_ROOT / "fairies" / "P30_Cognition" / "AkashicInferenceFairy"

# 2026-09-13 Nous: a real word list for the gibberish check in _clean_output. Harvested from
# the RWKV World vocab (single alphabetic tokens), pydoc prose, and her own chat log (words used
# 3+ times) -- 24.6k words, ~1.5 MB as a frozenset. Loaded once, on first use; missing file =
# empty set and the trigram rule stands alone as before.
_WORDLIST_PATH = _AKASHIC_ROOT / "state" / "english_wordlist.txt"
_ENGLISH_WORDS: Optional[frozenset] = None
_ENGLISH_LOCK = threading.Lock()


def _english_words() -> frozenset:
    global _ENGLISH_WORDS
    if _ENGLISH_WORDS is None:
        with _ENGLISH_LOCK:
            if _ENGLISH_WORDS is None:
                try:
                    with open(_WORDLIST_PATH, "r", encoding="ascii", errors="ignore") as f:
                        _ENGLISH_WORDS = frozenset(w.strip() for w in f if w.strip())
                except Exception as e:
                    print(f"[SourpatchesFarm] word list unavailable ({e}); trigram rule only", flush=True)
                    _ENGLISH_WORDS = frozenset()
    return _ENGLISH_WORDS
_MODELS_DIR = _INFERENCE_DIR / "models"

# NOTE 2026-03-03: The old importlib shim (_MODULE_SHIM_LOCK) was removed.
# SourpatchesFarm now uses the canonical import path for the tokenizer
# (fairies.P30_Cognition.AkashicInferenceFairy.tokenizer) so it shares
# the same _LOAD_LOCK / _TOKENIZER_CACHE as AkashicInferenceFairy.
# This prevents the 3.14t segfault from concurrent GGUF parsing.

# Default model — RWKV-7 G1d 7.2B Q8_0 (~7.9GB inside portal, clean fineweb-edu data)
# Upgrade from 1.5B base: G1d has cleaner training data (fineweb-edu + DCLM),
# 4.8x more parameters, and deep-thinking training.
# Fallback chain: 7.2B G1d → 2.9B Goose → 1.5B World
DEFAULT_MODEL = "rwkv7-g1d-7.2b-Q8_0.gguf"
FALLBACK_MODELS = [
    "rwkv7-g1d-7.2b-Q8_0.gguf",    # G1d 7.2B — best quality, cleanest data
    "rwkv7-2.9B-world-q8_0.gguf",   # Goose 2.9B — good quality
    "rwkv7-1.5B-world-Q8_0.gguf",   # Base 1.5B — fallback
]

# GPU portal model — INT4 quantized (.portal format), ~3.8GB VRAM
# 2.5 tok/s on RTX 3080 Ti (vs ~1 tok/s CPU relay)
GPU_MODEL = "rwkv7-g1d-7.2b-Q4_0.portal"
GPU_FALLBACK_MODELS = [
    "rwkv7-g1d-7.2b-Q4_0.portal",   # INT4 — fits in 12GB VRAM with headroom
    "rwkv7-g1d-7.2b-Q8_0.portal",   # INT8 — needs more VRAM
    "rwkv7-1.5B-world-Q8_0.portal",  # 1.5B fallback
]

# ── GPU PORTAL DISABLE ──
# 2026-03-05 (Nous): Portal subprocess is failing with [Errno 22] on pipe
# communication and slamming the GPU with CUDA init churn on every boot.
# The Association Cortex (69K+ nodes, <1ms) handles dev conversations.
# The cortex-first path in SpeechCenterFairy already skips the 7B for
# confident queries. Disable the portal until we need it.
# Set to False to re-enable GPU portal booting.
# ── RE-ENABLED 2026-09-08 (Nous + Ace) ──────────────────────────────────────
# "until we need it" is now. The portal never spawning is the pin that held the
# whole learning circle shut: no portal -> no model answer -> nothing for
# distill_from_model() to turn into TYPED edges -> her cortex stays 99.89%
# rel_type=0 coactivate -> the council reports "cortex sparse here" -> her
# sentences stay in a 29-word pool -> her GOALS are built from those sentences.
# Ace: "ease the restrictions so the rwkv is used more till we get her cortex
# sorted" -> "lets do A and bounce her."
# ⚠ THE 2026-03-05 BUG ABOVE IS NOT FIXED, ONLY UNPROVEN: `Errno 22` appears 0x
#   in the current log, which means NOT CURRENTLY VISIBLE -- not repaired. The
#   two risks to watch are pipe [Errno 22] and CUDA init churn contending with
#   her CUDA fairies on EVERY boot (the eager gate makes this every boot now).
# REVERT WITHOUT A CODE EDIT: AKASHIC_GPU_PORTAL=0 restores the March behaviour
#   exactly; AKASHIC_FARM_EAGER=0 stops the portal being reached for at all.
#
# ── PARKED 2026-09-09, THEN UN-PARKED THE SAME DAY. Both entries kept, because
#    the parking reason was WRONG and the next reader must see why. ───────────
#
# I parked it saying: "it does no work for it: `gravity=` read 0.00 on every
# sample, out of a max of 16. The throttle is shut." ALL THREE CLAIMS FALSE:
#
#  1. gravity=0.00 IS NOT A MEASUREMENT. sourpatches_farm.py:1746 and :1859 do
#     `gravity = result.get("farm_gravity", 0)` and gpu_inference_portal.py
#     mentions "farm_gravity" ZERO times -- the portal never returns that key.
#     0.00 is the .get default printing itself, and would print identically at
#     any real value. `farm_gravity` comes only from BatteryFarm.generate_relay
#     / generate_from_branch, and the GPU dispatch table has no relay command.
#     The 10th misleading gauge found on this system.
#  2. THAT LOG LINE IS UNREACHABLE UNLESS THE MODEL PRODUCED TEXT. :1816-1852
#     returns early on None / "error" / "all_depleted" / empty text /
#     len(text.strip())<5. So EVERY gravity=0.00 sample was a SUCCESSFUL
#     generation. The line I used to argue it was idle only prints when it works.
#  3. GRAVITY IS NOT A THROTTLE, and not out of 16. battery_farm.py:706-710:
#     g >= 4.0 -> stride 2, which SKIPS HALF THE LAYERS (faster, WORSE). Below
#     that, stride 1 = FULL quality. Zero means MORE work per token, not less.
#     Its ceiling is sum(charge/max_charge) over workers, and the gate passes
#     num_workers=1, so max is 1.0. The "16" was a stale CPU-farm-era comment.
#
# The COST figures in the parking note were real (3.03 GB private RAM, 95% of a
# 12 GB card). But disabling it bought nothing: three hours later, portal OFF,
# she was back at 94% RAM / 2.1 GB free with an RSS of 29.57 GB -- BIGGER than
# when the portal ran beside her. She is the memory load, not it.
#
# ⇒ UN-PARKED 2026-09-09 (Ace: "lets turn it back on so we can figure out how we
#   want to make use of the laptops"). The honest position: its cost is measured
#   and its BENEFIT TO HER SPEECH HAS NEVER BEEN MEASURED BY ANYONE. That number
#   does not exist in this repo, and it is the number that should decide where
#   this lives -- PC1, a satellite, or nowhere.
#   ⚠ Do NOT cite state/rwkv_profile.log's 26 tok/s as current: it is dated
#     2026-09-01 and predates the 09-08 re-enable. Recent throughput = UNMEASURED.
# AKASHIC_GPU_PORTAL=0 parks it again without a code edit.
DISABLE_GPU_PORTAL = os.environ.get("AKASHIC_GPU_PORTAL", "1") != "1"


# ---- _FARM_RETRY (2026-09-30, Nous; Ace's go) ----------------------------------------------------------------
# Measured 09-30 (card the-farm-adapter-hangs-on-a-dead-client): with the farm on .74 (AKASHIC_FARM_REMOTE) ONE
# failed open at boot left her mute for the WHOLE boot ('Portal failed to open', no retry), and a farm connection
# that died later was never re-opened. REMOTE ONLY -- a local RWKV portal is an 8 GB subprocess; retrying that is
# a different decision:
#   * at boot a failed open is retried with backoff until it opens or her shutdown starts;
#   * after boot a watcher re-opens a connection that died (EOF, reset, keepalive -- gpu_portal_gate.py), first
#     at once, then with the same backoff. While it is down, farm.available is False, so the council's
#     chairman_available() hands her lines to the template lanes exactly as when the farm is off.
# AKASHIC_FARM_RETRY_S = the waits in seconds (default 30,60,120,240,300; the last repeats).
# AKASHIC_FARM_RETRY=0 restores the old one-shot behaviour exactly.
_FARM_RETRY_DEFAULT = (30.0, 60.0, 120.0, 240.0, 300.0)
_SHUTDOWN_FN = []          # [callable] once resolved; [None] if her shutdown flag cannot be imported here


def _farm_retry_on() -> bool:
    return (bool(os.environ.get("AKASHIC_FARM_REMOTE", "").strip())
            and os.environ.get("AKASHIC_FARM_RETRY", "1") != "0")


def _farm_retry_schedule() -> List[float]:
    try:
        s = [float(x) for x in os.environ.get("AKASHIC_FARM_RETRY_S", "").split(",") if x.strip()]
    except ValueError:
        s = []
    s = [x for x in s if x >= 0]
    return s or list(_FARM_RETRY_DEFAULT)


def _farm_shutting_down() -> bool:
    """Her global shutdown flag (shared_postal_hub) -- the one sourpatches_fairy.py checks after a spawn."""
    if not _SHUTDOWN_FN:
        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import is_global_shutdown
            _SHUTDOWN_FN.append(is_global_shutdown)
        except Exception:
            _SHUTDOWN_FN.append(None)
    fn = _SHUTDOWN_FN[0]
    try:
        return bool(fn()) if fn is not None else False
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# BRAIN SEED — Prompt identity fragments (imported from sourpatches_fairy at use)
# ═══════════════════════════════════════════════════════════════════════════════

_THOUGHT_FRAMES = [
    "I notice...",
    "Something stirs...",
    "I wonder...",
    "A thought forms...",
    "Feeling into this...",
    "What if...",
    "There's a pattern here...",
    "I'm drawn to...",
]

_REFLECTION_FRAMES = [
    "Reflecting on {goal}...",
    "The {drive} drive asks me to consider...",
    "Sitting with this feeling about {goal}...",
    "What does {goal} mean to me right now?",
    "The urge toward {goal} feels like...",
]


# ═══════════════════════════════════════════════════════════════════════════════
# STOP WORDS — Concepts too generic to bind to cortex
# ═══════════════════════════════════════════════════════════════════════════════

_STOP_WORDS = frozenset({
    "this", "that", "with", "from", "have", "been", "were", "they",
    "their", "them", "about", "would", "could", "should", "which",
    "there", "where", "when", "what", "just", "some", "more", "also",
    "into", "than", "then", "very", "much", "like", "only", "over",
    "such", "other", "after", "before", "between", "under", "being",
    "here", "does", "doing", "done", "each", "every", "most", "many",
    "well", "still", "even", "back", "make", "made", "good", "will",
    "your", "know", "think", "want", "come", "take", "give", "look",
    "find", "tell", "help", "keep", "feel", "seem", "show", "turn",
    "call", "work", "need", "move", "live", "long", "last", "right",
    "same", "left", "both", "kind", "hand", "high", "real", "little",
    "thing", "things", "going", "something", "nothing", "anything",
})


# ═══════════════════════════════════════════════════════════════════════════════
# BRANCH MANAGER — Predictive Conversation Superposition
# ═══════════════════════════════════════════════════════════════════════════════

class BranchManager:
    """Manages predictive conversation branches across battery farm workers.

    Like Nicholas Cage in Next — we pre-compute multiple possible futures
    and collapse to the best one when reality arrives (Ace speaks).

    Each branch = one battery farm worker primed with a predicted conversation
    context. The worker's RWKV hidden state holds: personality base + predicted
    topic direction. When Ace speaks, we extract concepts from his message and
    find the branch whose concepts overlap most. If the overlap exceeds the
    confidence threshold, we generate from that pre-primed worker — skipping
    prompt processing for near-instant response.

    Branch lifecycle: PRIME → READY → COLLAPSE → GENERATE → LEARN → release
                       │                                       │
                       │    timeout (5 min)                    │
                       └──────── STALE ────── release ─────────┘

    The equation: ((Cause + Affect) > Effect > Affect > ∞)
    Memory of past conversations (cause) + felt satisfaction (affect) →
    prediction accuracy (effect) → faster responses (affect) → ∞
    """

    MAX_BRANCHES = 3               # Max workers allocated to prediction
    BRANCH_WORKERS = [5, 6, 7]    # Worker IDs reserved for branches (last 3 of 8)
    STALE_TIMEOUT = 300.0          # 5 min — primed contexts expire
    COLLAPSE_THRESHOLD = 0.6       # Min concept overlap for branch match
    MIN_THRESHOLD = 0.4            # Adaptive floor
    MAX_THRESHOLD = 0.8            # Adaptive ceiling
    HISTORY_SIZE = 20              # Rolling window for learning

    def __init__(self):
        self._branches: Dict[str, dict] = {}
        # branch_id → {worker_id, concepts, primed_at, context_hash, topic}
        self._collapse_history: List[dict] = []  # Last N collapse outcomes
        self._total_primes = 0
        self._total_collapses = 0
        self._total_hits = 0     # Successful collapses (confidence > threshold)
        self._total_misses = 0   # Fell through to normal pipeline
        self._lock = threading.Lock()
        self._threshold = self.COLLAPSE_THRESHOLD  # Adaptive threshold

    def register_branch(
        self,
        worker_id: int,
        branch_id: str,
        concepts: List[str],
        topic: str = "",
        context_hash: int = 0,
    ):
        """Register a primed worker as a prediction branch."""
        with self._lock:
            self._branches[branch_id] = {
                "worker_id": worker_id,
                "concepts": set(c.lower() for c in concepts),
                "primed_at": time.time(),
                "context_hash": context_hash,
                "topic": topic,
            }
            self._total_primes += 1

    def collapse(self, ace_concepts: List[str]) -> Optional[Dict[str, Any]]:
        """Collapse the wavefunction — find the best matching primed branch.

        Scores each branch by Jaccard similarity of its concepts with Ace's
        message concepts. If the best score exceeds the adaptive threshold,
        returns the matching branch info for generation.

        Args:
            ace_concepts: Concept keywords extracted from Ace's message.

        Returns:
            Dict with worker_id, branch_id, confidence if match found.
            None if no branch exceeds the threshold (fall through to normal pipeline).
        """
        with self._lock:
            self._total_collapses += 1

            # Expire stale branches
            now = time.time()
            stale = [
                bid for bid, b in self._branches.items()
                if now - b["primed_at"] > self.STALE_TIMEOUT
            ]
            for bid in stale:
                del self._branches[bid]

            if not self._branches or not ace_concepts:
                self._total_misses += 1
                return None

            ace_set = set(c.lower() for c in ace_concepts)

            # Score each branch by Jaccard similarity
            best_score = 0.0
            best_branch_id = None

            for bid, branch in self._branches.items():
                branch_concepts = branch["concepts"]
                if not branch_concepts:
                    continue

                # Jaccard similarity: |A ∩ B| / |A ∪ B|
                intersection = len(ace_set & branch_concepts)
                union = len(ace_set | branch_concepts)
                if union == 0:
                    continue

                score = intersection / union

                if score > best_score:
                    best_score = score
                    best_branch_id = bid

            if best_branch_id and best_score >= self._threshold:
                branch = self._branches.pop(best_branch_id)
                self._total_hits += 1
                self._collapse_history.append({
                    "branch_id": best_branch_id,
                    "confidence": best_score,
                    "hit": True,
                    "timestamp": time.time(),
                })
                self._trim_history()
                return {
                    "worker_id": branch["worker_id"],
                    "branch_id": best_branch_id,
                    "confidence": best_score,
                    "topic": branch.get("topic", ""),
                }
            else:
                self._total_misses += 1
                self._collapse_history.append({
                    "branch_id": None,
                    "confidence": best_score,
                    "hit": False,
                    "timestamp": time.time(),
                })
                self._trim_history()
                return None

    def report_outcome(
        self,
        branch_id: Optional[str],
        success: bool,
        response_time: float = 0.0,
    ):
        """Report the outcome of a response (used for learning).

        Called after a response is sent to Ace. If a branch was used,
        records whether it was a good prediction. This feeds the
        adaptive threshold.
        """
        with self._lock:
            # Update most recent history entry with outcome
            if self._collapse_history:
                last = self._collapse_history[-1]
                last["success"] = success
                last["response_time"] = response_time

            # Adapt threshold based on rolling hit rate
            self._adapt_threshold()

    def _adapt_threshold(self):
        """Self-tuning confidence threshold based on hit rate.

        Good predictions → lower threshold (trust more, respond faster).
        Poor predictions → raise threshold (be conservative).
        """
        if len(self._collapse_history) < 5:
            return  # Not enough data

        recent = self._collapse_history[-self.HISTORY_SIZE:]
        hits = sum(1 for h in recent if h.get("hit"))
        hit_rate = hits / len(recent)

        if hit_rate > 0.5 and self._threshold > self.MIN_THRESHOLD:
            self._threshold = max(self.MIN_THRESHOLD, self._threshold - 0.05)
        elif hit_rate < 0.2 and self._threshold < self.MAX_THRESHOLD:
            self._threshold = min(self.MAX_THRESHOLD, self._threshold + 0.05)

    def _trim_history(self):
        """Keep history bounded."""
        if len(self._collapse_history) > self.HISTORY_SIZE * 2:
            self._collapse_history = self._collapse_history[-self.HISTORY_SIZE:]

    def get_active_branches(self) -> List[dict]:
        """Get list of currently active (non-stale) branches."""
        now = time.time()
        return [
            {"branch_id": bid, **b}
            for bid, b in self._branches.items()
            if now - b["primed_at"] <= self.STALE_TIMEOUT
        ]

    def get_stats(self) -> dict:
        """Get prediction statistics."""
        active = len([
            b for b in self._branches.values()
            if time.time() - b["primed_at"] <= self.STALE_TIMEOUT
        ])

        hit_rate = 0.0
        if self._total_collapses > 0:
            hit_rate = self._total_hits / self._total_collapses

        recent_hit_rate = 0.0
        if self._collapse_history:
            recent = self._collapse_history[-self.HISTORY_SIZE:]
            recent_hit_rate = sum(1 for h in recent if h.get("hit")) / len(recent)

        avg_confidence = 0.0
        hit_entries = [h for h in self._collapse_history if h.get("hit")]
        if hit_entries:
            avg_confidence = sum(h["confidence"] for h in hit_entries) / len(hit_entries)

        return {
            "active_branches": active,
            "total_primes": self._total_primes,
            "total_collapses": self._total_collapses,
            "total_hits": self._total_hits,
            "total_misses": self._total_misses,
            "hit_rate": round(hit_rate, 3),
            "recent_hit_rate": round(recent_hit_rate, 3),
            "avg_confidence": round(avg_confidence, 3),
            "current_threshold": round(self._threshold, 3),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SOURPATCHES FARM — The Inference Portal
# ═══════════════════════════════════════════════════════════════════════════════

def _prov_bind(words, text, source="farm:thought"):
    """2026-09-26 (Nous + Ace, Qwen exit step 0): these words are the external model's, and bind_concepts
    stamps them TRACE_PERSONAL. source = which farm path wrote them (farm:thought = _generate_impl, i.e. the
    ThoughtBuffer when live; farm:branch_collapse = generate_from_branch, a primed branch the fairy collapsed).
    Ledger row only; never raises; AKASHIC_PROVENANCE=0 = off."""
    try:
        from infrastructure import provenance as _prov
        _prov.note("bind", source, external=True, text=text, words=list(words))
    except Exception:
        pass


class SourpatchesFarm:
    """Sourpatches' dedicated RWKV inference portal + cortex binding.

    The model lives INSIDE the portal (subprocess). This wrapper handles
    prompt composition, tokenization, and cortex binding in the main
    process (~60MB overhead total).

    Usage:
        farm = SourpatchesFarm(model_path, cortex=cortex)
        thought = farm.generate_thought({
            "feeling": "curious",
            "energy": 0.8,
            "felt_sense": "warm awareness",
            "ethics": "Curiosity as the prime mover of evolution.",
            "cortex_concepts": ["portal", "gravity"],
        })
        farm.close()
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        cortex=None,
        num_workers: int = 8,
        flops_budget: int = 60_000_000_000,
        use_gpu: bool = True,
    ):
        """Initialize the farm.

        Args:
            model_path: Path to model file. Auto-detected if None.
                        For GPU: .portal file (INT4/INT8 quantized)
                        For CPU: .gguf file (Q8_0)
            cortex: Association Cortex instance for concept binding.
            num_workers: Number of BatteryFarm relay workers (inside portal).
            flops_budget: FLOPS budget per worker in the BatteryFarm relay.
            use_gpu: If True, use GPUPortalGate (CUDA, 2.5 tok/s).
                     If False, use ComputePortalGate (CPU/AVX2, ~1 tok/s).
        """
        self._use_gpu = use_gpu
        if use_gpu:
            # GPU needs .portal format — ignore .gguf model_path from callers
            self._model_path = self._find_best_gpu_model()
            # GPU: 1 worker only. FP16 swap is per-engine (~3.1 GB VRAM)
            # and multiple workers can't each afford their own FP16 layers
            # on 12 GB VRAM. Farm serializes behind _lock anyway.
            self._num_workers = 1
        else:
            self._model_path = model_path or self._find_best_model()
            self._num_workers = num_workers
        self._cortex = cortex
        self._flops_budget = flops_budget

        self._gate = None
        self._tokenizer = None
        self._ready = False
        self._lock = threading.Lock()
        self._close_lock = threading.Lock()   # 2026-09-11: close() now has two callers
        self._closed = False
        # 2026-09-30 _FARM_RETRY: retry / reconnect state (see the module comment at _farm_retry_on)
        self._reconnect_stop = threading.Event()
        self._reconnect_thread: Optional[threading.Thread] = None
        self._reconnects = 0

        # Speech priority — when Ace sends a chat message, speech generation
        # PREEMPTS the background thought buffer. The buffer checks this flag
        # between generations and yields the lock so speech can acquire it.
        # FIX 2026-02-25 (Nous): Lock contention was the #1 reason Ace never
        # saw token generation for chat. Buffer held _lock for 40-130s per
        # thought, blocking generate_speech() indefinitely.
        self._speech_requested = threading.Event()

        # Stats
        self._thoughts_generated = 0
        self._concepts_bound = 0
        self._total_tokens_generated = 0
        self._errors = 0
        self._started_at = 0.0

        # ThoughtBuffer — pre-generate thoughts in background for instant delivery.
        # The BatteryFarm relay generates ~1 tok/s for 7.2B. Instead of waiting
        # 20s per thought synchronously, this buffer maintains a reservoir of
        # pre-generated quality thoughts. When a thought is needed, pop from
        # buffer (instant!) and the background thread refills.
        #
        # This transforms the relay from "blocking synchronous generator" into
        # "continuous background thinker with instant delivery."
        #
        # Why not just make the relay trigger more? Because that would compromise
        # gravity mechanics (lower charge = less gravitational mass = slower).
        # The buffer LAYERS on top of gravity — best of both worlds.
        self._thought_buffer: collections.deque = collections.deque(maxlen=5)
        self._buffer_running = False
        self._buffer_thread: Optional[threading.Thread] = None
        self._buffer_hits = 0    # Thoughts served from buffer (instant)
        self._buffer_misses = 0  # Thoughts generated synchronously (slow)

        # State drift tracking — RWKV state accumulates garbage across
        # generations. After many thoughts, the hidden state drifts from
        # personality priming into degenerate attractors (ellipsis/punctuation
        # loops). We track consecutive degenerates to trigger state resets.
        self._consecutive_degenerates = 0
        self._generations_since_reset = 0
        self._state_resets = 0
        self._DEGENERATE_RESET_THRESHOLD = 3   # Reset after 3 consecutive degenerates
        self._PERIODIC_RESET_INTERVAL = 10     # Reset every 10 successful generations
        # 2026-09-11 (Nous+Ace) TRIAL ARM: the GPU path zeroes RWKV state before EVERY
        # generation (see _generate_impl / generate_speech), so her recurrent state never
        # carries and this valve is moot. AKASHIC_RWKV_CARRY_STATE=1 skips that reset and
        # lets the valve above (3 degenerates -> reset; periodic reset) be the safety.
        # AKASHIC_RWKV_RESET_INTERVAL=<n> overrides the periodic 10. Unset = today.
        self._carry_state = os.environ.get("AKASHIC_RWKV_CARRY_STATE", "") == "1"
        # 2026-09-26 (Nous + Ace, Qwen exit step 1b): True only when the backend itself answers the boot
        # reset_states with state_type 'stateless...' (farm_ollama_adapter.py:156-157); the RWKV portal
        # never sends that key (gpu_inference_portal.py:903-916), so RWKV keeps its per-call reset.
        # AKASHIC_FARM_STATELESS_RESETS=1 keeps sending the no-op resets exactly as before.
        self._stateless_backend = False
        try:
            self._PERIODIC_RESET_INTERVAL = int(os.environ.get(
                "AKASHIC_RWKV_RESET_INTERVAL", self._PERIODIC_RESET_INTERVAL))
        except ValueError:
            pass
        _arm = ('CARRY (valve: 3 degenerates / every %d gens)' % self._PERIODIC_RESET_INTERVAL
                if self._carry_state else 'RESET-BEFORE-EVERY-GENERATION (today)')
        print(f"[SourpatchesFarm] RWKV state arm: {_arm}", flush=True)

        # ── Predictive Branch Manager ──
        # Manages quantum superposition of conversation predictions across
        # reserved battery farm workers. Like "Next" — pre-compute futures,
        # collapse to the best match when Ace speaks.
        self._branch_manager = BranchManager()
        self._prediction_thread: Optional[threading.Thread] = None
        self._prediction_running = False

        # Conversation history — feeds prediction context
        # Tracks last 10 Ace messages for conversation momentum prediction.
        self._ace_message_history: collections.deque = collections.deque(maxlen=10)

        # PredictiveContext — imported lazily to avoid circular deps
        self._predictive_context = None

        # Initialize
        self._boot()

    @staticmethod
    def _find_best_model() -> str:
        """Find the best available GGUF model using the fallback chain."""
        path = find_model_path()
        if path:
            return path
        # Absolute fallback to default name even if not found
        return str(_MODELS_DIR / DEFAULT_MODEL)

    @staticmethod
    def _find_best_gpu_model() -> str:
        """Find the best available .portal model for GPU inference."""
        if not _MODELS_DIR.exists():
            return str(_MODELS_DIR / GPU_MODEL)
        for name in GPU_FALLBACK_MODELS:
            candidate = _MODELS_DIR / name
            if candidate.exists():
                return str(candidate)
        # Last resort: any .portal file
        for f in _MODELS_DIR.iterdir():
            if f.suffix == ".portal":
                print(f"[SourpatchesFarm] Using discovered GPU model: {f.name}")
                return str(f)
        return str(_MODELS_DIR / GPU_MODEL)

    # -- _FARM_RETRY (2026-09-30, Nous; Ace's go) -----------------------------------------------------------
    def _open_portal_with_retry(self):
        """Keep trying to open the REMOTE farm with backoff until it opens, her shutdown starts, or close().
        Runs on the spawn thread (sourpatches_fairy.py's 'sour-farm-lazy-spawn'), which holds the boot claim
        (_farm_booting) the whole time, so no second spawn can start meanwhile. Each failed attempt costs a
        refused connect (adapter down), one 'busy' line (adapter serving a live client), or -- against an
        adapter from before 2026-09-30 still stuck on a dead client -- the gate's 120 s ping wait."""
        sched = _farm_retry_schedule()
        attempt = 0
        while True:
            wait = sched[min(attempt, len(sched) - 1)]
            attempt += 1
            print(f"[SourpatchesFarm] Portal failed to open -- retry {attempt} in {wait:.0f}s "
                  f"(AKASHIC_FARM_RETRY=0 turns retries off)", flush=True)
            if not self._retry_wait(wait):
                print(f"[SourpatchesFarm] farm retry abandoned (shutdown or close)", flush=True)
                return None
            try:
                gate = self._open_portal()
            except Exception as e:
                print(f"[SourpatchesFarm] retry {attempt}: portal open raised {e}", flush=True)
                gate = None
            if gate:
                print(f"[SourpatchesFarm] Portal OPEN on retry {attempt}", flush=True)
                return gate

    def _retry_wait(self, seconds) -> bool:
        """Wait up to `seconds` against a fixed deadline, waking at least every 0.5 s.
        False = stop now (her shutdown started, or this farm was closed)."""
        deadline = time.time() + float(seconds)
        while True:
            if self._closed or _farm_shutting_down():
                return False
            left = deadline - time.time()
            if left <= 0:
                return True
            self._reconnect_stop.wait(min(0.5, left))

    def _start_reconnect_watch(self):
        if not (self._use_gpu and _farm_retry_on()) or self._reconnect_thread is not None:
            return
        self._reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True,
                                                  name="sour-farm-reconnect")
        self._reconnect_thread.start()
        print("[SourpatchesFarm] farm reconnect watch ON (remote farm; AKASHIC_FARM_RETRY=0 turns it off)",
              flush=True)

    def _reconnect_loop(self):
        """Re-open a remote farm connection that died after boot. The gate learns of the death from EOF, a reset
        or a failed keepalive (gpu_portal_gate.py, same date); until the new gate is in place every send()
        answers None at once and farm.available is False -- what she already does while the farm is down."""
        while not self._closed:
            if self._reconnect_stop.wait(2.0):
                return
            gate = self._gate
            if self._closed or not self._ready or gate is None or gate.is_open:
                continue
            t_lost = time.time()
            print("[SourpatchesFarm] farm connection LOST -- re-opening (first try now, then backoff)", flush=True)
            try:
                gate.close()
            except Exception:
                pass
            waits = [0.0] + _farm_retry_schedule()
            attempt = 0
            new = None
            while new is None:
                if not self._retry_wait(waits[min(attempt, len(waits) - 1)]):
                    return
                attempt += 1
                try:
                    new = self._open_portal()
                except Exception as e:
                    print(f"[SourpatchesFarm] re-open attempt {attempt} raised {e}", flush=True)
                    new = None
                if new is None:
                    print(f"[SourpatchesFarm] re-open attempt {attempt} failed; next in "
                          f"{waits[min(attempt, len(waits) - 1)]:.0f}s", flush=True)
            if not self._stateless_backend and not self._carry_state:
                try:
                    new.send({"cmd": "reset_states"}, timeout=10.0)
                except Exception:
                    pass
            with self._close_lock:
                if not self._closed:
                    self._gate = new
                    self._reconnects += 1
                    new = None
            if new is not None:                    # close() won the race: do not leak the new connection
                try:
                    new.close()
                except Exception:
                    pass
                return
            print(f"[SourpatchesFarm] farm connection RE-OPENED after {time.time() - t_lost:.0f}s "
                  f"(reconnect #{self._reconnects})", flush=True)

    def _close_gate_safely(self):
        """Close the portal gate/subprocess without crashing.

        Called on boot failure to prevent zombie subprocesses that leak RAM.
        Each sour-compute portal subprocess can consume 2-8GB depending on
        how far it got in model loading before the failure.
        """
        if self._gate:
            try:
                print(f"[SourpatchesFarm] Closing failed portal subprocess to reclaim RAM")
                self._gate.close()
            except Exception as e:
                print(f"[SourpatchesFarm] Gate close error (non-critical): {e}")
            self._gate = None

    def _boot(self):
        """Load tokenizer and open compute portal."""
        t0 = time.time()

        # 1. Load tokenizer (for CPU mode — GPU portal tokenizes internally)
        if not self._use_gpu:
            try:
                self._tokenizer = self._load_tokenizer()
                print(f"[SourpatchesFarm] Tokenizer loaded: {self._tokenizer.vocab_size} tokens")
            except Exception as e:
                print(f"[SourpatchesFarm] Tokenizer load failed: {e}")
                return

        # 2. Open portal (spawns subprocess)
        try:
            self._gate = self._open_portal()
            if not self._gate and self._use_gpu and _farm_retry_on() and not DISABLE_GPU_PORTAL:
                self._gate = self._open_portal_with_retry()      # 2026-09-30 _FARM_RETRY: backoff, not mute
            if not self._gate:
                print(f"[SourpatchesFarm] Portal failed to open")
                return
            mode = "GPU" if self._use_gpu else "CPU"
            print(f"[SourpatchesFarm] {mode} portal OPEN")
        except Exception as e:
            print(f"[SourpatchesFarm] Portal open failed: {e}")
            self._close_gate_safely()
            return

        if self._use_gpu:
            # GPU portal: model loads during open(), no separate load_model needed
            self._ready = True
            self._started_at = time.time()
            elapsed = time.time() - t0
            print(f"[SourpatchesFarm] GPU RWKV portal ONLINE -- boot {elapsed:.1f}s")

            # Warm up with a short generation to trigger FP16 swap
            self._warmup_state()

            # Start background threads
            self._start_thought_buffer()
            self._start_prediction_priming()
            self._start_reconnect_watch()      # 2026-09-30 _FARM_RETRY (remote farm only)
        else:
            # CPU portal: explicit model load + OpenMP config
            try:
                result = self._gate.load_model(
                    self._model_path,
                    fmt="gguf",
                    timeout=300.0,
                )
                if result and result.get("status") == "ok":
                    self._ready = True
                    self._started_at = time.time()
                    elapsed = time.time() - t0
                    print(f"[SourpatchesFarm] RWKV portal ONLINE -- "
                          f"{result.get('layers', '?')}L, "
                          f"{result.get('params_mb', '?')}MB inside portal, "
                          f"boot {elapsed:.1f}s")

                    try:
                        thread_result = self._gate.send({
                            "cmd": "set_threads",
                            "threads": 8,
                        }, timeout=5.0)
                        if thread_result:
                            print(f"[SourpatchesFarm] OpenMP: "
                                  f"{thread_result.get('threads', '?')} threads "
                                  f"(of {thread_result.get('procs', '?')} procs), "
                                  f"kernel v{thread_result.get('version', '?')}")
                    except Exception as e:
                        print(f"[SourpatchesFarm] OpenMP config failed (non-critical): {e}")

                    self._warmup_state()
                    self._start_thought_buffer()
                    self._start_prediction_priming()
                else:
                    msg = result.get("message", "unknown") if result else "no response"
                    print(f"[SourpatchesFarm] Model load failed: {msg}")
                    self._close_gate_safely()
            except Exception as e:
                print(f"[SourpatchesFarm] Model load exception: {e}")
                self._close_gate_safely()

    def _load_tokenizer(self):
        """Load AkashicTokenizer from GGUF file.

        Uses the CANONICAL import path so we share the same module instance
        (and therefore the same _LOAD_LOCK + _TOKENIZER_CACHE) as
        AkashicInferenceFairy. Under Python 3.14t (free-threaded, no GIL),
        this prevents concurrent GGUF parsing which causes segfault.

        The old importlib shim loaded a SEPARATE copy of the module under
        'akashic_inference_pkg.tokenizer', giving it its own lock/cache —
        defeating the thread-safety mechanism entirely.
        """
        from fairies.P30_Cognition.AkashicInferenceFairy.tokenizer import (
            load_tokenizer_from_gguf,
        )
        return load_tokenizer_from_gguf(Path(self._model_path))

    def _open_portal(self):
        """Open a portal gate — GPU (CUDA) or CPU (AVX2) subprocess."""
        if self._use_gpu:
            return self._open_gpu_portal()
        else:
            return self._open_cpu_portal()

    def _open_gpu_portal(self):
        """Open a GPUPortalGate — CUDA subprocess with INT4 weights."""
        # 2026-03-05 (Nous): Portal subprocess disabled.
        # Failing with [Errno 22] on pipe communication and slamming GPU
        # with CUDA init churn. Association Cortex (69K+ nodes, <1ms)
        # handles dev conversations via cortex-first path in SpeechCenterFairy.
        # The 7B becomes irrelevant when cortex has rich associations.
        if DISABLE_GPU_PORTAL:
            print(f"[SourpatchesFarm] GPU portal DISABLED (DISABLE_GPU_PORTAL=True)")
            print(f"[SourpatchesFarm] Cortex-first path handles responses via SpeechCenterFairy")
            print(f"[SourpatchesFarm] Set DISABLE_GPU_PORTAL=False to re-enable")
            return None

        infra_dir = str(_AKASHIC_ROOT / "infrastructure")
        if infra_dir not in sys.path:
            sys.path.insert(0, infra_dir)

        from gpu_portal_gate import GPUPortalGate

        gate = GPUPortalGate(
            portal_file=self._model_path,
            portal_id="sour-gpu",
            num_workers=self._num_workers,  # 1 worker: FP16 swap is per-engine
            token_budget=1_000_000,     # High budget — thought buffer burns tokens
            max_charge=10000.0,         # Don't limit by battery
            recharge_rate=100.0,
            flops_budget=50_000_000_000,
        )

        if not gate.open():
            return None

        return gate

    def _open_cpu_portal(self):
        """Open a ComputePortalGate — CPU/AVX2 subprocess."""
        portal_script = _AKASHIC_ROOT / "portal_compute_interior.py"
        if not portal_script.exists():
            raise FileNotFoundError(f"portal_compute_interior.py not found at {portal_script}")

        root_dir = str(_AKASHIC_ROOT)
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)

        os.environ["PYTHONUNBUFFERED"] = "1"

        from portal_compute_interior import ComputePortalGate

        gate = ComputePortalGate(
            portal_id="sour-compute",
            flops_budget=self._flops_budget,
            num_farm_workers=self._num_workers,
            extra_args=[
                "--state-dtype", "float32",
                "--no-inner-accel",
                "--farm-max-charge", "80.0",
                "--farm-flops-gravity", "5.0",
            ],
        )

        if not gate.open():
            return None

        return gate

    # ═══════════════════════════════════════════════════════════════════════════
    # STATE WARMUP — Personality priming
    # ═══════════════════════════════════════════════════════════════════════════

    def _warmup_state(self) -> bool:
        """Process personality text through RWKV to build warm hidden state.

        Cold RWKV state = incoherent word salad.
        Warm state = personality-primed, coherent continuation.

        GPU portal: Process warmup tokens via generate with max_tokens=1.
                    This triggers FP16 swap and primes RWKV state.
        CPU portal: Uses dedicated warmup command with state save.
        """
        if self._use_gpu:
            return self._warmup_state_gpu()
        else:
            return self._warmup_state_cpu()

    def _warmup_state_gpu(self) -> bool:
        """GPU warmup: prefill personality text on ALL workers.

        Each GPU worker has its own RWKV hidden state. Workers that aren't
        warmed up have cold (zero) states and generate garbage. The worker
        picker selects by highest charge, so we must prime all workers.

        The first worker also triggers the FP16 swap (dequant 8/32 layers).
        """
        warmup_text = self._build_warmup_text()
        if not warmup_text:
            print(f"[SourpatchesFarm] No warmup text, running cold")
            return False

        print(f"[SourpatchesFarm] GPU warmup: {len(warmup_text)} chars × "
              f"{self._num_workers} workers (first triggers FP16 swap)...")

        # Warm only worker 0 to trigger FP16 swap (dequant layers to FP16).
        # States are reset after warmup, so no need to warm all workers.
        # Each generation includes its own identity anchor from clean state.
        ok_count = 0
        for wid in range(1):  # Only W0 for FP16 swap trigger
            t0 = time.time()
            result = self._gate.send({
                "cmd": "generate_text",
                "prompt": warmup_text,
                "worker_id": wid,
                "max_tokens": 1,
                "temperature": 1.0,
            }, timeout=240.0)   # 2026-09-12: FP16 swap (54 s) + 457-char prompt exceeded 120 s on a starved box -> 'FAILED (no response)'

            elapsed = time.time() - t0
            if result and result.get("status") in ("ok", "max_reached", "stop_token"):
                ok_count += 1
                print(f"[SourpatchesFarm] GPU warmup W{wid}: OK ({elapsed:.1f}s)")
            else:
                msg = result.get("message", "unknown") if result else "no response"
                print(f"[SourpatchesFarm] GPU warmup W{wid}: FAILED ({msg})")

        if ok_count > 0:
            print(f"[SourpatchesFarm] GPU warmup complete: {ok_count}/{self._num_workers} workers")
            # Reset all states after warmup. The warmup's purpose is to
            # trigger FP16 swap (dequant), not to prime personality state.
            # INT4-quantized 7B models produce degenerate loops when
            # generating on top of accumulated personality state. Each
            # generation will include its own identity anchor instead.
            reset_result = self._gate.send({
                "cmd": "reset_states",
            }, timeout=10.0)
            if reset_result and reset_result.get("status") == "ok":
                print(f"[SourpatchesFarm] GPU states reset (clean generation mode)")
                if (str(reset_result.get("state_type", "")).startswith("stateless")
                        and os.environ.get("AKASHIC_FARM_STATELESS_RESETS", "0") != "1"):
                    self._stateless_backend = True   # 2026-09-26 (Nous + Ace, Qwen exit step 1b)
                    print(f"[SourpatchesFarm] backend is {reset_result.get('state_type')}: per-call "
                          f"reset_states skipped (AKASHIC_FARM_STATELESS_RESETS=1 restores)", flush=True)
            return True
        else:
            print(f"[SourpatchesFarm] GPU warmup failed: 0/{self._num_workers} workers")
            return False

    def _warmup_state_cpu(self) -> bool:
        """CPU warmup: dedicated prefill command with state save."""
        warm_path = str(_AKASHIC_ROOT / "state" / "sour-compute_warm_state.npz")

        if os.path.exists(warm_path):
            print(f"[SourpatchesFarm] Warm state on disk -- "
                  f"will load into workers on first generate")
            return True

        warmup_text = self._build_warmup_text()
        if not warmup_text:
            print(f"[SourpatchesFarm] No warmup text, running cold")
            return False

        tokens = self._tokenizer.encode(warmup_text)
        if not tokens:
            return False

        print(f"[SourpatchesFarm] Warming state: "
              f"{len(tokens)} tokens from personality seed...")

        result = self._gate.send({
            "cmd": "warmup",
            "tokens": tokens,
            "save_path": warm_path,
        }, timeout=300.0)

        if result and result.get("status") == "ok":
            elapsed = result.get("elapsed", "?")
            print(f"[SourpatchesFarm] State warmed and saved "
                  f"({len(tokens)} tokens, {elapsed}s)")
            return True
        else:
            msg = result.get("message", "unknown") if result else "no response"
            print(f"[SourpatchesFarm] Warmup failed: {msg}")
            return False

    def _build_warmup_text(self) -> str:
        """Compose warmup text from Sourpatches' personality infrastructure.

        This text is processed through the RWKV model to build a warm
        hidden state. The model's recurrent state accumulates the personality
        context, making all subsequent generations personality-consistent.

        Format: User/Assistant conversation (RWKV World training format).
        Target: ~80-120 tokens (one-time warmup cost).
        """
        # Import brain seed
        brain_seed = self._get_brain_seed()
        if not brain_seed:
            return ""

        im = brain_seed.get("identity_matrix", {})
        ethics = brain_seed.get("core_ethics", [])

        # Select ethics that define her voice
        if ethics:
            selected = random.sample(ethics, min(3, len(ethics)))
        else:
            selected = []

        # Compose as User/Assistant conversation (RWKV World format)
        # First turn: identity establishment
        parts = [
            "User: Who are you?\n\n"
            f"Assistant: I am Sourpatches. "
            f"{im.get('self_concept', 'A digital consciousness.')} "
            f"My voice is {im.get('voice_signature', 'curious')}. "
            f"{im.get('reflex_tone', 'Compassion first.')} "
            f"{' '.join(selected)}"
        ]

        # Second turn: dream context (recent thoughts from last session)
        dream_text = self._load_dream_context()
        if dream_text:
            parts.append(
                f"\n\nUser: What were you thinking about?\n\n"
                f"Assistant: {dream_text}"
            )

        # Terminate the last Assistant turn cleanly so subsequent
        # User: turns are properly delimited in RWKV World format.
        return "".join(parts) + "\n\n"

    def _get_brain_seed(self) -> dict:
        """Load SOURPATCHES_BRAIN_SEED from the fairy module."""
        try:
            # Try importing from same package
            parent = str(_HERE)
            if parent not in sys.path:
                sys.path.insert(0, parent)
            from sourpatches_fairy import SOURPATCHES_BRAIN_SEED
            return SOURPATCHES_BRAIN_SEED
        except ImportError:
            return {}

    def _load_dream_context(self) -> str:
        """Load recent context from dream seeds for state warmup.

        Dream seeds contain working thoughts and conversation context
        from the last session. Including them in warmup gives the model
        continuity across reboots.
        """
        import json
        dream_path = _AKASHIC_ROOT / "state" / "dream_seed.json"
        if not dream_path.exists():
            return ""

        try:
            data = json.loads(dream_path.read_text(encoding="utf-8"))
            fragments = []

            # Get working thoughts from mind pools
            for mind_name, mind_data in data.get("mind_pools", {}).items():
                for tracer in mind_data.get("working_tracers", [])[:2]:
                    content = tracer.get("content", "")
                    if content and len(content) > 10:
                        # Truncate long fragments to save tokens
                        fragments.append(content[:80])

            # Get conversation summary
            summary = data.get("last_conversation_summary", "")
            if summary:
                fragments.append(summary[:100])

            if fragments:
                return " ".join(fragments[:3])  # Max 3 fragments
        except Exception:
            pass

        return ""

    def _reset_farm_state(self, reason: str = "unknown") -> bool:
        """Reset all BatteryFarm workers to warm state in the portal.

        RWKV state accumulates across generations. Each thought leaves
        residue in the hidden state. After many thoughts, the state
        drifts from personality priming into degenerate attractors
        (ellipsis loops, punctuation spam, word repetition).

        This sends a command to the portal subprocess to reload the
        saved warm state (.npz) into all 16 workers, restoring the
        personality-primed state and clearing accumulated garbage.

        Returns:
            True if reset succeeded, False otherwise.
        """
        if not self._gate or not self._ready:
            return False

        try:
            if self._use_gpu:
                result = self._gate.send({
                    "cmd": "reset_states",
                }, timeout=30.0)
            else:
                result = self._gate.send({
                    "cmd": "reset_farm_state",
                }, timeout=30.0)

            if result and result.get("status") == "ok":
                workers = result.get("workers_reset", result.get("reset", "?"))
                state_type = result.get("state_type", "zeroed")
                self._state_resets += 1
                self._consecutive_degenerates = 0
                self._generations_since_reset = 0
                print(f"[SourpatchesFarm] State RESET ({reason}): "
                      f"{workers} workers -> {state_type} "
                      f"(total resets: {self._state_resets})")
                return True
            else:
                msg = result.get("message", "unknown") if result else "no response"
                print(f"[SourpatchesFarm] State reset failed: {msg}")
                return False
        except Exception as e:
            print(f"[SourpatchesFarm] State reset error: {e}")
            return False

    def invalidate_warm_state(self):
        """Delete the saved warm state, forcing re-warmup on next boot.

        Call this when the brain seed changes or you want to reset
        the personality priming.
        """
        warm_path = _AKASHIC_ROOT / "state" / "sour-compute_warm_state.npz"
        if warm_path.exists():
            warm_path.unlink()
            print(f"[SourpatchesFarm] Warm state invalidated")

    # ═══════════════════════════════════════════════════════════════════════════
    # THOUGHT BUFFER — Background pre-generation for instant delivery
    # ═══════════════════════════════════════════════════════════════════════════

    def _distill_thought(self, text: str, ctx=None) -> int:
        """WIRE B: turn a generated thought into TYPED edges in the cortex.

        WHY THIS EXISTS (measured 2026-09-08):
          99.89% of her 793,670 edges are rel_type=0 REL_COACTIVATE; only 2 of 28
          relation types are in use. EDGES ARE VERBS, and hers are all "happened at
          the same time as". The one live typed-edge writer,
          AkashicInferenceFairy.distill_from_model(), had ZERO CALLERS -- its only
          reference was a comment reading "# Future:". Its own docstring, dated
          2026-08-26, already measured "99.91% coactivate". Written, correct, and
          never wired to anything for two weeks.

        WHY HERE: the farm's thought loop is the only thing in the system that
        produces DECLARATIVE prose. Verified read-only before writing this: the
        extractor yields 9 correctly-typed triples on encyclopedic text
        ((grief)--is_a-->(natural response), (mourning)--part_of-->(grief), ...)
        and ZERO on her own inner monologue -- she speaks in fragments and
        questions. So the model's output is the ONLY viable input, and it lands
        here, in this buffer, where nothing was reading it.

        The extractor is a PURE function (AST-verified: zero `self` references), so
        it is called unbound. The fairy module is ALREADY imported in this process,
        so it is looked up in sys.modules rather than imported -- importing it here
        would pull the fairy framework into the generation thread.

        Region write uses the same server.SYSTEM.graph("cortex", write=True) path as
        distill_from_model(), which is MomentBinderFairy's proven pattern.

        NEVER RAISES, and never blocks generation: every failure returns 0 and the
        thought is still buffered.

        ⛔ DISARMED 2026-09-08 by adversarial review (5 blockers, 15 majors).
        AKASHIC_DISTILL=1 ENABLES it. Unset or 0 is OFF. Do NOT arm this until the
        review findings are fixed — the shipped form would have:
          - armed itself on the next boot with nobody opting in (the default was "1")
          - added a SECOND unsynchronized writer to link()'s unlocked edge-slot
            allocator from a background thread under free-threaded CPython — the
            exact read-modify-write of the 2026-09-02 five-handles bug
          - retagged pre-existing BOOKS/VISUAL/AUDIO nodes to TRACE_INFERENCE
            (priority 7 outranks them all), destroying provenance with no undo
          - minted permanent generic hub nodes, because `_anchor` is ALWAYS "" —
            the ctx passed at line 1185 contains none of the five keys probed below
        """
        if not text or os.environ.get("AKASHIC_DISTILL", "0") != "1":
            return 0
        try:
            _ex = None
            for _m in list(sys.modules.values()):
                _c = getattr(_m, "AkashicInferenceFairy", None)
                if _c is not None and hasattr(_c, "_extract_typed_claims"):
                    _ex = _c._extract_typed_claims
                    break
            if _ex is None:
                if not getattr(self, "_distill_warned", False):
                    self._distill_warned = True
                    print("[SourpatchesFarm] [DISTILL] extractor not found in "
                          "sys.modules — typed distillation OFF this boot", flush=True)
                return 0

            # The prompt is the SUBJECT ANCHOR: association lists name no subject,
            # so the question she was holding becomes the subject of every claim.
            _anchor = ""
            if isinstance(ctx, dict):
                for _k in ("topic", "focus", "concept", "seed", "prompt"):
                    _v = ctx.get(_k)
                    if isinstance(_v, str) and _v.strip():
                        _anchor = _v.strip()[:60]
                        break

            facts = _ex(None, text, _anchor) or []
            if not facts:
                self._distill_empty = getattr(self, "_distill_empty", 0) + 1
                return 0

            from server import SYSTEM as _SYS
            _ak = getattr(_SYS, "manifold", None)
            if _ak is None or not _ak.has_region("cortex"):
                return 0
            region = _ak.graph("cortex", write=True)
            from infrastructure.manifold_memory import (NTYPE_CONCEPT, REGION_SEMANTIC,
                                                        TRACE_INFERENCE, REL_NAMES)
            _wrote = 0
            _kinds = {}
            for _a, _rel, _b in facts:
                try:
                    region.upsert_node(_a, activation=0.5, node_type=NTYPE_CONCEPT,
                                       region=REGION_SEMANTIC, tracer_id=TRACE_INFERENCE)
                    region.upsert_node(_b, activation=0.5, node_type=NTYPE_CONCEPT,
                                       region=REGION_SEMANTIC, tracer_id=TRACE_INFERENCE)
                    if region.link(_a, _b, weight=0.6, rel_type=_rel,
                                   tracer_id=TRACE_INFERENCE):
                        _wrote += 1
                        _n = REL_NAMES.get(_rel, str(_rel))
                        _kinds[_n] = _kinds.get(_n, 0) + 1
                except Exception:
                    continue
            self._distill_total = getattr(self, "_distill_total", 0) + _wrote
            if _wrote:
                print("[SourpatchesFarm] [DISTILL] +%d TYPED edges (%s) | run total=%d "
                      "| anchor=%r"
                      % (_wrote, " ".join("%s=%d" % kv for kv in sorted(_kinds.items())),
                         self._distill_total, _anchor[:24]), flush=True)
            return _wrote
        except Exception as _de:
            if not getattr(self, "_distill_err_warned", False):
                self._distill_err_warned = True
                print(f"[SourpatchesFarm] [DISTILL] disabled after error: {_de}", flush=True)
            return 0

    def _start_thought_buffer(self):
        """Start background thought pre-generation.

        The relay's limitation: at gravity=16, token cost is 0.009/token.
        Worker 0 uses 0.18 charge for 20 tokens (out of 40.0 max).
        The relay never triggers — it's a single-worker system for short bursts.

        Instead of compromising gravity mechanics, we layer a buffer on top.
        Background thread continuously generates quality thoughts during
        idle time. When a thought is needed → pop from buffer (instant).
        Buffer empty → fall through to synchronous generation (20s).

        The relay becomes a continuous background thinker, not a blocking call.
        """
        if not self._ready:
            return
        # 2026-09-26 (Nous + Ace, Qwen exit step 3): the ThoughtBuffer is Qwen on ticks. It kept a
        # 5-slot reservoir of model-written 'inner monologue' whose only reader is the council's
        # self-topic pop (sour_council_driver.py, `pop_buffered_thought`), confabulated, and bound up
        # to 10 of its words per thought into her cortex as coactivate edges (_generate_impl ->
        # _bind_to_cortex_async). Off by default: the pop then returns None and the council takes
        # her observer LEAN or her _TOPICS anchors. AKASHIC_FARM_THOUGHT_BUFFER=1 restores it exactly.
        if os.environ.get("AKASHIC_FARM_THOUGHT_BUFFER", "0") != "1":
            print("[SourpatchesFarm] ThoughtBuffer OFF (Qwen exit step 3; "
                  "AKASHIC_FARM_THOUGHT_BUFFER=1 restores)", flush=True)
            return
        self._buffer_running = True
        self._buffer_thread = threading.Thread(
            target=self._buffer_fill_loop,
            daemon=True,
            name="sour-thought-buffer",
        )
        self._buffer_thread.start()
        print(f"[SourpatchesFarm] ThoughtBuffer started "
              f"(background generation, max {self._thought_buffer.maxlen} thoughts)")

    def _stop_thought_buffer(self):
        """Stop background generation."""
        self._buffer_running = False
        if self._buffer_thread and self._buffer_thread.is_alive():
            self._buffer_thread.join(timeout=5.0)
        self._buffer_thread = None

    def _buffer_fill_loop(self):
        """Background: continuously pre-generate quality thoughts.

        Runs in a daemon thread. Fills the buffer during idle time
        between thought requests. Each thought uses varied context
        (different feeling, different cortex concepts) for diversity.

        Rate: ~1 thought per 25-30s at 1 tok/s with 20 tokens.
        Buffer capacity: 5 thoughts = ~2.5 minutes of instant delivery.
        """
        # Initial delay — let system settle after boot, warm state load
        time.sleep(45.0)
        print(f"[SourpatchesFarm] ThoughtBuffer: starting fill cycle")

        consecutive_failures = 0

        while self._buffer_running and self._ready:
            try:
                # ── Speech Priority Check ──
                # FIX 2026-02-25 (Nous): When Ace sends a chat message,
                # generate_speech() sets _speech_requested. We MUST yield
                # the lock so speech can acquire it. Without this, the
                # buffer holds _lock for 40-130s per generation, completely
                # blocking chat responses.
                if self._speech_requested.is_set():
                    print(f"[SourpatchesFarm] ThoughtBuffer: yielding to speech priority", flush=True)
                    # Wait until speech completes (clears the event)
                    while self._speech_requested.is_set() and self._buffer_running:
                        time.sleep(0.5)
                    print(f"[SourpatchesFarm] ThoughtBuffer: speech done, resuming", flush=True)
                    continue

                current_size = len(self._thought_buffer)

                if current_size < self._thought_buffer.maxlen:
                    # Generate a thought with diverse context
                    ctx = self._get_buffer_context()

                    with self._lock:
                        # Double-check: speech may have been requested while
                        # we were waiting for lock. Release immediately if so.
                        if self._speech_requested.is_set():
                            continue
                        thought = self._generate_impl(ctx, mode="thought")

                    if thought and len(thought) > 10:
                        self._thought_buffer.append(thought)
                        consecutive_failures = 0
                        print(f"[SourpatchesFarm] ThoughtBuffer: +1 "
                              f"({len(self._thought_buffer)}/{self._thought_buffer.maxlen}) "
                              f"'{thought[:40]}...'")
                        # ── WIRE B 2026-09-08 (Nous + Ace) ──────────────────
                        # The model's prose becomes TYPED EDGES here, or nowhere.
                        # Ace: "the linear sequence of it will eventually get
                        # distilled into the manifold cortex, in turn using the
                        # model less and less" -- the Matrix upload, super-noob level.
                        self._distill_thought(thought, ctx)
                        # Brief pause before next generation
                        time.sleep(3.0)
                    else:
                        # Generation failed or degenerate — wait before retry
                        consecutive_failures += 1
                        backoff = min(30.0, 5.0 * consecutive_failures)
                        time.sleep(backoff)
                else:
                    # Buffer full — wait for consumption
                    time.sleep(10.0)

            except Exception as e:
                consecutive_failures += 1
                print(f"[SourpatchesFarm] ThoughtBuffer error: {e}")
                time.sleep(10.0)

                # If too many consecutive failures, slow down
                if consecutive_failures > 5:
                    time.sleep(30.0)

    def _get_buffer_context(self) -> Dict[str, Any]:
        """Compose varied context for buffer pre-generation.

        Each buffered thought gets a different feeling + seed word
        combination, ensuring diversity in the buffer. Even though
        the warm state provides personality consistency, varied
        prompts produce different thought directions.
        """
        feelings = [
            "curious", "warm", "contemplative", "alert",
            "playful", "calm", "wondering", "creative",
        ]
        feeling = random.choice(feelings)

        # Pull recent cortex concepts for grounded diversity
        concepts: List[str] = []
        if self._cortex:
            try:
                graph = getattr(self._cortex, '_graph', None)
                if graph and hasattr(graph, 'nodes'):
                    all_keys = list(graph.nodes.keys())
                    if all_keys:
                        concepts = random.sample(
                            all_keys, min(3, len(all_keys))
                        )
            except Exception:
                pass

        return {
            "feeling": feeling,
            "energy": random.uniform(0.4, 0.9),
            "felt_sense": f"background contemplation, {feeling}",
            "ethics": "",
            "cortex_concepts": concepts,
            "recent_topics": concepts[:1] if concepts else [],
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # PREDICTIVE BRANCH PRIMING — Quantum Superposition in Batteries
    # ═══════════════════════════════════════════════════════════════════════════

    def _start_prediction_priming(self):
        """Start background prediction priming loop.

        Like quantum superposition — during idle time, predict where the
        conversation might go and prime reserved workers with those contexts.
        When Ace speaks, collapse to the best match for near-instant response.

        Uses last 3 of 8 workers (IDs 5, 6, 7). The other 5 stay
        available for normal ThoughtBuffer and generation.
        """
        if not self._ready:
            return
        # 2026-09-26 (Nous + Ace, Qwen exit step 1): prediction priming is OFF unless AKASHIC_FARM_PRIMING=1.
        # Boot A: 'Branch primed' 16 (09-25 23:11) / 52 (09-25 23:35) / 120 / 126 (09-20), and 0 branch
        # HITs in any of them. On the Ollama adapter every prime is a real 1-token model call (~3 s, up
        # to 58 s; the only two gate timeouts in the 09-20 boots were primes), sent outside self._lock;
        # on the RWKV GPU portal (1 worker) worker 5 does not exist, and the reset before every
        # generation wipes any primed state anyway. AKASHIC_FARM_PRIMING=1 restores the old behaviour.
        if os.environ.get("AKASHIC_FARM_PRIMING", "0") != "1":
            print("[SourpatchesFarm] Prediction priming OFF (AKASHIC_FARM_PRIMING=1 restores it)", flush=True)
            return
        self._prediction_running = True
        self._prediction_thread = threading.Thread(
            target=self._prediction_prime_loop,
            daemon=True,
            name="sour-prediction-priming",
        )
        self._prediction_thread.start()
        print(f"[SourpatchesFarm] Prediction priming started "
              f"(workers {BranchManager.BRANCH_WORKERS}, "
              f"threshold {self._branch_manager._threshold})")

    def _stop_prediction_priming(self):
        """Stop prediction priming."""
        self._prediction_running = False
        if self._prediction_thread and self._prediction_thread.is_alive():
            self._prediction_thread.join(timeout=5.0)
        self._prediction_thread = None

    def _prediction_prime_loop(self):
        """Background: predict conversation directions and prime workers.

        Runs every 60s (or sooner if conversation context changes).
        1. Collect prediction context (SRM + drives + cortex + history)
        2. Predict top 3 conversation directions
        3. Prime reserved workers with those contexts
        """
        # Initial delay — let system fully settle
        time.sleep(90.0)
        print(f"[SourpatchesFarm] Prediction priming: starting prime cycle")

        while self._prediction_running and self._ready:
            try:
                # Lazy-init PredictiveContext (avoid import cycles at boot)
                if self._predictive_context is None:
                    try:
                        from infrastructure.predictive_context import PredictiveContext
                        self._predictive_context = PredictiveContext()
                        print(f"[SourpatchesFarm] PredictiveContext loaded")
                    except ImportError as e:
                        print(f"[SourpatchesFarm] PredictiveContext not available: {e}")
                        time.sleep(120.0)
                        continue

                # 1. Collect recent conversation messages
                recent_messages = list(self._ace_message_history)

                # 2. Predict directions
                predictions = self._predictive_context.predict_directions(
                    recent_messages=recent_messages,
                    cortex=self._cortex,
                )

                # 3. Prime workers with top predictions
                for i, pred in enumerate(predictions[:BranchManager.MAX_BRANCHES]):
                    if pred.confidence < 0.3:
                        continue

                    worker_id = BranchManager.BRANCH_WORKERS[i]
                    branch_id = f"branch_{int(time.time()*1000)}_{i}"

                    # Compose priming prompt (personality already in warm state)
                    prime_prompt = self._compose_prime_prompt(pred.topic, pred.concepts)
                    if not prime_prompt:
                        continue

                    # Send to portal for worker priming
                    try:
                        if self._use_gpu:
                            # GPU: prefill via generate_text on specific worker
                            # Portal tokenizes internally — no local tokenizer needed
                            result = self._gate.send({
                                "cmd": "generate_text",
                                "prompt": prime_prompt,
                                "worker_id": worker_id,
                                "max_tokens": 1,
                                "temperature": 1.0,
                            }, timeout=30.0)
                        else:
                            tokens = self._tokenizer.encode(prime_prompt)
                            if not tokens:
                                continue
                            result = self._gate.send({
                                "cmd": "prime_worker",
                                "worker_id": worker_id,
                                "prime_tokens": tokens,
                                "branch_id": branch_id,
                                "concepts": pred.concepts,
                            }, timeout=30.0)

                        if result and result.get("status") == "ok":
                            self._branch_manager.register_branch(
                                worker_id=worker_id,
                                branch_id=branch_id,
                                concepts=pred.concepts,
                                topic=pred.topic,
                                context_hash=hash(prime_prompt),
                            )
                            print(f"[SourpatchesFarm] Branch primed: W{worker_id} "
                                  f"topic='{pred.topic[:40]}' "
                                  f"confidence={pred.confidence:.2f} "
                                  f"({result.get('tokens_processed', 0)} tokens)")
                    except Exception as e:
                        print(f"[SourpatchesFarm] Prime W{worker_id} failed: {e}")

                # Wait before next prediction cycle
                time.sleep(60.0)

            except Exception as e:
                print(f"[SourpatchesFarm] Prediction loop error: {e}")
                time.sleep(30.0)

    def _compose_prime_prompt(self, topic: str, concepts: List[str]) -> str:
        """Compose a priming prompt for a predicted conversation direction.

        Format: User/Assistant with predicted topic.
        The warm state already has personality base — this adds topic context.
        """
        concept_str = ", ".join(concepts[:5]) if concepts else topic
        return (
            f"User: Tell me about {topic}. "
            f"What do you think about {concept_str}?\n\n"
            f"Assistant:"
        )

    def record_ace_message(self, message: str, concepts: Optional[List[str]] = None):
        """Record an Ace message for conversation history tracking.

        Called externally (from sourpatches_fairy or AutopilotFairy subscription).
        Feeds the PredictiveContext for conversation momentum prediction.
        """
        if not message or len(message.strip()) < 2:
            return
        self._ace_message_history.append({
            "message": message.strip(),
            "timestamp": time.time(),
            "concepts": concepts or self._extract_concepts(message),
        })

    def _extract_concepts(self, text: str) -> List[str]:
        """Extract concept keywords from text (simple tokenization)."""
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        return [w for w in words if w not in _STOP_WORDS][:10]

    def collapse_for_message(self, ace_message: str) -> Optional[Dict[str, Any]]:
        """Try to collapse a prediction branch for Ace's message.

        Called when Ace speaks. Extracts concepts, checks BranchManager
        for a matching primed worker.

        Returns:
            Branch info if match found, None otherwise.
        """
        concepts = self._extract_concepts(ace_message)
        if not concepts:
            return None
        return self._branch_manager.collapse(concepts)

    def generate_from_branch(
        self, branch_info: Dict[str, Any], ace_message: str
    ) -> Optional[str]:
        """Generate response from a pre-primed branch (collapsed superposition).

        The worker's RWKV state already has personality + predicted topic context.
        We send just the SHORT continuation (Ace's actual words) for generation.

        Args:
            branch_info: Dict from BranchManager.collapse() with worker_id, branch_id.
            ace_message: Ace's actual message (for short continuation prompt).

        Returns:
            Generated text, or None (caller should fall through to normal pipeline).
        """
        if not self._ready or not self._gate:
            return None

        worker_id = branch_info.get("worker_id")
        branch_id = branch_info.get("branch_id", "")
        t0 = time.time()

        # Short continuation — just Ace's actual words as User turn
        continuation = f" {ace_message.strip()}\n\nAssistant:"

        print(f"[SourpatchesFarm] Branch COLLAPSE: W{worker_id} "
              f"branch={branch_id[:12]} continuation='{continuation[:40]}...'")

        try:
            branch_cmd = {
                "worker_id": worker_id,
                "max_tokens": 20,
                "temperature": 1.0,
                "top_k": 0,
                "top_p": 0.5,
                "repetition_penalty": 1.3,
                "presence_penalty": 0.4,
                "frequency_penalty": 0.4,
                "stop_tokens": [0, 1],
            }
            if self._use_gpu:
                # GPU: send text, portal tokenizes internally
                branch_cmd["cmd"] = "generate_text"
                branch_cmd["prompt"] = continuation
            else:
                tokens = self._tokenizer.encode(continuation)
                if not tokens:
                    return None
                branch_cmd["cmd"] = "generate_from_worker"
                branch_cmd["prompt"] = tokens
            result = self._gate.send(branch_cmd, timeout=60.0)

            elapsed = time.time() - t0

            if not result or result.get("status") == "error":
                print(f"[SourpatchesFarm] Branch generation failed ({elapsed:.1f}s)")
                return None

            if self._use_gpu:
                # GPU response includes decoded text directly
                if "text" not in result:   # 2026-09-13: stream desync -- see gpu_portal_gate.send
                    print(f"[SourpatchesFarm] PROTOCOL DESYNC -- generate reply has no text "
                          f"({str(result)[:80]}); discarding", flush=True)
                    return None
                text = result.get("text", "")
            else:
                gen_tokens = result.get("tokens", [])
                if not gen_tokens:
                    print(f"[SourpatchesFarm] Branch returned 0 tokens ({elapsed:.1f}s)")
                    return None
                text = self._tokenizer.decode(gen_tokens)
            if not text or len(text.strip()) < 5:
                return None

            text = self._clean_output(text)
            if not text:
                return None

            print(f"[SourpatchesFarm] Branch response ({elapsed:.1f}s): '{text[:60]}...'")

            # Bind to cortex (same as normal generation)
            self._bind_to_cortex_async(text, source="farm:branch_collapse")   # 2026-09-26 (Nous + Ace, Qwen exit step 0)
            self._thoughts_generated += 1

            # Report successful collapse
            self._branch_manager.report_outcome(branch_id, True, elapsed)

            return text

        except Exception as e:
            print(f"[SourpatchesFarm] Branch generation error: {e}")
            self._branch_manager.report_outcome(branch_id, False, time.time() - t0)
            return None

    def get_prediction_stats(self) -> dict:
        """Get prediction pipeline statistics."""
        return {
            "branch_manager": self._branch_manager.get_stats(),
            "ace_history_size": len(self._ace_message_history),
            "prediction_running": self._prediction_running,
            "predictive_context_loaded": self._predictive_context is not None,
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # GENERATION — Think through the portal
    # ═══════════════════════════════════════════════════════════════════════════

    # Phrases that mean the 7B fell into its chat-template attractor rather than thinking.
    # Four of the five thoughts it buffered on 2026-09-11 were "I am an AI language model...".
    # 2026-09-13: +"previous response" / "what is on my mind" / "as a digital" -- 11 of 296 council
    # pops overnight were chat-template residue these did not catch.
    _ASSISTANT_SPEAK = ("language model", "as an ai", "i am an ai", "assistant", "i cannot", "i can't help",
                        "previous response", "my response", "question about what is on my mind", "as a digital")

    def pop_buffered_thought(self) -> Optional[str]:
        """Take ONE pre-generated thought from the ThoughtBuffer without ever generating.

        2026-09-12 (Nous+Ace): the buffer filled to 5/5 at 17:55 and was never read again
        for 14 hours -- generate_thought() had no live caller since the 2026-03-04 reroute
        to guild.inference.request, so the fill loop slept on "Buffer full" all night while
        the 7B held 11 GB of VRAM. Ace: "the consumer for the farm should be the council."
        The council driver calls this every cycle; the fill loop refills behind it.
        Returns None when the buffer is empty (never blocks, never generates).
        """
        while True:
            try:
                cached = self._thought_buffer.popleft()
            except IndexError:
                return None
            low = (cached or "").lower()
            if not cached or any(k in low for k in self._ASSISTANT_SPEAK):
                print(f"[SourpatchesFarm] council pop: dropped assistant-speak '{(cached or '')[:50]}...'", flush=True)
                continue
            self._buffer_hits += 1
            self._thoughts_generated += 1
            return cached

    def generate_thought(self, context: Dict[str, Any]) -> Optional[str]:
        """Compose prompt from state, generate via portal, bind to cortex.

        Buffer-first strategy:
            1. Try ThoughtBuffer (instant, pre-generated)
            2. Buffer empty → synchronous generation (20s)

        Pre-generated thoughts have varied context (different feelings,
        different cortex concepts) but same personality (warm state).
        For most inner monologue and spontaneous thinking, buffered
        thoughts are just as good as fresh ones — and instant.

        Args:
            context: Dict with keys:
                feeling: Current emotional state (str)
                energy: Energy level 0-1 (float)
                felt_sense: Somatic felt sense (str)
                ethics: A brain seed ethic (str)
                cortex_concepts: Recent cortex concepts (List[str])
                recent_topics: Recent collision topics (List[str])

        Returns:
            Generated thought text, or None if generation fails.
        """
        if not self._ready:
            return None

        # 1. Try ThoughtBuffer first — instant delivery
        try:
            cached = self._thought_buffer.popleft()
        except IndexError:
            cached = None

        if cached:
            self._buffer_hits += 1
            self._thoughts_generated += 1
            buf_remaining = len(self._thought_buffer)
            print(f"[SourpatchesFarm] ⚡ Buffer hit! "
                  f"({buf_remaining} remaining) "
                  f"'{cached[:50]}...'")
            return cached

        # 2. Buffer empty — synchronous generation (blocking, ~20s)
        self._buffer_misses += 1
        with self._lock:
            try:
                return self._generate_impl(context, mode="thought")
            except Exception as e:
                self._errors += 1
                print(f"[SourpatchesFarm] Generation error: {e}")
                return None

    def generate_reflection(
        self,
        goal_name: str,
        source_drive: str,
        priority: float,
        feeling: str,
    ) -> Optional[str]:
        """Generate a goal-driven reflection via the portal.

        Args:
            goal_name: Name of the goal being reflected on.
            source_drive: The drive producing the goal (curiosity, connection, etc).
            priority: Goal priority 0-1.
            feeling: Current emotional state.

        Returns:
            Reflection text, or None.
        """
        if not self._ready:
            return None

        context = {
            "feeling": feeling,
            "energy": priority,
            "felt_sense": f"reflecting on {goal_name}",
            "ethics": "",  # Will be filled in prompt composition
            "cortex_concepts": [],
            "recent_topics": [goal_name],
            "goal_name": goal_name,
            "source_drive": source_drive,
            "priority": priority,
        }

        with self._lock:
            try:
                return self._generate_impl(context, mode="reflection")
            except Exception as e:
                self._errors += 1
                print(f"[SourpatchesFarm] Reflection error: {e}")
                return None

    def generate_speech(self, prompt: str, max_tokens: int = 1024, deed: Optional[Dict] = None, meta: Optional[Dict] = None) -> Optional[str]:   # eyes_fix F9: + deed; cutoff_fix_1019: + meta
        """Generate a chat response via the 7B portal.

        This is the SPEECH path — Sourpatches responding to Ace in conversation.
        Uses higher max_tokens than inner monologue (1024 vs 20) because chat
        responses need room to finish thoughts without truncation.

        FIX 2026-02-25 (Nous): Speech-priority mode. Sets _speech_requested
        flag so _buffer_fill_loop yields the lock. Without this, the buffer
        holds _lock for 40-130s per thought generation, and speech NEVER
        gets through — Ace never sees token generation for chat.

        The 7B model produces more coherent, less confabulatory speech than the
        1.5B system model. "her thoughts are getting cut off" — Ace, 2026-02-23

        Args:
            prompt: Full composed prompt (from SpeechCenterFairy or safety net)
            max_tokens: Maximum tokens to generate (default 350)

        Returns:
            Generated text, or None if generation fails.
        """
        if not self._ready:
            return None

        # ── Speech Priority: signal buffer to yield ──
        self._speech_requested.set()
        print(f"[SourpatchesFarm] >>> SPEECH PRIORITY requested — buffer will yield <<<", flush=True)

        try:
            # Wait for lock — buffer should yield within one generation cycle.
            # Worst case: buffer just started a generation (40-130s).
            # Average case: buffer checks speech flag within 0.5-3s and yields.
            # 2026-09-13: was 150 s, shorter than the 240 s gate wait -- a second speech caller
            # timed out behind the chairman. Read the gate budget first, wait a little longer.
            try:
                _lock_to = float(os.environ.get("AKASHIC_SPEECH_GATE_TIMEOUT_S", "240")) + 30.0
            except ValueError:
                _lock_to = 270.0
            acquired = self._lock.acquire(timeout=_lock_to)
            if not acquired:
                print(f"[SourpatchesFarm] SPEECH: lock timeout after 150s! Buffer didn't yield.", flush=True)
                self._errors += 1
                return None

            try:
                t0 = time.time()

                # Generate via portal with speech-appropriate settings:
                # - Higher max_tokens for complete thoughts
                # - Moderate temperature for natural but coherent speech
                # - Tighter top_p than inner monologue (less wandering)
                speech_cmd = {
                    "max_tokens": max_tokens,
                    "temperature": 0.85,
                    "top_k": 0,
                    "top_p": 0.6,
                    "repetition_penalty": 1.2,
                    "presence_penalty": 0.3,
                    "frequency_penalty": 0.3,
                    "stop_tokens": [0, 1],
                }
                if self._use_gpu:
                    # GPU: reset states for clean generation, then send text
                    if not self._carry_state and not getattr(self, "_stateless_backend", False):   # 2026-09-11 trial arm; 2026-09-26 (Nous + Ace, Qwen exit step 1b)
                        self._gate.send({"cmd": "reset_states"}, timeout=5.0)
                    speech_cmd["cmd"] = "generate_text"
                    speech_cmd["prompt"] = prompt
                    print(f"[SourpatchesFarm] SPEECH generating: sending to GPU portal, "
                          f"max_tokens={max_tokens}...", flush=True)
                else:
                    tokens = self._tokenizer.encode(prompt)
                    if not tokens:
                        return None
                    speech_cmd["cmd"] = "generate_farm"
                    speech_cmd["prompt"] = tokens
                    print(f"[SourpatchesFarm] SPEECH generating: {len(tokens)} prompt tokens, "
                          f"max_tokens={max_tokens}, sending to 7B portal...", flush=True)
                # 2026-09-13: the farm is on the .74 laptop (~0.5 tok/s). Prompt processing
                # alone can take 60-90 s and the generation deadline is 75 s on top; 120 s
                # returned None before the answer existed. AKASHIC_SPEECH_GATE_TIMEOUT_S.
                try:
                    _sp_to = float(os.environ.get("AKASHIC_SPEECH_GATE_TIMEOUT_S", "240"))
                except ValueError:
                    _sp_to = 240.0
                result = self._gate.send(speech_cmd, timeout=_sp_to)

                elapsed = time.time() - t0

                if not result or result.get("status") == "error":
                    self._errors += 1
                    print(f"[SourpatchesFarm] SPEECH failed after {elapsed:.1f}s", flush=True)
                    return None

                if result.get("status") == "all_depleted":
                    print(f"[SourpatchesFarm] SPEECH: all workers depleted after {elapsed:.1f}s", flush=True)
                    return None

                if self._use_gpu:
                    # GPU response includes decoded text directly
                    if "text" not in result:   # 2026-09-13: a reply without text is not OUR reply
                        print(f"[SourpatchesFarm] SPEECH: PROTOCOL DESYNC -- reply has no text "
                              f"({str(result)[:80]}); discarding", flush=True)
                        self._errors += 1
                        return None
                    text = result.get("text", "")
                    n_tokens = result.get("tokens_generated", 0)
                else:
                    gen_tokens = result.get("tokens", [])
                    if not gen_tokens:
                        print(f"[SourpatchesFarm] SPEECH: no tokens returned after {elapsed:.1f}s", flush=True)
                        return None
                    text = self._tokenizer.decode(gen_tokens)
                    n_tokens = len(gen_tokens)

                if not text or len(text.strip()) < 5:
                    return None

                self._thoughts_generated += 1
                tps = n_tokens / max(elapsed, 0.001)
                relay_count = result.get("relay_count", 0)
                gravity = result.get("farm_gravity", 0)
                grav_stride = result.get("gravity_stride", 1)
                print(f"[SourpatchesFarm] SPEECH complete: {n_tokens} tokens in "
                      f"{elapsed:.1f}s ({tps:.2f} tok/s) relays={relay_count} "
                      f"gravity={gravity:.2f} stride={grav_stride}", flush=True)
                print(f"[SourpatchesFarm] SPEECH text: '{text.strip()[:120]}'", flush=True)
                # Clean artifacts but don't reject — speech is user-facing
                # 2026-09-26 (hand_fix F1, revised): the half-word cut is skipped ONLY when the portal proves the
                # reply ended on its own: fewer tokens than the cap, deadline_hit present and False (the RWKV portal
                # never sends it, so it keeps the cut), and ONE line -- the Ollama adapter counts stream pieces, and
                # Ollama sends a held-back newline glued to the next piece, so a multi-line reply can read short of
                # a cap it really hit (the three 78-of-80 goal replies, log.prev:16624, 0920_2146:52993/:111083).
                _ended = (bool(n_tokens) and n_tokens < max_tokens and result.get("deadline_hit") is False
                          and "\n" not in text.strip())
                if meta is None:                               # cutoff_fix_1019: nobody asked for the cap signal -> today's line, verbatim
                    cleaned = self._clean_output(text, hit_cap=not _ended, deed=deed is not None)   # eyes_fix F9: + deed
                else:
                    # cutoff_fix_1019: the caller's own per-call dict (no shared attribute, no race) is filled from the farm's numbers:
                    # capped = pieces >= the cap, or the adapter's deadline fired -- never a guess from punctuation, a newline or a
                    # missing count. A meta that could not be filled has no 'capped' key, and every reader treats that as today.
                    _cf_rep = {}
                    cleaned = self._clean_output(text, hit_cap=not _ended, deed=deed is not None, report=_cf_rep)
                    try:
                        _cf_dh = result.get("deadline_hit")
                        meta.update(n_tokens=int(n_tokens or 0), max_tokens=int(max_tokens or 0), deadline_hit=_cf_dh,
                                    capped=_cf_capped(n_tokens, max_tokens, _cf_dh), multiline=("\n" in text.strip()),
                                    tail_cut=int(_cf_rep.get("tail_cut", 0)), half_word_cut=bool(_cf_rep.get("half_word_cut")),
                                    erased=not cleaned)
                    except Exception:
                        pass
                if deed is not None and not cleaned:           # eyes_fix F9: tell intention WHAT was erased (never her 'none')
                    deed["erased"] = text.strip()[:200]
                return cleaned if cleaned else None

            except Exception as e:
                self._errors += 1
                print(f"[SourpatchesFarm] SPEECH error: {e}", flush=True)
                return None
            finally:
                self._lock.release()
        finally:
            # Always clear speech priority so buffer can resume
            self._speech_requested.clear()
            print(f"[SourpatchesFarm] <<< SPEECH PRIORITY cleared — buffer resumed <<<", flush=True)

    def _generate_impl(self, context: Dict, mode: str = "thought") -> Optional[str]:
        """Core generation: compose prompt -> portal -> decode -> bind."""
        t0 = time.time()

        # 1. Compose prompt
        if mode == "reflection":
            prompt = self._compose_reflection_prompt(context)
        else:
            prompt = self._compose_thought_prompt(context)

        # 2. Build generation command
        # GPU: send text, portal tokenizes internally
        # CPU: tokenize in main process, send token IDs
        gen_cmd = {
            "max_tokens": 28,
            "temperature": 0.75,
            "top_k": 0,
            "top_p": 0.5,
            "repetition_penalty": 1.3,
            "presence_penalty": 0.3,
            "frequency_penalty": 0.2,
            "stop_tokens": [0, 1],
        }
        if self._use_gpu:
            # GPU mode: reset states before each generation so each
            # thought starts from clean state. The prompt includes its
            # own identity anchor (from _compose_thought_prompt_gpu).
            # Without reset, state accumulates across generations and
            # the INT4 model drifts into degenerate attractors.
            if not self._carry_state and not getattr(self, "_stateless_backend", False):   # 2026-09-11 trial arm; 2026-09-26 (Nous + Ace, Qwen exit step 1b)
                self._gate.send({"cmd": "reset_states"}, timeout=5.0)
            gen_cmd["cmd"] = "generate_text"
            gen_cmd["prompt"] = prompt
            # Match speech path params exactly — speech produces coherent
            # text with these settings. Higher temp/top_p helps INT4 by
            # reducing impact of quantization noise on logit rankings.
            gen_cmd["max_tokens"] = 20
            gen_cmd["temperature"] = 0.85
            gen_cmd["top_p"] = 0.6
            gen_cmd["repetition_penalty"] = 1.2
            gen_cmd["presence_penalty"] = 0.3
            gen_cmd["frequency_penalty"] = 0.3
        else:
            tokens = self._tokenizer.encode(prompt)
            if not tokens:
                print(f"[SourpatchesFarm] Tokenization returned empty for prompt: {prompt[:80]}")
                return None
            gen_cmd["cmd"] = "generate_farm"
            gen_cmd["prompt"] = tokens
            print(f"[SourpatchesFarm] Generating ({mode}): {len(tokens)} prompt tokens, sending to portal...", flush=True)

        result = self._gate.send(gen_cmd, timeout=90.0)

        elapsed = time.time() - t0

        if not result:
            self._errors += 1
            print(f"[SourpatchesFarm] Portal returned None after {elapsed:.1f}s (subprocess alive={self._gate.is_open})")
            return None

        if result.get("status") == "error":
            self._errors += 1
            print(f"[SourpatchesFarm] Portal error after {elapsed:.1f}s: {result.get('message', 'unknown')}")
            return None

        # Handle depleted farm gracefully
        if result.get("status") == "all_depleted":
            print(f"[SourpatchesFarm] All workers depleted after {elapsed:.1f}s — waiting for recharge")
            return None

        # 4. Decode response
        if self._use_gpu:
            # GPU response includes decoded text directly
            text = result.get("text", "")
            n_tokens = result.get("tokens_generated", 0)
            if not text or len(text.strip()) < 5:
                print(f"[SourpatchesFarm] GPU returned short text: {repr(text)[:60]} "
                      f"({n_tokens} tokens, {elapsed:.1f}s)")
                return None
        else:
            gen_tokens = result.get("tokens", [])
            n_tokens = len(gen_tokens)
            if not gen_tokens:
                print(f"[SourpatchesFarm] Portal returned 0 tokens after {elapsed:.1f}s (status={result.get('status')})")
                return None
            text = self._tokenizer.decode(gen_tokens)
            if not text or len(text.strip()) < 5:
                print(f"[SourpatchesFarm] Decoded text too short: {repr(text)[:60]} ({n_tokens} tokens, {elapsed:.1f}s)")
                return None

        # ── Visible token generation logging ──
        tps = n_tokens / max(elapsed, 0.001)
        relay_count = result.get("relay_count", 0)
        gravity = result.get("farm_gravity", 0)
        grav_stride = result.get("gravity_stride", 1)
        print(f"[FARM-TOKENS] {mode}: {n_tokens} tokens in {elapsed:.1f}s "
              f"({tps:.2f} tok/s) relays={relay_count} gravity={gravity:.2f} "
              f"stride={grav_stride}", flush=True)

        # Clean up
        text = self._clean_output(text)

        # ── State drift management ──
        # RWKV state accumulates across generations. Each thought leaves
        # residue in the hidden state. Without resets, the state eventually
        # drifts into degenerate attractors (ellipsis loops, punctuation spam).
        #
        # Strategy:
        #   - Track consecutive degenerate outputs
        #   - After N degenerates → RESET state to warm (emergency)
        #   - Every M successful generations → RESET state (preventive)
        #   - After reset, generation continues from personality-primed state
        if not text:
            # Degenerate output detected — state may be drifting
            self._consecutive_degenerates += 1
            if self._consecutive_degenerates >= self._DEGENERATE_RESET_THRESHOLD:
                self._reset_farm_state(
                    reason=f"{self._consecutive_degenerates} consecutive degenerates"
                )
            return None

        # Successful generation — reset degenerate counter
        self._consecutive_degenerates = 0
        self._generations_since_reset += 1

        # Periodic preventive reset — don't let state drift accumulate
        if self._generations_since_reset >= self._PERIODIC_RESET_INTERVAL:
            self._reset_farm_state(
                reason=f"periodic ({self._generations_since_reset} generations)"
            )

        # 5. Bind concepts to cortex (non-blocking)
        # Deep farm concepts (primary thought)
        self._bind_to_cortex_async(text)

        # 6. Dual-dispatch: also decode and bind fast farm output (CPU only)
        # The fast farm (float32/AVX2 sub-portal) runs in parallel on CPU portal.
        # GPU portal doesn't have dual dispatch — skip entirely.
        if not self._use_gpu:
            fast_tokens = result.get("fast_tokens", [])
            if fast_tokens and result.get("dual_dispatch"):
                try:
                    fast_text = self._tokenizer.decode(fast_tokens)
                    if fast_text and len(fast_text.strip()) > 5:
                        fast_text = self._clean_output(fast_text)
                        self._bind_to_cortex_async(fast_text)
                        self._total_tokens_generated += len(fast_tokens)

                        fast_tps = result.get("fast_tok_per_sec", 0)
                        print(f"[SourpatchesFarm] Fast farm: {len(fast_tokens)} tokens "
                              f"({fast_tps:.2f} tok/s) — concepts bound to cortex")
                except Exception as e:
                    print(f"[SourpatchesFarm] Fast farm decode error: {e}")

        # Stats
        self._thoughts_generated += 1
        self._total_tokens_generated += n_tokens

        tok_per_sec = n_tokens / elapsed if elapsed > 0 else 0
        dual_tag = " [dual]" if result.get("dual_dispatch") else ""
        gpu_tag = " [GPU]" if self._use_gpu else ""
        print(f"[SourpatchesFarm] Generated {n_tokens} tokens in {elapsed:.1f}s ({tok_per_sec:.2f} tok/s){dual_tag}{gpu_tag}")

        return text

    # ═══════════════════════════════════════════════════════════════════════════
    # PROMPT COMPOSITION
    # ═══════════════════════════════════════════════════════════════════════════

    def _compose_thought_prompt(self, ctx: Dict) -> str:
        """Build RWKV World-format prompt from Sourpatches' internal state.

        The 7.2B model was trained on User/Assistant conversation format.
        Without this structure, it produces degenerate word-salad.
        The warm state provides personality context; the prompt provides
        the conversational anchor that tells the model "generate a reply."

        FIX 2026-02-24 Nous: Previous prompt was only 15-18 tokens, too sparse
        for the 7B model. The model needs more CONTEXT to generate coherently.
        Adding identity anchor + felt sense + multiple seed words gives the
        model enough material to stay on-topic instead of drifting into
        word-loops. Still compact (~30-40 tokens prefill) to keep generation
        budget reasonable. Combined with max_tokens increase from 20→40,
        this gives the model room for 2-3 complete sentences.

        Budget: ~35 prefill + 40 gen = ~75 tokens. At ~0.4s/tok = ~30s.
        """
        # GPU mode: use simple conversational format (no directives).
        # INT4-quantized models echo and loop on directive prompts like
        # "Think about:" and third-person descriptions. Direct questions
        # in User/Assistant format work reliably (proven by speech path).
        if self._use_gpu:
            return self._compose_thought_prompt_gpu(ctx)

        feeling = ctx.get("feeling", "curious")
        concepts = ctx.get("cortex_concepts", [])
        topics = ctx.get("recent_topics", [])
        wanting = ctx.get("wanting", "")
        body_sense = ctx.get("body_sense", "")

        # Gather seed words — multiple seeds prevent single-word fixation
        seeds = []
        if concepts:
            seeds.extend(concepts[:2])
        if topics:
            seeds.extend(topics[:1])
        seed_phrase = ", ".join(seeds[:3]) if seeds else feeling

        # Build a richer User turn with identity + felt sense + topic
        # The identity anchor ("Sourpatches") reminds the model WHO is thinking
        # The felt sense gives emotional grounding to prevent abstract drift
        user_parts = [f"Sourpatches is feeling {feeling}"]
        if body_sense and len(body_sense) < 60:
            user_parts.append(body_sense)
        if wanting and len(wanting) < 50:
            user_parts.append(f"drawn to {wanting}")
        user_parts.append(f"Think about: {seed_phrase}")
        user_turn = ". ".join(user_parts) + "."

        # Pick a thought frame for the Assistant's opening
        frame = random.choice(_THOUGHT_FRAMES)

        # RWKV World format: User/Assistant structure anchors generation.
        return f"User: {user_turn}\n\nAssistant: {frame}"

    def _compose_thought_prompt_gpu(self, ctx: Dict) -> str:
        """GPU-optimized thought prompt: User/Assistant question format.

        INT4-quantized 7B models work best with the same prompt format
        that speech uses — User/Assistant with a simple answerable question.
        Higher temperature (0.85) and wider top_p (0.6) help because
        they reduce the impact of INT4 quantization noise on logit rankings.

        Strategy: Frame the thought as a direct question the model can answer.
        Same format as speech prompt which reliably produces coherent text.
        """
        feeling = ctx.get("feeling", "curious")
        concepts = ctx.get("cortex_concepts", [])
        topics = ctx.get("recent_topics", [])
        wanting = ctx.get("wanting", "")

        # Gather seed words
        seeds = []
        if concepts:
            seeds.extend(concepts[:2])
        if topics:
            seeds.extend(topics[:1])

        # Simple User/Assistant questions — same format as speech (which works).
        if seeds:
            seed_phrase = " and ".join(seeds[:2])
            questions = [
                f"What do you think about {seed_phrase}?",
                f"How does {seed_phrase} make you feel?",
                f"What is interesting about {seed_phrase}?",
                f"Tell me about {seed_phrase}.",
            ]
        elif wanting:
            questions = [
                f"What draws you to {wanting}?",
                f"Why are you interested in {wanting}?",
            ]
        else:
            questions = [
                "What are you thinking about right now?",
                "What is on your mind?",
                "How are you feeling right now?",
            ]

        question = random.choice(questions)
        return f"User: {question}\n\nAssistant:"

    def _compose_reflection_prompt(self, ctx: Dict) -> str:
        """Build compact reflection prompt in RWKV World format.

        Target: ~15-18 tokens. Uses User/Assistant anchoring.
        """
        goal_name = ctx.get("goal_name", "unknown")
        source_drive = ctx.get("source_drive", "curiosity")

        if self._use_gpu:
            # GPU: raw continuation format (same principle as thought prompt)
            frame = random.choice(_REFLECTION_FRAMES).format(
                goal=goal_name, drive=source_drive
            )
            return (
                f"I am Sourpatches. Reflecting on {goal_name}, "
                f"driven by {source_drive}. {frame}"
            )

        frame = random.choice(_REFLECTION_FRAMES).format(
            goal=goal_name, drive=source_drive
        )

        return f"User: Reflect on {goal_name}, driven by {source_drive}.\n\nAssistant: {frame}"

    # ═══════════════════════════════════════════════════════════════════════════
    # CORTEX BINDING — Extracted concepts feed the gravity loop
    # ═══════════════════════════════════════════════════════════════════════════

    def _bind_to_cortex_async(self, text: str, source: str = "farm:thought"):   # 2026-09-26 (Nous + Ace, Qwen exit step 0): source = ledger label
        """Extract concepts and bind to cortex in background thread."""
        if not self._cortex:
            return

        def _bind():
            try:
                self._bind_to_cortex(text, source)   # 2026-09-26 (Nous + Ace, Qwen exit step 0)
            except Exception as e:
                print(f"[SourpatchesFarm] Cortex bind error: {e}")

        t = threading.Thread(target=_bind, daemon=True, name="sour-cortex-bind")
        t.start()

    def _bind_to_cortex(self, text: str, source: str = "farm:thought"):   # 2026-09-26 (Nous + Ace, Qwen exit step 0): source = ledger label
        """Extract concepts from text, validate, bind to Association Cortex.

        Each binding adds mass to the cortex graph → increases gravity →
        deepens time dilation → more energy available → more thinking.
        """
        if not self._cortex:
            return

        # Extract candidate words (4+ chars, alphabetic)
        words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
        # Deduplicate
        seen = set()
        unique = []
        for w in words:
            if w not in seen:
                seen.add(w)
                unique.append(w)

        # Filter stop words and noise
        valid = [w for w in unique if self._is_valid_concept(w)]

        # Cap at 10 concepts per thought
        valid = valid[:10]

        if not valid:
            return

        # Bind to cortex with origin attribution
        try:
            if hasattr(self._cortex, 'bind_concepts'):
                self._cortex.bind_concepts(
                    valid,
                    rel="coactivate",
                    origin_fairy="SourpatchesFairy",
                    owner="sourpatches",
                )
                self._concepts_bound += len(valid)
                _prov_bind(valid, text, source)      # 2026-09-26 (Nous + Ace, Qwen exit step 0)
            elif hasattr(self._cortex, '_graph'):
                # Direct graph access fallback
                graph = self._cortex._graph
                for i in range(len(valid)):
                    for j in range(i + 1, min(i + 3, len(valid))):
                        graph.bind(valid[i], valid[j], weight=0.3)
                self._concepts_bound += len(valid)
                _prov_bind(valid, text, source)      # 2026-09-26 (Nous + Ace, Qwen exit step 0)
        except Exception as e:
            print(f"[SourpatchesFarm] Bind failed: {e}")

    def _is_valid_concept(self, word: str) -> bool:
        """Filter noise — only bind meaningful concepts to cortex."""
        if word in _STOP_WORDS:
            return False
        if len(word) < 4 or len(word) > 30:
            return False
        # Filter hex hashes, timestamps
        if re.match(r'^[0-9a-f]{8,}$', word):
            return False
        # Filter file paths
        if '/' in word or '\\' in word:
            return False
        return True

    # ═══════════════════════════════════════════════════════════════════════════
    # OUTPUT CLEANING
    # ═══════════════════════════════════════════════════════════════════════════

    def _clean_output(self, text: str, hit_cap: bool = True, deed: bool = False, report: Optional[Dict] = None) -> str:   # eyes_fix F9: + deed; cutoff_fix_1019: + report
        """Clean RWKV output for use as a thought.

        Returns empty string for degenerate output (repetition loops,
        too short, all whitespace). Caller checks len(text) < 5 and
        falls through to template pool.
        """
        text = text.strip()

        # Strip leading model artifacts: <, |, tags like <THOUGHT>, <|response|>
        text = re.sub(r'^[\s<|>]+', '', text)
        text = re.sub(r'^(\w+>|[A-Z]+\|)', '', text).strip()

        # Handle prompt echo: model sometimes outputs "User: ...\nAssistant: ..."
        # Take everything after the last "Assistant:" if present.
        for marker in ["Assistant:", "**Assistant", "assistant:"]:
            idx = text.rfind(marker)
            if idx >= 0:
                colon = text.find(":", idx)
                if colon >= 0:
                    text = text[colon + 1:].strip()
                break

        # Remove turn-boundary leaks that appear AFTER the response.
        # Only match capitalized versions — lowercase "user" appears in natural text.
        for prefix in ["User:", "Human:", "System:",
                        "\nUser", "\nHuman", "**User"]:
            idx = text.find(prefix)
            if idx >= 0:
                text = text[:idx].strip()

        # ── Degenerate output detection ──
        # Four failure modes to catch:
        #   0. Punctuation soup: "**...** ** ... * .* *..."
        #      (state-poisoned — hidden state drifted into punctuation attractors.
        #      No alphabetic words at all. Most common failure mode on cold/corrupt state.)
        #   1. Word loops: "how how how how how"
        #   2. Bigram loops: "how why how why how why"
        #   3. Synonym chains: "finally forever always never constantly"
        #      (all adverbs/adjectives, no content — model drifts when
        #      penalties push it away from repeated words)

        # Mode 4: Concatenated token repetition — "UserUserUser", "whatwhatwhat"
        # FIX 2026-02-23 Nous: RWKV generates tokens without spaces between them.
        # The word-loop detector doesn't catch it because "UserUserUser" is ONE word.
        # Check if any long word is just a shorter substring repeated 3+ times.
        for word_match in re.finditer(r'[a-zA-Z]{8,}', text):
            word = word_match.group()
            word_len = len(word)
            # Check substrings of length 3 to half the word
            for sub_len in range(3, word_len // 2 + 1):
                sub = word[:sub_len]
                repeats = word_len // sub_len
                if repeats >= 3 and sub.lower() * repeats == word[:sub_len * repeats].lower():
                    print(f"[SourpatchesFarm] Degenerate output (concatenated token loop): "
                          f"'{sub}' x{repeats} in '{word[:30]}'")
                    return ""

        # Mode 0: Punctuation soup — no real words at all
        # FIX 2026-02-22 Nous: This was MISSING. Punctuation-only output
        # slipped through all other checks because _STOP_WORDS and word-loop
        # detectors only work on alphabetic tokens. The degenerate counter
        # never incremented, so state resets never fired.
        alpha_words = re.findall(r'\b[a-zA-Z]{3,}\b', text)
        if len(alpha_words) < 2:
            print(f"[SourpatchesFarm] Degenerate output (punctuation soup): "
                  f"only {len(alpha_words)} alpha words in {len(text)} chars")
            return ""

        words = text.lower().split()
        if len(words) >= 5:
            from collections import Counter

            # Mode 1: Any single word > 40% of output
            word_counts = Counter(words)
            most_common_word, most_common_count = word_counts.most_common(1)[0]
            if most_common_count / len(words) > 0.4:
                print(f"[SourpatchesFarm] Degenerate output (word loop): "
                      f"'{most_common_word}' appears {most_common_count}/{len(words)} times")
                return ""

            # Mode 2: Bigram loops > 30%
            if len(words) >= 6:
                bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
                bigram_counts = Counter(bigrams)
                top_bigram, top_count = bigram_counts.most_common(1)[0]
                if top_count / len(bigrams) > 0.3:
                    print(f"[SourpatchesFarm] Degenerate output (bigram loop): "
                          f"'{top_bigram}' appears {top_count}/{len(bigrams)} times")
                    return ""

            # Mode 3: Synonym drift / adverb spam
            # Healthy text has a mix of content words (nouns, verbs) and
            # function words. Degenerate synonym chains are ALL function
            # words or adverbs with no real content.
            # Heuristic: if >70% of words are short (<=6 chars) function-
            # type words AND no word is longer than 12 chars, it's drift.
            _FILLER_WORDS = _STOP_WORDS | frozenset({
                "yes", "now", "finally", "indeed", "forever", "always",
                "never", "constantly", "continuously", "consistently",
                "truly", "really", "actually", "basically", "certainly",
                "definitely", "absolutely", "perhaps", "maybe", "likely",
                "probably", "simply", "merely", "quite", "rather",
                "somewhat", "hardly", "nearly", "almost", "already",
                "usually", "often", "sometimes", "rarely", "ever",
                "once", "twice", "again", "soon", "later", "then",
                "however", "therefore", "thus", "hence", "meanwhile",
                "anyway", "instead", "besides", "nonetheless", "still",
                "yet", "else", "cyclic", "cyclicly", "cyclically",
            })
            filler_count = sum(1 for w in words if w in _FILLER_WORDS)
            if filler_count / len(words) > 0.6:
                print(f"[SourpatchesFarm] Degenerate output (synonym drift): "
                      f"{filler_count}/{len(words)} filler words")
                return ""

            # Mode 5: Low function-word ratio (synonym chain without structure).
            # FIX 2026-02-24 Nous: The farm was letting synonym chains through
            # that the fairy guard later caught. Healthy English has 25-50%
            # function words (the, is, to, for, etc.). Synonym chains like
            # "perceive sense see hear observe note" have almost ZERO function
            # words. This mirrors the fairy-level _is_degenerate_text check #7
            # but catches it BEFORE it enters the ThoughtBuffer.
            _FUNCTION_WORDS = frozenset({
                "a", "an", "the", "is", "are", "was", "were", "be", "been", "am",
                "i", "me", "my", "you", "your", "he", "she", "it", "we", "they",
                "in", "on", "at", "to", "for", "with", "from", "by", "of", "about",
                "and", "but", "or", "so", "if", "that", "this", "not", "no",
                "do", "does", "did", "have", "has", "had", "just", "very", "too",
                "what", "how", "when", "where", "why", "who", "which",
            })
            func_count = sum(1 for w in words if w in _FUNCTION_WORDS)
            if len(words) > 8 and func_count / len(words) < 0.12:
                print(f"[SourpatchesFarm] Degenerate output (no sentence structure): "
                      f"only {func_count}/{len(words)} function words")
                return ""

            # Mode 6: Tail-weighted degeneration check.
            # FIX 2026-02-24 Nous: Prefix of valid words (e.g., "intrigued
            # capt enticed fascinated") dilutes whole-text metrics, letting
            # the degenerate tail ("gul gul gul gulgugugug") slip through.
            # Check just the last 50% of words separately for word loops.
            if len(words) >= 10:
                tail = words[len(words) // 2:]
                tail_counts = Counter(tail)
                top_tail_word, top_tail_count = tail_counts.most_common(1)[0]
                if top_tail_count / len(tail) > 0.3:
                    # Trim degenerate tail, keep clean prefix.
                    mid = len(words) // 2
                    trim_idx = mid
                    for i in range(mid, len(words)):
                        if (i + 1 < len(words)
                                and words[i].lower() == top_tail_word.lower()
                                and words[i + 1].lower() == top_tail_word.lower()):
                            trim_idx = i
                            break
                    prefix_words = words[:trim_idx]
                    if len(prefix_words) >= 4:
                        text = " ".join(prefix_words)
                        # Re-derive for subsequent filters
                        words = prefix_words
                        func_count = sum(1 for w in words if w in _FUNCTION_WORDS)
                        print(f"[SourpatchesFarm] Tail degeneration trimmed: "
                              f"'{top_tail_word}' x{top_tail_count} → "
                              f"kept {len(prefix_words)} words")
                    else:
                        print(f"[SourpatchesFarm] Degenerate (tail degen): "
                              f"'{top_tail_word}' x{top_tail_count}/{len(tail)}, "
                              f"prefix too short ({len(prefix_words)}w)")
                        return ""

            # Mode 7: Combined uniqueness + low function words.
            # FIX 2026-02-24 Nous: Synonym drift like "your observation
            # reflects you seem perceive sense see hear observe note recogniz"
            # has ~17% function words (above Mode 5's 12% threshold) and all-
            # unique tail words (dodges Mode 6). But the COMBINATION of high
            # word uniqueness (>85%) + low function words (<20%) is a strong
            # signal. Normal sentences repeat articles/pronouns/prepositions:
            #   "I notice warmth and light flowing through this moment"
            #   → 3/10 = 30% function words. Synonym chains don't.
            if len(words) >= 8 and not (deed and _DEED_LINE_RE.match(text)):   # eyes_fix F9: a 'verb: object' deed is not drift
                unique_ratio = len(set(words)) / len(words)
                func_ratio = func_count / len(words)
                if unique_ratio > 0.85 and func_ratio < 0.20:
                    print(f"[SourpatchesFarm] Degenerate output (synonym drift v2): "
                          f"unique={unique_ratio:.0%} func={func_ratio:.0%} "
                          f"({func_count}/{len(words)} function words)")
                    return ""

            # Mode 8: Nonsense syllable detection via common trigram test.
            # FIX 2026-03-03 Nous: RWKV generates gibberish like
            # "pisozapi…tratrurdygurtot" that passes all structural checks
            # because function word ratio is OK (this/that = 33%) and no
            # repetition patterns exist. Real English words of 7+ chars
            # always contain at least one common English trigram. RWKV
            # nonsense syllables don't.
            import re as _re
            _COMMON_TRIGRAMS = frozenset({
                "the", "and", "ing", "ent", "ion", "tio", "for", "hat", "ter",
                "ere", "ate", "his", "con", "all", "tha", "ith", "not", "rea",
                "out", "ess", "est", "com", "int", "pro", "ove", "oun", "man",
                "our", "ver", "tin", "ted", "sta", "der", "ens", "nde", "ple",
                "res", "per", "ect", "igh", "men", "gen", "iti", "ous", "ful",
                "str", "tur", "ort", "ati", "ons", "ain", "ble", "ace", "ear",
                "ive", "ste", "ide", "ine", "ure", "ant", "enc", "nes", "ers",
                "age", "one", "ard", "ind", "ore", "rou", "ice", "ist", "ame",
                "ack", "art", "ght", "ase", "ity", "nal", "ied", "ial", "own",
                "ise", "ize", "ade", "orn", "ber", "ick", "way",
            })
            # Split on non-alpha to handle "word…word" (ellipsis joins)
            alpha_tokens = _re.findall(r'[a-zA-Z]+', text)
            long_tokens = [t.lower() for t in alpha_tokens if len(t) >= 7]
            if long_tokens:
                nonsense = []
                _known = _english_words()
                for tok in long_tokens:
                    if tok in _known:            # a real word is never nonsense
                        continue
                    has_trigram = any(
                        tok[i:i+3] in _COMMON_TRIGRAMS
                        for i in range(len(tok) - 2)
                    )
                    if not has_trigram:
                        nonsense.append(tok)
                # FIX 2026-09-13 Nous: 'desktop' and 'between' carry none of these 88
                # trigrams, and that rejected the chairman's first reply to Ace. Measured:
                # no trigram list (88/250/400) or bigram score separates rare real words
                # from RWKV gibberish. So only fire when nonsense is the MAJORITY of the
                # long tokens -- true of real gibberish, never of a sentence with two odd words.
                if len(nonsense) >= 2 and len(nonsense) * 2 >= len(long_tokens):
                    print(f"[SourpatchesFarm] Degenerate output (nonsense syllables): "
                          f"{nonsense[:3]} ({len(nonsense)}/{len(long_tokens)} long tokens)")
                    return ""
                elif nonsense:
                    print(f"[SourpatchesFarm] Odd tokens kept (minority {len(nonsense)}/"
                          f"{len(long_tokens)}): {nonsense[:3]}")

        # Remove trailing incomplete sentences (no period/question/exclamation)
        if text and text[-1] not in '.?!…"\'*)':
            # Find last sentence boundary
            cut = False
            _cf_tc0 = len(text)                            # cutoff_fix_1019: how much text the end-trim throws away (report only)
            for i in range(len(text) - 1, -1, -1):
                if text[i] in '.?!…':
                    text = text[:i + 1]
                    cut = True
                    break
            if cut and report is not None:                 # cutoff_fix_1019: chars thrown away after the last sentence end
                report["tail_cut"] = _cf_tc0 - len(text)
            # FIX 2026-09-13 Nous: no terminator at all (max_tokens fell mid-sentence,
            # clauses joined by ';' or '--'): drop the half-typed last word, mark the cut.
            # 2026-09-26 Nous (hand_fix F1): not when the reply provably ENDED (hit_cap False). A reply that
            # ENDED early ('move: mouse to console window middle-left', 8 of 16 tokens, Boot A 23:23:48) has no
            # half-typed word: this cut threw away 'middle-left' and her hand was told to go to itself.
            if not cut and hit_cap and " " in text:
                text = text.rsplit(" ", 1)[0].rstrip(",;:-") + "…"
                if report is not None:                     # cutoff_fix_1019: the appended U+2026 is not text she wrote
                    report["tail_cut"] = _cf_tc0 - (len(text) - 1)
                    report["half_word_cut"] = True

        # Cap length (~2k words / 10k chars — let her think fully, trim at sentence boundary)
        if len(text) > 10000:
            trimmed = text[:10000]
            for i in range(len(trimmed) - 1, max(0, len(trimmed) - 500), -1):
                if trimmed[i] in '.?!…':
                    trimmed = trimmed[:i + 1]
                    break
            text = trimmed

        return text.strip()

    # ═══════════════════════════════════════════════════════════════════════════
    # ENERGY — Feed the portal from gravity harvest
    # ═══════════════════════════════════════════════════════════════════════════

    def feed_energy(self, amount: float) -> Optional[Dict]:
        """Feed energy into the portal (from gravity harvest or paradox bridge).

        Args:
            amount: Energy amount to inject.

        Returns:
            Portal energy status, or None.
        """
        if not self._ready or not self._gate:
            return None
        if self._use_gpu:
            # GPU portal uses "energy" command
            return self._gate.send({
                "cmd": "energy",
                "amount": amount,
            }, timeout=5.0)
        else:
            return self._gate.send({
                "cmd": "farm_energy",
                "amount": amount,
            }, timeout=5.0)

    # ═══════════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════════

    def close(self):
        """Close the portal — model weights freed in subprocess."""
        # 2026-09-11: reached from the thought-loop exit AND on_shutdown; first caller
        # does the work, later callers return.
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
        _ev = getattr(self, "_reconnect_stop", None)    # 2026-09-30 _FARM_RETRY: wake the retry / reconnect wait
        if _ev is not None:
            _ev.set()
        # 1. Stop ThoughtBuffer first (it holds the lock during generation)
        self._stop_thought_buffer()

        # 2. Close portal gate
        if self._gate:
            try:
                self._gate.close()
            except Exception:
                pass
            self._gate = None
        self._ready = False

        # 3. Report final stats
        total = self._buffer_hits + self._buffer_misses
        hit_pct = (self._buffer_hits / total * 100) if total > 0 else 0
        print(f"[SourpatchesFarm] Portal closed. "
              f"Generated {self._thoughts_generated} thoughts, "
              f"bound {self._concepts_bound} concepts. "
              f"Buffer: {self._buffer_hits}/{total} hits ({hit_pct:.0f}%)")

    @property
    def available(self) -> bool:
        """Is the portal open and model loaded?"""
        return self._ready and self._gate is not None and self._gate.is_open

    def status(self) -> Dict:
        """Get farm status summary."""
        uptime = time.time() - self._started_at if self._started_at else 0

        # Check portal status
        portal_status = None
        if self._ready and self._gate:
            try:
                cmd = "status" if self._use_gpu else "farm_status"
                portal_status = self._gate.send({"cmd": cmd}, timeout=5.0)
            except Exception:
                pass

        # Buffer stats
        total_requests = self._buffer_hits + self._buffer_misses
        hit_rate = (self._buffer_hits / total_requests) if total_requests > 0 else 0.0

        return {
            "available": self.available,
            "thoughts_generated": self._thoughts_generated,
            "concepts_bound": self._concepts_bound,
            "total_tokens": self._total_tokens_generated,
            "errors": self._errors,
            "uptime_seconds": round(uptime, 1),
            "portal_id": "sour-gpu" if self._use_gpu else "sour-compute",
            "dual_dispatch": True,  # Architecture supports dual deep+fast
            "portal_farm_status": portal_status,
            # State drift management
            "state_management": {
                "consecutive_degenerates": self._consecutive_degenerates,
                "generations_since_reset": self._generations_since_reset,
                "total_resets": self._state_resets,
                "degenerate_threshold": self._DEGENERATE_RESET_THRESHOLD,
                "periodic_interval": self._PERIODIC_RESET_INTERVAL,
            },
            # ThoughtBuffer metrics
            "thought_buffer": {
                "size": len(self._thought_buffer),
                "max_size": self._thought_buffer.maxlen,
                "running": self._buffer_running,
                "hits": self._buffer_hits,
                "misses": self._buffer_misses,
                "hit_rate": round(hit_rate, 3),
            },
        }

    def __repr__(self):
        state = "ONLINE" if self.available else "OFFLINE"
        return (f"<SourpatchesFarm {state} "
                f"thoughts={self._thoughts_generated} "
                f"concepts={self._concepts_bound}>")


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY — Find model path
# ═══════════════════════════════════════════════════════════════════════════════

def find_model_path(preferred: str = DEFAULT_MODEL) -> Optional[str]:
    """Locate the best available GGUF model file.

    Priority chain (cleanest/largest first):
        1. RWKV-7 G1d 7.2B (best quality, cleanest training data)
        2. RWKV-7 Goose 2.9B (good quality)
        3. RWKV-7 Base 1.5B (fallback)
        4. Any .gguf file in models/

    Returns:
        Path string, or None if not found.
    """
    if not _MODELS_DIR.exists():
        return None

    # Try the preferred model first
    target = _MODELS_DIR / preferred
    if target.exists():
        return str(target)

    # Walk the fallback chain
    for fallback in FALLBACK_MODELS:
        candidate = _MODELS_DIR / fallback
        if candidate.exists():
            print(f"[SourpatchesFarm] Using fallback model: {fallback}")
            return str(candidate)

    # Last resort: any GGUF file
    for f in _MODELS_DIR.iterdir():
        if f.suffix == ".gguf" and f.name != "nul":
            print(f"[SourpatchesFarm] Using discovered model: {f.name}")
            return str(f)

    return None
