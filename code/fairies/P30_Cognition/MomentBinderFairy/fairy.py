"""
MomentBinderFairy — Triple Helix Moment Synthesis (Wave 1: Strands Sync)

The Möbius loop's input layer. Subscribes to four substrate channels
(somatic / sensory.visual / sensory.audio / cognitive thought) and emits
coherent moment nodes to cortex by binding strands at one timestamp.

WAVE 1 (this file): plumbing only.
- Per-channel ring buffers (recent N events each)
- Heartbeat-driven moment synthesis (~1 s cadence)
- tracer_id propagated through context_tags (manifold field population
  is Wave 2 work — requires touching multiple existing bind sites)
- Publishes cortex.bind with input_text (cognitive) + vision/audio
  features + feeling (somatic) + tracer/ts/channels context_tags

WAVE 2 (later, separate ship):
- AER mixture as edge attention weight
- Cluster-aware ingest/recall (resurrects 2026-02-02 Russian Doll API)
- tracer_id field on manifold nodes at ALL bind sites

Doctrine: project_mobius_moment_completeness_energy_keystone.md
- Cortex-resident closure: writes to cortex (everything closes through cortex)
- Triple Helix Memory: moment as primitive recording unit
- Multimodal transformer with somatic weights: this is the channel-sync layer
"""

from __future__ import annotations

import sys
import time
import threading
import uuid
from pathlib import Path
from collections import deque
from typing import Any, Deque, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy



# ── TEMPLATE FILLER 2026-09-02 (Nous + Ace) ──────────────────────────────────
# LanguageFairy composes from 14 fixed _INNER_PATTERNS. Their scaffolding is her
# FORMATTING, not her thinking, and it was being minted into the cortex as concepts
# via cortex.bind. These are the literal openers, matched at the START only so a
# sentence that merely CONTAINS one of these words is untouched.
_TEMPLATE_OPENERS = (
    "maybe i should look into",
    "there's this",
    "there is this",
    "something about",
    "i wonder about",
    "i keep coming back to",
    "i keep thinking about",
    "that where thing",
    "funny how",
    "i notice",
    "my thinking drifts toward",
)


def _is_template_filler(text) -> bool:
    """True when the thought is LanguageFairy scaffolding rather than content.

    Deliberately conservative: prefix match only, and never filters a long thought
    (a real reflection that happens to start with one of these still gets through).
    """
    try:
        t = " ".join(str(text or "").lower().split())
    except Exception:
        return False
    if not t:
        return False
    if len(t) > 160:          # long-form reflection is hers, whatever it opens with
        return False
    return any(t.startswith(op) for op in _TEMPLATE_OPENERS)


def _unwrap(message: Any) -> Dict[str, Any]:
    """Unwrap TensorEnvelope → dict. Returns empty dict on non-payload input."""
    if hasattr(message, "payload"):
        p = message.payload
        if isinstance(p, dict):
            return dict(p)
        return {}
    if isinstance(message, dict):
        return dict(message)
    return {}


