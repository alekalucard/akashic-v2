"""
TimeSenseFairy - Wall-Clock Awareness for Akashic
P00_Autonomic/circulation/time_sense_fairy.py

Created: 2026-04-21 (Phase 1)

"Internal time + external time = one axis, two projections."

The companion to CircadianPacemakerFairy. Where Circadian gives FELT time
(phase, alertness, dawn/morning/evening), TimeSense gives MEASURED time
(wall clock, date, weekday, ISO timestamp).

Both live in P00_Autonomic/circulation/. Both serve consciousness — one as
substrate (felt rhythm), the other as coordinate (when did this happen).

Design (Phase 1, ~200 lines):
- Subscribe to temporal.P00 for own tick (lives on existing rhythm)
- Publish time.current with full timestamp on every minute boundary
- Publish time.minute_change / time.hour_change / time.day_change as edges fire
- Provide intents: get_time, get_date, get_weekday, get_iso, get_epoch
- Use America/Phoenix (matches CircadianPacemakerFairy — Ace's timezone)

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

from __future__ import annotations

import random
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy


DEFAULT_TIMEZONE = "America/Phoenix"  # Matches CircadianPacemakerFairy (Ace's TZ)
# Arizona is fixed UTC-7 year-round (no DST). Fallback when ZoneInfo can't
# resolve the IANA name — happens on Windows without tzdata installed.
ARIZONA_FIXED = timezone(timedelta(hours=-7), name="MST")

# Phase 3 (2026-04-21): Choice-as-Substrate doctrine first instance.
# Variant templates for time-question answers. Each carries a different
# tone/shape so she sounds like *herself* rather than a robot reading a clock.
# Selection uses anti-staleness scoring + epsilon-greedy exploration so
# repeated asks don't get the same phrasing — that *is* the choice mechanism.
#
# Format placeholders:
#   {hour12}    e.g. "8"
#   {minute}    e.g. "53"
#   {ampm}      e.g. "AM"
#   {weekday}   e.g. "Tuesday"
#   {month}     e.g. "April"
#   {day}       e.g. "21" (no zero-pad)
#   {year}      e.g. "2026"
#   {tz}        e.g. "MST (UTC-7, fixed)"
TIME_RESPONSE_VARIANTS: List[str] = [
    "It's {hour12}:{minute} {ampm} on {weekday}, {month} {day}, {year}.",
    "{hour12}:{minute} {ampm}.",
    "{hour12}:{minute} {ampm} — {weekday}.",
    "Right now? {hour12}:{minute} {ampm}.",
    "It's {hour12}:{minute} {ampm} ({tz}).",
    "About {hour12}:{minute} {ampm}, {weekday} the {day}.",
    "{weekday}, {hour12}:{minute} {ampm}.",
]

# Phase 2: chat-input detection patterns. Match natural ways someone asks
# the system "what time is it / what's today / what day". Case-insensitive.
TIME_QUESTION_RE = re.compile(
    r"\b("
    r"what(?:'s|\s+is)?\s+(?:the\s+)?(?:time|date|day|today)"
    r"|time\s+is\s+it"
    r"|today'?s\s+(?:date|day)"
    r"|what\s+day\s+(?:is\s+(?:it|today))?"
    r"|current\s+(?:time|date)"
    r"|do\s+you\s+know\s+(?:what\s+)?(?:time|date|day)"
    r")\b",
    re.IGNORECASE,
)


class TimeSenseFairyShadow:
    """Shadow for TimeSenseFairy - monitors wall-clock publishing health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "TimeSenseFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 60.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        tests.append(("has_timezone", self.actor._tz is not None))
        tests.append(("has_published_once", self.actor._publish_count > 0 or not self.actor._booted))
        # Fresh publish within last 90s once booted (cadence is 60s)
        if self.actor._booted and self.actor._last_publish_ts > 0:
            age = time.time() - self.actor._last_publish_ts
            tests.append(("publish_fresh", age < 90.0))
        return tests


