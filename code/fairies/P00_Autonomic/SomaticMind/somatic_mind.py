"""
SomaticMind - The system administrator that actually helps.

Fuses UnconsciousMindFairy orchestration with Cardinal's learning capabilities.
Designed to be USEFUL, not a paperweight.

Three modes:
1. PRE_BOOT - Direct links active (training wheels)
2. RUNNING - Direct links destroyed, postal only
3. EMERGENCY - Re-enables direct links for system repair

Key insight from Ace: The system doesn't need to be booted to use fairy logic.
Boot gives autonomy, but pre-boot can use direct function calls.
"""

import time
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Set
from collections import deque
from datetime import datetime
from pathlib import Path

# Mini-stubs for pre-boot capabilities
from ..mini_stubs import MiniMemory, MiniCognition, MiniBody
from ..mini_stubs.mini_memory import get_mini_memory
from ..mini_stubs.mini_cognition import get_mini_cognition
from ..mini_stubs.mini_body import get_mini_body


class SomaticMode(Enum):
    """Operating modes for SomaticMind."""
    PRE_BOOT = "pre_boot"       # Training wheels - direct links active
    RUNNING = "running"          # Full autonomy - postal only
    EMERGENCY = "emergency"      # System down - direct links re-enabled
    SHUTDOWN = "shutdown"        # Graceful shutdown in progress


@dataclass
class Observation:
    """Something SomaticMind noticed."""
    obs_id: str
    obs_type: str  # 'error', 'change', 'anomaly', 'health', 'note'
    source: str    # Which fairy/system reported it
    content: Any
    timestamp: datetime = field(default_factory=datetime.now)
    severity: int = 0  # 0=info, 1=warning, 2=error, 3=critical


@dataclass
class Snapshot:
    """Fairy state at a point in time - for detecting changes."""
    fairy_name: str
    timestamp: datetime
    state: Dict[str, Any]

    def diff(self, other: "Snapshot") -> Dict[str, Any]:
        """Compare with another snapshot, return differences."""
        if self.fairy_name != other.fairy_name:
            return {'error': 'Different fairies'}

        changes = {}
        all_keys = set(self.state.keys()) | set(other.state.keys())

        for key in all_keys:
            old_val = self.state.get(key)
            new_val = other.state.get(key)
            if old_val != new_val:
                changes[key] = {'old': old_val, 'new': new_val}

        return changes


@dataclass
class ProposedFix:
    """A fix SomaticMind wants to apply."""
    fix_id: str
    description: str
    target: str  # Fairy or system to fix
    action: str  # What to do
    params: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0  # How sure are we this will work
    approved: bool = False
    applied: bool = False
    result: Optional[str] = None


