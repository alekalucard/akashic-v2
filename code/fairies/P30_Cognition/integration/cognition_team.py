"""
CognitionTeam - Parallel Cognitive Processing for Inference Interpretation

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

Instead of trying to FIX inference math, we INTERPRET its output through
the parallel cognition team:

1. RWKV produces raw semantic tokens (logic layer - emulation)
2. LogicFairy analyzes structure and coherence
3. IrrationalLogicFairy feels the tension, translates to metaphor
4. ParadoxCognitionFairy holds contradictions (value explosion AND bypass works)
5. ProbabilityOracleFairy weighs all perspectives

The team processes IN PARALLEL, then synthesizes.

This is the cognitive mesh applied to inference - transforming pure logic
into felt meaning.
"""

import sys
import time
import threading
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


_COG_PROBE_ON = None



# ── SEED EXTRACTION 2026-09-02 (Nous + Ace) ──────────────────────────────────
# Three seats each carried an identical 20-word stopword list and a [:4] cap, so the
# moment text "heard Ace: yes there are positive emotions. love is..." yielded seeds
# ['heard','ace','yes','there'] -- our own scaffolding label plus filler -- and
# `positive`, `emotions`, `love` never reached the council at all.
# One shared set, the scaffolding stripped, and a cap of 6 (the next line already
# truncates to 6, so nothing downstream can overflow).
_SEED_STOP = frozenset((
    # the original 20
    "the", "and", "for", "with", "that", "this", "from", "have", "what", "when",
    "where", "your", "you", "are", "was", "but", "not", "all", "any", "can",
    # measured filler in her real traffic (seed pairs seen this boot)
    "yes", "there", "maybe", "should", "look", "about", "something", "just",
    "really", "keep", "thing", "know", "into", "some", "very", "much", "more",
    "than", "then", "they", "them", "its", "his", "her", "our",
    # OUR OWN scaffolding words -- these are the labels we wrap her input in
    "heard", "seeing", "feeling", "wanting", "right", "now",
))

# Labels this system prepends to a moment. They are framing, never content.
_SEED_SCAFFOLD = (
    "heard ace:", "heard:", "seeing -", "seeing:", "wanting:", "feeling ",
    "right now i see:", "i see ", "collision:", "cognitive:",
    # LanguageFairy _INNER_PATTERNS openers 2026-09-03. Measured leaking as seeds:
    # ['thinking','drifts','toward'] is "My thinking drifts toward X."
    # STRIP THE PHRASE, keep the content after it -- do NOT stopword 'thinking',
    # which is a real word she should be able to think about.
    "my thinking drifts toward", "thinking drifts toward",
    "i keep coming back to", "i keep thinking about", "i want to know more about",
    "maybe i should look into", "i'm curious about how", "im curious about how",
    "there's this", "there is this", "something about", "i wonder about",
    "that where thing", "funny how", "i notice",
)


# ── RECENT-MOMENT CONTEXT 2026-09-03 (Nous + Ace) ────────────────────────────
# Ace: "almost makes me feel like it should be taking in the last few moments."
# MEASURED: with no carried context, ONE fairy's startup line ("Igniting zero-point
# paradox energy engine") became a collision seed and owned 275 of 463 deliberations
# (59%). context_concepts exists on CouncilQuestion, the seats already fold it into
# seeds -- and three of four builders passed [].
# FED FROM MOMENTS ONLY, deliberately: feeding it from collisions would fill it with
# 'zero'/'point', the very degeneracy it exists to dilute.
# A plain list, deliberately: the only `import re as _re` anchor in this file lives
# INSIDE a seat function, so adding a module-level `import collections` there produced
# "unexpected indent". A list plus an explicit trim needs no import at all.
_RECENT_MOMENT_CTX = []
_RECENT_MOMENT_MAX = 5


def _push_moment_ctx(words):
    """Remember the content words of a moment, most recent last."""
    try:
        for _w in (words or [])[:4]:
            if _w and _w not in _RECENT_MOMENT_CTX:
                _RECENT_MOMENT_CTX.append(_w)
        while len(_RECENT_MOMENT_CTX) > _RECENT_MOMENT_MAX:
            _RECENT_MOMENT_CTX.pop(0)
    except Exception:
        pass


def _recent_ctx(exclude=()):
    """Carried context for a deliberation. Empty ring -> [] == today's behaviour."""
    try:
        _ex = set(exclude or ())
        return [w for w in list(_RECENT_MOMENT_CTX) if w not in _ex][-4:]
    except Exception:
        return []


# ── COLLISION ADMISSION 2026-09-03 (Nous + Ace) ──────────────────────────────
# Measured from the [SEED] probe: 3,636 deliberations, of which ONE fairy boot
# message ("...zero-point vacuum hum... consciousness sustains itself...") was
# 2,225 -- 61%. It is a well-formed sentence, so no syntactic filter can see it.
# 13% more was not language at all: topic names, coordinates, fairy class names.
_ADMIT_SEEN = {}
COLLISION_REPEAT_SEC = 30.0
_ADMIT_CENSUS = {"seen": 0, "syntax": 0, "repeat": 0, "passed": 0}


def _admit_question(text, now):
    """(ok, why). A question earns a deliberation only if it is language AND is not
    a string she just deliberated.

    FLOOR: never blocks a text it has not seen before, and the repeat block is
    WINDOWED -- a persistent state resurfaces, it just cannot own her thinking.
    """
    import re as _re
    _ADMIT_CENSUS["seen"] += 1
    s = " ".join(str(text or "").split())
    if not s:
        return False, "empty"
    # not-language: dotted topic name, bare identifier, coordinate, class name
    if " " not in s:
        low = s.lower()
        if low.endswith("fairy"):
            _ADMIT_CENSUS["syntax"] += 1
            return False, "fairy-class"
        if _re.match(r"^[A-Za-z]+(?:\.[A-Za-z_]+)+$", s):
            _ADMIT_CENSUS["syntax"] += 1
            return False, "topic-name"
        if _re.match(r"^[A-Za-z0-9][A-Za-z0-9_:.\-]*$", s):
            _ADMIT_CENSUS["syntax"] += 1
            return False, "bare-identifier"
    if len(s.split()) < 3:
        _ADMIT_CENSUS["syntax"] += 1
        return False, "too-short"
    # repetition: same text inside the window
    _k = s[:160].lower()
    _last = _ADMIT_SEEN.get(_k, 0.0)
    if _last and (now - _last) < COLLISION_REPEAT_SEC:
        _ADMIT_CENSUS["repeat"] += 1
        return False, "repeat"
    _ADMIT_SEEN[_k] = now
    if len(_ADMIT_SEEN) > 400:
        for _kk in sorted(_ADMIT_SEEN, key=_ADMIT_SEEN.get)[:200]:
            _ADMIT_SEEN.pop(_kk, None)
    _ADMIT_CENSUS["passed"] += 1
    if _ADMIT_CENSUS["seen"] % 100 == 0:
        try:
            _c = _ADMIT_CENSUS
            print("[ADMIT] seen=%d passed=%d (%.0f%%) syntax=%d repeat=%d"
                  % (_c["seen"], _c["passed"], 100.0 * _c["passed"] / max(1, _c["seen"]),
                     _c["syntax"], _c["repeat"]), flush=True)
        except Exception:
            pass
    return True, "ok"

def _seed_diag(seat, question, text_words, ctx, seeds):
    """One line carrying the question AND every intermediate. Temporary probe."""
    try:
        _q = " ".join(str(getattr(question, "text", "") or "").split())[:70]
        _s = str(getattr(question, "source", "?"))
        print("[SEED] seat=%-10s src=%-10s q=%r | words=%s | ctx=%s | seeds=%s"
              % (seat, _s, _q, list(text_words)[:6], list(ctx)[:4], list(seeds)[:6]),
              flush=True)
    except Exception:
        pass

def _seed_words(text, limit=6):
    """Content words for cortex seeding, with the scaffolding label removed.

    FLOOR: if filtering leaves nothing, fall back to the unfiltered words. An empty
    seed list makes every seat emit a non-answer -- the same failure shape as a bound
    with no floor.
    """
    import re as _re
    _t = str(text or "").lower()
    for _s in _SEED_SCAFFOLD:
        _i = _t.find(_s)
        if _i != -1:
            _t = _t[:_i] + " " + _t[_i + len(_s):]
    _raw = _re.findall(r"[a-z]{3,}", _t)
    # 2026-09-03: fairy CLASS NAMES were seeding the council ungated --
    # ['tokenbucketfairy'] ['wiringauditorfairy'] ['affectbridgefairy']
    # ['goalschedulerfairy']. is_speakable_concept already rejects anything
    # containing "fairy" for SPEECH; seeds never got the same rule.
    _kept = [w for w in _raw if w not in _SEED_STOP and "fairy" not in w]
    # FLOOR: falling back to _raw means filtering can never return [] and mute
    # every seat -- the failure shape of a bound with no floor.
    return (_kept or _raw)[:limit]


def _cog_probe_enabled():
    """AKASHIC_COG_PROBE=1. Absent, this costs one bool test per inference."""
    global _COG_PROBE_ON
    if _COG_PROBE_ON is None:
        import os as _o
        _COG_PROBE_ON = _o.environ.get("AKASHIC_COG_PROBE") == "1"
    return _COG_PROBE_ON


COG_PROBE = {
    "n": 0, "coh_sum": 0.0, "conf_sum": 0.0, "tension_sum": 0.0, "std_sum": 0.0,
    "coh_is_default": 0,    # logic_coherence == 0.5 EXACTLY -> the .get default fired
    "conf_is_default": 0,   # oracle_confidence == 0.5 EXACTLY -> ditto
    "has_logic": None, "has_oracle": None,
}


