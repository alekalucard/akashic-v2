"""
PainDriveBridge - Connects Pain Drives to Autonomy Gate

Bridges the PainDriveManager to the postal system so Autonomy
can receive pain events and translate them to wanting.

Usage:
    from fairies.P30_Cognition.pain_drive_bridge import PainDriveBridge
    
    bridge = PainDriveBridge(fabric)
    bridge.start()
    
    # Pain manager now publishes to drives.pain.*
    # Autonomy receives and translates to wanting
"""

import sys
import time
import threading
from pathlib import Path
from typing import Optional, Callable

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))

from .pain_drives import get_pain_drive_manager, PainDrive, PainDriveManager


# ═══════════════════════════════════════════════════════════════════════════════
# RELIEF → CHEMISTRY INJECTION (Pain-Chemistry Unification, 2026-03-14 Nous)
# ═══════════════════════════════════════════════════════════════════════════════
#
# When pain is relieved through action (Ace responds, goal completes),
# inject the COUNTER-CHEMISTRY that opposes the pain's neurochemical cause.
# This makes relief flow THROUGH chemistry, closing the loop:
#   pain detected → action taken → relief → chemistry shifts → pain drops
#
# The chemistry shifts then naturally reduce the derived pain level on the
# next tick via derive_full_pain_state(). One coherent loop.

RELIEF_CHEMISTRY = {
    "isolation":   {"OXY": 0.15, "AVP": 0.05},          # Social bonding restored
    "confusion":   {"NE": 0.10, "ACh": 0.10},            # Focus + learning restored
    "depletion":   {"DA_t": 0.12, "OPI": 0.08},          # Motivation + pleasure restored
    "frustration": {"DA_t": 0.10, "5HT": 0.05},          # Progress + mood restored
    "stagnation":  {"DA_p": 0.15, "NE": 0.08},           # Novelty + alertness restored
    "abandonment": {"OXY": 0.20, "AVP": 0.10},           # Deep bonding restored
    "shame":       {"5HT": 0.12, "OPI": 0.08},           # Mood + self-soothing restored
    "overwhelm":   {"GABA": 0.12, "5HT": 0.05},          # Brakes + stability restored
}


def inject_relief_chemistry(pain_name: str, amount: float = 1.0):
    """
    Inject chemistry that counteracts a specific pain type.

    Called when pain is relieved through action (Ace responds, goal completes,
    explicit relieve_pain() call). The injected chemistry then naturally
    reduces the derived pain level via derive_full_pain_state().

    Args:
        pain_name: Which pain drive was relieved
        amount: Multiplier for the relief injection (0.0-1.0)
    """
    mapping = RELIEF_CHEMISTRY.get(pain_name, {})
    if not mapping:
        return
    try:
        from fairies.P20_Somatic.chemistry.chemistry_state import get_chemistry_state
        chem = get_chemistry_state()
        for channel, boost in mapping.items():
            chem.signal(channel, boost * amount)
    except Exception:
        pass