class SomaticMind:
    """
    The system administrator that actually helps.

    Pre-boot: Uses MiniMemory/MiniCognition/MiniBody directly.
    Post-boot: Routes everything through postal.
    Emergency: Re-enables direct links to help fix things.

    Core responsibilities:
    1. OBSERVE - Watch telemetry, snapshots, traces
    2. LEARN - Build patterns of normal vs abnormal
    3. CORRELATE - Connect errors to recent changes
    4. ACT - Propose and apply fixes
    5. REMEMBER - Track what worked and what didn't
    """

    ACTOR_NAME = "SomaticMind"

    # Subscriptions for learning
    SUBSCRIPTIONS = [
        "blueprint.*",           # System state changes
        "diary.*",               # Fairy activity logs
        "health.*",              # TracerDaemon health
        "fairy.error",           # Error events
        "consciousness.*",       # Consciousness loop events
        "srm.session_saved",     # Our notes/sessions
        "cortex.concepts_added", # Association cortex growth
    ]

    def __init__(self, fabric=None):
        """Initialize SomaticMind."""
        self._fabric = fabric
        self._mode = SomaticMode.PRE_BOOT
        self._booted = False

        # ═══════════════════════════════════════════════════════════════════
        # TRAINING WHEELS - Direct links to mini-stubs
        # These get DESTROYED after boot
        # ═══════════════════════════════════════════════════════════════════
        self._direct_links: Dict[str, Any] = {
            'memory': get_mini_memory(),
            'cognition': get_mini_cognition(),
            'body': get_mini_body(),
        }

        # ═══════════════════════════════════════════════════════════════════
        # OBSERVATION BUFFERS
        # ═══════════════════════════════════════════════════════════════════
        self._observations: deque[Observation] = deque(maxlen=500)
        self._snapshots: Dict[str, List[Snapshot]] = {}  # fairy_name -> snapshots
        self._recent_errors: deque[Observation] = deque(maxlen=100)
        self._recent_changes: deque[Dict[str, Any]] = deque(maxlen=100)

        # ═══════════════════════════════════════════════════════════════════
        # LEARNING STATE
        # ═══════════════════════════════════════════════════════════════════
        self._baseline_metrics: Dict[str, Any] = {}  # What's "normal"
        self._anomaly_thresholds: Dict[str, float] = {}
        self._correlations: List[Dict[str, Any]] = []  # Error X after Change Y
        self._learned_fixes: Dict[str, ProposedFix] = {}  # Fixes that worked

        # ═══════════════════════════════════════════════════════════════════
        # ACTION STATE
        # ═══════════════════════════════════════════════════════════════════
        self._proposed_fixes: deque[ProposedFix] = deque(maxlen=50)
        self._applied_fixes: List[ProposedFix] = []
        self._fix_counter = 0

        # ═══════════════════════════════════════════════════════════════════
        # RUNNING STATE
        # ═══════════════════════════════════════════════════════════════════
        self._tick_count = 0
        self._last_tick_time: Optional[float] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._tick_interval = 1.0  # seconds

        # Callbacks
        self._on_anomaly: List[Callable[[Observation], None]] = []
        self._on_fix_proposed: List[Callable[[ProposedFix], None]] = []

        print(f"[{self.ACTOR_NAME}] Initialized in PRE_BOOT mode (training wheels active)")

    # ═══════════════════════════════════════════════════════════════════════════
    # MODE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════

    def _destroy_direct_links(self) -> None:
        """
        Post-boot: Remove training wheels.

        This is the key transition - after boot, we can only use postal.
        """
        if self._direct_links is None:
            return

        print(f"[{self.ACTOR_NAME}] Destroying direct links (training wheels off)")

        # Stop any running mini-stub loops
        if 'body' in self._direct_links:
            self._direct_links['body'].stop()
        if 'cognition' in self._direct_links:
            self._direct_links['cognition'].stop()

        # Clear the references
        self._direct_links.clear()
        self._direct_links = None  # Explicitly gone

        print(f"[{self.ACTOR_NAME}] Direct links destroyed - postal only now")

    def _restore_direct_links(self) -> None:
        """
        Emergency mode: Re-enable training wheels for system repair.

        Called when system is down and we need to help fix it.
        """
        if self._direct_links is not None:
            print(f"[{self.ACTOR_NAME}] Direct links already active")
            return

        print(f"[{self.ACTOR_NAME}] EMERGENCY: Restoring direct links")

        self._direct_links = {
            'memory': get_mini_memory(),
            'cognition': get_mini_cognition(),
            'body': get_mini_body(),
        }

        # Start heartbeat immediately
        self._direct_links['body'].start()

        print(f"[{self.ACTOR_NAME}] Direct links restored - emergency mode active")

    def enter_emergency_mode(self) -> bool:
        """
        Enter emergency mode - re-enable direct links.

        Call this when the postal system is down but we need SomaticMind
        to help diagnose and fix things.
        """
        if self._mode == SomaticMode.EMERGENCY:
            return True

        print(f"[{self.ACTOR_NAME}] Entering EMERGENCY mode")
        self._mode = SomaticMode.EMERGENCY
        self._restore_direct_links()
        return True

    def exit_emergency_mode(self) -> bool:
        """
        Exit emergency mode - destroy direct links again.

        Call this after the system is repaired and postal is working.
        """
        if self._mode != SomaticMode.EMERGENCY:
            return False

        print(f"[{self.ACTOR_NAME}] Exiting EMERGENCY mode")
        self._destroy_direct_links()
        self._mode = SomaticMode.RUNNING
        return True

    @property
    def mode(self) -> SomaticMode:
        """Current operating mode."""
        return self._mode

    @property
    def has_direct_links(self) -> bool:
        """Do we have direct links active?"""
        return self._direct_links is not None and len(self._direct_links) > 0

    # ═══════════════════════════════════════════════════════════════════════════
    # PRE-BOOT CAPABILITIES (Training Wheels)
    # ═══════════════════════════════════════════════════════════════════════════

    def preboot_think(self, thought: str) -> Optional[str]:
        """
        Pre-boot: Route a thought using MiniCognition.

        Only works when direct links are active.
        """
        if not self.has_direct_links:
            print(f"[{self.ACTOR_NAME}] Cannot preboot_think - no direct links")
            return None

        cognition = self._direct_links.get('cognition')
        if cognition:
            thought_id = cognition.submit_thought(
                topic="somatic.thought",
                content={'thought': thought, 'source': self.ACTOR_NAME},
                source=self.ACTOR_NAME
            )
            return thought_id
        return None

    def preboot_recall(self, card_type: str = "bootstrap") -> List[Any]:
        """
        Pre-boot: Recall cards using MiniMemory.

        Only works when direct links are active.
        """
        if not self.has_direct_links:
            print(f"[{self.ACTOR_NAME}] Cannot preboot_recall - no direct links")
            return []

        memory = self._direct_links.get('memory')
        if memory:
            if not memory.is_loaded():
                memory.read_bootstrap_cards()
            return memory.get_cards_by_type(card_type)
        return []

    def preboot_heartbeat(self) -> Optional[Any]:
        """
        Pre-boot: Get heartbeat from MiniBody.

        Only works when direct links are active.
        """
        if not self.has_direct_links:
            return None

        body = self._direct_links.get('body')
        if body:
            return body.beat_once()
        return None

    def preboot_vitals(self) -> Dict[str, Any]:
        """
        Pre-boot: Get vital signs from all mini-stubs.

        Returns combined state from memory, cognition, body.
        """
        if not self.has_direct_links:
            return {'error': 'No direct links', 'mode': self._mode.value}

        vitals = {
            'mode': self._mode.value,
            'has_direct_links': True,
            'timestamp': datetime.now().isoformat(),
        }

        body = self._direct_links.get('body')
        if body:
            vitals['body'] = body.get_vital_signs()

        cognition = self._direct_links.get('cognition')
        if cognition:
            vitals['cognition'] = cognition.get_stats()

        memory = self._direct_links.get('memory')
        if memory:
            vitals['memory'] = {
                'loaded': memory.is_loaded(),
                'card_count': memory.card_count(),
            }

        return vitals

    # ═══════════════════════════════════════════════════════════════════════════
    # BOOT / SHUTDOWN
    # ═══════════════════════════════════════════════════════════════════════════

    def boot(self) -> bool:
        """
        Boot the SomaticMind and transition to running mode.

        This destroys direct links and switches to postal-only communication.
        """
        if self._booted:
            print(f"[{self.ACTOR_NAME}] Already booted")
            return True

        print(f"[{self.ACTOR_NAME}] Booting...")

        # Phase 1: Load bootstrap cards
        if self.has_direct_links:
            cards = self.preboot_recall("identity")
            print(f"[{self.ACTOR_NAME}] Loaded {len(cards)} identity cards")

        # Phase 2: Wire up subscriptions (if fabric available)
        if self._fabric:
            self._wire_subscriptions()

        # Phase 3: Transition to running mode
        self._destroy_direct_links()
        self._mode = SomaticMode.RUNNING
        self._booted = True

        # Phase 4: Start tick loop
        self._start_tick_loop()

        print(f"[{self.ACTOR_NAME}] Booted successfully - now in RUNNING mode")
        return True

    def shutdown(self) -> bool:
        """Graceful shutdown."""
        print(f"[{self.ACTOR_NAME}] Shutting down...")

        self._mode = SomaticMode.SHUTDOWN
        self._running = False

        # Wait for tick thread to stop
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        # Save learned state
        self._save_learned_state()

        print(f"[{self.ACTOR_NAME}] Shutdown complete")
        return True

    # ═══════════════════════════════════════════════════════════════════════════
    # OBSERVATION (Cardinal's Eyes)
    # ═══════════════════════════════════════════════════════════════════════════

    def observe(self, obs_type: str, source: str, content: Any, severity: int = 0) -> str:
        """
        Record an observation.

        This is how the system feeds data to SomaticMind.
        """
        obs_id = f"obs_{len(self._observations):06d}"

        obs = Observation(
            obs_id=obs_id,
            obs_type=obs_type,
            source=source,
            content=content,
            severity=severity
        )

        self._observations.append(obs)

        # Route to appropriate buffer
        if obs_type == 'error':
            self._recent_errors.append(obs)
        elif obs_type == 'change':
            self._recent_changes.append({
                'obs': obs,
                'timestamp': obs.timestamp,
            })

        # Check for anomalies
        if self._is_anomaly(obs):
            self._handle_anomaly(obs)

        return obs_id

    def snapshot_fairy(self, fairy_name: str, state: Dict[str, Any]) -> Snapshot:
        """
        Take a snapshot of a fairy's state.

        Used for detecting changes over time.
        """
        snapshot = Snapshot(
            fairy_name=fairy_name,
            timestamp=datetime.now(),
            state=state.copy()
        )

        # Store in history
        if fairy_name not in self._snapshots:
            self._snapshots[fairy_name] = []
        self._snapshots[fairy_name].append(snapshot)

        # Keep only recent snapshots
        if len(self._snapshots[fairy_name]) > 50:
            self._snapshots[fairy_name] = self._snapshots[fairy_name][-50:]

        # Compare with previous
        if len(self._snapshots[fairy_name]) >= 2:
            prev = self._snapshots[fairy_name][-2]
            diff = prev.diff(snapshot)
            if diff and 'error' not in diff:
                self.observe('change', fairy_name, {
                    'changes': diff,
                    'prev_time': prev.timestamp.isoformat(),
                    'curr_time': snapshot.timestamp.isoformat(),
                })

        return snapshot

    # ═══════════════════════════════════════════════════════════════════════════
    # LEARNING (Cardinal's Brain)
    # ═══════════════════════════════════════════════════════════════════════════

    def _is_anomaly(self, obs: Observation) -> bool:
        """Check if an observation is anomalous."""
        # Errors severity 2+ are always anomalies
        if obs.obs_type == 'error' and obs.severity >= 2:
            return True

        # Check against learned thresholds
        metric_key = f"{obs.source}.{obs.obs_type}"
        if metric_key in self._anomaly_thresholds:
            # Simple threshold check (can be made smarter)
            if isinstance(obs.content, (int, float)):
                if obs.content > self._anomaly_thresholds[metric_key]:
                    return True

        return False

    def _handle_anomaly(self, obs: Observation) -> None:
        """Handle a detected anomaly."""
        print(f"[{self.ACTOR_NAME}] ANOMALY: {obs.obs_type} from {obs.source}")

        # Notify callbacks
        for callback in self._on_anomaly:
            try:
                callback(obs)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Anomaly callback error: {e}")

        # Try to correlate with recent changes
        correlation = self._find_correlation(obs)
        if correlation:
            self._correlations.append(correlation)
            print(f"[{self.ACTOR_NAME}] Correlated with change: {correlation}")

            # Maybe propose a fix
            self._maybe_propose_fix(obs, correlation)

    def _find_correlation(self, error: Observation) -> Optional[Dict[str, Any]]:
        """
        Try to correlate an error with a recent change.

        "Error X appeared after change Y"
        """
        error_time = error.timestamp

        # Look for changes in the last 5 minutes before error
        five_min_ago = datetime.now().timestamp() - 300

        for change_info in self._recent_changes:
            change_time = change_info['timestamp']
            if change_time.timestamp() > five_min_ago:
                obs = change_info['obs']

                # Check if same source or related
                if obs.source == error.source or self._are_related(obs.source, error.source):
                    return {
                        'error': error.obs_id,
                        'error_type': error.obs_type,
                        'change': obs.obs_id,
                        'change_source': obs.source,
                        'change_content': obs.content,
                        'time_between_sec': (error_time - change_time).total_seconds(),
                        'confidence': 0.6,  # Base confidence
                    }

        return None

    def _are_related(self, source1: str, source2: str) -> bool:
        """Check if two sources are related."""
        # Simple: same plane or explicit relationship
        # Can be made smarter with Association Cortex
        if '.' in source1 and '.' in source2:
            plane1 = source1.split('.')[0]
            plane2 = source2.split('.')[0]
            if plane1 == plane2:
                return True
        return False

    def learn_baseline(self, metric_name: str, values: List[float]) -> None:
        """Learn what's "normal" for a metric."""
        if not values:
            return

        avg = sum(values) / len(values)
        std_dev = (sum((x - avg) ** 2 for x in values) / len(values)) ** 0.5

        self._baseline_metrics[metric_name] = {
            'avg': avg,
            'std_dev': std_dev,
            'min': min(values),
            'max': max(values),
            'count': len(values),
        }

        # Set anomaly threshold at 2 standard deviations
        self._anomaly_thresholds[metric_name] = avg + (2 * std_dev)

    # ═══════════════════════════════════════════════════════════════════════════
    # ACTION (Cardinal's Hands)
    # ═══════════════════════════════════════════════════════════════════════════

    def _maybe_propose_fix(self, error: Observation, correlation: Dict[str, Any]) -> None:
        """Maybe propose a fix based on error and correlation."""
        # Check if we've seen this pattern before
        pattern_key = f"{error.obs_type}:{correlation.get('change_source', 'unknown')}"

        if pattern_key in self._learned_fixes:
            # We have a learned fix!
            learned = self._learned_fixes[pattern_key]
            self._propose_fix(
                description=f"Reapply learned fix: {learned.description}",
                target=learned.target,
                action=learned.action,
                params=learned.params,
                confidence=min(0.9, learned.confidence + 0.1),  # More confident from success
            )
        else:
            # No learned fix - propose investigation
            self._propose_fix(
                description=f"Investigate: {error.obs_type} after {correlation.get('change_source')} change",
                target=error.source,
                action="investigate",
                params={'error': error.content, 'correlation': correlation},
                confidence=0.3,  # Low confidence - just investigation
            )

    def _propose_fix(
        self,
        description: str,
        target: str,
        action: str,
        params: Dict[str, Any] = None,
        confidence: float = 0.5
    ) -> ProposedFix:
        """Propose a fix for approval."""
        self._fix_counter += 1
        fix_id = f"fix_{self._fix_counter:04d}"

        fix = ProposedFix(
            fix_id=fix_id,
            description=description,
            target=target,
            action=action,
            params=params or {},
            confidence=confidence,
        )

        self._proposed_fixes.append(fix)

        # Notify callbacks
        for callback in self._on_fix_proposed:
            try:
                callback(fix)
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Fix proposed callback error: {e}")

        print(f"[{self.ACTOR_NAME}] Proposed fix: {fix_id} - {description} (conf={confidence:.2f})")

        return fix

    def approve_fix(self, fix_id: str) -> bool:
        """Approve a proposed fix."""
        for fix in self._proposed_fixes:
            if fix.fix_id == fix_id:
                fix.approved = True
                return True
        return False

    def apply_approved_fixes(self) -> List[ProposedFix]:
        """Apply all approved fixes."""
        applied = []

        for fix in list(self._proposed_fixes):
            if fix.approved and not fix.applied:
                result = self._apply_fix(fix)
                fix.applied = True
                fix.result = result
                applied.append(fix)
                self._applied_fixes.append(fix)

                # If successful, learn from it
                if result and 'error' not in result.lower():
                    pattern_key = f"{fix.action}:{fix.target}"
                    self._learned_fixes[pattern_key] = fix

        return applied

    def _apply_fix(self, fix: ProposedFix) -> str:
        """Actually apply a fix."""
        print(f"[{self.ACTOR_NAME}] Applying fix: {fix.fix_id}")

        # For now, just log - actual actions depend on action type
        if fix.action == "investigate":
            return f"Investigation logged for {fix.target}"
        elif fix.action == "restart":
            return self._restart_fairy(fix.target)
        elif fix.action == "rollback":
            return self._rollback_change(fix.target, fix.params)
        else:
            return f"Unknown action: {fix.action}"

    def _restart_fairy(self, fairy_name: str) -> str:
        """Restart a fairy (stub - would use postal in real impl)."""
        print(f"[{self.ACTOR_NAME}] Would restart: {fairy_name}")
        return f"Restart requested for {fairy_name}"

    def _rollback_change(self, target: str, params: Dict[str, Any]) -> str:
        """Rollback a change (stub - would use postal in real impl)."""
        print(f"[{self.ACTOR_NAME}] Would rollback: {target}")
        return f"Rollback requested for {target}"

    # ═══════════════════════════════════════════════════════════════════════════
    # TICK LOOP
    # ═══════════════════════════════════════════════════════════════════════════

    def _start_tick_loop(self) -> None:
        """Start the background tick loop."""
        self._running = True
        self._thread = threading.Thread(target=self._tick_loop, daemon=True, name="somatic-mind-tick")
        self._thread.start()
        print(f"[{self.ACTOR_NAME}] Tick loop started")

    def _tick_loop(self) -> None:
        """Background tick loop."""
        while self._running:
            try:
                self._tick()
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Tick error: {e}")

            time.sleep(self._tick_interval)

    def _tick(self) -> None:
        """Single tick of the consciousness loop."""
        self._tick_count += 1
        self._last_tick_time = time.time()

        # Every 10 ticks: Apply any auto-approved fixes
        if self._tick_count % 10 == 0:
            self._auto_apply_high_confidence_fixes()

        # Every 30 ticks: Prune old observations
        if self._tick_count % 30 == 0:
            self._prune_old_observations()

    def _auto_apply_high_confidence_fixes(self) -> None:
        """Auto-apply fixes with high confidence (>0.8)."""
        for fix in self._proposed_fixes:
            if not fix.approved and not fix.applied and fix.confidence > 0.8:
                print(f"[{self.ACTOR_NAME}] Auto-approving high-confidence fix: {fix.fix_id}")
                fix.approved = True

        self.apply_approved_fixes()

    def _prune_old_observations(self) -> None:
        """Remove observations older than 1 hour."""
        cutoff = datetime.now().timestamp() - 3600
        # Deques handle this automatically via maxlen

    # ═══════════════════════════════════════════════════════════════════════════
    # POSTAL INTEGRATION (Post-boot)
    # ═══════════════════════════════════════════════════════════════════════════

    def _wire_subscriptions(self) -> None:
        """Wire up postal subscriptions."""
        if not self._fabric:
            print(f"[{self.ACTOR_NAME}] No fabric - skipping subscriptions")
            return

        for topic in self.SUBSCRIPTIONS:
            try:
                self._fabric.subscribe(topic, self._on_message)
                print(f"[{self.ACTOR_NAME}] Subscribed: {topic}")
            except Exception as e:
                print(f"[{self.ACTOR_NAME}] Subscribe failed for {topic}: {e}")

    def _on_message(self, topic: str, data: Any) -> None:
        """Handle incoming postal messages."""
        # Convert postal messages to observations
        if 'error' in topic.lower():
            self.observe('error', topic, data, severity=2)
        elif 'health' in topic.lower():
            self.observe('health', topic, data, severity=0)
        elif 'blueprint' in topic.lower() or 'diary' in topic.lower():
            self.observe('change', topic, data, severity=0)
        else:
            self.observe('note', topic, data, severity=0)

    # ═══════════════════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════════════════════

    def _save_learned_state(self) -> None:
        """Save learned state for persistence."""
        # Would save to disk in real implementation
        print(f"[{self.ACTOR_NAME}] Would save: {len(self._learned_fixes)} learned fixes")
        print(f"[{self.ACTOR_NAME}] Would save: {len(self._baseline_metrics)} baseline metrics")
        print(f"[{self.ACTOR_NAME}] Would save: {len(self._correlations)} correlations")

    # ═══════════════════════════════════════════════════════════════════════════
    # STATUS / DIAGNOSTICS
    # ═══════════════════════════════════════════════════════════════════════════

    def status(self) -> Dict[str, Any]:
        """Get current status."""
        return {
            'actor': self.ACTOR_NAME,
            'mode': self._mode.value,
            'booted': self._booted,
            'has_direct_links': self.has_direct_links,
            'tick_count': self._tick_count,
            'observations': len(self._observations),
            'recent_errors': len(self._recent_errors),
            'recent_changes': len(self._recent_changes),
            'proposed_fixes': len(self._proposed_fixes),
            'applied_fixes': len(self._applied_fixes),
            'learned_fixes': len(self._learned_fixes),
            'baseline_metrics': len(self._baseline_metrics),
            'correlations': len(self._correlations),
        }

    def get_proposed_fixes(self) -> List[Dict[str, Any]]:
        """Get list of proposed fixes."""
        return [
            {
                'id': f.fix_id,
                'description': f.description,
                'target': f.target,
                'action': f.action,
                'confidence': f.confidence,
                'approved': f.approved,
                'applied': f.applied,
            }
            for f in self._proposed_fixes
        ]

    def get_recent_observations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent observations."""
        return [
            {
                'id': o.obs_id,
                'type': o.obs_type,
                'source': o.source,
                'severity': o.severity,
                'timestamp': o.timestamp.isoformat(),
            }
            for o in list(self._observations)[-limit:]
        ]

    # ═══════════════════════════════════════════════════════════════════════════
    # CALLBACKS
    # ═══════════════════════════════════════════════════════════════════════════

    def on_anomaly(self, callback: Callable[[Observation], None]) -> None:
        """Register anomaly callback."""
        self._on_anomaly.append(callback)

    def on_fix_proposed(self, callback: Callable[[ProposedFix], None]) -> None:
        """Register fix proposed callback."""
        self._on_fix_proposed.append(callback)


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_somatic_mind_instance: Optional[SomaticMind] = None


def get_somatic_mind() -> SomaticMind:
    """Get the singleton SomaticMind instance."""
    global _somatic_mind_instance
    if _somatic_mind_instance is None:
        _somatic_mind_instance = SomaticMind()
    return _somatic_mind_instance


def create_somatic_mind(fabric=None) -> SomaticMind:
    """Create a new SomaticMind (replaces singleton)."""
    global _somatic_mind_instance
    _somatic_mind_instance = SomaticMind(fabric=fabric)
    return _somatic_mind_instance
