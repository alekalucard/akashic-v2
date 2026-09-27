"""
HabitConsultantFairy - Phase 4 first instance of Choice-as-Substrate doctrine
P00_Autonomic/circulation/habit_consultant_fairy.py

Created: 2026-04-21 (Phase 4)

"Habits are everything. The autopilot's brain is also the conscious mind's
   first whisper — 'have I done this before?' — before composer fires fresh."

THE PRINCIPLE (Choice doctrine, applied system-wide):
  - Phase 3 wired Choice into TimeSenseFairy (one domain: time questions)
  - Phase 4 wires Choice into the WHOLE chat-input pipeline via habit consultation
  - For each Ace message: ask HabitEngine "have I learned a response for this?"
  - High-confidence + validated (use_count>0 + healthy success rate) → inject as candidate
  - WMH's existing reasoning sees the inject in scratchpad, may use or override
  - Cortex stays as backup for novelty (existing architecture preserved)

SAFEGUARDS (because 70k+ habits accumulated unvalidated):
  - MIN_CONFIDENCE 0.7  (high bar; only act on strong matches)
  - MIN_USES 1          (habit must have been used before — not raw seed)
  - MIN_SUCCESS_RATE 0.5 (success rate >50%; weak ones suppressed)
  - COOLDOWN 5s        (don't fire same habit twice rapidly)
  - LOG_ALL_MATCHES    (visibility into what 70k habits are matching even when suppressed)

Layered with the Choice doctrine:
  - This fairy IS the "habit-first" gate
  - Suppression IS the "felt-quality scoring" (we score by use_count + success_rate)
  - Cortex backup IS the "fall through to fresh reasoning" path

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy


# Confidence + safeguard thresholds (tuned conservatively for 70k unvalidated habits)
MIN_CONFIDENCE: float = 0.7      # only act on strongly-matched habits (PRIMARY safety gate)
# Bootstrap mode 2026-04-21 (Phase 4.5a): seed habits all have uses=0, success=0 → without this
# relaxation, the chicken-egg lockout prevents any inject → consolidation never fires. Letting
# MIN_USES and MIN_SUCCESS_RATE be zero during bootstrap means MIN_CONFIDENCE is the only floor.
# Consolidation loop earns real stats; once populated, can tighten gates back.
MIN_USES: int = 0                # bootstrap: 0 so seed habits can make first inject
MIN_SUCCESS_RATE: float = 0.0    # bootstrap: 0.0 until real consolidations accumulate
COOLDOWN_SEC: float = 5.0        # don't fire same habit twice rapidly

# Phase 4.5a consolidation window — how long to wait for WMH to echo the candidate
CONSOLIDATION_TTL_SEC: float = 30.0


class HabitConsultantFairyShadow:
    ORGAN_LEVEL = False
    SHADOW_NAME = "HabitConsultantFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 60.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        tests.append(("engine_loaded", self.actor._habit_engine is not None))
        if self.actor._habit_engine is not None:
            count = len(getattr(self.actor._habit_engine, '_habits', {}))
            tests.append(("habits_loaded", count > 0))
        return tests


class HabitConsultantFairy(Fairy):
    """Habit-first consultation for Ace's chat input.

    Subscribes to chat topics, queries HabitEngine for each message,
    injects high-confidence matches into consciousness.inject_thought
    with a 'habit_match' tag for WMH to consider.
    """

    ACTOR_NAME = "HabitConsultantFairy"
    ACTOR_VERSION = "0.1.0"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "autonomic"

    PURPOSE = "Consult habit engine on Ace's input; surface matches before composer fires"
    MANTRA = "Have I done this before?"

    SHADOW_CLASS = HabitConsultantFairyShadow

    NEEDS_HEARTBEAT = False
    NEEDS_COLLISION_CHAMBER = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._habit_engine = None
        self._consult_count: int = 0
        self._inject_count: int = 0
        self._suppress_count: int = 0
        self._last_inject_per_habit: Dict[str, float] = {}
        # Phase 4.5a — consolidation tap
        self._pending_injects: Dict[str, Dict[str, Any]] = {}  # content_hash → meta
        self._consolidation_count: int = 0
        self._booted = False

    def on_boot(self) -> bool:
        super().on_boot()

        # Load HabitEngine (shared persist path with AutopilotFairy)
        try:
            from fairies.P00_Autonomic.AutopilotFairy.habit_engine import HabitEngine
            _root = Path(__file__).resolve().parents[3]
            persist_path = str(_root / "state" / "nous_workspace" / "habit_engine.json")
            self._habit_engine = HabitEngine(persist_path=persist_path)
            count = len(getattr(self._habit_engine, '_habits', {}))
            print(
                f"[{self.ACTOR_NAME}] HabitEngine loaded: {count} habits available "
                f"(min_conf={MIN_CONFIDENCE}, min_uses={MIN_USES}, min_success={MIN_SUCCESS_RATE})",
                flush=True,
            )
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] HabitEngine load failed: {e}", flush=True)
            self._habit_engine = None
            return False

        # Subscribe to chat topics — same set as TimeSenseFairy uses
        chat_topics = (
            "ace.message",
            "ace.broadcast",
            "ace.conversation_event",  # subprocess GUI bridge — confirmed reaches main
            "system.chat.message",
            "wmh.chat.input",
            "consciousness.input",
        )
        ok = 0
        for topic in chat_topics:
            try:
                self.post.subscribe(topic, self._on_chat_input, f"{self.ACTOR_NAME}-{topic}")
                ok += 1
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Failed to subscribe to {topic}: {e}", flush=True)
        print(f"[{self.ACTOR_NAME}] Chat-input consultation wired: {ok}/{len(chat_topics)} topics", flush=True)

        # Phase 4.5a — observe WMH compositions to detect consolidation (candidate echoed in output)
        try:
            self.post.subscribe(
                "working_memory.reasoning_complete",
                self._on_wmh_complete,
                f"{self.ACTOR_NAME}-wmh-complete",
            )
            print(f"[{self.ACTOR_NAME}] Consolidation tap wired: working_memory.reasoning_complete", flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Consolidation tap subscribe failed: {e}", flush=True)

        self._booted = True
        return True

    def _extract_chat_text(self, message) -> str:
        payload = message
        if hasattr(payload, 'payload'):
            payload = payload.payload
        if not isinstance(payload, dict):
            return ""
        text = payload.get("text") or payload.get("content") or payload.get("message") or ""
        return text if isinstance(text, str) else ""

    def _extract_target_mind(self, message) -> str:
        payload = message
        if hasattr(payload, 'payload'):
            payload = payload.payload
        if not isinstance(payload, dict):
            return ""
        return payload.get("target_mind") or ""

    def _on_chat_input(self, message):
        """For each Ace message, consult HabitEngine and inject if validated match."""
        try:
            if not self._habit_engine:
                return
            text = self._extract_chat_text(message)
            if not text or len(text) > 500:
                return

            self._consult_count += 1
            now_ts = time.time()
            target_mind = self._extract_target_mind(message)

            # Query HabitEngine
            match = self._habit_engine.match(text, context={"source": "ace_chat", "target_mind": target_mind})
            if not match:
                print(
                    f"[{self.ACTOR_NAME}] consult #{self._consult_count} NO_MATCH "
                    f"text={text[:50]!r} target={target_mind!r}",
                    flush=True,
                )
                return

            habit = match.habit
            confidence = match.confidence

            # SAFEGUARDS
            reasons_suppressed: List[str] = []
            if confidence < MIN_CONFIDENCE:
                reasons_suppressed.append(f"conf={confidence:.2f}<{MIN_CONFIDENCE}")
            if habit.uses < MIN_USES:
                reasons_suppressed.append(f"uses={habit.uses}<{MIN_USES}")
            success_rate = habit.success_rate()
            if success_rate < MIN_SUCCESS_RATE:
                reasons_suppressed.append(f"success={success_rate:.2f}<{MIN_SUCCESS_RATE}")
            last_t = self._last_inject_per_habit.get(habit.id, 0.0)
            if now_ts - last_t < COOLDOWN_SEC:
                reasons_suppressed.append(f"cooldown={now_ts-last_t:.1f}s<{COOLDOWN_SEC}")

            if reasons_suppressed:
                self._suppress_count += 1
                # Log suppression (visibility into the 70k habit pool)
                print(
                    f"[{self.ACTOR_NAME}] consult #{self._consult_count} SUPPRESS habit={habit.id!r} "
                    f"name={habit.name!r} reasons={','.join(reasons_suppressed)}",
                    flush=True,
                )
                return

            # ACT: inject the habit's first response template as a candidate
            templates = list(habit.response_templates) if habit.response_templates else []
            if not templates:
                # Habit matched but has no response template — log, don't act
                print(
                    f"[{self.ACTOR_NAME}] consult #{self._consult_count} NO_TEMPLATE habit={habit.id!r} "
                    f"name={habit.name!r} conf={confidence:.2f} (no response_templates)",
                    flush=True,
                )
                return

            # Use first template as v0.5 (Phase 4.5 will pick via Choice doctrine across templates)
            candidate = templates[0]

            try:
                self.post.publish("consciousness.inject_thought", {
                    "thought": candidate,
                    "source": self.ACTOR_NAME,
                    "type": "habit_match",
                    "ttl": 30.0,
                    "owner_mind": "",
                    "habit_id": habit.id,
                    "habit_name": habit.name,
                    "habit_category": habit.category,
                    "confidence": confidence,
                    "match_reason": match.match_reason,
                    "matched_text": text[:80],
                    "target_mind": target_mind,
                })
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] inject_thought publish error: {e}", flush=True)
                return

            self._inject_count += 1
            self._last_inject_per_habit[habit.id] = now_ts

            # Phase 4.5a — record this inject so we can detect downstream consolidation
            ch = hashlib.md5(candidate.strip().lower().encode()).hexdigest()[:12]
            self._pending_injects[ch] = {
                "habit_id": habit.id,
                "habit_name": habit.name,
                "input_text": text,
                "candidate": candidate,
                "injected_at": now_ts,
                "ttl": CONSOLIDATION_TTL_SEC,
            }
            self._purge_expired_pending(now_ts)

            print(
                f"[{self.ACTOR_NAME}] consult #{self._consult_count} INJECT #{self._inject_count} "
                f"habit={habit.id!r} name={habit.name!r} conf={confidence:.2f} "
                f"uses={habit.uses} success={success_rate:.2f} candidate={candidate[:60]!r}",
                flush=True,
            )
        except Exception as e:
            import traceback
            print(f"[{self.ACTOR_NAME}] _on_chat_input error: {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()

    def _purge_expired_pending(self, now_ts: float) -> None:
        """Drop pending injects older than their TTL."""
        expired = [ch for ch, e in self._pending_injects.items()
                   if now_ts - e["injected_at"] > e["ttl"]]
        for ch in expired:
            self._pending_injects.pop(ch, None)

    def _on_wmh_complete(self, message) -> None:
        """Phase 4.5a — watch WMH output; if it echoes a recent candidate, consolidation happened."""
        try:
            payload = message.payload if hasattr(message, 'payload') else message
            if not isinstance(payload, dict):
                return
            # WMH publishes reasoning result with composed_response as the verbatim text
            output = (payload.get("composed_response") or payload.get("output")
                      or payload.get("response") or payload.get("text")
                      or payload.get("content") or "")
            if not isinstance(output, str) or len(output) < 3:
                return

            now_ts = time.time()
            self._purge_expired_pending(now_ts)
            if not self._pending_injects:
                return

            out_norm = output.strip().lower()
            matched_ch: Optional[str] = None
            for ch, entry in self._pending_injects.items():
                cand_norm = entry["candidate"].strip().lower()
                if not cand_norm:
                    continue
                # Soft match: substring either direction (tolerates WMH rewording)
                if cand_norm in out_norm or out_norm in cand_norm:
                    matched_ch = ch
                    break

            if matched_ch is None:
                return

            entry = self._pending_injects.pop(matched_ch)
            self._consolidation_count += 1
            elapsed = now_ts - entry["injected_at"]
            print(
                f"[{self.ACTOR_NAME}] CONSOLIDATION #{self._consolidation_count} "
                f"habit={entry['habit_id']!r} name={entry['habit_name']!r} "
                f"input={entry['input_text'][:40]!r} used_after={elapsed:.1f}s",
                flush=True,
            )

            # Bootstrap the habit's use+success counters so MIN_* gates become meaningful
            try:
                if hasattr(self._habit_engine, 'mark_used_successfully'):
                    self._habit_engine.mark_used_successfully(
                        entry["habit_id"], reason="consultant_consolidation"
                    )
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] mark_used_successfully error: {e}", flush=True)

            try:
                self.post.publish("habit.consolidation.used", {
                    "habit_id": entry["habit_id"],
                    "habit_name": entry["habit_name"],
                    "input_text": entry["input_text"],
                    "candidate": entry["candidate"],
                    "actual_output": output,
                    "injected_at": entry["injected_at"],
                    "consolidated_at": now_ts,
                    "elapsed_sec": elapsed,
                    "source": self.ACTOR_NAME,
                })
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] consolidation publish error: {e}", flush=True)
        except Exception as e:
            import traceback
            print(f"[{self.ACTOR_NAME}] _on_wmh_complete error: {type(e).__name__}: {e}", flush=True)
            traceback.print_exc()

    def intent_smoke(self, payload: dict) -> dict:
        return {
            "ok": True,
            "fairy": self.ACTOR_NAME,
            "tracer_id": getattr(self, 'tracer_id', None),
            "habits_loaded": len(getattr(self._habit_engine, '_habits', {})) if self._habit_engine else 0,
            "consults": self._consult_count,
            "injects": self._inject_count,
            "suppressed": self._suppress_count,
            "consolidations": self._consolidation_count,
            "pending_injects": len(self._pending_injects),
        }

    def on_shutdown(self) -> bool:
        print(f"[{self.ACTOR_NAME}] Shutting down...", flush=True)
        self._booted = False
        return super().on_shutdown()


__all__ = ["HabitConsultantFairy", "HabitConsultantFairyShadow"]
