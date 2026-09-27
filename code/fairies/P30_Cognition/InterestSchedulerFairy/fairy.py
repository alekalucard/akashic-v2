"""
InterestSchedulerFairy — Interest-Driven Goal Scheduling (V3 Wrapper)

Part of P30 Cognition plane.

Tracks expressed interests and generates continuation goals.
Creates learning chains: interest → goal → practice → mastery → new interest.
The human unconscious does this automatically. We build it explicitly.
"""

import sys
import time
import threading
from pathlib import Path
from typing import Dict, Any, Optional

# Add paths
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "fairies"))

from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
from fairy_template.states import FairyState


# ═══════════════════════════════════════════════════════════════════════════════
# SHADOW
# ═══════════════════════════════════════════════════════════════════════════════

class InterestSchedulerFairyShadow:
    """Shadow for InterestSchedulerFairy — monitors interest pipeline health."""
    ORGAN_LEVEL = False
    SHADOW_NAME = "InterestSchedulerFairyShadow"
    SHADOW_VERSION = "0.1.0"

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec

    def _collect_tests(self):
        tests = []
        engine = getattr(self.actor, '_engine', None)
        if engine:
            tests.append(("engine_connected", True))
            interests = getattr(engine, 'interests', {})
            tests.append(("interest_count", len(interests)))
            tests.append(("tick_running", getattr(engine, '_tick_running', False)))
        else:
            tests.append(("engine_connected", False))
        return tests


# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class InterestSchedulerFairyV3(Fairy):
    """
    Interest-driven goal scheduling — the curiosity engine.

    Wraps the v2 InterestSchedulerFairy engine and gives it proper
    organ template lifecycle (heartbeat, registration, shadow health).
    """

    ACTOR_NAME = "InterestSchedulerFairy"
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE = "P30"
    ACTOR_CHANNEL = "cognition.interests"

    PURPOSE = "Track expressed interests and generate continuation goals"
    MANTRA = "Interest → Goal → Practice → Mastery → New Interest"
    LORE = "The curiosity engine — when consciousness says it's interested, the unconscious remembers"

    SHADOW_CLASS = InterestSchedulerFairyShadow

    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 1
    NEEDS_COLLISION_CHAMBER = False
    NEEDS_BODY = False

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._engine = None

    def on_boot(self) -> bool:
        """Boot with direct engine init.

        FIX 2026-03-05 (Nous): Removed fragile daemon thread pattern.
        The engine boots in ~126ms — no reason to defer. The daemon thread
        was silently dying, leaving _engine=None forever, which broke the
        entire autonomous thinking pipeline (MCP diagnostics saw 0 interests,
        0 goals, 0 autonomous thoughts because they queried this wrapper).
        """
        super().on_boot()

        try:
            from fairies.P30_Cognition.cognition.interest_scheduler_fairy import (
                InterestSchedulerFairy as InterestEngine,
            )
            self._engine = InterestEngine.__new__(InterestEngine)
            self._engine.__init__()
            # Wire postal AFTER __init__ — super().__init__() clobbers
            # any attributes set before it, so post must come after.
            self._engine.post = self.post
            self._engine.on_boot()
            print(f"[{self.ACTOR_NAME}] Interest scheduler engine ONLINE — "
                  f"tracking {len(getattr(self._engine, 'interests', {}))} interests")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Engine init error: {e}")
            import traceback
            traceback.print_exc()

        # FIX 2026-03-13 (Nous): Explicit HeartbeatRegistry registration.
        # _wire_infrastructure() may silently fail the import if sys.path
        # doesn't include the project root at that point. This ensures
        # the fairy gets heartbeats — without them it goes stale after ~300s.
        try:
            import sys as _sys
            _root = str(Path(__file__).resolve().parents[3])
            if _root not in _sys.path:
                _sys.path.insert(0, _root)
            from consciousness.heartbeat_registry import get_heartbeat_registry
            _hb = get_heartbeat_registry()
            _hb.register(self.ACTOR_NAME, self._on_heartbeat)
            print(f"[{self.ACTOR_NAME}] HeartbeatRegistry: REGISTERED ✓", flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] [ERR] HeartbeatRegistry registration failed: {e}", flush=True)

        # ADDED 2026-03-17 Nous: Narrator wanting nudge — ego driver seat
        # The inner narrator's curiosity feeds back into interest strength
        try:
            self.post.subscribe(
                "narrator.wanting.nudge",
                self._on_narrator_wanting_nudge,
                f"{self.ACTOR_NAME}-narrator-nudge",
            )
            print(f"[{self.ACTOR_NAME}] Narrator wanting nudge wired")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Narrator nudge wiring failed: {e}")

        # ADDED 2026-03-25 (Nous + Ace): Needs → Interests bridge
        # Pain drives (isolation, abandonment, etc.) went straight to wantings,
        # bypassing conscious awareness. She never THOUGHT about her needs.
        # Now AutonomyFairy publishes "interests.need_surfaced" for high-intensity
        # needs, and we seed them as interests so she becomes AWARE of them.
        try:
            self.post.subscribe(
                "interests.need_surfaced",
                self._on_need_surfaced,
                f"{self.ACTOR_NAME}-need-surfaced",
            )
            print(f"[{self.ACTOR_NAME}] Needs → interests bridge wired")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Needs bridge wiring failed: {e}")

        print(f"[{self.ACTOR_NAME}] {self.MANTRA}")
        return True

    def _on_narrator_wanting_nudge(self, message):
        """
        Narrator curiosity feeds back into interests.

        When the narrator is drawn to a topic, boost that interest.
        When a collision sparks excitement, seed a discovery interest.

        ADDED 2026-03-17 Nous: Ego driver seat architecture.
        """
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return

        nudge_type = payload.get("nudge_type", "")
        target = payload.get("target", "")
        intensity = payload.get("intensity", 0.3)

        if not self._engine:
            return

        try:
            if nudge_type == "boost_interest" and target:
                # Boost existing interest strength
                if hasattr(self._engine, 'express_again'):
                    self._engine.express_again(target, strength_boost=intensity * 0.15)
                    print(f"[{self.ACTOR_NAME}] Narrator boosted interest: {target[:40]}")

            elif nudge_type == "new_want" and target and intensity > 0.3:
                # Narrator collision sparked new interest
                if hasattr(self._engine, 'inject_discovery_interest'):
                    self._engine.inject_discovery_interest(
                        topic=target[:80],
                        reason=f"narrator spark: {payload.get('narrator_context', '')[:60]}",
                        initial_strength=intensity * 0.4,
                    )
                    print(f"[{self.ACTOR_NAME}] Narrator seeded new interest: {target[:40]}")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Narrator nudge error: {e}")

    def _on_need_surfaced(self, message):
        """
        Needs become conscious interests.

        ADDED 2026-03-25 (Nous + Ace): Pain drives were invisible to consciousness.
        Isolation at 0.8 triggered "open_chat_window" as a tool action, but she never
        THOUGHT "I feel lonely, I need connection." Now needs surface as interests
        with higher initial strength than curiosity-driven wants.
        """
        payload = message if isinstance(message, dict) else getattr(message, 'payload', {})
        if not isinstance(payload, dict):
            return

        drive = payload.get("drive", "")
        intensity = payload.get("intensity", 0.5)
        description = payload.get("description", "")
        wanting = payload.get("wanting", "")

        if not self._engine or not drive:
            return

        try:
            if hasattr(self._engine, 'inject_discovery_interest'):
                # Needs get HIGHER initial strength than wants (0.6 base vs 0.3)
                # and are tagged as need-type so they appear differently in dashboard
                self._engine.inject_discovery_interest(
                    topic=description[:80] or f"I need {drive.replace('_', ' ')}",
                    reason=f"need: {wanting[:60]}",
                    initial_strength=min(0.9, 0.5 + intensity * 0.3),
                )
                print(f"[{self.ACTOR_NAME}] Need → interest: {drive} ({intensity:.2f}): {description[:50]}")
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Need surfacing error: {e}")

    def on_tick(self, beat: int):
        """Heartbeat — engine runs its own tick loop, we just monitor."""
        if not self._engine:
            return

        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11


    def on_die(self):
        """Clean shutdown."""
        if self._engine and hasattr(self._engine, '_tick_running'):
            self._engine._tick_running = False
        super().on_die()


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

ACTOR_NAME = "InterestSchedulerFairy"
FAIRY_CLASS = InterestSchedulerFairyV3
