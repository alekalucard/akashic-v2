"""
CardinalMixin - SAO-style autonomous system administrator capabilities.

Fuses P00 SomaticMind's survival system into P20 SomaticMindFairy:
- Mode management (PRE_BOOT, RUNNING, EMERGENCY, SHUTDOWN)
- Training wheels (direct links to mini-stubs for pre-boot / emergency)
- Observation pipeline (observe → anomaly detection → correlation)
- Snapshot & diff (track fairy state changes over time)
- Fix pipeline (propose → approve → apply → learn)
- Auto-apply high confidence fixes (>0.8)
- Persistence of learned fixes and baselines

Like SAO's Cardinal: maintains, balances, and fixes the world autonomously.
"""

import time
import json
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from collections import deque, defaultdict
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# CARDINAL INBOX - Persistent anomaly/fix log Ace can read
# ═══════════════════════════════════════════════════════════════════════════════
CARDINAL_INBOX = Path(__file__).parent.parent.parent.parent.parent / "state" / "cardinal_inbox.jsonl"
_inbox_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════════════════════════
# DATA TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class CardinalMode(Enum):
    """Operating modes for the Cardinal system."""
    PRE_BOOT = "pre_boot"       # Training wheels - direct links active
    RUNNING = "running"          # Full autonomy - postal only
    EMERGENCY = "emergency"      # System down - direct links re-enabled
    SHUTDOWN = "shutdown"        # Graceful shutdown in progress


@dataclass
class Observation:
    """Something Cardinal noticed."""
    obs_id: str
    obs_type: str  # 'error', 'change', 'anomaly', 'health', 'note'
    source: str
    content: Any
    timestamp: float = field(default_factory=time.time)
    severity: int = 0  # 0=info, 1=warning, 2=error, 3=critical


@dataclass
class FairySnapshot:
    """Fairy state at a point in time - for detecting changes."""
    fairy_name: str
    timestamp: float
    state: Dict[str, Any]

    def diff(self, other: "FairySnapshot") -> Dict[str, Any]:
        """Compare with another snapshot, return differences."""
        if self.fairy_name != other.fairy_name:
            return {"error": "Different fairies"}
        changes = {}
        all_keys = set(self.state.keys()) | set(other.state.keys())
        for key in all_keys:
            old_val = self.state.get(key)
            new_val = other.state.get(key)
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}
        return changes


@dataclass
class ProposedFix:
    """A fix Cardinal wants to apply."""
    fix_id: str
    description: str
    target: str
    action: str  # 'restart', 'rollback', 'investigate', 'reconfig'
    params: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    approved: bool = False
    applied: bool = False
    result: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════════════════════
# THE MIXIN
# ═══════════════════════════════════════════════════════════════════════════════