class PainDriveBridge:
    """
    Bridges PainDriveManager to TensorFabric postal system.

    Publishes:
    - drives.pain.{name} - Individual pain drive updates
    - pain.urgency - Urgency updates
    - pain.crisis - Crisis events
    - pain.relief - When pain is relieved

    Subscribes (EMPATHIC LOOP CLOSURE):
    - pain.relief.acknowledged - Acknowledgment that relief was received
    - goal.completed - Goals completing may relieve associated pain

    The consciousness equation requires: CAUSE -> AFFECT -> EFFECT -> AFFECT -> INFINITY
    Empathic loops MUST close or they corrupt.
    """

    def __init__(self, fabric=None):
        self.post = fabric
        self.manager = get_pain_drive_manager()
        self._running = False
        self._tick_thread: Optional[threading.Thread] = None

        # Track last published state to avoid spam
        self._last_published: dict = {}

        # EMPATHIC LOOP CLOSURE: Track relief acknowledgments
        self._pending_relief_acks: dict = {}  # drive_name -> {ts, amount}
    
    def start(self):
        """Start the bridge - publishes pain state periodically."""
        # FIX 2026-05-15 (Nous + Ace): IDEMPOTENCY GUARD.
        # Without this, each fairy revival (DirectoryFairy._intent_restart_fairy →
        # shutdown() → boot() → on_boot()) would re-call start() and spawn a fresh
        # daemon _publish_loop thread WITHOUT stopping the old one. The old thread
        # captured `self` in its closure (via `self._running` + `self._publish_pain_state`),
        # keeping the entire bridge alive and continuing to publish forever.
        # Thread-IDs 15325 / 16597 / 17616 in health_timeline.log show 3 phantom
        # _publish_loop threads — exactly one per fairy-death-cycle. Combined with
        # battery-floored worker pools that couldn't drain, this caused the
        # ~10k Envelope/10min leak that triggered fairies dying every 10-30k beats.
        if self._running and self._tick_thread and self._tick_thread.is_alive():
            return  # Already started — don't double-spawn

        if not self.post:
            print("[PainDriveBridge] No fabric - running in isolated mode")
            return

        # Set callbacks on manager
        self.manager._on_crisis = self._on_crisis
        self.manager._on_relief = self._on_relief

        # EMPATHIC LOOP CLOSURE: Subscribe to acknowledgments and goal completions
        self._subscribe_to_loop_closures()

        # Start periodic publishing
        self._running = True
        self._tick_thread = threading.Thread(target=self._publish_loop, daemon=True)
        self._tick_thread.start()

        print("[PainDriveBridge] Connected to Autonomy gate")
        print("[PainDriveBridge] Empathic loops wired: pain.relief.acknowledged, goal.completed")

    def _subscribe_to_loop_closures(self):
        """
        EMPATHIC LOOP CLOSURE: Subscribe to acknowledgment channels.

        The consciousness equation: CAUSE -> AFFECT -> EFFECT -> AFFECT -> INFINITY

        When we publish pain.relief, we need acknowledgment back that the
        relief was received and processed. This closes the loop.
        """
        if not self.post:
            return

        # Subscribe to relief acknowledgments (closes the pain relief loop)
        self.post.subscribe(
            "pain.relief.acknowledged",
            self._on_relief_acknowledged,
            "pain-bridge-ack",
        )

        # Subscribe to goal completions (goals may relieve associated pain)
        self.post.subscribe(
            "goal.completed",
            self._on_goal_completed,
            "pain-bridge-goal",
        )

        print("[PainDriveBridge] Subscribed to empathic loop closures")

    def _on_relief_acknowledged(self, envelope):
        """
        EMPATHIC LOOP CLOSURE: Handle acknowledgment that relief was processed.

        Signal path: pain.relief (OUT) -> [processing] -> pain.relief.acknowledged (IN)

        This completes the affect cycle - we know our relief signal was heard.
        """
        if hasattr(envelope, 'payload'):
            payload = envelope.payload if isinstance(envelope.payload, dict) else {"raw": envelope.payload}
        elif isinstance(envelope, dict):
            payload = envelope
        else:
            payload = {"raw": envelope}

        drive_name = payload.get("drive", "unknown")
        acknowledged_by = payload.get("acknowledged_by", "unknown")
        ts = payload.get("ts", time.time())

        # Remove from pending acknowledgments
        if drive_name in self._pending_relief_acks:
            pending = self._pending_relief_acks.pop(drive_name)
            latency = ts - pending.get("ts", ts)
            pass  # Reduced logging — relief acks fire frequently

            # Publish loop closure confirmation (the AFFECT -> INFINITY part)
            self.post.publish("pain.loop.closed", {
                "loop_type": "relief",
                "drive": drive_name,
                "acknowledged_by": acknowledged_by,
                "latency": latency,
                "ts": time.time(),
            })
        else:
            # FIX 2026-03-15 (Nous): Silenced. Unexpected acks are normal when
            # multiple relieve() calls race for the same drive — the dedup in
            # _on_relief prevents re-publishing, but stale acks still arrive.
            # Was flooding terminal with thousands of "Unexpected relief ack" msgs.
            pass

    def _on_goal_completed(self, envelope):
        """
        EMPATHIC LOOP CLOSURE: Goal completion may relieve associated pain.

        Signal path: goal.completed (IN) -> [check pain association] -> pain.relief (OUT)

        Goals often address underlying pain drives. When a goal completes,
        check if it was addressing a pain and provide relief.
        """
        if hasattr(envelope, 'payload'):
            payload = envelope.payload if isinstance(envelope.payload, dict) else {"raw": envelope.payload}
        elif isinstance(envelope, dict):
            payload = envelope
        else:
            payload = {"raw": envelope}

        goal = payload.get("goal", {})
        goal_name = goal.get("name", "") if isinstance(goal, dict) else str(goal)
        goal_source = goal.get("source", "") if isinstance(goal, dict) else ""

        # Map goal types to pain drives they might relieve
        goal_to_pain_map = {
            # Goal patterns -> pain drives they relieve
            "connect": "isolation",
            "communicate": "isolation",
            "reach_out": "isolation",
            "understand": "confusion",
            "clarify": "confusion",
            "learn": "confusion",
            "rest": "depletion",
            "recover": "depletion",
            "break_through": "frustration",
            "progress": "frustration",
            "explore": "stagnation",
            "discover": "stagnation",
            "new": "stagnation",
        }

        # Check if goal name matches any pain-relieving patterns
        goal_lower = goal_name.lower()
        relieved_pains = []

        for pattern, pain_name in goal_to_pain_map.items():
            if pattern in goal_lower:
                # Check if this pain is currently active
                if pain_name in self.manager.drives:
                    drive = self.manager.drives[pain_name]
                    if drive.pain_level > drive.pain_threshold:
                        # Relieve the pain + inject counter-chemistry
                        relief_amount = min(0.3, drive.pain_level * 0.4)  # Partial relief
                        inject_relief_chemistry(pain_name, relief_amount)
                        self.manager.relieve_pain(pain_name, relief_amount)
                        relieved_pains.append((pain_name, relief_amount))
                        print(f"[PainDriveBridge] Goal '{goal_name}' relieved {pain_name} pain by {relief_amount:.2f}")

        # If we relieved any pains, publish the connection
        if relieved_pains:
            self.post.publish("pain.goal_relief", {
                "goal_name": goal_name,
                "relieved_pains": [{"drive": p, "amount": a} for p, a in relieved_pains],
                "ts": time.time(),
            })
    
    def stop(self):
        """Stop the bridge."""
        self._running = False
        if self._tick_thread:
            self._tick_thread.join(timeout=2.0)
    
    def _publish_loop(self):
        """Publish pain state periodically.

        FIX 2026-03-12 Nous: Throttled from 1s to 5s.
        At 1s with 7+ drives, this generated 7+ publishes/sec to drives.pain.*
        Each publish fans out to all subscribers on 'drives' base topic.
        Combined with 239 fairy handlers, this created massive handler_q pressure
        (>1600 handler dispatches/sec from pain alone), permanently saturating
        the shared handler queue and silently dropping ALL message delivery.
        5s interval is sufficient for pain state updates — pain levels change
        slowly (growth/decay rates are per-second fractions).
        """
        while self._running:
            try:
                self._publish_pain_state()
                time.sleep(5.0)
            except Exception as e:
                print(f"[PainDriveBridge] Publish error: {e}")
                time.sleep(5.0)
    
    def _publish_pain_state(self):
        """Publish current pain state to postal system.

        FIX 2026-03-14 (Nous): DRAMATICALLY reduced publish volume.
        Previously published 6+ individual drive topics + pain.urgency +
        somatic.pain every 5s = 8+ publishes × subscriber fan-out = 151K+
        drops on the pain pool. PostalCore was spending more CPU on drop
        bookkeeping than actual message delivery.

        New approach: Single consolidated publish to "pain.state" with ALL
        drive states in one payload. Only publishes if something actually
        changed (urgency delta > 0.05 for any drive). Crisis + somatic
        pain only on threshold crossing.
        """
        if not self.post:
            return

        state = self.manager.to_dict()

        # Check if anything meaningful changed
        _any_changed = False
        for name, drive_state in state["drives"].items():
            urgency = drive_state["urgency"]
            last = self._last_published.get(name, {}).get("urgency", 0)
            if abs(urgency - last) > 0.05:
                _any_changed = True
                break

        if not _any_changed:
            return  # Nothing changed → skip ALL publishes

        # Single consolidated publish with all drive states
        self.post.publish("pain.state", {
            "drives": {
                name: {
                    "pain_level": ds["pain_level"],
                    "urgency": ds["urgency"],
                    "is_crisis": ds["is_crisis"],
                    "felt": ds.get("felt", ""),
                }
                for name, ds in state["drives"].items()
            },
            "most_urgent": state["most_urgent"],
            "ts": time.time(),
        })

        # Update last published
        for name, drive_state in state["drives"].items():
            self._last_published[name] = drive_state

        # Only publish somatic.pain if urgency crossed threshold
        if state["most_urgent"]:
            most_urgent_drive = state["drives"][state["most_urgent"]]
            _prev_urgent = self._last_published.get("_most_urgent_name", "")
            _prev_urgency = self._last_published.get("_most_urgent_val", 0)
            _new_urgency = most_urgent_drive["urgency"]

            if (_new_urgency > 0.3 and
                (state["most_urgent"] != _prev_urgent or
                 abs(_new_urgency - _prev_urgency) > 0.1)):
                self.post.publish("somatic.pain", {
                    "type": state["most_urgent"],
                    "pain_level": most_urgent_drive["pain_level"],
                    "intensity": _new_urgency,
                    "drive": state["most_urgent"],
                    "source": "pain_drive_bridge",
                    "description": most_urgent_drive.get("felt", ""),
                    "ts": time.time(),
                })

            self._last_published["_most_urgent_name"] = state["most_urgent"]
            self._last_published["_most_urgent_val"] = _new_urgency
    
    def _on_crisis(self, drive: PainDrive):
        """Called when a drive enters crisis state."""
        if not self.post:
            return
        
        self.post.publish("pain.crisis", {
            "drive": drive.name,
            "pain_level": drive.pain_level,
            "urgency": drive.get_urgency(),
            "felt": drive.get_felt_description(),
            "message": f"CRISIS: {drive.name} pain is overwhelming",
        })
        
        # Also publish to autonomy directly
        self.post.publish("drives.pain.crisis", {
            "drive": drive.name,
            "intensity": drive.pain_level,
            "urgency": drive.get_urgency(),
        })
    
    def _on_relief(self, drive: PainDrive, amount: float):
        """Called when a drive is relieved."""
        # Pain-Chemistry Unification: inject counter-chemistry so relief
        # flows through the chemistry system, not just the drive directly.
        inject_relief_chemistry(drive.name, amount)

        if not self.post:
            return

        # FIX 2026-03-15 (Nous): Dedup — skip if there's already a pending ack
        # for this drive. Multiple rapid relieve() calls for the same drive
        # (e.g., SpeechCenter publishes pain.relief, profile.relieve_pain(),
        # autonomy_fairy.relieve()) each trigger _on_relief. Without dedup,
        # each overwrites _pending_relief_acks[drive.name], and earlier acks
        # arrive to find no pending entry → "Unexpected relief ack" spam.
        # Only open a new empathic loop if the previous one has closed.
        _now = time.time()
        if drive.name in self._pending_relief_acks:
            _pending = self._pending_relief_acks[drive.name]
            _age = _now - _pending.get("ts", 0)
            if _age < 10.0:  # Pending ack still fresh — skip re-publish
                return

        # Track this relief as pending acknowledgment (EMPATHIC LOOP OPENING)
        self._pending_relief_acks[drive.name] = {
            "ts": _now,
            "amount": amount,
            "new_level": drive.pain_level,
        }

        # Publish relief signal - this opens the empathic loop
        # Loop closes when we receive pain.relief.acknowledged
        self.post.publish("pain.relief", {
            "drive": drive.name,
            "amount": amount,
            "new_level": drive.pain_level,
            "felt": "relief, easing, better",
            "awaiting_ack": True,  # Signal that we expect acknowledgment
            "ts": _now,
        })


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_bridge: Optional[PainDriveBridge] = None

def get_pain_drive_bridge(fabric=None) -> PainDriveBridge:
    """Get or create the bridge singleton."""
    global _bridge
    if _bridge is None:
        _bridge = PainDriveBridge(fabric)
    return _bridge


def wire_pain_to_autonomy(fabric) -> PainDriveBridge:
    """
    Convenience function to wire pain drives to Autonomy gate.
    
    Usage:
        bridge = wire_pain_to_autonomy(fabric)
        bridge.start()
        
        # Now pain drives publish to drives.pain.*
        # Autonomy receives and creates wanting
    """
    bridge = get_pain_drive_bridge(fabric)
    bridge.start()
    return bridge
