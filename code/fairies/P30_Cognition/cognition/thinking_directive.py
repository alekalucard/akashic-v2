"""thinking_directive — canonical contract for the `thinking.directive` postal topic.

Purpose
-------
This module defines the payload contract for directed thinking in Akashic.
It's the product of WMH_DIRECTED_THINKING Slice 1 (plan file
`Claude_Office/plans/WMH_DIRECTED_THINKING.md`, 2026-04-24).

Context
-------
Prior to this plan, the DynamicThinkingOrchestrator ran on its own private
daemon thread and started thinking chains autonomously via internal heartbeat.
WMH had no way to direct "think about this specific topic" and cognition
fairies (SourpatchesFairy, SomaticMindFairy, NousFairy, IrrationalLogic,
ParadoxCognition, HybridCognition) didn't drive thinking — they reacted
downstream.

This contract flips that pattern. A `thinking.directive` message carries the
intent ("here is something that should be thought about") with enough context
that subscribing cognition fairies can decide whether it's within their
specialty, and if so spawn a thinking chain claimed under their OWN
trace_id. WMH converges outputs via the `convergence_id` field.

Slice 1 (this file) defines ONLY the contract. No publisher/subscriber code
is wired yet — that's Slice 2-5 in the plan.

Convention
----------
Import the constants/dataclass here instead of stringly-typed topic names
or ad-hoc dicts. That way publishers and subscribers share one source of
truth, and future refactors are a single-file change.

Usage
-----
Publisher (e.g., WMH in Slice 3)::

    from fairies.P30_Cognition.cognition.thinking_directive import (
        THINKING_DIRECTIVE_TOPIC, ThinkingDirective, Source, Urgency,
    )

    directive = ThinkingDirective.from_ace_input(
        goal="What did Ace mean by 'holistic refactor'?",
        tracer_id=TRACE_ACE,
    )
    self.post.publish(THINKING_DIRECTIVE_TOPIC, directive.to_dict())

Subscriber (e.g., SourpatchesFairy in Slice 4)::

    from fairies.P30_Cognition.cognition.thinking_directive import (
        THINKING_DIRECTIVE_TOPIC, ThinkingDirective,
    )

    def on_boot(self):
        ...
        self.post.subscribe(THINKING_DIRECTIVE_TOPIC, self._on_thinking_directive)

    def _on_thinking_directive(self, payload: dict):
        directive = ThinkingDirective.from_dict(payload)
        if self._is_within_my_specialty(directive):
            self.thought_engine.start_chain(
                goal=directive.goal,
                source=f"directive:{directive.source}",
                owner_trace_id=self.my_tracer_id,
                convergence_id=directive.convergence_id,
            )
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
import uuid
import time


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

#: Canonical postal topic name for directed thinking.
#: Publishers: WMH (Slice 3). Subscribers: cognition fairies (Slice 4).
THINKING_DIRECTIVE_TOPIC = "thinking.directive"

#: Companion topic for convergence aggregation — subscribers publish results
#: here with the original `convergence_id` so WMH can aggregate. Slice 5.
THINKING_CONVERGENCE_TOPIC = "thinking.convergence"


class Source:
    """Canonical source-of-directive values. Use these constants rather than
    free-form strings so subscribers can filter/route by source type reliably.

    - ACE_INPUT: directive arose from Ace's chat/voice input (highest priority
      in most subscriber policies)
    - GOAL_PROMOTED: a goal was promoted from pending to active — WMH directs
      thinking about the goal
    - SOMATIC_STUCK: a fairy's DirectiveEvolver emitted `somatic.stuck` — meta:
      think about WHY we're stuck (closes the learning loop)
    - AFFECT_SPIKE: a strong affect state change — focus thinking on the source
    - INTEREST_DETECTED: InterestSchedulerFairy surfaced a strong interest
    - META: a directive about the system's own operation (admin/diagnostic)
    """
    ACE_INPUT = "ace_input"
    GOAL_PROMOTED = "goal_promoted"
    SOMATIC_STUCK = "somatic_stuck"
    AFFECT_SPIKE = "affect_spike"
    INTEREST_DETECTED = "interest_detected"
    META = "meta"


class Urgency:
    """Canonical urgency levels.

    Subscribers use urgency to decide whether to preempt their current chain,
    queue for next cycle, or file-and-forget. Ace_input typically arrives as
    HIGH; ambient goal-promoted as NORMAL; passive interest as LOW.
    """
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"  # reserved for safety/substrate-level events


# ─────────────────────────────────────────────────────────────────────────────
# Payload dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ThinkingDirective:
    """Canonical payload for the `thinking.directive` topic.

    Every field has a defined purpose; subscribers should feel safe importing
    and relying on this contract. Adding new fields is permitted (dataclass is
    extensible); REMOVING or renaming fields requires plan-level review.

    Fields
    ------
    goal : str
        What to think about. Free-form text or a reference (e.g., "goal_42" or
        "ace_msg:<id>"). Subscribers interpret per their specialty.

    source : str
        One of the `Source` constants. Identifies the upstream trigger.

    tracer_id : int
        The trace_id of the originator. For Ace input, TRACE_ACE. For goal
        promotions, typically TRACE_PERSONAL. For Nous-originated, TRACE_NOUS.
        Subscribers may set their own trace_id when spawning sub-chains; this
        field records the ORIGIN, not necessarily the current owner.

    urgency : str
        One of the `Urgency` constants.

    topic_hash : str
        Stable hash/key for DirectiveEvolver integration. Identifies the
        "topic" being thought about so per-topic action-ratio tracking can
        function across directive arrivals. Empty string if not applicable.

    aer_state : Optional[Dict[str, Any]]
        Current AER state (valence, intensity, paradox_residue) if relevant.
        Enables AER-driven α contribution in CollisionChamber (see
        coordinate_inference.compute_affect_coupling). Optional — subscribers
        that don't use AER can ignore.

    convergence_id : str
        Auto-generated UUID. All sub-chains spawned in response to this
        directive should tag their completion events with this ID so WMH can
        aggregate converged outputs in Slice 5. Do not reuse across
        directives.

    timestamp : float
        Publication time (time.time()). For diagnostics + SYSTEM_TELLS_ON_ITSELF.

    context : Dict[str, Any]
        Free-form extra context (e.g., the full Ace message, the goal record,
        the triggering event). Subscribers pull what they need.
    """
    goal: str
    source: str = Source.META
    tracer_id: int = 0  # TRACE_UNKNOWN
    urgency: str = Urgency.NORMAL
    topic_hash: str = ""
    aer_state: Optional[Dict[str, Any]] = None
    convergence_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for postal.publish. Dataclass asdict() is sufficient."""
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ThinkingDirective":
        """Deserialize a postal payload. Extra unknown keys are ignored
        (forward-compatibility). Missing required fields use defaults.
        """
        known_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in payload.items() if k in known_fields}
        if "goal" not in filtered:
            filtered["goal"] = "(no goal specified)"
        return cls(**filtered)

    # ── Factory methods for common cases ─────────────────────────────────

    @classmethod
    def from_ace_input(cls, goal: str, tracer_id: int, *,
                       topic_hash: str = "",
                       context: Optional[Dict[str, Any]] = None,
                       ) -> "ThinkingDirective":
        """Factory — directive arising from Ace's chat/voice input.

        Usage (typical, in WMH)::
            directive = ThinkingDirective.from_ace_input(
                goal=ace_message_text,
                tracer_id=TRACE_ACE,
                context={"message_id": msg.id, "session": sess.id},
            )
        """
        return cls(
            goal=goal,
            source=Source.ACE_INPUT,
            tracer_id=tracer_id,
            urgency=Urgency.HIGH,
            topic_hash=topic_hash,
            context=context or {},
        )

    @classmethod
    def from_goal_promoted(cls, goal: str, tracer_id: int, *,
                            topic_hash: str = "",
                            context: Optional[Dict[str, Any]] = None,
                            ) -> "ThinkingDirective":
        """Factory — directive arising from a goal being promoted to active."""
        return cls(
            goal=goal,
            source=Source.GOAL_PROMOTED,
            tracer_id=tracer_id,
            urgency=Urgency.NORMAL,
            topic_hash=topic_hash,
            context=context or {},
        )

    @classmethod
    def from_somatic_stuck(cls, goal: str, tracer_id: int, *,
                            topic_hash: str,
                            iterations: int,
                            last_thought: str = "",
                            ) -> "ThinkingDirective":
        """Factory — meta-directive after a fairy's forced-escape fired.

        This closes the DirectiveEvolver loop: fairy got stuck → emits
        somatic.stuck → WMH receives → publishes thinking.directive asking
        "why are we stuck on {topic_hash}?" → subscribing cognition fairies
        think about the stuckness itself.
        """
        return cls(
            goal=goal,
            source=Source.SOMATIC_STUCK,
            tracer_id=tracer_id,
            urgency=Urgency.NORMAL,
            topic_hash=topic_hash,
            context={
                "iterations_before_escape": iterations,
                "last_thought_before_escape": last_thought,
            },
        )

    @classmethod
    def from_affect_spike(cls, goal: str, tracer_id: int, *,
                           aer_state: Dict[str, Any],
                           context: Optional[Dict[str, Any]] = None,
                           ) -> "ThinkingDirective":
        """Factory — directive arising from a strong affect state change.

        The `aer_state` should include valence / intensity / paradox_residue
        so downstream CollisionChamber α computation + Meaning Selection
        scoring can use it.
        """
        return cls(
            goal=goal,
            source=Source.AFFECT_SPIKE,
            tracer_id=tracer_id,
            urgency=Urgency.NORMAL,
            aer_state=aer_state,
            context=context or {},
        )