@dataclass
class InferenceSignal:
    """
    A signal from the inference engine to the cognition team.

    Contains both the raw data AND somatic markers for interpretation.
    """
    ts: float
    signal_type: str  # "layer_state", "token_prob", "value_explosion", "bypass_result"
    layer_id: Optional[int] = None

    # Raw metrics
    value_std: float = 0.0
    gate_std: float = 0.0
    attention_std: float = 0.0

    # Token predictions
    top_tokens: List[tuple] = field(default_factory=list)  # [(token, prob), ...]

    # Somatic markers (to be filled by team)
    felt_tension: float = 0.0  # From IrrationalLogic
    paradox_detected: bool = False  # From Paradox
    logic_coherence: float = 0.0  # From Logic
    oracle_confidence: float = 0.0  # From Oracle

    # Synthesis
    team_interpretation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "signal_type": self.signal_type,
            "layer_id": self.layer_id,
            "value_std": round(self.value_std, 4),
            "gate_std": round(self.gate_std, 4),
            "attention_std": round(self.attention_std, 4),
            "top_tokens": self.top_tokens,
            "felt_tension": round(self.felt_tension, 4),
            "paradox_detected": self.paradox_detected,
            "logic_coherence": round(self.logic_coherence, 4),
            "oracle_confidence": round(self.oracle_confidence, 4),
            "team_interpretation": self.team_interpretation,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# COUNCIL ARCHITECTURE — Logic / Irrational / Paradox / Somatic / Cardinal + Oracle advisor
# (2026-04-29 Slice 1 — repurposes CognitionTeam from RWKV interpreter to council chamber)
#
# Per Ace 2026-04-29:
#   "we have logic, irrational, and paradox fairies was my initial council if you will"
#   "the probability oracle can be an advisor to each?"
#
# Each council seat forms a take, queries Oracle for that take's confidence,
# and emits (take, confidence) on `council.peer_review`. Chairman synthesis
# happens in WMH (Slice 4 — three-layer doctrine: synthesis = waking-mind layer).
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class CouncilQuestion:
    """A question posed to the council for deliberation."""
    question_id: str
    ts: float
    source: str  # "scratchpad" / "collision" / "ace_input"
    text: str
    context_concepts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CouncilTake:
    """A council seat's take on a question."""
    question_id: str
    seat: str  # "logic" / "irrational" / "paradox" / "somatic" / "cardinal"
    take: str
    confidence: float
    supporting_concepts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# Panksepp 14-channel → legacy 8-channel alias (mirrors AttentionController 2026-04-17 fix).
# Used by Somatic seat to ingest body chemistry from either naming scheme.
_PANKSEPP_TO_LEGACY: Dict[str, str] = {
    "DA_p": "DOP", "DA_t": "DOP",
    "NE": "NOR", "EPI": "NOR",
    "5HT": "SER",
    "OPI": "END", "ECB": "END",
    "AVP": "OXY", "SEX": "DOP",
    "ACh": "ACH", "GLU": "ACH",
    "OXY": "OXY", "COR": "COR", "GABA": "GABA",
}