class CardinalMixin:
    """
    Cardinal system administrator capabilities.

    Provides:
    - _cardinal_init(): Call in __init__ to set up state
    - _cardinal_boot(): Call in on_boot to transition from PRE_BOOT to RUNNING
    - _cardinal_tick(beat): Call in on_tick for periodic operations
    - enter_emergency_mode() / exit_emergency_mode(): Mode transitions
    - observe(): Feed observations from anywhere
    - snapshot_fairy(): Take fairy state snapshots
    - get_cardinal_status(): Full status dict
    """

    # Topics Cardinal listens to for observations
    CARDINAL_SUBSCRIPTIONS = [
        "fairy.error",
        "fairy.heartbeat",
        "health.*",
        "blueprint.*",
        "diary.*",
        "cardinal.gaps_detected",  # Sprint 1: gap scan results from AdminTaskQueue
    ]

    def _cardinal_init(self) -> None:
        """Initialize Cardinal state. Call from __init__."""
        # Mode
        self._cardinal_mode = CardinalMode.PRE_BOOT
        self._cardinal_booted = False

        # Training wheels - direct links to mini-stubs
        self._direct_links: Optional[Dict[str, Any]] = None
        self._training_wheels_available = False
        try:
            from fairies.P00_Autonomic.mini_stubs import MiniMemory, MiniCognition, MiniBody
            from fairies.P00_Autonomic.mini_stubs.mini_memory import get_mini_memory
            from fairies.P00_Autonomic.mini_stubs.mini_cognition import get_mini_cognition
            from fairies.P00_Autonomic.mini_stubs.mini_body import get_mini_body
            self._mini_memory_factory = get_mini_memory
            self._mini_cognition_factory = get_mini_cognition
            self._mini_body_factory = get_mini_body
            self._training_wheels_available = True
        except ImportError:
            self._mini_memory_factory = None
            self._mini_cognition_factory = None
            self._mini_body_factory = None

        # Observation buffers
        self._observations: deque = deque(maxlen=500)
        self._recent_errors: deque = deque(maxlen=100)
        self._recent_changes: deque = deque(maxlen=100)

        # Snapshot history: fairy_name -> list of snapshots
        self._fairy_snapshots: Dict[str, List[FairySnapshot]] = {}

        # Learning state
        self._baseline_metrics: Dict[str, Dict[str, float]] = {}
        self._anomaly_thresholds: Dict[str, float] = {}
        self._correlations: List[Dict[str, Any]] = []
        self._learned_fixes: Dict[str, ProposedFix] = {}

        # Fix pipeline
        self._proposed_fixes: deque = deque(maxlen=50)
        self._applied_fixes: List[ProposedFix] = []
        self._fix_counter = 0

        # Callbacks
        self._on_anomaly_callbacks: List[Callable] = []
        self._on_fix_proposed_callbacks: List[Callable] = []

        # ─── Cardinal Sprint 1: Failure Pattern Tracking ───
        # Accumulated gap signals from capability_gap_scan (admin_tasks.py)
        # Keyed by domain → {type, count, first_seen, last_seen, details}
        self._failure_patterns: Dict[str, Dict[str, Any]] = {}
        # History of all gap scan results for trend analysis
        self._gap_scan_history: deque = deque(maxlen=100)
        # Meta-gap filter: track gap detection rate to prevent recursive self-mod
        self._gap_timestamps: deque = deque(maxlen=50)  # timestamps of detected gaps
        self._gap_cooldown_until: float = 0.0  # if > time.time(), suppress new gaps

        # ─── Death Frequency Tracking (2026-02-23) ───
        # Track per-fairy death counts for pattern learning.
        # Cardinal's MOST COMMON observation is fairy_dead_extended errors,
        # but the old pipeline required a correlated "change" to learn from them.
        # This tracks death frequency directly so Cardinal learns which fairies
        # are chronically dying and proposes fixes.
        self._death_counts: Dict[str, int] = {}           # fairy_name → death count this session
        self._death_timestamps: Dict[str, List[float]] = {}  # fairy_name → recent death timestamps
        self._death_wave_count: int = 0                    # total mass death waves detected
        self._death_patterns_learned: int = 0              # patterns learned from death frequency
        self._chronic_death_threshold: int = 3             # deaths before it's a pattern
        self._death_wave_threshold: int = 5                # simultaneous deaths = mass wave

        # Persistence path
        self._cardinal_state_path = Path(__file__).parent.parent.parent.parent.parent / "state" / "cardinal_learned.json"

        # Load any previously learned state
        self._load_learned_state()

    # ═══════════════════════════════════════════════════════════════════════════
    # MODE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════

    @property
    def cardinal_mode(self) -> CardinalMode:
        """Current Cardinal operating mode."""
        return self._cardinal_mode

    @property
    def has_direct_links(self) -> bool:
        """Are training wheels active?"""
        return self._direct_links is not None and len(self._direct_links) > 0

    def _enable_training_wheels(self) -> bool:
        """Enable direct links to mini-stubs."""
        if not self._training_wheels_available:
            return False
        if self._direct_links is not None:
            return True

        try:
            self._direct_links = {
                "memory": self._mini_memory_factory(),
                "cognition": self._mini_cognition_factory(),
                "body": self._mini_body_factory(),
            }
            print(f"[{self.ACTOR_NAME}] Cardinal: Training wheels ENABLED")
            return True
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Cardinal: Training wheels failed: {e}")
            self._direct_links = None
            return False

    def _disable_training_wheels(self) -> None:
        """Disable direct links - switch to postal only."""
        if self._direct_links is None:
            return

        # Stop any running mini-stubs
        for name, stub in self._direct_links.items():
            if hasattr(stub, "stop"):
                try:
                    stub.stop()
                except Exception:
                    pass

        self._direct_links = None
        print(f"[{self.ACTOR_NAME}] Cardinal: Training wheels DISABLED - postal only")

    def enter_emergency_mode(self) -> bool:
        """
        Enter emergency mode - re-enable direct links for system repair.

        Call when postal is down but we need to diagnose/fix things.
        """
        if self._cardinal_mode == CardinalMode.EMERGENCY:
            return True

        print(f"[{self.ACTOR_NAME}] Cardinal: EMERGENCY MODE ACTIVATED")
        self._cardinal_mode = CardinalMode.EMERGENCY

        # Restore training wheels
        self._enable_training_wheels()

        # Publish emergency event if postal still works
        if hasattr(self, "post") and self.post:
            try:
                self.post.publish("cardinal.emergency", {
                    "mode": "emergency",
                    "reason": "manual_trigger",
                    "timestamp": time.time(),
                })
            except Exception:
                pass

        return True

    def exit_emergency_mode(self) -> bool:
        """Exit emergency mode, return to running."""
        if self._cardinal_mode != CardinalMode.EMERGENCY:
            return False

        print(f"[{self.ACTOR_NAME}] Cardinal: Exiting emergency mode")
        self._disable_training_wheels()
        self._cardinal_mode = CardinalMode.RUNNING
        return True

    # ═══════════════════════════════════════════════════════════════════════════
    # PRE-BOOT CAPABILITIES
    # ═══════════════════════════════════════════════════════════════════════════

    def preboot_think(self, thought: str) -> Optional[str]:
        """Route a thought via MiniCognition (pre-boot/emergency only)."""
        if not self.has_direct_links:
            return None
        cognition = self._direct_links.get("cognition")
        if cognition and hasattr(cognition, "submit_thought"):
            return cognition.submit_thought(
                topic="cardinal.thought",
                content={"thought": thought, "source": getattr(self, "ACTOR_NAME", "Cardinal")},
                source=getattr(self, "ACTOR_NAME", "Cardinal"),
            )
        return None

    def preboot_recall(self, card_type: str = "bootstrap") -> list:
        """Recall bootstrap cards via MiniMemory (pre-boot/emergency only)."""
        if not self.has_direct_links:
            return []
        memory = self._direct_links.get("memory")
        if memory:
            if hasattr(memory, "is_loaded") and not memory.is_loaded():
                memory.read_bootstrap_cards()
            if hasattr(memory, "get_cards_by_type"):
                return memory.get_cards_by_type(card_type)
        return []

    def preboot_vitals(self) -> Dict[str, Any]:
        """Get vital signs from mini-stubs (pre-boot/emergency only)."""
        if not self.has_direct_links:
            return {"error": "No direct links", "mode": self._cardinal_mode.value}

        vitals = {
            "mode": self._cardinal_mode.value,
            "has_direct_links": True,
            "timestamp": time.time(),
        }
        body = self._direct_links.get("body")
        if body and hasattr(body, "get_vital_signs"):
            vitals["body"] = body.get_vital_signs()
        cognition = self._direct_links.get("cognition")
        if cognition and hasattr(cognition, "get_stats"):
            vitals["cognition"] = cognition.get_stats()
        memory = self._direct_links.get("memory")
        if memory:
            vitals["memory"] = {
                "loaded": memory.is_loaded() if hasattr(memory, "is_loaded") else False,
                "card_count": memory.card_count() if hasattr(memory, "card_count") else 0,
            }
        return vitals

    # ═══════════════════════════════════════════════════════════════════════════
    # BOOT / SHUTDOWN
    # ═══════════════════════════════════════════════════════════════════════════

    def _cardinal_boot(self) -> None:
        """
        Transition Cardinal from PRE_BOOT to RUNNING.

        Call from on_boot AFTER postal is available.
        """
        if self._cardinal_booted:
            return

        # Enable training wheels for pre-boot phase
        if self._training_wheels_available:
            self._enable_training_wheels()
            # Load bootstrap cards
            cards = self.preboot_recall("identity")
            if cards:
                print(f"[{self.ACTOR_NAME}] Cardinal: Loaded {len(cards)} identity cards")

        # Wire observation subscriptions
        if hasattr(self, "post") and self.post:
            for topic in self.CARDINAL_SUBSCRIPTIONS:
                try:
                    self.post.subscribe(topic, self._cardinal_on_message)
                except Exception as e:
                    print(f"[{self.ACTOR_NAME}] Cardinal: Subscribe failed for {topic}: {e}")

        # Transition to RUNNING
        self._disable_training_wheels()
        self._cardinal_mode = CardinalMode.RUNNING
        self._cardinal_booted = True

        print(f"[{self.ACTOR_NAME}] Cardinal: Booted - RUNNING mode")

    def _cardinal_shutdown(self) -> None:
        """Graceful Cardinal shutdown. Call from shutdown handler."""
        self._cardinal_mode = CardinalMode.SHUTDOWN
        self._save_learned_state()
        print(f"[{self.ACTOR_NAME}] Cardinal: Shutdown - saved {len(self._learned_fixes)} learned fixes")

    # ═══════════════════════════════════════════════════════════════════════════
    # OBSERVATION PIPELINE
    # ═══════════════════════════════════════════════════════════════════════════

    def observe(self, obs_type: str, source: str, content: Any, severity: int = 0) -> str:
        """
        Record an observation. This is how the system feeds data to Cardinal.

        Args:
            obs_type: 'error', 'change', 'anomaly', 'health', 'note'
            source: Which fairy/system reported it
            content: The observation data
            severity: 0=info, 1=warning, 2=error, 3=critical

        Returns:
            Observation ID
        """
        obs_id = f"obs_{len(self._observations):06d}"
        obs = Observation(
            obs_id=obs_id,
            obs_type=obs_type,
            source=source,
            content=content,
            severity=severity,
        )

        self._observations.append(obs)

        if obs_type == "error":
            self._recent_errors.append(obs)
        elif obs_type == "change":
            self._recent_changes.append(obs)

        # Check for anomalies
        if self._is_anomaly(obs):
            self._handle_anomaly(obs)

        return obs_id

    def snapshot_fairy(self, fairy_name: str, state: Dict[str, Any]) -> FairySnapshot:
        """Take a snapshot of a fairy's state for change tracking."""
        snapshot = FairySnapshot(
            fairy_name=fairy_name,
            timestamp=time.time(),
            state=state.copy(),
        )

        if fairy_name not in self._fairy_snapshots:
            self._fairy_snapshots[fairy_name] = []
        self._fairy_snapshots[fairy_name].append(snapshot)

        # Keep only recent
        if len(self._fairy_snapshots[fairy_name]) > 50:
            self._fairy_snapshots[fairy_name] = self._fairy_snapshots[fairy_name][-50:]

        # Compare with previous
        history = self._fairy_snapshots[fairy_name]
        if len(history) >= 2:
            diff = history[-2].diff(snapshot)
            if diff and "error" not in diff:
                self.observe("change", fairy_name, {
                    "changes": diff,
                    "snapshot_count": len(history),
                })

        return snapshot

    def _cardinal_on_message(self, envelope) -> None:
        """Handle incoming postal messages, convert to observations."""
        # Extract topic and data from envelope
        if isinstance(envelope, dict):
            topic = envelope.get("topic", "")
            data = envelope.get("payload", envelope.get("data", envelope))
        elif hasattr(envelope, "topic"):
            topic = envelope.topic
            data = getattr(envelope, "payload", envelope)
        else:
            topic = str(envelope)
            data = envelope

        if "cardinal.gaps_detected" in str(topic):
            # Sprint 1: Gap scan results — feed to failure pattern tracker
            if isinstance(data, dict):
                self._track_failure_pattern(data)
            return
        elif "error" in str(topic).lower():
            # FIX 2026-02-06: Extract fairy name from payload for clearer attribution
            source = str(topic)
            if isinstance(data, dict):
                source = data.get("fairy", data.get("actor", data.get("name", str(topic))))
            self.observe("error", source, data, severity=2)
        elif "health" in str(topic).lower():
            self.observe("health", str(topic), data, severity=0)
        elif "heartbeat" in str(topic).lower():
            self.observe("health", str(topic), data, severity=0)
        elif "blueprint" in str(topic).lower() or "diary" in str(topic).lower():
            self.observe("change", str(topic), data, severity=0)
        else:
            self.observe("note", str(topic), data, severity=0)

    # ═══════════════════════════════════════════════════════════════════════════
    # ANOMALY DETECTION & CORRELATION
    # ═══════════════════════════════════════════════════════════════════════════

    def _is_anomaly(self, obs: Observation) -> bool:
        """Check if an observation is anomalous."""
        # Errors severity 2+ are always anomalies
        if obs.obs_type == "error" and obs.severity >= 2:
            return True

        # Check against learned thresholds
        metric_key = f"{obs.source}.{obs.obs_type}"
        if metric_key in self._anomaly_thresholds:
            if isinstance(obs.content, (int, float)):
                if obs.content > self._anomaly_thresholds[metric_key]:
                    return True

        return False

    def _handle_anomaly(self, obs: Observation) -> None:
        """Handle a detected anomaly — guild-enhanced root cause analysis.

        2026-02-23: Added inbox persistence + rate-limited console output.
        All anomalies go to state/cardinal_inbox.jsonl (Ace's readable inbox).
        Console prints rate-limited to 1 per source per 60s to reduce noise.
        """
        actor = getattr(self, "ACTOR_NAME", "Cardinal")

        # ─── Rate-limit console output per source (2026-02-23) ───
        now = time.time()
        if not hasattr(self, '_anomaly_last_print'):
            self._anomaly_last_print: Dict[str, float] = {}
        last_print = self._anomaly_last_print.get(obs.source, 0)
        if now - last_print > 60.0:  # Max 1 print per source per 60s
            print(f"[{actor}] Cardinal ANOMALY: {obs.obs_type} from {obs.source} (sev={obs.severity})")
            self._anomaly_last_print[obs.source] = now

        # ─── Write to persistent inbox (2026-02-23) ───
        # This is the log Ace can read to see what Cardinal noticed.
        self._write_to_inbox({
            "type": "anomaly",
            "obs_type": obs.obs_type,
            "source": obs.source,
            "severity": obs.severity,
            "content": str(obs.content)[:200],
            "timestamp": datetime.now().isoformat(),
            "unix_time": now,
        })

        for callback in self._on_anomaly_callbacks:
            try:
                callback(obs)
            except Exception:
                pass

        # Try to correlate with recent changes
        correlation = self._find_correlation(obs)

        # ═══════════════════════════════════════════════════════════════════
        # GUILD-FIRST: Ask inference guild for deeper root cause analysis
        # ═══════════════════════════════════════════════════════════════════
        if hasattr(self, 'guild_request') and obs.severity >= 2:
            try:
                _recent_obs = [
                    f"{o.obs_type}:{o.source}" for o in list(self._observations)[-5:]
                ]
                _guild_resp = self.guild_request(
                    prompt=f"Anomaly detected: {obs.obs_type} from {obs.source} (severity={obs.severity}). "
                           f"Content: {str(obs.content)[:100]}. "
                           f"Recent observations: {_recent_obs}. "
                           f"{'Correlation found: ' + str(correlation) if correlation else 'No correlation found.'}. "
                           f"What is the likely root cause? Reply briefly.",
                    context={"anomaly": obs.obs_type, "source": obs.source, "severity": obs.severity},
                    mode="team_only",
                    timeout=2.0,
                )
                if _guild_resp and _guild_resp.get("team_result"):
                    _tr = _guild_resp["team_result"]
                    _analysis = _tr.get("synthesis") or _tr.get("logic") or ""
                    if _analysis:
                        print(f"[{actor}] Cardinal GUILD analysis: {_analysis[:120]}")
                        # Enrich the correlation with guild insight
                        if correlation:
                            correlation["guild_analysis"] = _analysis[:200]
                        else:
                            correlation = {
                                "error": obs.obs_id,
                                "error_type": obs.obs_type,
                                "guild_analysis": _analysis[:200],
                                "confidence": 0.5,
                            }
            except Exception:
                pass

        if correlation:
            self._correlations.append(correlation)
            # Maybe propose a fix
            self._maybe_propose_fix(obs, correlation)

    def _find_correlation(self, error: Observation) -> Optional[Dict[str, Any]]:
        """Try to correlate an error with a recent change."""
        five_min_ago = time.time() - 300

        for change in self._recent_changes:
            if change.timestamp > five_min_ago:
                # Check if same source or related plane
                if change.source == error.source or self._are_related(change.source, error.source):
                    return {
                        "error": error.obs_id,
                        "error_type": error.obs_type,
                        "change": change.obs_id,
                        "change_source": change.source,
                        "time_between_sec": error.timestamp - change.timestamp,
                        "confidence": 0.6,
                    }

        return None

    def _are_related(self, source1: str, source2: str) -> bool:
        """Check if two sources are in the same plane."""
        # Simple plane-matching heuristic
        for prefix in ("P00", "P10", "P20", "P30", "P40", "P50", "P60"):
            if prefix in str(source1) and prefix in str(source2):
                return True
        return False

    def learn_baseline(self, metric_name: str, values: List[float]) -> None:
        """Learn what's 'normal' for a metric."""
        if not values:
            return
        avg = sum(values) / len(values)
        std_dev = (sum((x - avg) ** 2 for x in values) / len(values)) ** 0.5

        self._baseline_metrics[metric_name] = {
            "avg": avg,
            "std_dev": std_dev,
            "min": min(values),
            "max": max(values),
            "count": len(values),
        }
        self._anomaly_thresholds[metric_name] = avg + (2 * std_dev)

    # ═══════════════════════════════════════════════════════════════════════════
    # FAILURE PATTERN TRACKING (Cardinal Sprint 1)
    # ═══════════════════════════════════════════════════════════════════════════

    def _track_failure_pattern(self, gap_data: Dict[str, Any]) -> None:
        """
        Accumulate gap scan results into persistent failure patterns.

        Called when 'cardinal.gaps_detected' is received from AdminTaskQueue.
        Builds a pattern map keyed by domain, tracking frequency, severity
        trends, and gap types. This feeds Phase 2 (SkillFactory).

        Safety: GW-1 meta-gap filter — if > 3 gaps in < 10 minutes,
        enter cooldown and publish boss_ask notification.
        """
        now = time.time()
        actor = getattr(self, "ACTOR_NAME", "Cardinal")

        # ─── GW-1: Meta-gap filter (recursive self-mod protection) ───
        if now < self._gap_cooldown_until:
            return  # In cooldown — suppress gap processing

        gaps = gap_data.get("gaps", [])
        scan_stats = gap_data.get("scan_stats", {})

        if not gaps:
            return

        # Track gap detection rate
        self._gap_timestamps.append(now)

        # Check for meta-gap: > 3 gap detections in < 10 minutes
        recent_gap_count = sum(
            1 for ts in self._gap_timestamps
            if (now - ts) < 600  # 10 minutes
        )
        if recent_gap_count > 3:
            self._gap_cooldown_until = now + 900  # 15-minute cooldown
            print(f"[{actor}] Cardinal GW-1: Meta-gap filter triggered "
                  f"({recent_gap_count} gaps in 10min) → 15min cooldown")
            # Notify for human review
            self._write_to_inbox({
                "type": "meta_gap_alert",
                "gap_count": recent_gap_count,
                "cooldown_until": self._gap_cooldown_until,
                "message": "Too many gaps detected — possible recursive self-mod. "
                           "Cardinal entering 15-minute cooldown.",
                "timestamp": datetime.now().isoformat(),
            })
            if hasattr(self, "post") and self.post:
                try:
                    self.post.publish("cardinal.meta_gap_alert", {
                        "gap_count": recent_gap_count,
                        "cooldown_until": self._gap_cooldown_until,
                        "message": "Too many gaps detected — possible recursive self-mod. "
                                   "Cardinal entering 15-minute cooldown.",
                        "timestamp": now,
                    })
                except Exception:
                    pass
            return

        # ─── Accumulate patterns ───
        self._gap_scan_history.append({
            "gaps": gaps,
            "scan_stats": scan_stats,
            "timestamp": now,
        })

        for gap in gaps:
            domain = gap.get("domain", "unknown")
            gap_type = gap.get("type", "unknown")
            severity = gap.get("severity", 0.5)

            if domain not in self._failure_patterns:
                self._failure_patterns[domain] = {
                    "domain": domain,
                    "gap_types": defaultdict(int),
                    "total_detections": 0,
                    "total_severity": 0.0,
                    "first_seen": now,
                    "last_seen": now,
                    "top_goal": None,
                    "slow_count": 0,
                    "details": [],
                }

            pattern = self._failure_patterns[domain]
            pattern["gap_types"][gap_type] += 1
            pattern["total_detections"] += 1
            pattern["total_severity"] += severity
            pattern["last_seen"] = now

            # Track specific details
            if gap_type == "repeated_failure":
                pattern["top_goal"] = gap.get("top_goal", pattern["top_goal"])
            elif gap_type == "capability_inefficiency":
                pattern["slow_count"] += gap.get("slow_count", 0)

            # Keep last 10 raw gap records per domain
            pattern["details"].append(gap)
            if len(pattern["details"]) > 10:
                pattern["details"] = pattern["details"][-10:]

        # Log significant pattern accumulation
        for domain, pat in self._failure_patterns.items():
            if pat["total_detections"] >= 5 and pat["total_detections"] % 5 == 0:
                avg_sev = pat["total_severity"] / max(1, pat["total_detections"])
                print(f"[{actor}] Cardinal pattern: {domain} → "
                      f"{pat['total_detections']} detections, "
                      f"avg severity {avg_sev:.2f}, "
                      f"types: {dict(pat['gap_types'])}")

        # Publish pattern update for dashboard / future SkillFactory
        if hasattr(self, "post") and self.post:
            try:
                top_patterns = self._get_top_failure_patterns(5)
                if top_patterns:
                    self.post.publish("cardinal.patterns_updated", {
                        "top_patterns": top_patterns,
                        "total_domains_tracked": len(self._failure_patterns),
                        "timestamp": now,
                    })
            except Exception:
                pass

    def _get_top_failure_patterns(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get the N most severe failure patterns, sorted by weighted score."""
        scored = []
        for domain, pat in self._failure_patterns.items():
            avg_severity = pat["total_severity"] / max(1, pat["total_detections"])
            # Score = detection count * average severity * recency factor
            age_hours = (time.time() - pat["last_seen"]) / 3600
            recency = max(0.1, 1.0 - (age_hours / 24.0))  # Decays over 24h
            score = pat["total_detections"] * avg_severity * recency
            scored.append({
                "domain": domain,
                "score": round(score, 3),
                "detections": pat["total_detections"],
                "avg_severity": round(avg_severity, 3),
                "gap_types": dict(pat["gap_types"]),
                "top_goal": pat.get("top_goal"),
                "slow_count": pat.get("slow_count", 0),
                "first_seen": pat["first_seen"],
                "last_seen": pat["last_seen"],
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:n]

    def get_failure_patterns(self) -> Dict[str, Any]:
        """Get all failure patterns for diagnostics / dashboard."""
        return {
            "patterns": self._get_top_failure_patterns(20),
            "total_domains": len(self._failure_patterns),
            "gap_scan_history_size": len(self._gap_scan_history),
            "cooldown_active": time.time() < self._gap_cooldown_until,
            "cooldown_remaining": max(0, self._gap_cooldown_until - time.time()),
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # FIX PIPELINE
    # ═══════════════════════════════════════════════════════════════════════════

    def _maybe_propose_fix(self, error: Observation, correlation: Dict[str, Any]) -> None:
        """Maybe propose a fix based on error and correlation."""
        pattern_key = f"{error.obs_type}:{correlation.get('change_source', 'unknown')}"

        if pattern_key in self._learned_fixes:
            learned = self._learned_fixes[pattern_key]
            self._propose_fix(
                description=f"Reapply learned fix: {learned.description}",
                target=learned.target,
                action=learned.action,
                params=learned.params,
                confidence=min(0.9, learned.confidence + 0.1),
            )
        else:
            # ═══════════════════════════════════════════════════════════════
            # GUILD-FIRST: Ask guild for intelligent fix suggestion
            # ═══════════════════════════════════════════════════════════════
            _guild_action = None
            _guild_desc = None
            if hasattr(self, 'guild_request'):
                try:
                    _guild_analysis = correlation.get("guild_analysis", "")
                    _guild_resp = self.guild_request(
                        prompt=f"Error: {error.obs_type} from {error.source}. "
                               f"{'Analysis: ' + _guild_analysis[:100] if _guild_analysis else ''} "
                               f"What action to take? Options: investigate, restart, rollback, reconfig. "
                               f"Reply: action_name|confidence|description",
                        context={"error": error.obs_type, "source": error.source},
                        mode="team_only",
                        timeout=1.5,
                    )
                    if _guild_resp and _guild_resp.get("team_result"):
                        _tr = _guild_resp["team_result"]
                        _text = (_tr.get("synthesis") or _tr.get("logic") or "").strip()
                        if "|" in _text:
                            _parts = _text.split("|")
                            _guild_action = _parts[0].strip().lower()
                            if _guild_action not in ("investigate", "restart", "rollback", "reconfig"):
                                _guild_action = "investigate"
                            try:
                                _guild_conf = float(_parts[1].strip())
                            except (ValueError, IndexError):
                                _guild_conf = 0.4
                            _guild_desc = _parts[2].strip() if len(_parts) > 2 else f"Guild-suggested {_guild_action}"
                except Exception:
                    pass

            if _guild_action and _guild_desc:
                self._propose_fix(
                    description=_guild_desc[:120],
                    target=error.source,
                    action=_guild_action,
                    params={"error_id": error.obs_id, "correlation": correlation},
                    confidence=min(0.7, _guild_conf),
                )
            else:
                self._propose_fix(
                    description=f"Investigate: {error.obs_type} after {correlation.get('change_source')} change",
                    target=error.source,
                    action="investigate",
                    params={"error_id": error.obs_id, "correlation": correlation},
                    confidence=0.3,
                )

    def _propose_fix(
        self,
        description: str,
        target: str,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        confidence: float = 0.5,
    ) -> ProposedFix:
        """Propose a fix for approval."""
        self._fix_counter += 1
        fix = ProposedFix(
            fix_id=f"fix_{self._fix_counter:04d}",
            description=description,
            target=target,
            action=action,
            params=params or {},
            confidence=confidence,
        )

        self._proposed_fixes.append(fix)

        for callback in self._on_fix_proposed_callbacks:
            try:
                callback(fix)
            except Exception:
                pass

        actor = getattr(self, "ACTOR_NAME", "Cardinal")
        print(f"[{actor}] Cardinal fix proposed: {fix.fix_id} - {description} (conf={confidence:.2f})")

        # Write to persistent inbox (2026-02-23)
        self._write_to_inbox({
            "type": "fix_proposed",
            "fix_id": fix.fix_id,
            "description": description,
            "target": target,
            "action": action,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
        })

        # Publish to postal
        if hasattr(self, "post") and self.post:
            try:
                self.post.publish("cardinal.fix_proposed", {
                    "fix_id": fix.fix_id,
                    "description": description,
                    "target": target,
                    "action": action,
                    "confidence": confidence,
                })
            except Exception:
                pass

        return fix

    def approve_fix(self, fix_id: str) -> bool:
        """Approve a proposed fix."""
        for fix in self._proposed_fixes:
            if fix.fix_id == fix_id:
                fix.approved = True
                return True
        return False

    def apply_approved_fixes(self) -> List[ProposedFix]:
        """Apply all approved fixes. Returns list of applied fixes."""
        applied = []
        for fix in list(self._proposed_fixes):
            if fix.approved and not fix.applied:
                result = self._apply_fix(fix)
                fix.applied = True
                fix.result = result
                applied.append(fix)
                self._applied_fixes.append(fix)

                # Learn from success
                if result and "error" not in str(result).lower():
                    pattern_key = f"{fix.action}:{fix.target}"
                    self._learned_fixes[pattern_key] = fix
        return applied

    def _apply_fix(self, fix: ProposedFix) -> str:
        """Actually apply a fix."""
        actor = getattr(self, "ACTOR_NAME", "Cardinal")
        print(f"[{actor}] Cardinal applying fix: {fix.fix_id} ({fix.action} on {fix.target})")

        if fix.action == "investigate":
            return f"Investigation logged for {fix.target}"
        elif fix.action == "restart":
            return self._cardinal_restart_fairy(fix.target)
        elif fix.action == "rollback":
            return f"Rollback requested for {fix.target}"
        elif fix.action == "reconfig":
            return f"Reconfig requested for {fix.target}"
        else:
            return f"Unknown action: {fix.action}"

    def _cardinal_restart_fairy(self, fairy_name: str) -> str:
        """Restart a fairy via postal."""
        if hasattr(self, "post") and self.post:
            try:
                self.post.publish("fairy.restart", {
                    "fairy_name": fairy_name,
                    "reason": "cardinal_fix",
                    "timestamp": time.time(),
                })
                return f"Restart signal sent for {fairy_name}"
            except Exception as e:
                return f"Restart failed: {e}"
        return f"No postal - cannot restart {fairy_name}"

    def _auto_apply_high_confidence_fixes(self) -> None:
        """Auto-approve and apply fixes with confidence > 0.8."""
        for fix in self._proposed_fixes:
            if not fix.approved and not fix.applied and fix.confidence > 0.8:
                actor = getattr(self, "ACTOR_NAME", "Cardinal")
                print(f"[{actor}] Cardinal auto-approving: {fix.fix_id} (conf={fix.confidence:.2f})")
                fix.approved = True

        self.apply_approved_fixes()

    # ═══════════════════════════════════════════════════════════════════════════
    # TICK INTEGRATION
    # ═══════════════════════════════════════════════════════════════════════════

    def _cardinal_tick(self, beat: int) -> None:
        """
        Cardinal tick operations. Call from on_tick.

        Runs observation processing, auto-fixes, snapshots, and learning.
        """
        if self._cardinal_mode == CardinalMode.SHUTDOWN:
            return

        # Every 10 ticks: auto-apply high confidence fixes
        if beat % 10 == 0:
            self._auto_apply_high_confidence_fixes()

        # Every 60 ticks: snapshot all known fairies from directory
        if beat % 60 == 0:
            self._snapshot_known_fairies()

        # Every 60 ticks (offset by 30): learn baselines from system metrics
        if beat % 60 == 30:
            self._learn_from_snapshots()

        # Every 120 ticks: prune old data, save learned state
        if beat % 120 == 0:
            self._save_learned_state()

        # Every 30 ticks: check for dead fairies (severity escalation)
        if beat % 30 == 0:
            self._check_fairy_health()

        # Every 90 ticks: log failure pattern summary (Sprint 1)
        if beat % 90 == 0 and self._failure_patterns:
            top = self._get_top_failure_patterns(3)
            if top:
                actor = getattr(self, "ACTOR_NAME", "Cardinal")
                domains = ", ".join(f"{p['domain']}({p['detections']})" for p in top)
                print(f"[{actor}] Cardinal patterns: {domains}")

    def _snapshot_known_fairies(self) -> None:
        """Take snapshots of all known fairies from directory."""
        try:
            from directory import get_directory
            directory = get_directory()
            if directory and hasattr(directory, "get_registry"):
                registry = directory.get_registry()
                for name, info in registry.items():
                    state = {
                        "status": info.get("status", "unknown"),
                        "last_heartbeat": info.get("last_heartbeat", 0),
                        "plane": info.get("plane", ""),
                    }
                    self.snapshot_fairy(name, state)
        except Exception:
            pass

    def _check_fairy_health(self) -> None:
        """Check for fairies that might need intervention.

        2026-02-23: Now feeds death frequency tracker for direct pattern learning.
        """
        try:
            from directory import get_directory
            directory = get_directory()
            if not directory or not hasattr(directory, "get_registry"):
                return

            registry = directory.get_registry()
            now = time.time()
            dead_this_check = []

            for name, info in registry.items():
                status = info.get("status", "unknown")
                last_hb = info.get("last_heartbeat", 0)

                # Fairy dead for more than 5 minutes? That's a critical anomaly
                if status == "dead" and last_hb > 0 and (now - last_hb) > 300:
                    self.observe("error", name, {
                        "issue": "fairy_dead_extended",
                        "dead_for_sec": now - last_hb,
                    }, severity=2)
                    dead_this_check.append(name)

                # Fairy stale for more than 2 minutes? Warning
                elif status == "stale" and last_hb > 0 and (now - last_hb) > 120:
                    self.observe("health", name, {
                        "issue": "fairy_stale_extended",
                        "stale_for_sec": now - last_hb,
                    }, severity=1)

            # ─── Feed death frequency tracker (2026-02-23) ───
            if dead_this_check:
                self._track_death_frequency(dead_this_check, now)

        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # DEATH FREQUENCY LEARNING (2026-02-23)
    # ═══════════════════════════════════════════════════════════════════════════

    def _track_death_frequency(self, dead_fairies: List[str], now: float) -> None:
        """Track fairy death frequency and learn patterns directly.

        The old pipeline required error→change correlation to learn anything.
        But fairy_dead_extended errors never had associated "change" observations,
        so Cardinal never learned. This tracks death frequency directly:

        1. Per-fairy death counting → chronic death pattern (3+ deaths)
        2. Mass death wave detection → process-freeze pattern (5+ simultaneous)
        3. Automatic baseline learning from death cadence

        This is Cardinal's primary learning input — the most abundant signal.
        """
        actor = getattr(self, "ACTOR_NAME", "Cardinal")

        # ─── 1. Track per-fairy death counts ───
        for fairy_name in dead_fairies:
            self._death_counts[fairy_name] = self._death_counts.get(fairy_name, 0) + 1
            if fairy_name not in self._death_timestamps:
                self._death_timestamps[fairy_name] = []
            self._death_timestamps[fairy_name].append(now)
            # Keep last 20 timestamps per fairy
            if len(self._death_timestamps[fairy_name]) > 20:
                self._death_timestamps[fairy_name] = self._death_timestamps[fairy_name][-20:]

        # ─── 2. Detect mass death waves (process freeze signature) ───
        if len(dead_fairies) >= self._death_wave_threshold:
            self._death_wave_count += 1
            # Record as a "change" observation — this enables correlation!
            # The key insight: a mass death wave IS a change event (process freeze).
            self.observe("change", "process_freeze", {
                "wave_size": len(dead_fairies),
                "fairies": dead_fairies[:10],  # Cap for readability
                "wave_number": self._death_wave_count,
            }, severity=1)

            # Learn baseline for wave size
            wave_sizes = [len(dead_fairies)]
            existing = self._baseline_metrics.get("death_wave.size")
            if existing:
                # Blend with existing
                wave_sizes = [existing["avg"]] * existing.get("count", 1) + wave_sizes
            self.learn_baseline("death_wave.size", wave_sizes[-20:])

        # ─── 3. Learn chronic death patterns (per-fairy) ───
        for fairy_name in dead_fairies:
            count = self._death_counts[fairy_name]
            if count == self._chronic_death_threshold:
                # First time this fairy hits threshold — learn pattern
                self._death_patterns_learned += 1

                # Calculate death cadence from timestamps
                timestamps = self._death_timestamps.get(fairy_name, [])
                if len(timestamps) >= 2:
                    intervals = [
                        timestamps[i+1] - timestamps[i]
                        for i in range(len(timestamps) - 1)
                    ]
                    avg_interval = sum(intervals) / len(intervals)
                else:
                    avg_interval = 0.0

                # Record as failure pattern (same structure as gap scan patterns)
                pattern_key = f"chronic_death:{fairy_name}"
                if pattern_key not in self._failure_patterns:
                    self._failure_patterns[pattern_key] = {
                        "domain": "fairy_health",
                        "gap_types": defaultdict(int),
                        "total_detections": count,
                        "total_severity": count * 0.5,
                        "first_seen": timestamps[0] if timestamps else now,
                        "last_seen": now,
                        "top_goal": None,
                        "slow_count": 0,
                        "details": [],
                    }
                self._failure_patterns[pattern_key]["gap_types"]["chronic_death"] += 1
                self._failure_patterns[pattern_key]["total_detections"] = count
                self._failure_patterns[pattern_key]["last_seen"] = now
                self._failure_patterns[pattern_key]["details"].append({
                    "type": "chronic_death",
                    "fairy": fairy_name,
                    "death_count": count,
                    "avg_interval_sec": round(avg_interval, 1),
                    "timestamp": now,
                })
                # Keep last 10 details
                details = self._failure_patterns[pattern_key]["details"]
                if len(details) > 10:
                    self._failure_patterns[pattern_key]["details"] = details[-10:]

                # Learn death cadence baseline per fairy
                if len(timestamps) >= 3:
                    intervals = [
                        timestamps[i+1] - timestamps[i]
                        for i in range(len(timestamps) - 1)
                    ]
                    self.learn_baseline(f"death_interval.{fairy_name}", intervals)

                print(f"[{actor}] Cardinal LEARNED: {fairy_name} chronic death pattern "
                      f"({count} deaths, avg interval {avg_interval:.0f}s)")

                # Write to inbox
                self._write_to_inbox({
                    "type": "pattern_learned",
                    "pattern": "chronic_death",
                    "fairy": fairy_name,
                    "death_count": count,
                    "avg_interval_sec": round(avg_interval, 1),
                    "timestamp": datetime.now().isoformat(),
                })

            elif count > self._chronic_death_threshold and count % 5 == 0:
                # Every 5 additional deaths, update the pattern
                pattern_key = f"chronic_death:{fairy_name}"
                if pattern_key in self._failure_patterns:
                    self._failure_patterns[pattern_key]["total_detections"] = count
                    self._failure_patterns[pattern_key]["total_severity"] = count * 0.5
                    self._failure_patterns[pattern_key]["last_seen"] = now

    def _learn_from_snapshots(self) -> None:
        """Learn baselines from fairy snapshot data.

        Called periodically to build what 'normal' looks like.
        Feeds learn_baseline() with actual metric values so Cardinal
        can detect anomalies using learned thresholds (not just hardcoded).

        2026-02-23: New — previously learn_baseline() was never called.
        """
        try:
            from directory import get_directory
            directory = get_directory()
            if not directory or not hasattr(directory, "get_registry"):
                return

            registry = directory.get_registry()
            now = time.time()

            # Collect metrics across all fairies
            alive_count = 0
            dead_count = 0
            stale_count = 0
            heartbeat_ages = []

            for name, info in registry.items():
                status = info.get("status", "unknown")
                last_hb = info.get("last_heartbeat", 0)

                if status == "alive":
                    alive_count += 1
                elif status == "dead":
                    dead_count += 1
                elif status == "stale":
                    stale_count += 1

                if last_hb > 0:
                    age = now - last_hb
                    if age < 600:  # Only recent heartbeats (< 10 min)
                        heartbeat_ages.append(age)

            total = alive_count + dead_count + stale_count
            if total > 0:
                # Learn what normal alive/dead ratios look like
                self.learn_baseline("system.alive_ratio",
                                    [alive_count / total])
                self.learn_baseline("system.dead_count",
                                    [float(dead_count)])

            if heartbeat_ages:
                self.learn_baseline("system.heartbeat_age", heartbeat_ages)

        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ═══════════════════════════════════════════════════════════════════════════

    def _save_learned_state(self) -> None:
        """Save learned fixes, baselines, and failure patterns to disk."""
        try:
            # Serialize failure patterns (defaultdict → regular dict for JSON)
            serialized_patterns = {}
            for domain, pat in self._failure_patterns.items():
                serialized_patterns[domain] = {
                    "domain": pat["domain"],
                    "gap_types": dict(pat.get("gap_types", {})),
                    "total_detections": pat["total_detections"],
                    "total_severity": pat["total_severity"],
                    "first_seen": pat["first_seen"],
                    "last_seen": pat["last_seen"],
                    "top_goal": pat.get("top_goal"),
                    "slow_count": pat.get("slow_count", 0),
                    # Don't persist raw details — they're ephemeral
                }

            state = {
                "learned_fixes": {
                    k: {
                        "description": v.description,
                        "target": v.target,
                        "action": v.action,
                        "params": v.params,
                        "confidence": v.confidence,
                    }
                    for k, v in self._learned_fixes.items()
                },
                "baseline_metrics": self._baseline_metrics,
                "anomaly_thresholds": self._anomaly_thresholds,
                "failure_patterns": serialized_patterns,
                "correlation_count": len(self._correlations),
                "applied_fix_count": len(self._applied_fixes),
                # ─── Death frequency stats (2026-02-23) ───
                "death_tracking": {
                    "death_counts": dict(self._death_counts),
                    "death_wave_count": self._death_wave_count,
                    "patterns_learned": self._death_patterns_learned,
                    "chronic_fairies": [
                        name for name, count in self._death_counts.items()
                        if count >= self._chronic_death_threshold
                    ],
                },
                "saved_at": time.time(),
            }

            self._cardinal_state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._cardinal_state_path, "w") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    def _load_learned_state(self) -> None:
        """Load previously learned state from disk."""
        try:
            if not self._cardinal_state_path.exists():
                return

            with open(self._cardinal_state_path) as f:
                state = json.load(f)

            # Restore baselines and thresholds
            self._baseline_metrics = state.get("baseline_metrics", {})
            self._anomaly_thresholds = state.get("anomaly_thresholds", {})

            # Restore learned fixes
            for pattern_key, fix_data in state.get("learned_fixes", {}).items():
                self._learned_fixes[pattern_key] = ProposedFix(
                    fix_id=f"learned_{pattern_key}",
                    description=fix_data["description"],
                    target=fix_data["target"],
                    action=fix_data["action"],
                    params=fix_data.get("params", {}),
                    confidence=fix_data.get("confidence", 0.5),
                    approved=True,
                    applied=True,
                )

            # Restore failure patterns (Sprint 1)
            for domain, pat_data in state.get("failure_patterns", {}).items():
                self._failure_patterns[domain] = {
                    "domain": pat_data.get("domain", domain),
                    "gap_types": defaultdict(int, pat_data.get("gap_types", {})),
                    "total_detections": pat_data.get("total_detections", 0),
                    "total_severity": pat_data.get("total_severity", 0.0),
                    "first_seen": pat_data.get("first_seen", 0),
                    "last_seen": pat_data.get("last_seen", 0),
                    "top_goal": pat_data.get("top_goal"),
                    "slow_count": pat_data.get("slow_count", 0),
                    "details": [],  # Ephemeral — not persisted
                }

            actor = getattr(self, "ACTOR_NAME", "Cardinal")
            print(f"[{actor}] Cardinal: Loaded {len(self._learned_fixes)} learned fixes, "
                  f"{len(self._baseline_metrics)} baselines, "
                  f"{len(self._failure_patterns)} failure patterns")
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════════
    # INBOX PERSISTENCE (2026-02-23)
    # ═══════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _write_to_inbox(entry: Dict[str, Any]) -> None:
        """Write an entry to the Cardinal inbox (state/cardinal_inbox.jsonl).

        Thread-safe, append-only. Ace reads this to see what Cardinal noticed.
        File rotates by session — cleared on boot.
        """
        try:
            CARDINAL_INBOX.parent.mkdir(parents=True, exist_ok=True)
            with _inbox_lock:
                with open(CARDINAL_INBOX, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, default=str) + "\n")
        except Exception:
            pass  # Never crash the pipeline for logging

    # ═══════════════════════════════════════════════════════════════════════════
    # STATUS / DIAGNOSTICS
    # ═══════════════════════════════════════════════════════════════════════════

    def get_cardinal_status(self) -> Dict[str, Any]:
        """Get full Cardinal status."""
        return {
            "mode": self._cardinal_mode.value,
            "booted": self._cardinal_booted,
            "has_direct_links": self.has_direct_links,
            "training_wheels_available": self._training_wheels_available,
            "observations": len(self._observations),
            "recent_errors": len(self._recent_errors),
            "recent_changes": len(self._recent_changes),
            "snapshots_tracked": len(self._fairy_snapshots),
            "proposed_fixes": len(self._proposed_fixes),
            "applied_fixes": len(self._applied_fixes),
            "learned_fixes": len(self._learned_fixes),
            "baseline_metrics": len(self._baseline_metrics),
            "correlations": len(self._correlations),
            # Sprint 1: Failure pattern tracking
            "failure_patterns_tracked": len(self._failure_patterns),
            "gap_cooldown_active": time.time() < self._gap_cooldown_until,
            "top_failure_domains": [
                p["domain"] for p in self._get_top_failure_patterns(3)
            ],
            # Death frequency learning (2026-02-23)
            "death_tracking": {
                "total_deaths_tracked": sum(self._death_counts.values()),
                "unique_dying_fairies": len(self._death_counts),
                "chronic_fairies": len([
                    n for n, c in self._death_counts.items()
                    if c >= self._chronic_death_threshold
                ]),
                "death_waves": self._death_wave_count,
                "patterns_learned": self._death_patterns_learned,
            },
        }

    def get_proposed_fixes(self) -> List[Dict[str, Any]]:
        """Get list of proposed fixes."""
        return [
            {
                "id": f.fix_id,
                "description": f.description,
                "target": f.target,
                "action": f.action,
                "confidence": f.confidence,
                "approved": f.approved,
                "applied": f.applied,
                "result": f.result,
            }
            for f in self._proposed_fixes
        ]

    def get_recent_observations(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent observations."""
        return [
            {
                "id": o.obs_id,
                "type": o.obs_type,
                "source": o.source,
                "severity": o.severity,
                "timestamp": o.timestamp,
            }
            for o in list(self._observations)[-limit:]
        ]

    def on_cardinal_anomaly(self, callback: Callable) -> None:
        """Register anomaly callback."""
        self._on_anomaly_callbacks.append(callback)

    def on_cardinal_fix_proposed(self, callback: Callable) -> None:
        """Register fix proposed callback."""
        self._on_fix_proposed_callbacks.append(callback)