# ─────────────────────────────────────────────────────────────────────────────
# Validation helper
# ─────────────────────────────────────────────────────────────────────────────

def validate(payload: Dict[str, Any]) -> Optional[str]:
    """Best-effort validator. Returns None if payload looks well-formed,
    otherwise a human-readable error string. Non-strict — unknown fields OK.

    Use this in subscribers to sanity-check before spawning a chain:

        err = thinking_directive.validate(payload)
        if err:
            print(f"[{self.ACTOR_NAME}] bad thinking.directive: {err}")
            return
        directive = ThinkingDirective.from_dict(payload)
    """
    if not isinstance(payload, dict):
        return f"payload must be dict, got {type(payload).__name__}"
    if "goal" not in payload:
        return "missing required field 'goal'"
    if not isinstance(payload.get("goal"), str):
        return "'goal' must be str"
    src = payload.get("source")
    if src is not None and not isinstance(src, str):
        return "'source' must be str"
    urg = payload.get("urgency")
    if urg is not None and urg not in (
        Urgency.LOW, Urgency.NORMAL, Urgency.HIGH, Urgency.CRITICAL
    ):
        return f"'urgency' invalid: {urg!r}"
    return None


__all__ = [
    "THINKING_DIRECTIVE_TOPIC",
    "THINKING_CONVERGENCE_TOPIC",
    "Source",
    "Urgency",
    "ThinkingDirective",
    "validate",
]