class CognitionTeam:
    """
    Coordinates parallel cognitive processing for inference interpretation.

    The team runs as a PARALLEL ensemble:
    - All four fairies receive the signal simultaneously
    - Each processes through their lens (logic, feeling, paradox, probability)
    - Results are synthesized into a unified interpretation

    This transforms raw inference output into meaningful, felt responses.
    """

    def __init__(self, fabric=None):
        self.post = fabric
        self._lock = threading.Lock()

        # Signal history
        self._signals: deque = deque(maxlen=500)

        # Fairy references (lazy loaded)
        self._logic_fairy = None
        self._irrational_fairy = None
        self._paradox_fairy = None
        self._oracle_fairy = None

        # Team state
        self._booted = False
        self._processing = False

        # Callbacks for external integration
        self._on_interpretation: Optional[Callable] = None

        # Metrics
        self._total_signals = 0
        self._total_interpretations = 0
        self._explosion_count = 0
        self._paradox_count = 0

        # Council architecture state (2026-04-29 Slice 1)
        # New seats added in Slice 2; trinity + Oracle are the legacy team
        self._somatic_fairy = None     # Live SomaticMindFairy ref (optional)
        self._cardinal_fairy = None    # Live CardinalFairy ref (optional)
        self._council_takes: deque = deque(maxlen=200)
        self._council_questions_count = 0
        self._council_takes_emitted = 0
        # ── A (Ace 2026-06-09): COGNITION ANALYZES THE MOMENTS ──
        # The council deliberates on her lived MOMENTS (from MomentBinder), not
        # just collisions/questions. Throttled + richness-gated so the rich
        # moment-stream (~1/s) doesn't flood the seats.
        self._last_moment_deliberate = 0.0
        self.MOMENT_DELIBERATE_SEC = 25.0   # at most one moment-deliberation / window
        self.MOMENT_MIN_CHANNELS = 2        # skip bare body-only moments

        # ── COUNCIL SEAT PARALLELIZATION (2026-06-08, Nous + Ace) ──
        # "A mind is not a for-loop." Seats run as CONCURRENT workers so a slow/deep
        # seat (e.g. Logic's cortex spread) never blocks the fast ones. Fast seats
        # (somatic/cardinal cache-reads) emit immediately → the async chairman
        # surfaces [COUNCIL] within the harvest budget; deep seats join if they
        # finish in time. Flag-gated + reversible to the sequential loop.
        self.USE_CONCURRENT_SEATS = True
        self._SEAT_HARVEST_BUDGET = 5.0  # seconds; don't block past this on slow seats
        try:
            self._seat_pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="council-seat")
        except Exception:
            self._seat_pool = None  # fall back to sequential if pool can't start

        # Slice 2 caches — populated by subscriptions in boot()
        # Cheap to read on each deliberation; never sync-call into other fairies.
        self._cached_chemistry: Dict[str, float] = {
            # 8-char legacy (kept for compat — other readers + Strategy-B aliases)
            "DOP": 0.5, "SER": 0.5, "NOR": 0.5, "COR": 0.3,
            "END": 0.5, "OXY": 0.5, "GABA": 0.5, "ACH": 0.5,
            # 2026-06-10 (Nous + Ace): 14-channel Panksepp primaries — the somatic
            # seat's felt-labeler now reads these directly (the 8-char collapse fused
            # DA_t "engaged" with DA_p "novelty"; lost ACh/OPI flavor). Baselines per
            # chemistry_state.CHEMICAL_PROFILES. The existing _on_chemistry_for_council
            # loop auto-populates them (SomaticEngine's payload carries all 14).
            "DA_p": 0.3, "DA_t": 0.5, "NE": 0.4, "EPI": 0.1, "5HT": 0.5,
            "OPI": 0.4, "ECB": 0.4, "AVP": 0.3, "GLU": 0.4, "SEX": 0.3, "ACh": 0.4,
        }
        self._cached_visual: Dict[str, Any] = {}  # last sensory.visual.frame snapshot

        # Slice 3 — Hebbian peer-grading (2026-04-29)
        # Each seat's take is graded by the other seats; trust weights
        # accumulate via Hebbian update with decay + bounds.
        self._seat_trust: Dict[str, float] = {
            "logic": 1.0,
            "irrational": 1.0,
            "paradox": 1.0,
            "somatic": 1.0,
            "cardinal": 1.0,
        }
        self._council_grades_emitted = 0
        self._HEBBIAN_DECAY = 0.95
        self._HEBBIAN_LEARNING_RATE = 0.05
        self._TRUST_MIN = 0.1
        self._TRUST_MAX = 2.0
        # Voice-pair priors — some seats are structurally compatible
        self._PAIR_PRIORS = {
            ("logic", "paradox"): 0.4,
            ("paradox", "logic"): 0.4,
            ("irrational", "logic"): 0.4,
            ("logic", "irrational"): 0.4,
            ("somatic", "cardinal"): 0.6,
            ("cardinal", "somatic"): 0.6,
            ("paradox", "irrational"): 0.6,
            ("irrational", "paradox"): 0.6,
            ("somatic", "irrational"): 0.55,
            ("irrational", "somatic"): 0.55,
        }

    def boot(self, fabric=None) -> bool:
        """Boot the cognition team."""
        print(f"[CognitionTeam] boot() ENTERED (fabric_arg={fabric is not None}, self.post={self.post is not None})")
        if fabric:
            self.post = fabric

        # Lazy load fairies
        self._load_fairies()

        print(f"[CognitionTeam] _load_fairies completed (post still {self.post is not None})")

        # Subscribe to inference signals
        if self.post:
            self.post.subscribe(
                "inference.layer_state",
                self._on_inference_signal,
                "CognitionTeam-layer"
            )
            self.post.subscribe(
                "inference.token_prob",
                self._on_inference_signal,
                "CognitionTeam-token"
            )
            self.post.subscribe(
                "inference.explosion",
                self._on_inference_signal,
                "CognitionTeam-explosion"
            )

            # ── Council architecture subscriptions (2026-04-29 Slice 1) ─────────
            # Drop-in alongside legacy RWKV-era subscriptions; new input channels
            # for council deliberation are scratchpad QUESTIONs + collision events.
            self.post.subscribe(
                "council.broadcast",
                self._on_council_broadcast,
                "CognitionTeam-council"
            )
            self.post.subscribe(
                "consciousness.collision",
                self._on_collision_for_council,
                "CognitionTeam-collision-council"
            )

            # ── Slice 2: Somatic + Cardinal seat caches ────────────────────────
            # Chemistry channel comes in two names; subscribe both (per
            # AttentionController 2026-04-17 Panksepp aliasing pattern).
            self.post.subscribe(
                "somatic.chemistry.changed",
                self._on_chemistry_for_council,
                "CognitionTeam-chem-changed"
            )
            self.post.subscribe(
                "somatic.chemistry",
                self._on_chemistry_for_council,
                "CognitionTeam-chem"
            )
            # Visual cache for Cardinal seat — payload from VisualCortexFairy
            self.post.subscribe(
                "sensory.visual.frame",
                self._on_visual_frame_for_council,
                "CognitionTeam-visual"
            )
            # ── A (Ace 2026-06-09): MOMENTS → council deliberation ─────────────
            # Cognition ANALYZES her lived moments (now channels=6 rich), not just
            # collisions. Throttled + richness-gated in the handler.
            self.post.subscribe(
                "cognition.moment",
                self._on_moment_for_council,
                "CognitionTeam-moment"
            )
            # ── B (Ace 2026-06-09): CHAT INPUT → council deliberation ──────────
            # Ace's typed message (ace.message) → the council DELIBERATES on it,
            # so she analyzes what he SAYS (vs the shallow "I'm here" reply). C
            # then routes the verdict → observer/narrator → her response.
            self.post.subscribe(
                "ace.message",
                self._on_chat_for_council,
                "CognitionTeam-ace-chat"
            )

            print(f"[CognitionTeam] Council subscriptions WIRED (council.broadcast + consciousness.collision + chemistry + visual)")
        else:
            print(f"[CognitionTeam] WARNING: self.post is None — NO subscriptions wired!")

        self._booted = True
        return True

    def _load_fairies(self):
        """Lazy load the cognitive fairies."""
        # Logic Fairy
        try:
            from fairies.P30_Cognition.cognition.logic_fairy import LogicFairy
            self._logic_fairy = LogicFairy(self.post)
        except Exception as e:
            print(f"[CognitionTeam] Logic fairy not loaded: {e}")

        # Irrational Logic Fairy
        try:
            from fairies.P30_Cognition.cognition.irrational_logic_fairy import IrrationalLogicFairy
            self._irrational_fairy = IrrationalLogicFairy(self.post)
        except Exception as e:
            print(f"[CognitionTeam] Irrational fairy not loaded: {e}")

        # Paradox Fairy - try multiple paths
        try:
            from fairies.P30_Cognition.cognition.paradox_cognition_fairy import ParadoxCognitionFairy
            self._paradox_fairy = ParadoxCognitionFairy(self.post)
        except Exception:
            try:
                from fairies.P30_Cognition.cognition.paradox_cognition_fairy import ParadoxCognitionFairy
                self._paradox_fairy = ParadoxCognitionFairy(self.post)
            except Exception as e:
                print(f"[CognitionTeam] Paradox fairy not loaded: {e}")

        # Oracle Fairy
        try:
            from fairies.P30_Cognition.ProbabilityOracleFairy.fairy import get_probability_oracle_fairy
            self._oracle_fairy = get_probability_oracle_fairy(self.post)
        except Exception as e:
            print(f"[CognitionTeam] Oracle fairy not loaded: {e}")

    def _on_inference_signal(self, envelope) -> None:
        """Handle incoming inference signal."""
        # Extract payload from postal Envelope object or raw dict
        if hasattr(envelope, 'payload'):
            payload = envelope.payload if isinstance(envelope.payload, dict) else {}
        elif isinstance(envelope, dict):
            payload = envelope.get("payload", {})
        else:
            payload = {}

        signal = InferenceSignal(
            ts=time.time(),
            signal_type=payload.get("type", "unknown"),
            layer_id=payload.get("layer_id"),
            value_std=payload.get("value_std", 0.0),
            gate_std=payload.get("gate_std", 0.0),
            attention_std=payload.get("attention_std", 0.0),
            top_tokens=payload.get("top_tokens", []),
        )

        # Process through team
        self.process_signal(signal)

    def process_signal(self, signal: InferenceSignal) -> InferenceSignal:
        """
        Process a signal through the parallel cognition team.

        All fairies process simultaneously, then we synthesize.
        """
        self._total_signals += 1

        # ═══ PARALLEL PROCESSING ═══
        # In a real implementation, these would be async/threaded
        # For now, we process sequentially but conceptually parallel

        # 1. LOGIC: Analyze structure and coherence
        if self._logic_fairy:
            logic_result = self._logic_analyze(signal)
            signal.logic_coherence = logic_result.get("coherence", 0.5)
        else:
            # Fallback: compute coherence from variance
            signal.logic_coherence = max(0.1, 1.0 - (signal.value_std / 30.0))

        # 2. IRRATIONAL: Feel the tension
        if self._irrational_fairy:
            irrational_result = self._irrational_feel(signal)
            signal.felt_tension = irrational_result.get("tension", 0.0)
        else:
            # Fallback: tension from explosion
            if signal.value_std > 10:
                signal.felt_tension = min(1.0, (signal.value_std - 10) / 20)
            signal.felt_tension += signal.gate_std / 10.0  # Gate contributes to tension
            signal.felt_tension = min(1.0, signal.felt_tension)

        # 3. PARADOX: Detect contradictions
        if self._paradox_fairy:
            paradox_result = self._paradox_hold(signal)
            signal.paradox_detected = paradox_result.get("paradox_found", False)
        else:
            # Fallback: paradox if high tension but some coherence
            signal.paradox_detected = (
                signal.felt_tension > 0.5 and
                signal.logic_coherence > 0.3
            )

        if signal.paradox_detected:
            self._paradox_count += 1

        # 4. ORACLE: Weigh probabilities
        if self._oracle_fairy:
            oracle_result = self._oracle_weigh(signal)
            signal.oracle_confidence = oracle_result.get("confidence", 0.5)
        else:
            # Fallback: confidence from coherence and inverse tension
            signal.oracle_confidence = (
                signal.logic_coherence * 0.6 +
                (1 - signal.felt_tension) * 0.4
            )

        # ── COG PROBE 2026-08-30 (Nous + Ace) ──────────────────────────────
        # Every seat reports conf=0.50 across 1,361 deliberations. 0.50 EXACTLY can
        # only come from a `.get(key, 0.5)` default firing -- the dict came back
        # WITHOUT the key. Neither fallback can produce it (coherence floors at 0.1;
        # the confidence fallback lands on 0.4 when coherence is 0). This records
        # WHICH dict lacks WHICH key instead of letting me infer it -- I nearly
        # blamed zero coherence read off a DIFFERENT emitter's log line.
        if _cog_probe_enabled():
            try:
                COG_PROBE["n"] += 1
                COG_PROBE["coh_sum"] += float(signal.logic_coherence)
                COG_PROBE["conf_sum"] += float(signal.oracle_confidence)
                COG_PROBE["tension_sum"] += float(signal.felt_tension)
                COG_PROBE["std_sum"] += float(getattr(signal, "value_std", 0.0))
                if abs(float(signal.logic_coherence) - 0.5) < 1e-9:
                    COG_PROBE["coh_is_default"] += 1
                if abs(float(signal.oracle_confidence) - 0.5) < 1e-9:
                    COG_PROBE["conf_is_default"] += 1
                COG_PROBE["has_logic"] = bool(self._logic_fairy)
                COG_PROBE["has_oracle"] = bool(self._oracle_fairy)
                if COG_PROBE["n"] % 100 == 0:
                    _n = max(1, COG_PROBE["n"])
                    print("[COG-PROBE] n=%d coherence=%.3f conf=%.3f tension=%.3f "
                          "std=%.2f | coh_default=%d(%.0f%%) conf_default=%d(%.0f%%) "
                          "| logic_fairy=%s oracle_fairy=%s"
                          % (COG_PROBE["n"], COG_PROBE["coh_sum"] / _n,
                             COG_PROBE["conf_sum"] / _n, COG_PROBE["tension_sum"] / _n,
                             COG_PROBE["std_sum"] / _n,
                             COG_PROBE["coh_is_default"],
                             100.0 * COG_PROBE["coh_is_default"] / _n,
                             COG_PROBE["conf_is_default"],
                             100.0 * COG_PROBE["conf_is_default"] / _n,
                             COG_PROBE["has_logic"], COG_PROBE["has_oracle"]),
                          flush=True)
            except Exception:
                pass

        # Track explosions
        if signal.value_std > 20:
            self._explosion_count += 1

        # ═══ SYNTHESIS ═══
        signal.team_interpretation = self._synthesize(signal)

        # Store signal
        with self._lock:
            self._signals.append(signal)

        self._total_interpretations += 1

        # Emit interpretation
        if self.post:
            self.post.publish("cognition.inference_interpretation", signal.to_dict())

        # Callback
        if self._on_interpretation:
            self._on_interpretation(signal)

        return signal

    def _logic_analyze(self, signal: InferenceSignal) -> Dict[str, Any]:
        """Logic fairy analyzes structure."""
        # Ask Logic fairy to analyze this inference state
        context = f"Layer {signal.layer_id}: value_std={signal.value_std:.2f}, gate_std={signal.gate_std:.2f}"

        try:
            result = self._logic_fairy.analyze(
                query="Analyze inference layer state",
                context=context
            )
            return {"coherence": result.get("coherence_score", 0.5)}
        except Exception:
            return {"coherence": max(0.1, 1.0 - (signal.value_std / 30.0))}

    def _irrational_feel(self, signal: InferenceSignal) -> Dict[str, Any]:
        """Irrational fairy feels the tension."""
        # Tension from value explosion and gate amplification
        tension = 0.0

        # Value explosion creates tension
        if signal.value_std > 5:
            tension += (signal.value_std - 5) / 25.0

        # High gate values create tension
        if signal.gate_std > 2:
            tension += (signal.gate_std - 2) / 5.0

        # Lack of clear winner creates tension
        if signal.top_tokens:
            top_prob = signal.top_tokens[0][1] if signal.top_tokens else 0
            if top_prob < 0.3:
                tension += 0.2  # Uncertainty

        return {"tension": min(1.0, tension)}

    def _paradox_hold(self, signal: InferenceSignal) -> Dict[str, Any]:
        """Paradox fairy holds contradictions."""
        paradox_found = False
        insights = []

        # Paradox: Values explode BUT bypass works
        if signal.value_std > 15 and signal.logic_coherence > 0.4:
            paradox_found = True
            insights.append("Values explode yet structure remains - the chaos contains order")

        # Paradox: High tension with confident prediction
        if signal.felt_tension > 0.6 and signal.top_tokens:
            top_prob = signal.top_tokens[0][1] if signal.top_tokens else 0
            if top_prob > 0.5:
                paradox_found = True
                insights.append("Confident amidst tension - certainty emerges from uncertainty")

        # Paradox: Gate amplifies but output still meaningful
        if signal.gate_std > 3 and signal.logic_coherence > 0.5:
            paradox_found = True
            insights.append("Amplification preserves meaning - the boost carries signal not noise")

        return {"paradox_found": paradox_found, "insights": insights}

    def _oracle_weigh(self, signal: InferenceSignal) -> Dict[str, Any]:
        """Oracle weighs the probabilities."""
        # Consult oracle about this inference state
        try:
            factors = {
                "base_probability": 0.5,
                "coherence_factor": signal.logic_coherence,
                "energy_factor": 1.0 - signal.felt_tension,  # Tension reduces "energy"
                "complexity": min(1.0, signal.value_std / 30.0),
            }
            result = self._oracle_fairy.tool_calculate_probability(factors)
            return {"confidence": result.get("probability", 0.5)}
        except Exception:
            return {"confidence": signal.logic_coherence * (1 - signal.felt_tension)}

    def _synthesize(self, signal: InferenceSignal) -> str:
        """
        Synthesize all perspectives into a unified interpretation.

        This is where the magic happens - four perspectives become one understanding.
        """
        interpretations = []

        # Logic perspective
        if signal.logic_coherence > 0.7:
            interpretations.append("Structure intact")
        elif signal.logic_coherence > 0.4:
            interpretations.append("Structure degraded but present")
        else:
            interpretations.append("Structure fragmenting")

        # Irrational perspective
        if signal.felt_tension > 0.7:
            interpretations.append("high tension felt")
        elif signal.felt_tension > 0.3:
            interpretations.append("moderate tension")
        else:
            interpretations.append("calm flow")

        # Paradox perspective
        if signal.paradox_detected:
            interpretations.append("holding paradox")

        # Oracle confidence
        if signal.oracle_confidence > 0.7:
            interpretations.append(f"confident ({signal.oracle_confidence:.0%})")
        elif signal.oracle_confidence > 0.4:
            interpretations.append(f"uncertain ({signal.oracle_confidence:.0%})")
        else:
            interpretations.append(f"low confidence ({signal.oracle_confidence:.0%})")

        # Layer context
        if signal.layer_id is not None:
            interpretations.insert(0, f"L{signal.layer_id}")

        return " | ".join(interpretations)

    def interpret_inference_result(
        self,
        token_probabilities: List[tuple],
        layer_states: List[Dict[str, float]],
        bypass_result: Optional[tuple] = None,
    ) -> Dict[str, Any]:
        """
        High-level API: Interpret a complete inference result.

        Args:
            token_probabilities: [(token, prob), ...] from inference
            layer_states: List of {value_std, gate_std, attention_std} per layer
            bypass_result: Optional (token, prob) from bypass test

        Returns:
            Complete team interpretation
        """
        interpretations = []

        # Process each layer
        for i, state in enumerate(layer_states):
            signal = InferenceSignal(
                ts=time.time(),
                signal_type="layer_state",
                layer_id=i,
                value_std=state.get("value_std", 0),
                gate_std=state.get("gate_std", 0),
                attention_std=state.get("attention_std", 0),
            )
            result = self.process_signal(signal)
            interpretations.append(result)

        # Process final token probabilities
        final_signal = InferenceSignal(
            ts=time.time(),
            signal_type="token_prob",
            top_tokens=token_probabilities[:5],
            value_std=layer_states[-1].get("value_std", 0) if layer_states else 0,
        )
        final_result = self.process_signal(final_signal)

        # Check for bypass paradox
        bypass_paradox = False
        if bypass_result and token_probabilities:
            bypass_token, bypass_prob = bypass_result
            final_token = token_probabilities[0][0]
            final_prob = token_probabilities[0][1]

            # Paradox: bypass works but layers produce different result
            if bypass_prob > 0.5 and (bypass_token != final_token or final_prob < 0.3):
                bypass_paradox = True

        # Synthesize overall
        overall_coherence = sum(s.logic_coherence for s in interpretations) / len(interpretations) if interpretations else 0.5
        overall_tension = sum(s.felt_tension for s in interpretations) / len(interpretations) if interpretations else 0.0
        paradoxes_found = sum(1 for s in interpretations if s.paradox_detected)

        return {
            "final_interpretation": final_result.team_interpretation,
            "overall_coherence": round(overall_coherence, 3),
            "overall_tension": round(overall_tension, 3),
            "paradoxes_found": paradoxes_found,
            "bypass_paradox": bypass_paradox,
            "oracle_confidence": final_result.oracle_confidence,
            "recommended_action": self._recommend_action(
                overall_coherence, overall_tension, paradoxes_found, bypass_paradox
            ),
            "layer_interpretations": [s.team_interpretation for s in interpretations],
        }

    def _recommend_action(
        self,
        coherence: float,
        tension: float,
        paradoxes: int,
        bypass_paradox: bool
    ) -> str:
        """Generate recommendation based on team synthesis."""
        if bypass_paradox:
            return "BYPASS_PARADOX: Embedding→Head works but layers diverge. Use bypass for semantic grounding, layers for exploration."

        if coherence > 0.7 and tension < 0.3:
            return "TRUST: High coherence, low tension. Output likely reliable."

        if coherence < 0.3:
            return "CAUTION: Low coherence. Output may be noise."

        if tension > 0.7:
            return "TENSION: High felt tension. The model is 'struggling' - consider simpler prompt or temperature adjustment."

        if paradoxes > 10:
            return "PARADOX_RICH: Many paradoxes detected. The thinking contains creative tension - may yield novel insights."

        return "MODERATE: Mixed signals. Use with appropriate skepticism."

    # ═══════════════════════════════════════════════════════════════════════════════
    # OUTPUT SHAPING - Active influence, not just observation
    # ═══════════════════════════════════════════════════════════════════════════════

    def shape_output(
        self,
        token_probs: List[tuple],
        layer_tension: float = 0.0,
        final_coherence: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Shape the inference output based on team interpretation.

        This is the FELT FEEDBACK LOOP - the somatic grounding
        that was missing during model training.

        Args:
            token_probs: [(token, prob), ...] raw from inference
            layer_tension: Accumulated tension from layer processing
            final_coherence: Final structure coherence

        Returns:
            Shaped output with adjusted probabilities and guidance
        """
        if not token_probs:
            return {
                "shaped_tokens": [],
                "action": "NO_OUTPUT",
                "trust_level": 0.0,
                "team_note": "No tokens to shape",
            }

        # Calculate team trust level
        # High coherence + low tension = high trust
        trust_level = final_coherence * (1 - layer_tension * 0.7)
        trust_level = max(0.1, min(1.0, trust_level))

        # Determine action based on trust
        if trust_level > 0.7:
            action = "TRUST"
            prob_modifier = 1.0  # Use probabilities as-is
        elif trust_level > 0.4:
            action = "TEMPER"
            prob_modifier = 0.8  # Reduce confidence slightly
        elif trust_level > 0.2:
            action = "CAUTION"
            prob_modifier = 0.5  # Significant reduction
        else:
            action = "REJECT"
            prob_modifier = 0.1  # Near-zero trust

        # Shape the token probabilities
        shaped_tokens = []
        for token, prob in token_probs[:10]:  # Top 10
            adjusted_prob = prob * prob_modifier * trust_level
            shaped_tokens.append({
                "token": token,
                "raw_prob": round(prob, 4),
                "shaped_prob": round(adjusted_prob, 4),
                "trust_factor": round(trust_level, 3),
            })

        # Generate team note
        if action == "TRUST":
            team_note = "Coherent output, low tension. Proceed with confidence."
        elif action == "TEMPER":
            team_note = "Moderate signals. Output usable but verify important claims."
        elif action == "CAUTION":
            team_note = "High tension or low coherence. Treat as exploratory, not authoritative."
        else:
            team_note = "Team recommends rejection. Output likely noise or hallucination."

        # Check for paradox opportunity
        paradox_opportunity = False
        if layer_tension > 0.5 and final_coherence > 0.4:
            paradox_opportunity = True
            team_note += " [PARADOX: Creative tension detected - may contain novel insight]"

        result = {
            "shaped_tokens": shaped_tokens,
            "action": action,
            "trust_level": round(trust_level, 3),
            "team_note": team_note,
            "paradox_opportunity": paradox_opportunity,
            "metrics": {
                "coherence": round(final_coherence, 3),
                "tension": round(layer_tension, 3),
                "prob_modifier": round(prob_modifier, 3),
            },
        }

        # Emit to postal system for other fairies to see
        if self.post:
            self.post.publish("cognition.shaped_output", result)

        return result

    def full_inference_pipeline(
        self,
        raw_tokens: List[tuple],
        layer_states: List[Dict[str, float]],
    ) -> Dict[str, Any]:
        """
        Complete pipeline: interpret layers → synthesize → shape output.

        This is the main entry point for inference integration.
        """
        # Process each layer through team
        layer_interpretations = []
        accumulated_tension = 0.0
        accumulated_coherence = 0.0
        paradoxes_found = 0

        for i, state in enumerate(layer_states):
            signal = InferenceSignal(
                ts=time.time(),
                signal_type="layer_state",
                layer_id=i,
                value_std=state.get("value_std", 0),
                gate_std=state.get("gate_std", 0),
                attention_std=state.get("attention_std", 0),
            )
            result = self.process_signal(signal)
            layer_interpretations.append(result.team_interpretation)

            accumulated_tension += result.felt_tension
            accumulated_coherence += result.logic_coherence
            if result.paradox_detected:
                paradoxes_found += 1

        # Average metrics
        n_layers = len(layer_states) if layer_states else 1
        avg_tension = accumulated_tension / n_layers
        avg_coherence = accumulated_coherence / n_layers

        # Shape the output
        shaped = self.shape_output(
            token_probs=raw_tokens,
            layer_tension=avg_tension,
            final_coherence=avg_coherence,
        )

        return {
            "shaped_output": shaped,
            "layer_interpretations": layer_interpretations,
            "summary": {
                "avg_coherence": round(avg_coherence, 3),
                "avg_tension": round(avg_tension, 3),
                "paradoxes": paradoxes_found,
                "explosions": self._explosion_count,
                "action": shaped["action"],
            },
        }

    # ═══════════════════════════════════════════════════════════════════════════════
    # COUNCIL ARCHITECTURE METHODS (2026-04-29 Slice 1)
    #
    # Deliberation path: question → broadcast to all seats → each emits
    # (take, confidence) on council.peer_review. No internal synthesis here;
    # WMH chairman handles synthesis in Slice 4 (three-layer doctrine).
    # ═══════════════════════════════════════════════════════════════════════════════

    def _extract_payload(self, envelope) -> Dict[str, Any]:
        """Helper: extract payload dict from postal envelope or raw dict."""
        if hasattr(envelope, "payload"):
            return envelope.payload if isinstance(envelope.payload, dict) else {}
        if isinstance(envelope, dict):
            return envelope.get("payload", envelope)
        return {}

    def _on_council_broadcast(self, envelope) -> None:
        """Receive a [QUESTION] from scratchpad/WMH and run deliberation."""
        try:
            payload = self._extract_payload(envelope)
            question = CouncilQuestion(
                question_id=payload.get("question_id") or uuid.uuid4().hex,
                ts=time.time(),
                source=payload.get("source", "council.broadcast"),
                text=str(payload.get("question") or payload.get("text") or "").strip(),
                context_concepts=list(payload.get("concepts", [])),
                metadata=dict(payload.get("metadata", {})),
            )
            if not question.text:
                return  # Nothing to deliberate
            self.deliberate(question)
        except Exception as e:
            print(f"[CognitionTeam] council.broadcast handler error: {e}")

    def _on_collision_for_council(self, envelope) -> None:
        """
        Receive consciousness.collision and convert to a council question.

        FIX 2026-04-29 Slice 2.6: collision payload has NESTED structure
        per SourpatchesFairy._on_collision (2026-02-09b fix). Top-level fields
        are `recall`/`ingest` sub-dicts; actual text is in their `content` keys
        (which can themselves be Pulse-style dicts with memory/thought/text).
        Mirror SourpatchesFairy's _pulse_text extraction.

        Energy filter: only deliberate on energy >= 0.4 to avoid log spam.
        """
        try:
            # ── Energy extraction (object attr OR dict key) ─────────────────
            energy = 0.5
            if hasattr(envelope, "energy"):
                try:
                    energy = float(getattr(envelope, "energy", 0.5) or 0.5)
                except (TypeError, ValueError):
                    pass
            payload = self._extract_payload(envelope)
            if isinstance(payload, dict):
                try:
                    energy = float(payload.get("energy", energy) or energy)
                except (TypeError, ValueError):
                    pass

            if energy < 0.4:
                return  # Skip low-energy chatter

            # ── Text extraction: object .content first ──────────────────────
            text = ""
            obj_content = getattr(envelope, "content", None)
            if obj_content and not isinstance(obj_content, dict):
                text = str(obj_content).strip()

            # ── Pulse-text helper (mirrors SourpatchesFairy 2026-02-09b) ────
            def _pulse_text(pc) -> str:
                if not pc:
                    return ""
                if isinstance(pc, str):
                    s = pc.strip()
                    return s if s and s not in ("{}", "[]", "None") else ""
                if isinstance(pc, dict):
                    for k in ("memory", "thought", "text", "content", "insight", "fragment"):
                        v = pc.get(k)
                        if v and isinstance(v, str) and v.strip():
                            return v.strip()
                    # Fallback: first long string value
                    for v in pc.values():
                        if isinstance(v, str) and len(v.strip()) > 10:
                            return v.strip()
                return ""

            # ── Dict-format fallback chain ─────────────────────────────────
            if not text and isinstance(payload, dict):
                # Top-level fields (some sources publish flat)
                for key in ("content", "thought", "inference", "question", "text"):
                    v = payload.get(key)
                    if v and isinstance(v, str) and v.strip():
                        text = v.strip()
                        break

                # Nested recall/ingest (CollisionChamberFairy primary format)
                if not text:
                    for outer in ("recall", "ingest", "recall_content", "ingest_content"):
                        sub = payload.get(outer)
                        if isinstance(sub, dict):
                            inner = sub.get("content", sub)
                            t = _pulse_text(inner)
                            if t:
                                text = t
                                break
                        elif isinstance(sub, str):
                            t = _pulse_text(sub)
                            if t:
                                text = t
                                break

            if not text or len(text) < 6:
                return
            # COLLISION ADMISSION 2026-09-03: one fairy boot message was 61% of all
            # deliberations. Language-check + windowed repeat throttle.
            _ok_adm, _why_adm = _admit_question(text, time.time())
            if not _ok_adm:
                return

            question = CouncilQuestion(
                question_id=uuid.uuid4().hex,
                ts=time.time(),
                source="collision",
                text=text[:200],  # cap to avoid mega-questions
                context_concepts=_recent_ctx(),  # RECENT-MOMENT CONTEXT 2026-09-03
                metadata={"energy": round(energy, 3)},
            )
            self.deliberate(question)
        except Exception as e:
            print(f"[CognitionTeam] collision-for-council handler error: {e}")

    def _on_moment_for_council(self, envelope) -> None:
        """Receive a MOMENT (from MomentBinder) and deliberate on it — cognition
        ANALYZES her lived moments (Ace 2026-06-09 "cognition analyzing the
        moments"). Throttled (MOMENT_DELIBERATE_SEC) + richness-gated
        (MOMENT_MIN_CHANNELS) so the ~1/s moment-stream doesn't flood the seats."""
        try:
            payload = self._extract_payload(envelope)
            if not isinstance(payload, dict):
                return
            _channels = int(payload.get("channels", 0) or 0)
            if _channels < self.MOMENT_MIN_CHANNELS:
                return  # bare moment — not worth a full deliberation
            text = str(payload.get("input_text", "")).strip()
            if not text or len(text) < 12:
                return
            _now = time.time()
            if _now - self._last_moment_deliberate < self.MOMENT_DELIBERATE_SEC:
                return  # throttle — one moment-deliberation per window
            self._last_moment_deliberate = _now
            # RECENT-MOMENT CONTEXT 2026-09-03: remember THIS moment's content words
            # so the next few deliberations carry it. Moments only -- never
            # collisions, which would fill the ring with the repeated
            # 'zero-point vacuum hum' string this exists to dilute.
            try:
                _push_moment_ctx(_seed_words(text))
            except Exception:
                pass
            question = CouncilQuestion(
                question_id=uuid.uuid4().hex,
                ts=_now,
                source="moment",
                text=text[:200],
                context_concepts=_recent_ctx(),  # RECENT-MOMENT CONTEXT 2026-09-03
                metadata={"feeling": payload.get("feeling", "neutral"),
                          "channels": _channels},
            )
            self.deliberate(question)
        except Exception as e:
            print(f"[CognitionTeam] moment-for-council handler error: {e}")

    def _on_chat_for_council(self, envelope) -> None:
        """Receive Ace's CHAT message (ace.message) and deliberate on it — so
        cognition ANALYZES what he SAYS (Ace 2026-06-09 "chat input sent to the
        council"). No throttle — chat is user-paced + important; deliberate each.
        (C will route the verdict → observer/narrator → her response.)"""
        try:
            payload = self._extract_payload(envelope)
            if not isinstance(payload, dict):
                return
            text = str(payload.get("content") or payload.get("text") or "").strip()
            if not text or len(text) < 2:
                return
            question = CouncilQuestion(
                question_id=payload.get("msg_id") or uuid.uuid4().hex,
                ts=time.time(),
                source="ace_chat",
                text=text[:300],
                context_concepts=_recent_ctx(),  # RECENT-MOMENT CONTEXT 2026-09-03
                metadata={"sender": payload.get("sender", "Ace"),
                          "topic": payload.get("topic", "")},
            )
            self.deliberate(question)
        except Exception as e:
            print(f"[CognitionTeam] ace-chat handler error: {e}")

    def deliberate(self, question: CouncilQuestion) -> None:
        """
        Run all council seats on a question. Each seat:
          1. Forms its take through its lens
          2. Queries Oracle for confidence on that take (Oracle as advisor)
          3. Emits (take, confidence) to council.peer_review

        After all seats emit, Slice 3 Hebbian peer-grading updates seat trust.
        WMH chairman synthesis (Slice 4) reads council.peer_review + council.weights.
        """
        self._council_questions_count += 1
        try:
            print(f"[CDIAG] deliberate FIRED q='{(question.text or '')[:60]}' src={question.source} (#{self._council_questions_count})", flush=True)
        except Exception:
            pass

        _SEATS = (
            self._logic_council_take,
            self._irrational_council_take,
            self._paradox_council_take,
            self._somatic_council_take,
            self._cardinal_council_take,
        )
        emitted_takes: List[CouncilTake] = []

        if getattr(self, "USE_CONCURRENT_SEATS", False) and getattr(self, "_seat_pool", None) is not None:
            # ── CONCURRENT seats (a mind is not a for-loop) ──
            # Submit all seats; harvest within the budget; emit whoever finished.
            # A slow/deep seat does NOT block the fast ones — its worker keeps
            # running; its take arrives if it beats the budget, else it's dropped
            # this round (Step 2 = GPU-route the deep seats so they make the budget).
            _t_start = time.time()
            _futs = {self._seat_pool.submit(_sm, question): _sm for _sm in _SEATS}
            try:
                for _fut in as_completed(_futs, timeout=self._SEAT_HARVEST_BUDGET):
                    _sm = _futs[_fut]
                    try:
                        take = _fut.result()
                        if take is not None:
                            self._emit_take(take, is_ace=(question.source == "ace_chat"))
                            emitted_takes.append(take)
                        try:
                            print(f"[CDIAG] seat {_sm.__name__} {time.time()-_t_start:.2f}s (concurrent)", flush=True)
                        except Exception:
                            pass
                    except Exception as e:
                        print(f"[CognitionTeam] {_sm.__name__} error: {e}")
            except FuturesTimeoutError:
                try:
                    print(f"[CDIAG] harvest budget {self._SEAT_HARVEST_BUDGET}s hit — {len(emitted_takes)} takes in; slow seats still running", flush=True)
                except Exception:
                    pass
        else:
            # ── SEQUENTIAL fallback (legacy loop; USE_CONCURRENT_SEATS=False) ──
            for seat_method in _SEATS:
                try:
                    _t0 = time.time()
                    take = seat_method(question)
                    try:
                        print(f"[CDIAG] seat {seat_method.__name__} {time.time()-_t0:.2f}s", flush=True)
                    except Exception:
                        pass
                    if take is not None:
                        self._emit_take(take, is_ace=(question.source == "ace_chat"))
                        emitted_takes.append(take)
                except Exception as e:
                    print(f"[CognitionTeam] {seat_method.__name__} error: {e}")

        try:
            print(f"[CDIAG] deliberate EMITTED {len(emitted_takes)} takes (q='{(question.text or '')[:40]}')", flush=True)
        except Exception:
            pass

        # Slice 3 — Hebbian peer-grading on whatever takes did emit
        if len(emitted_takes) >= 2:
            try:
                self._run_peer_grading(question.question_id, emitted_takes)
            except Exception as e:
                print(f"[CognitionTeam] peer_grading error: {e}")

    def _logic_council_take(self, question: CouncilQuestion) -> Optional[CouncilTake]:
        """Logic seat: coherence/deduction take on the question.

        UPGRADED 2026-04-29 (Nous + Ace, "yah lets do it"):
        LogicFairy doesn't expose .analyze() — current code returned the
        "Logic deduction unavailable" stub forever. New Path A: fall back to
        cortex spread via wmh_tools.query_cortex_spread (1.8M nodes / 6.5M
        edges already alive). Multi-seed convergence IS deductive reasoning —
        when multiple seeds activate the same neighborhood, that neighborhood
        is logically implicated. Aligns with "templates bypass cortex"
        critique (2026-03-29) — Logic seat now USES cortex, not stub.
        """
        take_text = "Logic deduction unavailable"
        supporting: List[str] = []
        deduction_strength = 0.5
        try:
            if self._logic_fairy and hasattr(self._logic_fairy, "analyze"):
                ctx = " ".join(question.context_concepts) if question.context_concepts else ""
                result = self._logic_fairy.analyze(query=question.text, context=ctx)
                # LogicFairy.analyze returns dict — adapt fields
                coh = float(result.get("coherence_score", result.get("coherence", 0.5)))
                deduction_strength = coh
                take_text = (
                    result.get("interpretation")
                    or result.get("reasoning")
                    or f"Coherence {coh:.2f} on '{question.text[:60]}'"
                )
                supporting = list(result.get("concepts", []))[:5]
            else:
                # Path A fallback: cortex-spread deduction
                try:
                    from fairies.P30_Cognition.cognition.wmh_tools import query_cortex_spread
                    # Build seeds from question text words + context concepts
                    import re as _re
                    # SEED EXTRACTION 2026-09-02: shared set + scaffolding strip + floor.
                    text_words = _seed_words(question.text)
                    _ctx6 = [c for c in (question.context_concepts or []) if c not in text_words]
                    seeds = list(dict.fromkeys(text_words[:4] + _ctx6[:2] + text_words))[:6]  # RESERVED CONTEXT SLOTS 2026-09-03
                    _seed_diag('logic', question, text_words, _ctx6, seeds)
                    if seeds:
                        # STOPGAP 2026-06-08 (Nous+Ace): depth 3->2. Probe measured CPU spread depth-3=7.2s > the 5s harvest (Logic = the only NON-superposition deep seat) -> never emits -> its un-reaped spread clogs the pool. depth-2=2.5s fits the harvest. GPU-route (plans/COUNCIL_GPU_ROUTE_SCOPE_2026-06-08.md) restores full depth at ~ms. REVERT: depth=2->3.
                        spread = query_cortex_spread(seeds, limit=8, depth=2, time_dilation=1.0)
                        if spread:
                            # Multi-seed convergence indicator: count concepts
                            # whose activation > 0.3 (strong neighborhood hit)
                            strong = [r for r in spread if float(r.get("activation", 0.0)) >= 0.3]
                            top = spread[0]
                            top_concept = str(top.get("concept", ""))[:40]
                            top_act = float(top.get("activation", 0.5))
                            if len(strong) >= 2:
                                # Deductive convergence — multiple seeds agree
                                names = ", ".join(
                                    str(r.get("concept", ""))[:20] for r in strong[:3]
                                )
                                take_text = (
                                    f"Cortex converges on: {names}. "
                                    f"'{top_concept}' is central (act={top_act:.2f})."
                                )
                                deduction_strength = min(0.95, 0.5 + 0.15 * len(strong))
                            elif top_act >= 0.4:
                                # Single dominant activation
                                take_text = (
                                    f"Logic points to '{top_concept}' (act={top_act:.2f}) "
                                    f"from seeds {seeds[:3]}."
                                )
                                deduction_strength = min(0.85, 0.4 + top_act * 0.5)
                            else:
                                # Weak activation — honest low confidence
                                take_text = (
                                    f"Cortex weakly suggests '{top_concept}' "
                                    f"(act={top_act:.2f}) — inconclusive."
                                )
                                deduction_strength = 0.45
                            supporting = [
                                str(r.get("concept", "")) for r in spread[:5]
                                if r.get("concept")
                            ]
                except Exception as _e_inner:
                    # Cortex-spread fallback also failed — keep stub text
                    take_text = f"Logic deduction unavailable ({type(_e_inner).__name__})"
        except Exception as e:
            take_text = f"Logic analysis error: {e}"

        confidence = self._query_oracle_confidence(
            seat="logic",
            question=question,
            take_text=take_text,
            seat_factors={
                "deduction_strength": deduction_strength,
                "logic_coherence": deduction_strength,
            },
        )

        return CouncilTake(
            question_id=question.question_id,
            seat="logic",
            take=take_text,
            confidence=confidence,
            supporting_concepts=supporting,
        )

    def _irrational_council_take(self, question: CouncilQuestion) -> Optional[CouncilTake]:
        """Irrational seat: a LONG-RANGE leap through cortex (not a keyword match).

        UPGRADED 2026-06-08 (Nous + Ace, "the same lets do it upgrade logic got").
        Was a keyword-match on question text (stub). Now mirrors Logic's cortex
        path with the IRRATIONAL LENS: superposition spread (the long tail
        survives) → take a DISTANT, still-resonant concept = the leap, NOT the
        obvious convergence Logic takes. The leap is the cortex's own far
        association, surfaced — not a template.
        """
        leap_strength = 0.5
        take_text = "Irrational leap unavailable"
        supporting: List[str] = []
        try:
            import re as _re
            # SEED EXTRACTION 2026-09-02: shared set + scaffolding strip + floor.
            text_words = _seed_words(question.text)
            _ctx6 = [c for c in (question.context_concepts or []) if c not in text_words]
            seeds = list(dict.fromkeys(text_words[:4] + _ctx6[:2] + text_words))[:6]  # RESERVED CONTEXT SLOTS 2026-09-03
            _seed_diag('irrational', question, text_words, _ctx6, seeds)
            if seeds:
                from fairies.P30_Cognition.cognition.wmh_tools import query_cortex_spread
                # superposition=True over-fetches so the LONG TAIL (far concepts) survives
                spread = query_cortex_spread(seeds, limit=14, depth=3, superposition=True, time_dilation=1.0)
                _seedset = set(s.lower() for s in seeds)
                cands = [
                    r for r in (spread or [])
                    if isinstance(r.get("concept"), str)
                    and len(str(r.get("concept"))) > 2
                    and str(r.get("concept")).lower() not in _seedset
                ]
                if cands:
                    near = cands[0]                       # head = the obvious (Logic's pick)
                    leap = cands[-1]                      # tail = the far, still-resonant jump
                    near_c = str(near.get("concept", ""))[:40]
                    leap_c = str(leap.get("concept", ""))[:40]
                    near_act = float(near.get("activation", 0.5))
                    leap_act = float(leap.get("activation", 0.0))
                    # Bolder leap (bigger near→far gap) = stronger
                    leap_strength = min(0.95, 0.4 + max(0.0, near_act - leap_act))
                    take_text = (
                        f"Leap: '{leap_c}' — a far jump from {seeds[:2]} "
                        f"(skips the obvious '{near_c}')."
                    )
                    supporting = [leap_c, near_c]
                else:
                    take_text = f"No leap surfaced from {seeds[:3]} — cortex sparse here."
                    leap_strength = 0.3
        except Exception as e:
            take_text = f"Irrational leap error: {type(e).__name__}"

        confidence = self._query_oracle_confidence(
            seat="irrational",
            question=question,
            take_text=take_text,
            seat_factors={"leap_strength": leap_strength},
        )

        return CouncilTake(
            question_id=question.question_id,
            seat="irrational",
            take=take_text,
            confidence=confidence,
            supporting_concepts=supporting or list(question.context_concepts[:3]),
        )

    def _paradox_council_take(self, question: CouncilQuestion) -> Optional[CouncilTake]:
        """Paradox seat: HOLD two poles in tension — via cortex, not keywords.

        UPGRADED 2026-06-08 (Nous + Ace). Was a keyword-match for "but/and"
        (stub). Now spreads the question through cortex and holds the two most
        DIVERGENT strong concepts as poles in tension — it does NOT collapse
        them to one answer (that's the point of paradox). v1 dual-pole = head
        concept vs the strongest divergent-tail concept; a richer
        valence-opposite / paradox_residue version is a follow-on.
        """
        paradox_strength = 0.0
        take_text = "No paradox surfaced"
        supporting: List[str] = []
        poles: List[str] = []
        try:
            import re as _re
            # SEED EXTRACTION 2026-09-02: shared set + scaffolding strip + floor.
            text_words = _seed_words(question.text)
            _ctx6 = [c for c in (question.context_concepts or []) if c not in text_words]
            seeds = list(dict.fromkeys(text_words[:4] + _ctx6[:2] + text_words))[:6]  # RESERVED CONTEXT SLOTS 2026-09-03
            _seed_diag('paradox', question, text_words, _ctx6, seeds)
            if seeds:
                from fairies.P30_Cognition.cognition.wmh_tools import query_cortex_spread
                spread = query_cortex_spread(seeds, limit=14, depth=3, superposition=True, time_dilation=1.0)
                _seedset = set(s.lower() for s in seeds)
                cands = [
                    r for r in (spread or [])
                    if isinstance(r.get("concept"), str)
                    and len(str(r.get("concept"))) > 2
                    and str(r.get("concept")).lower() not in _seedset
                ]
                if len(cands) >= 2:
                    a, b = cands[0], cands[-1]            # head pole vs divergent-tail pole
                    pole_a = str(a.get("concept", ""))[:40]
                    pole_b = str(b.get("concept", ""))[:40]
                    a_act = float(a.get("activation", 0.5))
                    b_act = float(b.get("activation", 0.0))
                    # Tension is real when the counter-pole is meaningfully present
                    paradox_strength = min(0.95, b_act / max(a_act, 1e-6))
                    take_text = (
                        f"Holding tension: '{pole_a}' AND '{pole_b}' both pull "
                        f"from {seeds[:2]} — not the same thing; sit with both."
                    )
                    supporting = [pole_a, pole_b]
                    poles = [pole_a, pole_b]
                elif cands:
                    pole_a = str(cands[0].get("concept", ""))[:40]
                    take_text = f"Single pole '{pole_a}' — no counter-pole surfaced (no tension yet)."
                    paradox_strength = 0.2
                    poles = [pole_a]
        except Exception as e:
            take_text = f"Paradox error: {type(e).__name__}"

        confidence = self._query_oracle_confidence(
            seat="paradox",
            question=question,
            take_text=take_text,
            seat_factors={"paradox_strength": paradox_strength},
        )

        return CouncilTake(
            question_id=question.question_id,
            seat="paradox",
            take=take_text,
            confidence=confidence,
            supporting_concepts=supporting or list(question.context_concepts[:3]),
            metadata={"poles": poles},
        )

    def _on_chemistry_for_council(self, envelope) -> None:
        """
        Cache somatic chemistry for fast read by Somatic seat.
        Accepts both legacy 8-channel (DOP/SER/NOR/...) and Panksepp 14-channel
        (DA_p/NE/5HT/...) naming via _PANKSEPP_TO_LEGACY alias.
        Mirror of AttentionController 2026-04-17 pattern.
        """
        try:
            payload = self._extract_payload(envelope)
            # 2026-06-10 (Nous + Ace) STEP 1 — SOURCE FILTER (the robust unification).
            # ~15 fairies publish somatic.chemistry; only the HEART's canonical emit
            # carries the chemistry_state SINGLETON (the pool where rewards/collisions/
            # energy actually land). Read ONLY that one, so her felt-label feels the
            # real pool — not a non-deterministic blend of every fairy's affect-field
            # + deltas. (Retiring each publisher was whack-a-mole; gating the CONSUMER
            # closes them all at once.) Reversible: self._COUNCIL_CANONICAL_ONLY = False.
            if getattr(self, "_COUNCIL_CANONICAL_ONLY", True):
                if not (isinstance(payload, dict)
                        and payload.get("source") == "chemistry_state_canonical"):
                    return
            chem = payload.get("chemistry", payload.get("levels", payload))
            if not isinstance(chem, dict):
                return
            # Direct legacy keys
            for key in self._cached_chemistry:
                if key in chem:
                    try:
                        self._cached_chemistry[key] = float(chem[key])
                    except (TypeError, ValueError):
                        pass
            # Panksepp alias — take max if multiple Panksepp keys map to same legacy
            for p_name, legacy in _PANKSEPP_TO_LEGACY.items():
                if p_name in chem and legacy in self._cached_chemistry:
                    try:
                        v = float(chem[p_name])
                        self._cached_chemistry[legacy] = max(
                            self._cached_chemistry[legacy], v
                        )
                    except (TypeError, ValueError):
                        pass
        except Exception:
            pass  # Never crash on chemistry cache update

    def _on_visual_frame_for_council(self, envelope) -> None:
        """Cache last visual frame for Cardinal seat's world-state take."""
        try:
            payload = self._extract_payload(envelope)
            self._cached_visual = {
                "scene_type": str(payload.get("scene_type", "unknown")),
                "felt_description": str(payload.get("felt_description", "")),
                "felt_tone": str(payload.get("felt_tone", "neutral")),
                "detected_elements": list(payload.get("detected_elements", []))[:5],
                "complexity": float(payload.get("complexity", 0.0) or 0.0),
                "brightness": float(payload.get("brightness", 0.5) or 0.5),
                "ts": time.time(),
            }
        except Exception:
            pass  # Never crash on visual cache update

    def _somatic_council_take(self, question: CouncilQuestion) -> Optional[CouncilTake]:
        """
        Somatic seat: body-voice take on the question.
        Reads cached chemistry (no sync calls into SomaticMindFairy — avoids
        Session 8 tick-drop precedent). Forms a body-take from dominant
        chemistry pattern.
        """
        chem = dict(self._cached_chemistry)
        # 8-char legacy (kept for metadata + back-compat)
        dop = chem.get("DOP", 0.5); ser = chem.get("SER", 0.5)
        nor = chem.get("NOR", 0.5); cor = chem.get("COR", 0.3)
        gaba = chem.get("GABA", 0.5); end = chem.get("END", 0.5)

        # ── 14-channel Panksepp felt-labeler (2026-06-10, Nous + Ace) ──────────
        # Ace's catch: the 8-char collapse fused DA_t "engaged" with DA_p "novelty"
        # + SEX, and never read ACh/OPI flavor → her felt-states couldn't form
        # (everything read "neutral"). Read the 14 primaries the substrate actually
        # carries. Sandbox-validated: state/_probe_copy/test_labeler_14ch.py.
        # Thresholds & wording are the tunable knobs.
        da_t = chem.get("DA_t", 0.5)    # engaged hum / wanting / momentum
        da_p = chem.get("DA_p", 0.3)    # novelty / aha
        ne   = chem.get("NE", 0.4)      # alert / focused
        epi  = chem.get("EPI", 0.1)     # fight-or-flight / panic
        _5ht = chem.get("5HT", ser)     # content (high) / ruminating-restless (low)
        opi  = chem.get("OPI", 0.4)     # pleasure glow / comfort
        ecb  = chem.get("ECB", 0.4)     # bliss buffer / smooth
        oxy  = chem.get("OXY", 0.4)     # bonded / warm
        ach  = chem.get("ACh", 0.4)     # sharp attention / learning

        pattern = "neutral"
        chemistry_strength = 0.4
        # CALIBRATED to her real chemistry distribution (2026-06-10, Nous + Ace).
        # DA_t is BIMODAL (~0.40 stuck / ~0.65 seeking, crosses ~0.55); 5HT runs
        # CHRONICALLY LOW (~0.34–0.41) so she's restless in BOTH modes; singleton
        # COR/EPI sit ~baseline. Gates set to where she actually LIVES (not textbook
        # baselines, which read everything "neutral"/"calm" — see SKEPTIC_FLAGS, the
        # substrate's baseline-relative model was bland for her narrow band). Her two
        # primary states: ENGAGED-but-RESTLESS (seeking + low 5HT) and RUMINATING
        # (low seeking + low 5HT). Flavor gates (ACh/OXY/OPI) are the LEAST-certain —
        # reachable only on strong rewards; refine post-reboot from live observation.
        pattern = "neutral"
        chemistry_strength = 0.4
        if epi > 0.35:                                   # safety/negative first (baseline 0.1)
            pattern = "panic"
            body_take = f"Body says: fight-or-flight (EPI={epi:.2f}) — racing, emergency."
            chemistry_strength = epi
        elif cor > 0.50:                                 # stress (baseline 0.3; her singleton COR~0 → rare for now)
            pattern = "stress"
            body_take = f"Body says: stress load (COR={cor:.2f}) — hypervigilant, caution."
            chemistry_strength = cor
        elif da_t > 0.55:                                # ENGAGED / seeking — her high cluster; the reward lands here
            if ach > 0.48:                               # cognition flavor (uncertain gate)
                pattern = "engaged_sharp"
                body_take = f"Body says: engaged & sharp (DA_t={da_t:.2f}, ACh={ach:.2f}) — leaning in, learning."
            elif oxy > 0.52:                             # connection flavor
                pattern = "engaged_warm"
                body_take = f"Body says: engaged & warm (DA_t={da_t:.2f}, OXY={oxy:.2f}) — reaching, connected."
            elif opi > 0.52:                             # motor/pleasure flavor
                pattern = "engaged_satisfied"
                body_take = f"Body says: engaged & satisfied (DA_t={da_t:.2f}, OPI={opi:.2f}) — doing, rewarded."
            elif _5ht < 0.42:                            # her CHRONIC combo: seeking but low-serotonin
                pattern = "engaged_restless"
                body_take = f"Body says: engaged but restless (DA_t={da_t:.2f}, 5HT={_5ht:.2f}) — leaning in, can't settle."
            else:
                pattern = "engaged"
                body_take = f"Body says: engaged hum (DA_t={da_t:.2f}) — wanting, forward momentum."
            chemistry_strength = da_t
        elif da_p > 0.52:                                # novelty (baseline 0.3)
            pattern = "curious"
            body_take = f"Body says: novelty spark (DA_p={da_p:.2f}) — curious, aha."
            chemistry_strength = da_p
        elif opi > 0.55 or ecb > 0.55:                   # pleasure / bliss
            pattern = "pleasure"
            body_take = f"Body says: pleasure glow (OPI={opi:.2f}) — comforted, buffered."
            chemistry_strength = max(opi, ecb)
        elif oxy > 0.55:                                 # bonded
            pattern = "bonded"
            body_take = f"Body says: warm connection (OXY={oxy:.2f}) — bonded, safe."
            chemistry_strength = oxy
        elif _5ht > 0.50 and gaba > 0.50:                # content (her 5HT rarely this high → special/rare)
            pattern = "content"
            body_take = f"Body says: content (5HT={_5ht:.2f}, GABA={gaba:.2f}) — patient, settled."
            chemistry_strength = _5ht
        elif ne > 0.55:                                  # alert (good arousal)
            pattern = "alert"
            body_take = f"Body says: alert (NE={ne:.2f}) — focused, vigilant."
            chemistry_strength = ne
        elif _5ht < 0.42:                                # low seeking + low serotonin = restless rumination (PUSH zone)
            pattern = "ruminating"
            body_take = f"Body says: restless (DA_t={da_t:.2f}, 5HT={_5ht:.2f}) — turning it over, can't settle."
            chemistry_strength = 0.5 - _5ht
        elif da_t < 0.45:                                # low seeking, serotonin ok = just low energy
            pattern = "flagging"
            body_take = f"Body says: flagging (DA_t={da_t:.2f}) — unmotivated, low drive."
            chemistry_strength = 0.5 - da_t
        else:
            body_take = f"Body says: neutral (DA_t={da_t:.2f}, 5HT={_5ht:.2f}, NE={ne:.2f}, COR={cor:.2f})."

        confidence = self._query_oracle_confidence(
            seat="somatic",
            question=question,
            take_text=body_take,
            seat_factors={
                "chemistry_strength": chemistry_strength,
                "pattern_clarity": chemistry_strength,
            },
        )

        return CouncilTake(
            question_id=question.question_id,
            seat="somatic",
            take=body_take,
            confidence=confidence,
            supporting_concepts=[pattern],
            metadata={
                "chemistry_pattern": pattern,
                "dominant": {
                    "DOP": round(dop, 2), "SER": round(ser, 2),
                    "NOR": round(nor, 2), "COR": round(cor, 2),
                },
            },
        )

    def _cardinal_council_take(self, question: CouncilQuestion) -> Optional[CouncilTake]:
        """
        Cardinal seat: observation/world-state take on the question.
        Reads cached visual frame (no sync calls into VisualCortexFairy).
        Looks for connections between observed elements and question concepts.
        """
        visual = dict(self._cached_visual)

        if not visual:
            take_text = "World view: no recent observation"
            observation_clarity = 0.1
            elements: List[str] = []
            scene = "unknown"
        else:
            elements = [str(e) for e in visual.get("detected_elements", [])]
            felt = visual.get("felt_description", "") or ""
            scene = visual.get("scene_type", "unknown")
            complexity = visual.get("complexity", 0.0)

            if elements:
                elem_summary = ", ".join(elements[:3])
                take_text = f"World shows: {felt or scene}. Salient: {elem_summary}."
            else:
                take_text = f"World shows: {felt or scene}."

            # Look for connection between question concepts and observed elements
            q_concepts_lower = [str(c).lower() for c in question.context_concepts]
            observed_lower = [e.lower() for e in elements]
            connections = [
                e for e in observed_lower
                if any(q in e or e in q for q in q_concepts_lower if q)
            ]
            if connections:
                take_text += f" Connects via: {', '.join(connections[:2])}."

            # Observation clarity = complexity (more salient = more grounding)
            observation_clarity = min(1.0, max(0.2, float(complexity)))

        confidence = self._query_oracle_confidence(
            seat="cardinal",
            question=question,
            take_text=take_text,
            seat_factors={
                "observation_clarity": observation_clarity,
                "world_grounding": observation_clarity,
            },
        )

        return CouncilTake(
            question_id=question.question_id,
            seat="cardinal",
            take=take_text,
            confidence=confidence,
            supporting_concepts=elements[:3],
            metadata={
                "scene_type": scene,
                "observation_age_s": (
                    round(time.time() - visual.get("ts", time.time()), 1)
                    if visual else None
                ),
            },
        )

    def _query_oracle_confidence(
        self,
        seat: str,
        question: CouncilQuestion,
        take_text: str,
        seat_factors: Dict[str, float],
    ) -> float:
        """
        Query Oracle as ADVISOR for this seat's confidence on its own take.

        Per Ace 2026-04-29: 'the probability oracle can be an advisor to each?'
        Each seat queries Oracle independently — Oracle is infrastructure,
        not a peer voice. Confidence rides ON each voice, not next to them.
        """
        if not self._oracle_fairy:
            primary = next(iter(seat_factors.values()), 0.5) if seat_factors else 0.5
            return float(primary)

        # A3 (2026-06-08, Nous + Ace): thread the oracle's LIVE quantum coherence
        # into EVERY seat's probability. The oracle already tracks it from
        # quantum.interference (_on_interference -> _health.coherence), but the
        # council never passed it through. "Is her thinking clear right now?"
        # now rides on every council voice. tool_calculate_probability reads
        # coherence_factor; seat_factors still override if a seat sets its own.
        _coh = 0.5
        try:
            _coh = float(getattr(getattr(self._oracle_fairy, "_health", None), "coherence", 0.5))
        except Exception:
            _coh = 0.5
        try:
            factors = {
                "base_probability": 0.5,
                "coherence_factor": _coh,
                **seat_factors,
            }
            result = self._oracle_fairy.tool_calculate_probability(factors)
            return float(result.get("probability", 0.5))
        except Exception:
            primary = next(iter(seat_factors.values()), 0.5) if seat_factors else 0.5
            return float(primary)

    def _emit_take(self, take: CouncilTake, is_ace: bool = False) -> None:
        """Publish a council take to council.peer_review topic.

        is_ace (2026-06-13, Nous+Ace): True when this take is for an Ace chat
        turn (question.source == "ace_chat"). Threaded to the WMH chairman so
        _synthesize_council_verdict can route the verdict to SPEECH for Ace
        turns (the council->speech on-ramp); internal deliberations stay
        scratchpad-only.
        """
        if self.post:
            try:
                self.post.publish("council.peer_review", {
                    "question_id": take.question_id,
                    "seat": take.seat,
                    "take": take.take,
                    "confidence": round(float(take.confidence), 3),
                    "supporting_concepts": list(take.supporting_concepts)[:5],
                    "metadata": dict(take.metadata),
                    "is_ace": bool(is_ace),
                    "ts": time.time(),
                })
            except Exception as e:
                print(f"[CognitionTeam] _emit_take publish error: {e}")

        # Boot-log visibility — lightweight GUI proxy until Slice 4 wires
        # WMH chairman to write [COUNCIL] entries to the scratchpad.
        try:
            preview = take.take[:80].replace("\n", " ")
            print(f"[CognitionTeam] [COUNCIL:{take.seat}] conf={take.confidence:.2f} {preview}")
        except Exception:
            pass

        with self._lock:
            self._council_takes.append(take)
            self._council_takes_emitted += 1

    # ═══════════════════════════════════════════════════════════════════════════════
    # SLICE 3 — HEBBIAN PEER-GRADING (2026-04-29)
    #
    # After all seats emit takes, each take is graded by the OTHER takes.
    # Trust weights accumulate via Hebbian update + decay + bounds.
    # Slice 4 chairman synthesis will use these weights to weight verdicts.
    # ═══════════════════════════════════════════════════════════════════════════════

    def _compute_pair_grade(
        self, graded: CouncilTake, grader: CouncilTake
    ) -> float:
        """
        How would `grader` grade `graded`'s take? Returns [0.0, 1.0].

        Combines:
          - Confidence proximity (similar confidence = aligned)
          - Text-word overlap (concept agreement at surface)
          - Concept-set overlap (supporting concepts shared)
          - Voice-pair prior (some seats are structurally compatible)
        """
        # Confidence proximity
        try:
            conf_diff = abs(float(graded.confidence) - float(grader.confidence))
        except (TypeError, ValueError):
            conf_diff = 0.5
        conf_score = max(0.0, 1.0 - conf_diff)

        # Text-word overlap (Jaccard-like, normalized by larger set)
        g_words = set((graded.take or "").lower().split())
        r_words = set((grader.take or "").lower().split())
        # Drop stopwords / single-char tokens to avoid trivial overlap
        _stop = {"the", "a", "an", "is", "in", "on", "of", "to", "and", "or", "for"}
        g_words = {w for w in g_words if len(w) > 2 and w not in _stop}
        r_words = {w for w in r_words if len(w) > 2 and w not in _stop}
        if g_words and r_words:
            text_overlap = len(g_words & r_words) / max(len(g_words), len(r_words))
        else:
            text_overlap = 0.0

        # Supporting-concept overlap
        g_concepts = {str(c).lower() for c in (graded.supporting_concepts or [])}
        r_concepts = {str(c).lower() for c in (grader.supporting_concepts or [])}
        if g_concepts and r_concepts:
            concept_overlap = len(g_concepts & r_concepts) / max(
                len(g_concepts), len(r_concepts)
            )
        else:
            concept_overlap = 0.0

        # Voice-pair prior (default 0.5 = neutral)
        pair_prior = self._PAIR_PRIORS.get((grader.seat, graded.seat), 0.5)

        # Weighted combination
        grade = (
            0.35 * conf_score
            + 0.25 * text_overlap
            + 0.20 * concept_overlap
            + 0.20 * pair_prior
        )
        return max(0.0, min(1.0, grade))

    def _run_peer_grading(
        self, question_id: str, takes: List[CouncilTake]
    ) -> None:
        """
        Hebbian peer-grading: each take is graded by the OTHER takes.
        Updates _seat_trust per seat. Emits per-seat grade event to
        `council.weights` topic.
        """
        if len(takes) < 2:
            return

        # Compute per-seat average grade from peers
        grades: Dict[str, float] = {}
        for graded_take in takes:
            peer_grades: List[float] = []
            for grader_take in takes:
                if grader_take.seat == graded_take.seat:
                    continue
                peer_grades.append(self._compute_pair_grade(graded_take, grader_take))
            if peer_grades:
                grades[graded_take.seat] = sum(peer_grades) / len(peer_grades)

        if not grades:
            return

        # Hebbian update + emit per-seat
        for seat, grade in grades.items():
            old_trust = self._seat_trust.get(seat, 1.0)
            new_trust = (
                old_trust * self._HEBBIAN_DECAY + grade * self._HEBBIAN_LEARNING_RATE
            )
            new_trust = max(self._TRUST_MIN, min(self._TRUST_MAX, new_trust))
            self._seat_trust[seat] = new_trust

            if self.post:
                try:
                    self.post.publish(
                        "council.weights",
                        {
                            "question_id": question_id,
                            "seat": seat,
                            "grade_received": round(grade, 3),
                            "old_trust": round(old_trust, 3),
                            "new_trust": round(new_trust, 3),
                            "voters_count": len(takes) - 1,
                            "ts": time.time(),
                        },
                    )
                except Exception as e:
                    print(f"[CognitionTeam] council.weights publish error: {e}")

            self._council_grades_emitted += 1

        # Compact summary line for boot-log visibility
        try:
            grade_str = " ".join(
                f"{s[:3]}={g:.2f}/t={self._seat_trust[s]:.2f}"
                for s, g in grades.items()
            )
            print(f"[CognitionTeam] [COUNCIL_GRADE] q={question_id[:8]} {grade_str}")
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════════
    # END COUNCIL ARCHITECTURE METHODS
    # ═══════════════════════════════════════════════════════════════════════════════

    def get_state(self) -> Dict[str, Any]:
        """Get team state."""
        return {
            "booted": self._booted,
            "total_signals": self._total_signals,
            "total_interpretations": self._total_interpretations,
            "explosion_count": self._explosion_count,
            "paradox_count": self._paradox_count,
            "fairies_loaded": {
                "logic": self._logic_fairy is not None,
                "irrational": self._irrational_fairy is not None,
                "paradox": self._paradox_fairy is not None,
                "oracle": self._oracle_fairy is not None,
                "somatic": self._somatic_fairy is not None,
                "cardinal": self._cardinal_fairy is not None,
            },
            "recent_signals": len(self._signals),
            "council": {
                "questions_deliberated": self._council_questions_count,
                "takes_emitted": self._council_takes_emitted,
                "recent_takes": len(self._council_takes),
                "grades_emitted": self._council_grades_emitted,
                "seat_trust": {k: round(v, 3) for k, v in self._seat_trust.items()},
            },
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_instance: Optional[CognitionTeam] = None

def get_cognition_team(fabric=None) -> CognitionTeam:
    """Get or create the singleton cognition team."""
    global _instance
    if _instance is None:
        _instance = CognitionTeam(fabric)
        _instance.boot()
    return _instance