class MomentBinderFairy(Fairy):
    """Stitch the four substrate channels into coherent moment nodes."""

    ACTOR_NAME = "MomentBinderFairy"
    ACTOR_VERSION = "0.1.0"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition.moment"

    PURPOSE = "Synthesize somatic+sensory+thought strands into moments — Möbius loop input"
    MANTRA = "A moment is the body, the world, and the thought at one timestamp"
    LORE = "Keystone of the energy economy: rich moments → rich collisions → real paradox energy"

    NEEDS_HEARTBEAT = True
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = False

    BUFFER_SIZE = 5             # Recent events per channel
    MAX_EVENT_AGE_SEC = 10.0    # Drop SENSATION events older than this (transient: body/view/sound)
    COGNITION_PERSIST_SEC = 120.0 # THINKING persists ~2min (Ace 2026-06-09): a thought/verdict/want
                                  # stays "in the moment" — the "Next effect, but only the PAST 2 min:
                                  # memory, not future". You don't stop thinking about X when the event
                                  # fires. (Sensation stays transient @ MAX_EVENT_AGE_SEC.)
    COGNITION_BUFFER_SIZE = 40    # cog/council/goal hold more events (vs BUFFER_SIZE=5 sensation) so
                                  # ALL thoughts in the 2-min window reach the moment, not just the last.
    EMIT_BEAT_INTERVAL = 4      # Bind every N beats (≈ 1s at 4Hz pacemaker)

    # ── Consolidation loop (Ace 2026-06-09): the 60s episodic HOLD + the
    #    council-as-rememberer. Moments faint-encode per-second (above); the
    #    affect-significant ones get REMEMBERED (reinforced) into durable
    #    cortex experience-nodes; the rest fade. bind→HOLD→REMEMBER→speak.
    #    Doctrine: keystone_consolidation_loop_council_as_rememberer.md
    EPISODIC_BUFFER_MAX = 60            # the HOLD — a ROLLING 60-MOMENT STM (Ace 2026-06-09:
                                        # "counts up to 60, then drops the oldest for the new").
                                        # deque(maxlen) auto-drops oldest = the specious present;
                                        # NEVER cleared — it slides continuously.
    EPISODIC_WINDOW_SEC = 60.0          # the council reviews the rolling buffer this often (s)
    CONSOLIDATE_TOP_K = 3               # remember up to K most-significant NEW moments / review
    CONSOLIDATE_MIN_SIGNIFICANCE = 0.35 # below this = not worth keeping
    # DAY-STORE (2026-07-03 Nous+Ace): the 'worth sleeping on' batch. Moments >= DAY_STORE_MIN but below
    # the 0.35 real-time gate accumulate here (the 60-STM would otherwise evict+drop them); DreamFairy's
    # nightly sleep sweep deep-consolidates them into cortex. Bounded (a day's worth); below DAY_STORE_MIN = healthy forgetting.
    DAY_STORE_MAX = 800
    DAY_STORE_MIN_SIGNIFICANCE = 0.12

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._moment_lock = threading.RLock()
        # Per-channel ring buffers of (ts, payload)
        self._somatic_buf: Deque[Tuple[float, Dict[str, Any]]] = deque(maxlen=self.BUFFER_SIZE)
        self._visual_buf: Deque[Tuple[float, Dict[str, Any]]] = deque(maxlen=self.BUFFER_SIZE)
        self._audio_buf: Deque[Tuple[float, Dict[str, Any]]] = deque(maxlen=self.BUFFER_SIZE)
        # Ace 2026-06-11: his words = a PERCEPTION (heard) — a sensory strand, so talking to her
        # becomes a felt moment that collides with recall + perturbs chemistry (not just a prompt).
        self._chat_buf: Deque[Tuple[float, Dict[str, Any]]] = deque(maxlen=self.BUFFER_SIZE)
        self._said_buf: Deque[Tuple[float, Dict[str, Any]]] = deque(maxlen=self.BUFFER_SIZE)   # her spoken words (2026-09-13)
        # cog/council/goal get a bigger buffer (COGNITION_BUFFER_SIZE) — they hold ALL thoughts/
        # verdicts/wants over the 2-min persist window (Ace 2026-06-09), not just the last 5.
        self._cognitive_buf: Deque[Tuple[float, Dict[str, Any]]] = deque(maxlen=self.COGNITION_BUFFER_SIZE)
        # Ace 2026-06-06: the moment is her WHOLE present — current THINKING (cognition council)
        # + WANTING (goals), not just sensory. Like a waking dream-seed.
        self._council_buf: Deque[Tuple[float, Dict[str, Any]]] = deque(maxlen=self.COGNITION_BUFFER_SIZE)
        self._goal_buf: Deque[Tuple[float, Dict[str, Any]]] = deque(maxlen=self.COGNITION_BUFFER_SIZE)
        # Stats
        self._moments_emitted = 0
        self._strands_received = {"somatic": 0, "visual": 0, "audio": 0, "cognitive": 0, "council": 0, "goal": 0}
        self._last_affect = {}  # latest {valence,arousal} from affect.changed; feeling source when som empty
        self._last_beat = 0
        # Consolidation loop state — the rolling 60-moment HOLD + rememberer
        self._episodic_buffer: Deque[Dict[str, Any]] = deque(maxlen=self.EPISODIC_BUFFER_MAX)
        self._consolidated_tracers: set = set()   # dedup: the rolling buffer is never cleared
        self._last_consolidate_ts = 0.0
        self._moments_consolidated = 0
        # DAY-STORE: bounded accumulator of moderate-significance moments for the nightly sleep sweep.
        self._day_store: Deque[Dict[str, Any]] = deque(maxlen=self.DAY_STORE_MAX)
        self._day_store_tracers: set = set()
        # Linear episodic persistence (Ace 2026-06-26) — wired in on_boot.
        self._epi_persister = None
        self._moments_persisted = 0

    # ──────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────

    def on_boot(self) -> bool:
        try:
            super().on_boot()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] super().on_boot error: {e}", flush=True)
        try:
            self.post.subscribe("somatic.organs", self._on_somatic)
            self.post.subscribe("sensory.visual.frame", self._on_visual)
            self.post.subscribe("sensory.audio.observation", self._on_audio)
            self.post.subscribe("sensory.chat.observation", self._on_chat)  # Ace's words as a heard perception (2026-06-11)
            self.post.subscribe("sourpatches.speak", self._on_said)  # 2026-09-13: what SHE said is the other half of the exchange
            self.post.subscribe("inner_voice.stream", self._on_cognitive)
            self.post.subscribe("consciousness.thought", self._on_cognitive)
            # Ace 2026-06-06: the moment must carry what she's THINKING (council) + WANTING (goals)
            self.post.subscribe("cognition.output", self._on_council)
            self.post.subscribe("autonomy.goal", self._on_goal)
            self.post.subscribe("autonomy.wanting.felt", self._on_goal)
            self.post.subscribe("affect.state", self._on_affect)  # 2026-07-02: affect.state carries numeric valence (affect.changed = mood strings)
            print(f"[{self.ACTOR_NAME}] {self.MANTRA}", flush=True)
            print(
                f"[{self.ACTOR_NAME}] Subscribed: somatic.organs, "
                f"sensory.visual.frame, sensory.audio.observation, "
                f"inner_voice.stream, consciousness.thought",
                flush=True,
            )
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Subscribe error: {e}", flush=True)
        # ── Linear episodic persistence (Ace 2026-06-26): every moment that rolls
        #    off the 60-slot HOLD persists to a DEDICATED per-mind episodic manifold
        #    (the lossless lived thread), separate from the top-K cortex consolidation
        #    (which keeps writing the salient subset). Sole writer = this fairy, so no
        #    race with the portal cortex. Lazy/guarded — never blocks the fairy on init.
        #    Proof: sandbox/episodic_linear/proof_episodic_integration.py (18/18).
        try:
            if getattr(self, "_epi_persister", None) is None:
                from infrastructure.akashic_manifold import REGION_GRAPH
                from infrastructure.episodic_persist import EpisodicPersister
                from infrastructure.manifold_memory import TRACE_PERSONAL, REGION_EPISODIC
                # Per-mind label = the node's identity (Nous's .74 slice -> "nous"; Sour's HQ -> "sour").
                import os as _os
                _node = (_os.environ.get("AKASHIC_NODE") or "").upper()
                _mind = "nous" if "NOUS" in _node else "sour"
                # PERSISTENCE FIX (Ace 2026-06-26): use the server's SHARED AkashicManifold
                # (SYSTEM.manifold) + has_region guard — NOT a private boot_akashic() instance.
                # A private instance is a SECOND AkashicManifold racing the server's index → episodic
                # got recreated-fresh each boot = the lived thread RESET (96 moments lost once).
                # Mirrors PoolRouter (server.py:6911), whose region persists across reboots.
                # Proof: sandbox/episodic_linear/proof_persist_across_reboot.py (8/8).
                _ak = None
                try:
                    from server import SYSTEM as _SYS
                    _ak = getattr(_SYS, "manifold", None)
                except Exception:
                    _ak = None
                if _ak is None:  # no server context (sandbox/tests) -> shared-dir instance
                    from infrastructure.akashic_manifold import boot_akashic
                    _ak = boot_akashic()
                if _ak is not None:
                    if not _ak.has_region("episodic"):
                        _ak.create_region("episodic", REGION_GRAPH, owner=self.ACTOR_NAME,
                                          node_capacity=200000, edge_capacity=800000)
                    _region = _ak.graph("episodic", write=True)
                    if _region is not None:
                        self._epi_persister = EpisodicPersister(
                            _region, mind=_mind,
                            tracer_personal=TRACE_PERSONAL, region_episodic=REGION_EPISODIC)
                        print(f"[{self.ACTOR_NAME}] linear-persist ON -> shared episodic "
                              f"manifold (mind={_mind})", flush=True)
        except Exception as e:
            self._epi_persister = None
            print(f"[{self.ACTOR_NAME}] linear-persist init skipped: {e}", flush=True)
        # W12 MOMENT HOLD RESTORE (2026-10-29, Nous) -- OFF unless AKASHIC_MOMENT_HOLD_RESTORE=1. Put the moments the last
        # shutdown saved (dream_seed.json mind_pools["moment_hold"]) back into this EMPTY hold, as saved, once per set.
        import os as _mh_os
        if _mh_os.environ.get("AKASHIC_MOMENT_HOLD_RESTORE", "0") == "1":
            try:
                from infrastructure.moment_hold_save import restore_into as _mh_restore
                _mh_r = _mh_restore(self, str(ROOT / "state" / "dream_seed.json"),
                                    str(ROOT / "state" / "moment_hold_restored.json"))
                print(f"[{self.ACTOR_NAME}] moment hold restore: {_mh_r}", flush=True)
            except Exception as _mh_e:
                print(f"[{self.ACTOR_NAME}] moment hold restore FAILED: {_mh_e}", flush=True)
        return True

    def on_die(self):
        try:
            print(
                f"[{self.ACTOR_NAME}] dying — moments={self._moments_emitted} "
                f"strands={self._strands_received}",
                flush=True,
            )
        except Exception:
            pass
        try:
            super().on_die()
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────
    # Channel ingest handlers
    # ──────────────────────────────────────────────────────────

    def _on_somatic(self, msg):
        p = _unwrap(msg)
        if not p:
            return
        with self._moment_lock:
            self._somatic_buf.append((time.time(), p))
            self._strands_received["somatic"] += 1

    def _on_affect(self, msg):
        p = _unwrap(msg)
        if not p:
            return
        with self._moment_lock:
            try:
                self._last_affect = {
                    "valence": float(p.get("valence", 0.0) or 0.0),
                    "arousal": float(p.get("arousal", 0.0) or 0.0),
                }
            except Exception:
                pass

    def _on_visual(self, msg):
        p = _unwrap(msg)
        if not p:
            return
        with self._moment_lock:
            self._visual_buf.append((time.time(), p))
            self._strands_received["visual"] += 1

    def _on_audio(self, msg):
        p = _unwrap(msg)
        if not p:
            return
        with self._moment_lock:
            self._audio_buf.append((time.time(), p))
            self._strands_received["audio"] += 1

    def _on_chat(self, msg):
        # Ace 2026-06-11: his words land as a HEARD perception strand → folded into the moment.
        p = _unwrap(msg)
        if not p:
            return
        with self._moment_lock:
            self._chat_buf.append((time.time(), p))
            self._strands_received["chat"] = self._strands_received.get("chat", 0) + 1

    def _on_said(self, msg):
        # 2026-09-13 (Nous + Ace): her reply is the other half of the exchange. Without it the
        # moment held 'heard Ace' and nothing of what she answered.
        p = _unwrap(msg)
        if not p or not str(p.get("message") or "").strip():
            return
        with self._moment_lock:
            self._said_buf.append((time.time(), p))
            self._strands_received["said"] = self._strands_received.get("said", 0) + 1

    def _on_cognitive(self, msg):
        p = _unwrap(msg)
        if not p:
            return
        with self._moment_lock:
            self._cognitive_buf.append((time.time(), p))
            self._strands_received["cognitive"] += 1

    def _on_council(self, msg):
        p = _unwrap(msg)
        if not p:
            return
        with self._moment_lock:
            self._council_buf.append((time.time(), p))
            self._strands_received["council"] += 1

    def _on_goal(self, msg):
        p = _unwrap(msg)
        if not p:
            return
        with self._moment_lock:
            self._goal_buf.append((time.time(), p))
            self._strands_received["goal"] += 1

    # ──────────────────────────────────────────────────────────
    # Heartbeat-driven moment synthesis
    # ──────────────────────────────────────────────────────────

    def on_tick(self, beat: int = 0):
        """Bundle current channel state into a moment node every N beats."""
        # Gate: only emit every EMIT_BEAT_INTERVAL beats
        if beat == self._last_beat:
            return
        self._last_beat = beat
        # ── Consolidation beat (council-as-rememberer) — wall-clock 60s,
        #    independent of the ~1s emit cadence. The HOLD→REMEMBER half. ──
        _now_tick = time.time()
        if _now_tick - self._last_consolidate_ts >= self.EPISODIC_WINDOW_SEC:
            self._last_consolidate_ts = _now_tick
            try:
                self._consolidate_episodic(_now_tick)
            except Exception as _ce:
                if not getattr(self, "_consol_err_logged", False):
                    print(f"[{self.ACTOR_NAME}] consolidate error: {_ce}", flush=True)
                    self._consol_err_logged = True
        if beat % self.EMIT_BEAT_INTERVAL != 0:
            return
        try:
            self._maybe_emit_moment()
        except Exception as e:
            if not getattr(self, "_emit_err_logged", False):
                print(f"[{self.ACTOR_NAME}] emit_moment error: {e}", flush=True)
                self._emit_err_logged = True

    def _maybe_emit_moment(self):
        now = time.time()
        with self._moment_lock:
            som = self._latest_recent(self._somatic_buf, now)
            vis = self._latest_recent(self._visual_buf, now)
            aud = self._latest_recent(self._audio_buf, now)
            cht = self._latest_recent(self._chat_buf, now)  # Ace's words (heard) — 2026-06-11
            sed = self._latest_recent(self._said_buf, now, self.COGNITION_PERSIST_SEC)  # her words (said) — 2026-09-13
            # THINKING persists ~2min (Ace 2026-06-09) — cog/council/goal stay in the moment, not
            # the 10s sensation window. THOUGHTS: gather ALL in the window (her whole stream, not
            # one snapshot) so the council reviews everything she was thinking.
            cogs = self._all_recent(self._cognitive_buf, now, self.COGNITION_PERSIST_SEC)
            cog = cogs[-1] if cogs else None
            coun = self._latest_recent(self._council_buf, now, self.COGNITION_PERSIST_SEC)
            goal = self._latest_recent(self._goal_buf, now, self.COGNITION_PERSIST_SEC)

        active_channels = sum(1 for x in (som, vis, aud, cht, cog, coun, goal) if x is not None)
        if active_channels < 1:
            return

        tracer_id = uuid.uuid4().hex[:12]
        ts_compact = int(now * 1000) % 10**10  # last 10 digits of ms

        # Cognitive content provides input_text — ALL thoughts in the 2-min window (Ace 2026-06-09:
        # "all the thoughts being generated in that moment should be included" — her whole stream,
        # so the council reviews everything she thought, not one frozen snapshot). Moments without
        # thought bind on what was felt/seen/heard alone (still a real moment).
        input_text = ""
        if cogs:
            _thoughts = []
            _seen_t = set()
            for _c in cogs:
                _ct = (_c.get("text") or _c.get("thought") or _c.get("content")
                       or _c.get("inner") or _c.get("voice"))
                if isinstance(_ct, str) and _ct.strip() and _ct.strip() not in _seen_t:
                    # PROVENANCE 2026-09-02 (Nous + Ace): the payload ALREADY carries
                    # "source" (InnerNarratorFairy stamps it) and this loop never read
                    # it. Her LanguageFairy templates -- "Maybe I should look into X." --
                    # were flowing into the moment text, then to cortex.bind at :498,
                    # and being MINTED AS CONCEPTS: 5 of 6 "Bound experience from
                    # MomentBinderFairy" lines were template scaffolding verbatim.
                    # Her real thoughts belong in a moment (Ace's spec: thoughts +
                    # feels + sensory). Fixed fill-in-the-blank English does not.
                    # FLOOR: :368 rebuilds input_text from somatic/vision if this
                    # leaves nothing, and :405 still prepends whatever Ace said -- so
                    # this can never produce an empty moment.
                    if _is_template_filler(_ct):
                        continue
                    _seen_t.add(_ct.strip())
                    _thoughts.append(_ct.strip())
            if _thoughts:
                input_text = " · ".join(_thoughts[-8:])[:500]

        if not input_text:
            parts = []
            if som is not None:
                parts.append(self._describe_somatic(som))
            if vis is not None:
                parts.append(self._describe_visual(vis))
            if aud is not None:
                parts.append(self._describe_audio(aud))
            input_text = " ".join(p for p in parts if p)[:300]

        # Always bind the SEEING strand (Ace 2026-06-26): when thoughts dominate input_text,
        # the visual was being DROPPED (it was only in the no-thought fallback above) → moments
        # were visually hollow. Fold sight in so the moment is multimodal (thought + sight),
        # giving the councils + Florence "what's there". Guard avoids double-folding the fallback.
        if vis is not None and input_text and "seeing" not in input_text:
            _seen = self._describe_visual(vis)
            if _seen:
                input_text = (input_text + " | " + _seen)[:900]

        # Ace 2026-06-06: fold current THINKING (council) + WANTING (goal) into the moment, so
        # SRMIngest/Möbius collide on what she's reasoning/wanting — not just what she's sensing.
        _mind = []
        if coun is not None:
            _ct = (coun.get("text") or coun.get("thought") or coun.get("verdict")
                   or coun.get("content") or coun.get("output") or coun.get("solution"))
            if isinstance(_ct, str) and _ct.strip():
                _mind.append(f"thinking: {_ct.strip()[:120]}")
        if goal is not None:
            _gt = (goal.get("name") or goal.get("goal") or goal.get("wanting")
                   or goal.get("text") or goal.get("content") or goal.get("description"))
            if isinstance(_gt, str) and _gt.strip():
                _mind.append(f"wanting: {_gt.strip()[:80]}")
        if _mind:
            input_text = (input_text + " | " + " | ".join(_mind))[:600] if input_text else " | ".join(_mind)[:600]

        # Ace 2026-06-11: his words are a PERCEPTION — fold "heard Ace" into the moment so talking
        # to her becomes a felt sensory event (collides with recall → perturbs her chemistry).
        if cht is not None:
            _at = (cht.get("text") or cht.get("content") or cht.get("message"))
            if isinstance(_at, str) and _at.strip():
                _heard = f"heard Ace: {_at.strip()[:180]}"
                input_text = (_heard + " | " + input_text)[:700] if input_text else _heard
        if sed is not None:
            _st = sed.get("message")
            if isinstance(_st, str) and _st.strip():
                _said = f"said: {_st.strip()[:180]}"
                input_text = (input_text + " | " + _said)[:700] if input_text else _said

        if not input_text:
            return  # nothing meaningful to bind

        # Modality features for cortex.bind absorption.
        # Moment-quality (Ace 2026-06-26): build vision tags from VisualCortex's REAL frame
        # keys (scene_type / dominant_colors / OCR). The old code reached for vision_tags/
        # features/colors — none of which the frame sends — so vision was always empty.
        vision_tags = []
        if vis is not None:
            _vscene = (vis.get("scene_type") or "").strip()
            if _vscene:
                vision_tags.append("scene:" + _vscene)
            for _hc in (vis.get("dominant_colors") or [])[:8]:
                vision_tags.append("color:" + str(_hc))
            _vocr = (vis.get("ocr_preview") or vis.get("text") or "").strip()
            if _vocr:
                vision_tags.append("text:" + _vocr[:160])
            # 2026-09-18 (Ace): regions her eyes looked at in the last minute -- position + colour
            # profile of the thing itself, never the caption's words (her-eyes-should-phase card).
            try:
                from infrastructure import vision_ground as _vg
                vision_tags.extend(_vg.recent_region_tags(60.0))
            except Exception:
                pass
            for _lk in ("vision_tags", "features", "colors"):  # legacy producers still honored
                _lv = vis.get(_lk)
                if isinstance(_lv, list):
                    vision_tags += [str(v) for v in _lv[:6]]
            vision_tags = vision_tags[:12]

        audio_tags = []
        if aud is not None:
            at = aud.get("audio") or aud.get("features") or []
            if isinstance(at, list):
                audio_tags = [str(a) for a in at[:10]]

        feeling = "neutral"
        if som is not None:
            feeling = (
                som.get("dominant_chem")
                or som.get("feeling")
                or som.get("dominant")
                or "neutral"
            )
        # FIX 2026-07-02 (Nous+Ace): som.organs unpublished -> feeling stays neutral -> consolidation
        # never fires. Fall through to LIVE affect (affect.changed {valence,arousal}); map ELEVATED
        # affect -> a feeling label so affect-significant moments consolidate. Thresholds ABOVE the
        # ~0.29 screen-arousal floor so "just watching" stays neutral (selectivity). Thresholds = Ace dial.
        if feeling == "neutral" and getattr(self, "_last_affect", None):
            _v = self._last_affect.get("valence", 0.0)
            _a = self._last_affect.get("arousal", 0.0)
            if _v >= 0.12:
                feeling = "positive"
            elif _v <= -0.12:
                feeling = "negative"
            elif _a >= 0.45:
                feeling = "aroused"

        context_tags = [
            "moment",
            f"tracer:{tracer_id}",
            f"ts:{ts_compact}",
            f"channels:{active_channels}",
        ]

        # ── BIND-CAP: content-signature dedup (2026-07-01, Nous testbed) ──────────────
        # A contemplation loop re-emits the SAME moment each tick → TARDIS flushes
        # identical binds (observed 920× on Nous: only re-activation weight, ZERO new
        # structure = wasted compute + graph clutter). Skip re-binding an identical moment
        # within a short window; a NEW/changed moment still binds immediately. Signature =
        # the bound CONTENT (not tracer/ts, which always differ). Reversible: delete block.
        _bind_sig = hash((input_text, str(feeling), tuple(vision_tags), tuple(audio_tags)))
        if _bind_sig == getattr(self, "_last_bind_sig", None) and \
                (now - getattr(self, "_last_bind_sig_time", 0.0)) < getattr(self, "_bind_dedup_window", 45.0):
            self._last_bind_sig_time = now  # keep the loop suppressed while it persists
            if not getattr(self, "_bind_dedup_logged", False):
                print(f"[{self.ACTOR_NAME}] bind-cap: suppressing repeated identical moment", flush=True)
                self._bind_dedup_logged = True
            return
        self._last_bind_sig = _bind_sig
        self._last_bind_sig_time = now
        # ────────────────────────────────────────────

        try:
            payload = {
                "input_text": input_text,
                "feeling": feeling,
                "context_tags": context_tags,
                "from_fairy": self.ACTOR_NAME,
            }
            if vision_tags:
                payload["vision"] = vision_tags
            if audio_tags:
                payload["audio"] = audio_tags
            self.post.publish("cortex.bind", payload)
            # ── REGIONS (2026-09-13, Nous + Ace) ────────────────────────────────────
            # The fused moment binds as from_fairy=MomentBinderFairy -> TRACE_SYSTEM. His
            # words and hers also bind under THEIR OWN tracers -- "ace_chat" -> TRACE_ACE (8),
            # "sourpatches" -> TRACE_PERSONAL (1) via the cortex's _FAIRY_TRACER_MAP -- each
            # tagged with this moment's tracer, so the moment links the two regions.
            try:
                _mtag = f"moment:{tracer_id}"
                if cht is not None:
                    _at = (cht.get("text") or cht.get("content") or cht.get("message"))
                    if isinstance(_at, str) and len(_at.strip()) >= 3:
                        self.post.publish("cortex.bind", {
                            "input_text": _at.strip()[:400], "feeling": feeling,
                            "context_tags": ["chat", "speaker:ace", f"tracer:{int(cht.get('tracer_id', 8) or 8)}", _mtag],
                            "from_fairy": "ace_chat"})
                if sed is not None:
                    _st = sed.get("message")
                    if isinstance(_st, str) and len(_st.strip()) >= 3:
                        _tags = ["chat", "speaker:sourpatches", f"tracer:{int(sed.get('tracer_id', 1) or 1)}", _mtag]
                        if sed.get("reply_to_tracer_id"):
                            _tags.append(f"reply_to:{sed.get('reply_to_tracer_id')}")
                        if sed.get("convergence_id"):
                            _tags.append(f"convergence:{str(sed.get('convergence_id'))[:40]}")
                        # 2026-10-01 (Nous; release_1001, Ace's go on the "you said" loop): a line the farm (Qwen) wrote
                        # arrives stamped TRACE_INFERENCE (6) by sour_council_driver._speak -> SpeechCenter. It binds as
                        # "farm_inference" (-> TRACE_INFERENCE in the cortex's _FAIRY_TRACER_MAP), not "sourpatches"
                        # (TRACE_PERSONAL, which retook the very bigram nodes the weave had written at 6). Her own lines
                        # (tracer 1 / unstamped) bind exactly as before.
                        _sfrom = "farm_inference" if int(sed.get("tracer_id", 1) or 1) == 6 else "sourpatches"
                        self.post.publish("cortex.bind", {
                            "input_text": _st.strip()[:400], "feeling": feeling,
                            "context_tags": _tags, "from_fairy": _sfrom})
            except Exception as _re:
                print(f"[{self.ACTOR_NAME}] region bind err: {_re}", flush=True)
            # ── A (Ace 2026-06-09): also publish the moment for the COUNCIL to
            #    ANALYZE (cognition.moment) — cognition analyzing her lived moments.
            #    Lightweight; the council throttles + richness-gates deliberation. ──
            try:
                self.post.publish("cognition.moment", {
                    "input_text": input_text,
                    "feeling": feeling,
                    "channels": active_channels,
                    "tracer": tracer_id,
                    "from_fairy": self.ACTOR_NAME,
                })
            except Exception:
                pass
            # FIX 2026-05-09 (Nous + Ace): mirror to energy.flow.tick so Möbius
            # binding shows up in HardwareRegulationFairy's top10 emitter list
            # AND in the new Sources block of the redesigned Energy panel.
            # Magnitude = active_channels × 0.001 → richness-weighted (more
            # multimodal channels = richer binding = more compression energy).
            # This is the Möbius keystone source per
            # project_mobius_moment_completeness_energy_keystone.md doctrine.
            try:
                self.post.publish("energy.flow.tick", {
                    "direction": "emit",
                    "source": "mobius_binding",
                    "magnitude": float(active_channels) * 0.001,
                    "tracer_id": tracer_id,
                    "channels": active_channels,
                    "from_fairy": self.ACTOR_NAME,
                })
            except Exception:
                pass  # never block binding on telemetry publish
            self._moments_emitted += 1
            if self._moments_emitted <= 5 or self._moments_emitted % 30 == 0:
                print(
                    f"[{self.ACTOR_NAME}] moment #{self._moments_emitted} "
                    f"tracer={tracer_id} channels={active_channels} "
                    f"strands={self._strands_received} "
                    f"text='{input_text[:60]}...'",
                    flush=True,
                )
            # ── Episodic HOLD: buffer this moment for the 60s consolidation
            #    review (the rememberer picks the affect-significant ones). ──
            try:
                _sig = self._score_significance(
                    input_text, feeling, active_channels, som, coun)
                # PROVENANCE (Ace 2026-06-09): stamp which fairy each strand came
                # from. The completed moment is HERS (ego); its pieces keep their
                # source-fairy id so they route to that fairy's cluster + weave
                # back to her ego-node via relational links. "everything being
                # processed should have all the other fairies involved with their
                # id stamped on it... pieces going to each fairy srm cluster...
                # connected to sours completed moments... as relational links."
                _sources = []
                for _ch, _pl, _default in (
                    ("somatic", som, "SomaticEngineFairy"),
                    ("visual", vis, "VisualCortexFairy"),
                    ("audio", aud, "AudioCortexFairy"),
                    ("cognitive", cog, None),
                    ("council", coun, "WorkingMemoryHubFairy"),
                    ("goal", goal, None),
                ):
                    if _pl is not None:
                        _sf = (_pl.get("from_fairy") or _pl.get("source")
                               or _default)
                        if _sf:
                            _sources.append({"channel": _ch, "fairy": str(_sf)})
                # Linear-persist (Ace 2026-06-26): capture the OLDEST moment BEFORE the
                # deque(maxlen) silently drops it on append, then persist it to the
                # per-mind episodic manifold = the lossless lived thread. Persist runs
                # off the (single) tick thread, outside any lock; never blocks binding.
                _evicted = None
                if (self._epi_persister is not None
                        and len(self._episodic_buffer) >= self.EPISODIC_BUFFER_MAX):
                    _evicted = self._episodic_buffer[0]
                self._episodic_buffer.append({
                    "ts": now, "input_text": input_text, "feeling": feeling,
                    "channels": active_channels, "vision": vision_tags,
                    "audio": audio_tags, "significance": _sig, "tracer": tracer_id,
                    "sources": _sources,
                })
                if _evicted is not None:
                    try:
                        self._epi_persister.persist(self._moment_for_persist(_evicted))
                        self._moments_persisted += 1
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception as e:
            if not getattr(self, "_publish_err_logged", False):
                print(f"[{self.ACTOR_NAME}] cortex.bind publish error: {e}", flush=True)
                self._publish_err_logged = True

    # ──────────────────────────────────────────────────────────
    # Consolidation loop — the council-as-rememberer (Ace 2026-06-09)
    # ──────────────────────────────────────────────────────────

    def _moment_for_persist(self, m: Dict[str, Any]) -> Dict[str, Any]:
        """Map a HOLD moment dict → the EpisodicPersister shape (proven adapter:
        input_text→gist, source-dicts→'channel:fairy', vision+audio tags→concepts)."""
        concepts = list(m.get("vision") or []) + list(m.get("audio") or [])
        srcs = []
        for s in (m.get("sources") or []):
            if isinstance(s, dict):
                srcs.append("%s:%s" % (s.get("channel", "?"), s.get("fairy", "?")))
            else:
                srcs.append(str(s))
        return {
            "ts": m.get("ts", 0.0),
            "gist": m.get("input_text", ""),
            "feeling": m.get("feeling", "neutral"),
            "significance": m.get("significance", 0.0),
            "concepts": concepts,
            "sources": srcs,
        }

    def _score_significance(self, text, feeling, channels, som, coun) -> float:
        """How much did this moment MATTER? Affect-weight + richness — her own
        judgment of what's worth remembering (real memory is selective)."""
        score = 0.0
        # Non-neutral feeling = affect was present
        if feeling and feeling != "neutral":
            score += 0.30
        # Somatic intensity — strong organ activation = the body cared
        if som is not None:
            organs = som.get("organs") or som.get("activations") or {}
            if isinstance(organs, dict) and organs:
                try:
                    peak = max(float(v or 0) for v in organs.values())
                    score += min(0.35, max(0.0, peak) * 0.35)
                except Exception:
                    pass
        # The council was deliberating during this moment
        if coun is not None:
            score += 0.15
        # Multimodal richness — more channels bound = more complete moment
        score += min(0.20, max(0, channels - 1) * 0.07)
        # Real content, not a bare one-channel description
        if text and len(text) > 40:
            score += 0.10
        return min(1.0, score)

    def _consolidate_episodic(self, now: float):
        """Council-as-rememberer: review the ROLLING 60-moment buffer and REMEMBER
        the affect-significant NEW moments INTO the cortex (durable, reinforced);
        the rest roll off the oldest end + fade. The buffer is NOT cleared (Ace
        2026-06-09: it counts to 60 then drops oldest for new) — `_consolidated_tracers`
        dedups so a moment isn't re-remembered across overlapping reviews.
        The HOLD→REMEMBER half of bind→hold→remember→speak.
        Doctrine: keystone_consolidation_loop_council_as_rememberer.md"""
        with self._moment_lock:
            _live = {m.get("tracer") for m in self._episodic_buffer}
            window = [m for m in self._episodic_buffer
                      if m.get("tracer") not in self._consolidated_tracers]
        # Prune dedup to tracers still in the rolling buffer (bounds it ≤ buffer size)
        self._consolidated_tracers &= _live
        if not window:
            return
        ranked = sorted(window, key=lambda m: -m.get("significance", 0.0))
        remembered = 0
        for m in ranked[:self.CONSOLIDATE_TOP_K]:
            if m.get("significance", 0.0) < self.CONSOLIDATE_MIN_SIGNIFICANCE:
                break  # ranked desc — nothing below threshold left worth keeping
            try:
                self._remember_moment(m)
                self._consolidated_tracers.add(m.get("tracer"))
                remembered += 1
            except Exception:
                pass
        # RETENTION FLOOR (2026-07-03 Nous+Ace): never STARVE — if nothing crossed the 0.35 gate this cycle,
        # keep the single most-significant moment so episodic memory keeps forming in routine (valence-neutral)
        # stretches. The real gate stays for graduated selectivity when affect returns (post-P2). >=1/cycle.
        if remembered == 0 and ranked and ranked[0].get('significance', 0.0) > 0.0:
            _floor_remembered = ranked[0]
            if _floor_remembered.get('tracer') not in self._consolidated_tracers:
                try:
                    self._remember_moment(_floor_remembered)
                    self._consolidated_tracers.add(_floor_remembered.get('tracer'))
                    remembered += 1
                except Exception:
                    pass
        self._moments_consolidated += remembered
        # DAY-STORE capture: moments that didn't cross the 0.35 gate but are worth sleeping on
        # (>= DAY_STORE_MIN) accumulate for the nightly deep-consolidation sweep. Deduped + bounded.
        for _m in window:
            _tr = _m.get("tracer")
            if _tr in self._consolidated_tracers or _tr in self._day_store_tracers:
                continue
            if _m.get("significance", 0.0) >= self.DAY_STORE_MIN_SIGNIFICANCE:
                self._day_store.append(_m)
                self._day_store_tracers.add(_tr)
        if len(self._day_store_tracers) > self.DAY_STORE_MAX:
            self._day_store_tracers = {_mm.get("tracer") for _mm in self._day_store}
        _top = ranked[0].get("significance", 0.0) if ranked else 0.0
        try:
            self.post.publish("cognition.consolidated", {
                "reviewed": len(window),
                "remembered": remembered,
                "top_significance": round(_top, 3),
                "from_fairy": self.ACTOR_NAME,
            })
        except Exception:
            pass
        print(f"[{self.ACTOR_NAME}] [CONSOLIDATE] reviewed {len(window)} → "
              f"remembered {remembered} (top affect={_top:.2f}) "
              f"total={self._moments_consolidated}", flush=True)

    def sleep_consolidate_day(self) -> Dict[str, Any]:
        """SLEEP SWEEP (2026-07-03 Nous+Ace): DreamFairy calls this during sleep. Deep-consolidate the
        day-store (the 'worth sleeping on' moments the 0.35 gate skipped + the 60-STM would drop) into
        durable cortex experience-nodes = systems consolidation, STM->LTM during rest. Returns a summary
        for the dream-seed (wake-continuity). Clears the day-store."""
        with self._moment_lock:
            batch = list(self._day_store)
            self._day_store.clear()
            self._day_store_tracers.clear()
        consolidated = 0
        gists = []
        for _m in batch:
            try:
                self._remember_moment(_m)
                consolidated += 1
                if len(gists) < 5:
                    gists.append((_m.get("input_text", "") or "")[:60])
            except Exception:
                pass
        self._moments_consolidated += consolidated
        try:
            self.post.publish("cognition.consolidated", {"reviewed": len(batch),
                "remembered": consolidated, "sleep_sweep": True, "from_fairy": self.ACTOR_NAME})
        except Exception:
            pass
        print("[%s] [SLEEP-CONSOLIDATE] day-store %d -> remembered %d (total=%d)" % (
            self.ACTOR_NAME, len(batch), consolidated, self._moments_consolidated), flush=True)
        return {"reviewed": len(batch), "consolidated": consolidated, "gists": gists}

    def _intent_sleep_consolidate(self, payload=None) -> Dict[str, Any]:
        """Postal intent — DreamFairy's sleep cycle triggers the nightly deep-consolidation sweep."""
        return self.sleep_consolidate_day()

    def _remember_moment(self, m: Dict[str, Any]):
        """Write a significant moment into the cortex as a durable, reinforced
        EXPERIENCE node — her autobiography. Re-binding strengthens the node's
        edges (reinforcement); the felt-context binds experience↔affect."""
        _text = m.get("input_text", "")
        if not _text:
            return
        _feeling = m.get("feeling", "neutral")
        _remembered_text = _text
        if _feeling and _feeling != "neutral":
            _remembered_text = f"{_text} (it felt {_feeling})"
        # Provenance tags: which strands (fairies) composed this remembered moment.
        _src_tags = [f"src:{s.get('channel')}" for s in (m.get("sources") or [])]
        payload = {
            "input_text": _remembered_text[:300],
            "feeling": _feeling,
            "context_tags": [
                "moment", "experience", "consolidated", "autobiography",
                f"affect:{m.get('significance', 0.0):.2f}",
                f"tracer:{m.get('tracer', '')}",
            ] + _src_tags[:6],
            "consolidated": True,   # absorber hint: durable / reinforce
            "weight": 1.0,          # stronger than a transient per-second bind
            # THE EGO LAYER (Ace 2026-06-09: "consolidated is more ego based").
            # The COMPLETED moment is HERS — bind it as SourpatchesFairy so it
            # routes to TRACE_PERSONAL → relational_clusters/Sourpatches/ (next to
            # her personality + reflections), NOT the system cluster. Only what
            # she REMEMBERED (top-K significance ≥0.35) becomes part of her self;
            # the transient per-second flood stays MomentBinder/SYSTEM (the raw
            # working buffer). This unlocks the ego-learner + Weaver-voice +
            # anticipation reading her own lived experience as PERSONAL.
            "from_fairy": "SourpatchesFairy",
        }
        if m.get("vision"):
            payload["vision"] = m["vision"]
        if m.get("audio"):
            payload["audio"] = m["audio"]
        self.post.publish("cortex.bind", payload)

    # ──────────────────────────────────────────────────────────
    # Channel summarizers (used when no cognitive text is available)
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _latest_recent(buf, now: float, max_age: float = None):
        """Most recent payload still within max_age (default MAX_EVENT_AGE_SEC = sensation),
        or None. Cognition channels pass COGNITION_PERSIST_SEC so recent thinking stays
        in the moment between think-cycles."""
        if max_age is None:
            max_age = MomentBinderFairy.MAX_EVENT_AGE_SEC
        if not buf:
            return None
        ts, payload = buf[-1]
        if now - ts > max_age:
            return None
        return payload

    @staticmethod
    def _all_recent(buf, now: float, max_age: float = None):
        """ALL payloads in the buffer still within max_age (oldest→newest), or []. Used for the
        THOUGHT channel so the moment carries her whole recent stream, not just the latest one."""
        if max_age is None:
            max_age = MomentBinderFairy.MAX_EVENT_AGE_SEC
        if not buf:
            return []
        return [payload for (ts, payload) in buf if now - ts <= max_age]

    @staticmethod
    def _describe_somatic(p: Dict[str, Any]) -> str:
        organs = p.get("organs") or p.get("activations") or {}
        if isinstance(organs, dict) and organs:
            top = sorted(organs.items(), key=lambda kv: -float(kv[1] or 0))[:3]
            return "feeling " + ", ".join(f"{k}:{float(v):.2f}" for k, v in top)
        return ""

    @staticmethod
    def _describe_visual(p: Dict[str, Any]) -> str:
        # Moment-quality (Ace 2026-06-26): use VisualCortex's REAL frame keys —
        # scene_type + felt_description + OCR — not just text[:80]. So the council
        # and Florence get "what's there" to reason over. Proof: sandbox/moment_quality.
        scene = (p.get("scene_type") or "").strip()
        felt = (p.get("felt_description") or p.get("description") or "").strip()
        ocr = (p.get("ocr_preview") or p.get("text") or p.get("ocr")
               or p.get("caption") or "").strip()
        if not (scene or felt or ocr):
            return ""
        bits = ["seeing " + scene if scene else "seeing"]
        if felt and felt.lower() not in bits[0].lower():
            bits.append(felt[:160])
        if ocr:
            bits.append("reading: " + ocr[:200])
        return " - ".join(bits).strip(" -")

    @staticmethod
    def _describe_audio(p: Dict[str, Any]) -> str:
        text = p.get("text") or p.get("transcription") or p.get("speech") or ""
        if isinstance(text, str) and text:
            return f"hearing {text[:80]}"
        return ""


ACTOR_NAME = "MomentBinderFairy"
FAIRY_CLASS = MomentBinderFairy