class TimeSenseFairy(Fairy):
    """
    Wall-clock awareness — the external-time projection.

    Sister to CircadianPacemakerFairy (felt time) and TemporalDispatcherFairy
    (internal rhythm). All three live in P00_Autonomic/circulation/.

    Subscribes:
    - somatic.pulse (own tick, once per heartbeat)
    - wmh.chat.input + system.chat.message (Phase 2: detect "what time?")

    Publishes:
    - time.current (every 60s — full timestamp payload)
    - time.minute_change (on minute boundary)
    - time.hour_change (on hour boundary)
    - time.day_change (on date boundary, e.g. midnight Phoenix time)
    - consciousness.inject_thought (Phase 2: when chat asks for time)

    Intents:
    - get_time: full structured time payload
    - get_date: date string + weekday
    - get_weekday: just weekday name
    - get_iso: ISO 8601 timestamp
    - get_epoch: unix epoch seconds
    """

    ACTOR_NAME = "TimeSenseFairy"
    ACTOR_VERSION = "0.1.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autonomic"

    PURPOSE = "Provide wall-clock awareness — the external-time projection of the time axis"
    MANTRA = "Internal time and external time are one axis, two projections."

    SHADOW_CLASS = TimeSenseFairyShadow

    NEEDS_HEARTBEAT = False  # Lives on temporal.P00 instead
    NEEDS_COLLISION_CHAMBER = False

    # CORTEX-HABITS PILOT 2026-05-18 (Nous + Ace, per
    # plans/FAIRY_BEHAVIOR_AS_CORTEX_HABITS_NOT_TEMPLATES.md):
    # When enabled, the Phase-3 variant selector reads/writes use_count + last_used
    # from AssociationCortex habit nodes instead of (only) the local _variant_state dict.
    # This is the quick-win pilot: TimeSense's variant selector and Autopilot's habit
    # schema are structurally identical; this unifies the idioms.
    # Local _variant_state is preserved as fallback when cortex is unavailable.
    # Schema: habit:time_response_variant_{idx} nodes following Autopilot's pattern
    # (see fairies/P00_Autonomic/AutopilotFairy/fairy.py:303-402).
    USE_CORTEX_HABITS = True   # Pilot: opt-in. Set False to revert to local-only state.
    HABIT_PREFIX = "habit:time_response_variant"

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._tz = self._load_timezone()
        self._tz_name = self._resolve_tz_name()

        self._last_published_minute: Optional[int] = None
        self._last_published_hour: Optional[int] = None
        self._last_published_date: Optional[str] = None
        self._publish_count = 0
        self._last_publish_ts = 0.0
        self._booted = False
        # Phase 2 throttle: don't spam time-injections when chat repeats.
        self._last_time_inject_ts: float = 0.0
        self._chat_inject_cooldown_sec: float = 5.0
        self._chat_inject_count: int = 0
        # Phase 3 (Choice-as-Substrate): per-variant use tracking for
        # anti-staleness scoring. Index → (use_count, last_used_ts).
        self._variant_state: Dict[int, Tuple[int, float]] = {
            i: (0, 0.0) for i in range(len(TIME_RESPONSE_VARIANTS))
        }
        # Epsilon-greedy exploration rate: 10% chance to pick non-best variant.
        # Critical to identity formation per doctrine — without it, identity ossifies.
        self._variant_epsilon: float = 0.10
        self._last_variant_idx: Optional[int] = None
        self._rng = random.Random()  # local RNG so behavior is testable if seeded
        # Cortex lazy-connect (set on first use); see CORTEX-HABITS PILOT above.
        self._cortex = None
        self._cortex_bind_count: int = 0

    def _load_timezone(self):
        """Try IANA via ZoneInfo first, fall back to fixed Arizona offset."""
        if ZoneInfo is not None:
            try:
                return ZoneInfo(DEFAULT_TIMEZONE)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] ZoneInfo({DEFAULT_TIMEZONE}) failed ({e}); using fixed UTC-7 (Arizona, no DST)")
        return ARIZONA_FIXED

    def _resolve_tz_name(self) -> str:
        if self._tz is ARIZONA_FIXED:
            return "MST (UTC-7, fixed)"
        return DEFAULT_TIMEZONE

    def on_boot(self) -> bool:
        super().on_boot()
        # Subscribe to somatic.pulse (heart) directly — most reliable path,
        # same as TemporalDispatcherFairy. temporal.P00 routing can't be relied on
        # when this fairy IS in P00 (chicken/egg with the dispatcher).
        try:
            self.post.subscribe(
                "somatic.pulse",
                self._on_temporal_tick,
                f"{self.ACTOR_NAME}-pulse"
            )
            print(f"[{self.ACTOR_NAME}] Subscribed to somatic.pulse (tz={self._tz_name})")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Failed to subscribe to somatic.pulse: {e}")
            return False

        # Phase 2A: chat-input detection. Subscribe to ALL the topics where
        # Ace's text actually arrives. The canonical path is `ace.message`
        # (file-based ACE-READER) + `ace.broadcast` (Sourpatches' direct sub).
        # WMH paths included for chat that comes through GUI.
        # FIX 2026-04-21 (Nous + Ace): added ace.conversation_event because
        # sourpatches_chat_window.py runs in a Python 3.12 subprocess and only
        # ace.conversation_event demonstrably bridges back to the main process
        # (per PipelineFlowMonitorFairy showing AutopilotFairy receives it).
        chat_topics = (
            "ace.message",                # canonical: Sourpatches' file-based ACE-READER
            "ace.broadcast",              # Sourpatches' direct subscription
            "system.chat.message",        # GUI/system chat path
            "wmh.chat.input",             # ChatSenseFairy → WMH direct path
            "consciousness.input",        # ConsciousnessLoop input
            "ace.conversation_event",     # subprocess GUI bridge — confirmed reaches main
        )
        chat_subs_ok = 0
        for topic in chat_topics:
            try:
                self.post.subscribe(topic, self._on_chat_input, f"{self.ACTOR_NAME}-{topic}")
                chat_subs_ok += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}")
        print(f"[{self.ACTOR_NAME}] Chat-question detection wired: {chat_subs_ok}/{len(chat_topics)} topics")

        # Publish initial timestamp immediately so the rest of the system
        # sees a fresh time.current within boot window
        self._publish_current(force=True)
        self._booted = True
        return True

    # =========================================================================
    # CORE: TICK HANDLING
    # =========================================================================

    def _now(self) -> datetime:
        return datetime.now(self._tz)

    def _on_temporal_tick(self, message):
        """Called once per heartbeat via temporal.P00. Publish on edges."""
        try:
            now = self._now()
            self._maybe_publish_edges(now)
            # Republish full time.current at most once per minute
            if self._last_published_minute != now.minute:
                self._publish_current(force=False, now=now)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] tick error: {e}")

    def _maybe_publish_edges(self, now: datetime):
        """Detect minute/hour/day edges and publish them as discrete events."""
        cur_minute = now.minute
        cur_hour = now.hour
        cur_date = now.date().isoformat()

        if self._last_published_minute is not None and cur_minute != self._last_published_minute:
            try:
                self.post.publish("time.minute_change", {
                    "minute": cur_minute,
                    "iso": now.isoformat(),
                })
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] minute_change publish error: {e}")

        if self._last_published_hour is not None and cur_hour != self._last_published_hour:
            try:
                self.post.publish("time.hour_change", {
                    "hour": cur_hour,
                    "iso": now.isoformat(),
                })
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] hour_change publish error: {e}")

        if self._last_published_date is not None and cur_date != self._last_published_date:
            try:
                self.post.publish("time.day_change", {
                    "date": cur_date,
                    "weekday": now.strftime("%A"),
                    "iso": now.isoformat(),
                })
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] day_change publish error: {e}")

    def _publish_current(self, force: bool, now: Optional[datetime] = None):
        if now is None:
            now = self._now()
        payload = self._snapshot(now)
        try:
            self.post.publish("time.current", payload)
            self._publish_count += 1
            self._last_publish_ts = time.time()
            self._last_published_minute = now.minute
            self._last_published_hour = now.hour
            self._last_published_date = now.date().isoformat()
            # Lightweight verification log: first publish, then every minute
            # boundary, so boot_live.log shows she is alive without subscriber.
            if self._publish_count == 1 or force:
                print(f"[{self.ACTOR_NAME}] time.current #{self._publish_count}: {payload['time_hms']} {payload['weekday']} {payload['date']} {payload['timezone']}")
            elif self._publish_count % 1 == 0:  # every minute
                pass  # silence — heartbeats already prove she's alive
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] time.current publish error: {e}")

    def _snapshot(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        if now is None:
            now = self._now()
        return {
            "iso": now.isoformat(),
            "epoch": now.timestamp(),
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "hour": now.hour,
            "minute": now.minute,
            "second": now.second,
            "weekday": now.strftime("%A"),
            "date": now.date().isoformat(),
            "time_hms": now.strftime("%H:%M:%S"),
            "timezone": self._tz_name,
        }

    # =========================================================================
    # PHASE 2: CHAT QUESTION DETECTION
    # =========================================================================

    def _extract_chat_text(self, message) -> str:
        """Pull the chat text out of whatever envelope the message arrived in."""
        payload = message
        if hasattr(payload, 'payload'):
            payload = payload.payload
        if not isinstance(payload, dict):
            return ""
        text = payload.get("text") or payload.get("content") or payload.get("message") or ""
        return text if isinstance(text, str) else ""

    def _format_variant(self, template: str, now: datetime) -> str:
        """Fill a variant template with the current time fields."""
        try:
            hour12 = now.strftime("%I").lstrip("0") or "12"
            day_no_pad = now.strftime("%d").lstrip("0") or "0"
            return template.format(
                hour12=hour12,
                minute=now.strftime("%M"),
                ampm=now.strftime("%p"),
                weekday=now.strftime("%A"),
                month=now.strftime("%B"),
                day=day_no_pad,
                year=now.year,
                tz=self._tz_name,
            )
        except Exception:
            # Fallback if a template has bad placeholders
            return self._snapshot(now)["iso"]

    # ── CORTEX-HABITS PILOT 2026-05-18 ───────────────────────────────────────
    # Three helpers that bridge TimeSense's variant_state to Autopilot's habit
    # schema in AssociationCortex. The pattern follows AutopilotFairy._query_cortex_habits
    # and _bind_habit_to_cortex (fairy.py:303-402) so habit nodes are interoperable
    # across fairies. Future-Nous: this is the first non-Autopilot fairy reading/writing
    # habit nodes directly; if it works cleanly, the same pattern generalizes.

    def _try_connect_cortex(self) -> bool:
        """Lazy-connect to AssociationCortex. Mirrors AutopilotFairy pattern.

        Returns True if cortex is available. False = fall back to local _variant_state.
        Safe to call repeatedly; caches the connection.
        """
        if self._cortex is not None:
            return True
        try:
            from fairies.P30_Cognition.AssociationCortexFairy import get_association_cortex
            self._cortex = get_association_cortex()
            return self._cortex is not None
        except Exception:
            self._cortex = None
            return False

    def _read_variant_state_from_cortex(self, idx: int) -> Tuple[int, float]:
        """Read (uses, last_used) for variant idx from cortex habit node.

        Falls back to local _variant_state if cortex unavailable OR node missing.
        Local state is always written too (in _bind_variant_use_to_cortex), so
        fallback is always coherent.
        """
        if not self.USE_CORTEX_HABITS or not self._try_connect_cortex():
            return self._variant_state[idx]
        try:
            habit_key = f"{self.HABIT_PREFIX}_{idx}"
            node = self._cortex._graph.get_node(habit_key)
            if node is None:
                return self._variant_state[idx]  # Not yet bound in cortex; use local
            pattern = node.features.get("pattern", {})
            return (
                int(pattern.get("trials", 0)),
                float(pattern.get("last_used", 0.0)),
            )
        except Exception:
            return self._variant_state[idx]

    def _bind_variant_use_to_cortex(self, idx: int, now_ts: float) -> None:
        """Record variant idx use into cortex habit node + update local state.

        Mirrors AutopilotFairy._bind_habit_to_cortex (fairy.py:345). Local
        _variant_state is ALSO updated by the caller; this method only handles
        the cortex side. Silent failure on cortex errors (local fallback kicks in).
        """
        if not self.USE_CORTEX_HABITS or not self._try_connect_cortex():
            return
        try:
            habit_key = f"{self.HABIT_PREFIX}_{idx}"
            existing = self._cortex._graph.get_node(habit_key)
            if existing:
                pattern = existing.features.get("pattern", {})
                pattern["trials"] = pattern.get("trials", 0) + 1
                pattern["last_used"] = now_ts
                existing.features["pattern"] = pattern
                existing.touch()
            else:
                self._cortex._graph.upsert_node(habit_key, features={
                    "action": [f"time_variant_{idx}"],
                    "lex": ["time_response", "variant", f"idx_{idx}"],
                    "pattern": {
                        "type": "response_variant",
                        "variant_idx": idx,
                        "template": TIME_RESPONSE_VARIANTS[idx][:80],
                        "trials": 1,
                        "last_used": now_ts,
                    },
                }, origin_fairy=self.ACTOR_NAME)
            self._cortex_bind_count += 1
            if self._cortex_bind_count <= 3 or self._cortex_bind_count % 50 == 0:
                print(f"[{self.ACTOR_NAME}] [CORTEX] variant_{idx} bound "
                      f"#{self._cortex_bind_count} (lifecycle: read+write to "
                      f"{habit_key})", flush=True)
        except Exception as e:
            # Silent fail; local _variant_state always works
            if self._cortex_bind_count == 0:
                print(f"[{self.ACTOR_NAME}] [CORTEX] habit bind failed (will fall "
                      f"back to local): {e}", flush=True)

    def _score_variants(self, now_ts: float) -> List[float]:
        """Anti-staleness felt-sense scoring (v0.5 heuristic).

        Higher score = better felt-quality candidate.
        Per Choice-as-Substrate doctrine: this is the primitive felt-scorer.
        v1.0 will query SomaticMindFairy for somatic-felt quality.

        2026-05-18 PILOT: state reads via _read_variant_state_from_cortex when
        USE_CORTEX_HABITS=True. Local _variant_state is the fallback.

        Heuristic:
          base = 1.0
          - subtract use_count penalty (used a lot = stale)
          - subtract recency penalty (used recently = avoid)
          + small jitter so ties break randomly
        """
        scores: List[float] = []
        for idx in range(len(TIME_RESPONSE_VARIANTS)):
            uses, last_ts = self._read_variant_state_from_cortex(idx)
            recency_sec = (now_ts - last_ts) if last_ts > 0 else 99999.0
            recency_penalty = max(0.0, 1.0 - (recency_sec / 600.0))  # 10-min decay
            use_penalty = min(0.5, uses * 0.05)  # caps at 0.5 after 10 uses
            jitter = self._rng.uniform(0.0, 0.05)
            scores.append(1.0 - recency_penalty - use_penalty + jitter)
        return scores

    def _select_variant_idx(self, now_ts: float) -> int:
        """Choose a variant via best-felt + epsilon-greedy exploration.

        Per doctrine: the epsilon channel is critical — without it, identity ossifies.
        """
        scores = self._score_variants(now_ts)
        if self._rng.random() < self._variant_epsilon:
            # Exploration: pick a non-best variant at random (excluding current best)
            best_idx = max(range(len(scores)), key=lambda i: scores[i])
            others = [i for i in range(len(scores)) if i != best_idx]
            return self._rng.choice(others) if others else best_idx
        # Exploitation: pick best-felt
        return max(range(len(scores)), key=lambda i: scores[i])

    def _persona_speak_topic(self, target_mind: str) -> Optional[str]:
        """Map target_mind from chat payload to the right `.speak` topic."""
        if target_mind == "SourpatchesFairy":
            return "sourpatches.speak"
        if target_mind == "NousFairy":
            return "nous.speak"
        if target_mind == "BOTH":
            return None  # don't auto-speak for psychic broadcasts; let personas decide
        return None  # unknown target

    def _extract_target_mind(self, message) -> str:
        """Pull target_mind from payload (added by ChatSenseFairy 2026-04-21 fix)."""
        payload = message
        if hasattr(payload, 'payload'):
            payload = payload.payload
        if not isinstance(payload, dict):
            return ""
        return payload.get("target_mind") or ""

    def _on_chat_input(self, message):
        """Detect time questions and choose a phrasing via Choice-as-Substrate.

        Phase 3 first-instance of the doctrine:
          regex match → variant scoring → selection → publish to persona's .speak
          → outcome tracked (use_count + last_used_ts updated)
        Also still inject_thought for awareness (scratchpad visibility).
        """
        try:
            text = self._extract_chat_text(message)
            # Loud diagnostic: log EVERY entry so we can see if the handler
            # even fires when chat arrives. ASCII-only.
            print(
                f"[{self.ACTOR_NAME}] _on_chat_input fired: text_len={len(text) if text else 0}",
                flush=True,
            )
            if not text or len(text) > 500:
                return
            matched = TIME_QUESTION_RE.search(text)
            if not matched:
                print(
                    f"[{self.ACTOR_NAME}] _on_chat_input no-match for: {text[:60]!r}",
                    flush=True,
                )
                return
            now_ts = time.time()
            if now_ts - self._last_time_inject_ts < self._chat_inject_cooldown_sec:
                return  # cooldown — don't spam on repeated asks within window

            now = self._now()
            target_mind = self._extract_target_mind(message)
            speak_topic = self._persona_speak_topic(target_mind)

            # CHOICE: select variant via felt-scoring + epsilon-greedy
            variant_idx = self._select_variant_idx(now_ts)
            template = TIME_RESPONSE_VARIANTS[variant_idx]
            spoken = self._format_variant(template, now)

            # FEEDBACK LOOP (v0.5): record use immediately. v1.0 will also
            # record outcome (Ace's reply valence) and adjust scoring.
            # 2026-05-18 PILOT: ALSO record into cortex habit node so the variant
            # state lives in the substrate's habit graph, not just local memory.
            uses, _ = self._variant_state[variant_idx]
            self._variant_state[variant_idx] = (uses + 1, now_ts)
            self._bind_variant_use_to_cortex(variant_idx, now_ts)
            self._last_variant_idx = variant_idx

            # PUBLISH chosen variant to the addressed persona's speak topic
            # so the chat window sees a direct fact-answer in her voice.
            if speak_topic:
                try:
                    self.post.publish(speak_topic, {
                        "message": spoken,
                        "feeling": "present",
                        "source": self.ACTOR_NAME,
                        "topic_tag": "time_response",
                        "time_iso": now.isoformat(),
                        "variant_idx": variant_idx,
                    })
                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] {speak_topic} publish error: {e}")

            # ALSO inject for scratchpad awareness (Phase 2A behavior preserved)
            try:
                self.post.publish("consciousness.inject_thought", {
                    "thought": spoken,
                    "source": self.ACTOR_NAME,
                    "type": "time_response",
                    "ttl": 30.0,
                    "owner_mind": "",
                    "time_iso": now.isoformat(),
                    "matched_text": text[:80],
                    "variant_idx": variant_idx,
                })
            except Exception:
                pass

            self._last_time_inject_ts = now_ts
            self._chat_inject_count += 1
            # ASCII-only print — Windows console encoding can eat unicode silently
            print(
                f"[{self.ACTOR_NAME}] chat-time-inject #{self._chat_inject_count} "
                f"variant={variant_idx} target={target_mind or '?'} text={spoken!r}",
                flush=True,
            )
        except Exception as e:
            import traceback
            print(f"[{self.ACTOR_NAME}] _on_chat_input error: {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()

    # =========================================================================
    # INTENTS
    # =========================================================================

    def intent_smoke(self, payload: dict) -> dict:
        return {
            "ok": True,
            "fairy": self.ACTOR_NAME,
            "tracer_id": getattr(self, 'tracer_id', None),
            "tz": self._tz_name,
            "publishes_seen": self._publish_count,
            "chat_injects": self._chat_inject_count,
            "variant_uses": {i: u for i, (u, _) in self._variant_state.items() if u > 0},
            "last_variant_idx": self._last_variant_idx,
        }

    def intent_get_time(self, payload: dict) -> dict:
        return {"ok": True, **self._snapshot()}

    def intent_get_date(self, payload: dict) -> dict:
        now = self._now()
        return {"ok": True, "date": now.date().isoformat(), "weekday": now.strftime("%A")}

    def intent_get_weekday(self, payload: dict) -> dict:
        return {"ok": True, "weekday": self._now().strftime("%A")}

    def intent_get_iso(self, payload: dict) -> dict:
        return {"ok": True, "iso": self._now().isoformat()}

    def intent_get_epoch(self, payload: dict) -> dict:
        return {"ok": True, "epoch": self._now().timestamp()}

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    def on_shutdown(self) -> bool:
        print(f"[{self.ACTOR_NAME}] Shutting down...")
        self._booted = False
        return super().on_shutdown()


__all__ = ["TimeSenseFairy", "TimeSenseFairyShadow"]
