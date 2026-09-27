# AkashicLibrarianFairy - System-wide Actor Registry and Status Hub
# ===================================================================
#
# Purpose: Central registry that:
#   - Tracks all actors/fairies across the system
#   - Maintains Akashic Cards (rich state view per actor)
#   - Provides directory view (plane -> actor mapping)
#   - Ingests telemetry and status updates
#   - Composes GUI status frames (change-gated)
#
# Philosophy: "See the shape inside the signal."
#
# ===================================================================

from __future__ import annotations

import json
import time
import hashlib
import threading
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from dataclasses import dataclass, field

# V2 imports
# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
from fairies.P00_Autonomic.organ_template import MyFairy as Fairy, FairyState

# TracerWorkerMixin is optional - fallback to empty class if not available
try:
    from fairies.P00_Autonomic.tracer_worker_system import TracerWorkerMixin
except ImportError:
    class TracerWorkerMixin:
        """Fallback empty mixin when tracer system not available."""
        pass


def _extract_payload(message) -> Dict[str, Any]:
    """Extract payload from TensorEnvelope or dict message."""
    if hasattr(message, 'payload'):
        payload = message.payload
        if isinstance(payload, dict):
            return dict(payload)
        return {"raw": payload}
    elif isinstance(message, dict):
        return dict(message)
    return {"raw": message}


# ===================================================================
# DATA STRUCTURES
# ===================================================================

@dataclass
class AkashicCard:
    """
    Rich state representation for a single actor/fairy.

    The "soul" of each entity in the system.
    """
    actor: str
    plane: str = "unknown"
    channel: str = "unknown"
    version: str = ""

    # Identity
    purpose: str = ""
    mantra: str = ""
    lore: str = ""
    role: str = "fairy"

    # Health
    status: str = "unknown"  # ok, warn, error, info, unknown
    health_message: str = ""

    # Timestamps
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    # State tracking
    counters: Dict[str, int] = field(default_factory=dict)
    bugs: List[Dict[str, Any]] = field(default_factory=list)
    checks: List[Dict[str, Any]] = field(default_factory=list)

    # Blueprint
    blueprint_sha: Optional[str] = None

    # Character sheet (directive ring + subsystems)
    character_sheet: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        return {
            "actor": self.actor,
            "plane": self.plane,
            "channel": self.channel,
            "version": self.version,
            "purpose": self.purpose,
            "mantra": self.mantra,
            "lore": self.lore,
            "role": self.role,
            "status": self.status,
            "health_message": self.health_message,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "counters": self.counters,
            "bugs": self.bugs[-20:],  # Keep last 20 bugs
            "checks": self.checks[-20:],  # Keep last 20 checks
            "blueprint_sha": self.blueprint_sha,
            "character_sheet": self.character_sheet,
        }


@dataclass
class DirectoryEntry:
    """
    Lightweight directory entry for actor listing.
    """
    actor: str
    name: str = ""
    plane: str = "unknown"
    channel: str = "unknown"
    status: str = "unknown"
    role: str = "fairy"
    version: str = ""
    last_seen: Optional[str] = None
    bug_count: int = 0
    has_card: bool = False

    def to_dict(self) -> dict:
        return {
            "actor": self.actor,
            "name": self.name or self.actor,
            "plane": self.plane,
            "channel": self.channel,
            "status": self.status,
            "role": self.role,
            "version": self.version,
            "last_seen": self.last_seen,
            "bugs": self.bug_count,
            "has_card": self.has_card,
        }


# ===================================================================
# AKASHIC LIBRARIAN FAIRY
# ===================================================================

class AkashicLibrarianFairy(Fairy):
    """
    Central registry and status hub for all actors in the system.

    Maintains:
      - Akashic Cards: Rich state for each actor
      - Directory Index: Plane -> actor mappings
      - Bug Feed: System-wide issue tracking
      - GUI Frames: Status visualization (change-gated)

    Topics subscribed:
      - telemetry: System telemetry events
      - fairy.status: Fairy status updates
      - fairy.card: Card upsert events
      - directory.register: Registration events

    Topics published:
      - librarian.card.updated: When a card changes
      - librarian.gui.frame: GUI status frames
    """

    ACTOR_NAME = "AkashicLibrarianFairy"
    ACTOR_PLANE = "P10"
    ACTOR_CHANNEL = "library"

    PURPOSE = "Track all actors and maintain rich state view"
    MANTRA = "See the shape inside the signal"

    def __init__(self, fabric=None):
        super().__init__(fabric)
        self._init_tracer_worker()

        # Core state
        self._cards: Dict[str, AkashicCard] = {}
        self._directory: Dict[str, DirectoryEntry] = {}
        self._bugs: List[Dict[str, Any]] = []

        # GUI state (change-gated)
        self._last_gui_sig: Optional[str] = None
        self._gui_seq: int = 0

        # Thread safety
        self._lock = threading.Lock()

        # Meters (for GUI chemistry display)
        self._meters = {
            "dopamine": 0.0,
            "serotonin": 0.0,
            "cortisol": 0.0,
            "adrenaline": 0.0,
        }

        # ─── Pattern E.1 — StagedSubstrateMonitor (2026-04-27, Nous + Ace) ──
        # Per Claude_Office/plans/DEVELOPMENTAL_AI_INTEGRATION_2026-04-27.md
        # Pattern E. Tracks substrate-energy state to make development
        # observable. Builds on SYSTEM_TELLS Slice 1 infrastructure (same
        # error-feed/GUI-emit pattern, repurposed for substrate-state).
        # Subscribes to cortex compression, paradox energy, gravity, and
        # Dr Zero cognition cycles. Periodically emits substrate.stage
        # snapshots; on stage-transition, also pushes a substrate-stage
        # entry to the bug feed for visibility.
        from collections import deque as _deque
        self._substrate_state: Dict[str, float] = {
            "compression_ratio": 0.0,
            "avg_compression": 0.0,
            "paradox_pulse_total": 0.0,
            "paradox_pulse_rate": 0.0,
            "gravity_tau": 1.0,
            "gravity_mass": 0.0,
            "gravity_tau_var": 0.0,
        }
        self._substrate_windows = {
            "compression": _deque(maxlen=30),
            "paradox": _deque(maxlen=30),
            "gravity_tau": _deque(maxlen=30),
        }
        # Dr Zero cycle status distribution (5-state Pattern D taxonomy)
        self._cycle_status_counts: Dict[str, int] = {
            "fully-mastered": 0,
            "task-success-no-substrate-progress": 0,  # foreign-currency cycles
            "true-learning-edge": 0,
            "task-fail-substrate-progress": 0,
            "overload": 0,
            # Legacy 3-state (back-compat with pre-Pattern-D cycles)
            "too_easy": 0,
            "optimal": 0,
            "too_hard": 0,
        }
        self._cycle_total = 0
        self._last_substrate_emit_ts: float = 0.0
        self._last_stage_signature: Optional[str] = None
        # Stage thresholds — crossing any of these emits a stage-transition
        self._SUBSTRATE_EMIT_INTERVAL = 60.0  # seconds between periodic emits
        self._STAGE_COMPRESSION_BUCKETS = (1.0, 1.5, 2.0, 3.0, 5.0)
        self._STAGE_GRAVITY_TAU_BUCKETS = (1.0, 1.1, 1.5, 2.0, 3.0)
        # Foreign-currency rate above this is the diagnostic alarm
        self._FOREIGN_CURRENCY_ALARM = 0.50  # >50% of cycles producing no substrate progress

    # ===================================================================
    # LIFECYCLE
    # ===================================================================

    def on_boot(self):
        """Initialize on boot"""
        # IMPORTANT: Call super() to trigger HeartbeatMixin auto-start
        super().on_boot()
        self.log("Akashic Librarian booted - tracking all actors")
        return True


    def on_tick(self, beat: int = 0):
        """Periodic tick — seed specialist reflections."""
        # SUBSTRATE REFLECTION: Handled by Organ Template _substrate_reflect() since 2026-03-11



    def on_wire(self, postal):
        """Wire to postal system"""
        # Subscribe to system events
        postal.subscribe("telemetry", self._on_telemetry)
        postal.subscribe("fairy.status", self._on_fairy_status)
        postal.subscribe("fairy.card", self._on_card_upsert)
        postal.subscribe("directory.register", self._on_registration)
        postal.subscribe("consciousness.tick", self._on_consciousness_tick)
        # FIX 2026-04-26 (Nous + Ace) — SYSTEM_TELLS_ON_ITSELF Slice 1.
        # ForensicScribeFairy publishes forensic.alert with throttling + dedup
        # whenever errors/warnings are detected. Previously this had ZERO
        # subscribers — published into the void. Wiring AkashicLibrarian as
        # the consumer so alerts flow into the bug feed + GUI surface.
        # Plan: Claude_Office/plans/SYSTEM_TELLS_ON_ITSELF.md
        # Memory: project_observation_driven_concurrent_development_doctrine.md
        #         (this is the architectural completion of Ace's "system tells
        #         on itself" methodology — moving the system from eyes-without-
        #         mouth to eyes-and-mouth-coupled-to-GUI-surfacing)
        postal.subscribe("forensic.alert", self._on_forensic_alert)

        # ─── Pattern E.1 substrate-state subscriptions (2026-04-27) ──────────
        # StagedSubstrateMonitor: makes substrate development observable.
        # Same shape as SYSTEM_TELLS Slice 1 (above), repurposed from
        # error-state to substrate-state. Each substrate publisher gets a
        # corresponding subscriber here; rolling windows feed periodic
        # substrate.stage emits and stage-transition events.
        postal.subscribe("cortex.compression.progress", self._on_compression_progress)
        postal.subscribe("paradox.energy.pulse", self._on_paradox_pulse)
        postal.subscribe("portal.gravity.state", self._on_gravity_state)
        postal.subscribe("cognition.cycle", self._on_cognition_cycle)

    def _on_consciousness_tick(self, message: Dict[str, Any]):
        """Handle consciousness tick - emit GUI if changed"""
        # Pattern E.1 (2026-04-27): also evaluate substrate stage on each tick.
        # Internal throttling caps actual emit cadence to once per
        # _SUBSTRATE_EMIT_INTERVAL seconds, so this is cheap on every tick.
        try:
            self._maybe_emit_substrate_stage()
        except Exception:
            pass
        self.emit_gui_if_changed()

    # ===================================================================
    # TELEMETRY INGESTION
    # ===================================================================

    def _on_telemetry(self, message: Dict[str, Any]):
        """Handle telemetry events"""
        payload = _extract_payload(message)
        self._ingest(payload)

    def _on_fairy_status(self, message: Dict[str, Any]):
        """Handle fairy status updates"""
        payload = _extract_payload(message)
        self._ingest(payload)

    def _on_card_upsert(self, message: Dict[str, Any]):
        """Handle card upsert events"""
        payload = _extract_payload(message)
        actor = payload.get("actor")
        card_data = payload.get("card", {})

        if not actor:
            return

        with self._lock:
            card = self._get_or_create_card(actor)

            # Merge card data
            for key, value in card_data.items():
                if hasattr(card, key):
                    setattr(card, key, value)

            card.last_seen = time.time()
            self._update_directory_from_card(card)

    def _on_registration(self, message: Dict[str, Any]):
        """Handle registration events"""
        payload = _extract_payload(message)
        actor = payload.get("actor") or payload.get("name")
        if not actor:
            return

        with self._lock:
            card = self._get_or_create_card(actor)
            card.plane = payload.get("plane", card.plane)
            card.channel = payload.get("channel", card.channel)
            card.version = payload.get("version", card.version)
            card.role = payload.get("role", card.role)
            card.purpose = payload.get("purpose", card.purpose)
            card.status = "ok"
            card.last_seen = time.time()

            self._update_directory_from_card(card)

    def _on_forensic_alert(self, message: Dict[str, Any]):
        """Handle forensic.alert events — SYSTEM_TELLS_ON_ITSELF Slice 1 (2026-04-26).

        ForensicScribeFairy publishes forensic.alert with throttling + dedup
        when errors/warnings are detected via fairy.error / telemetry / shadow.health.
        We ingest these as bug-feed entries and update the actor's card status
        so the GUI frame composition picks them up on the next consciousness.tick.

        Payload shape (from ForensicScribeFairy._raise_alert at fairy.py:495-501):
            {
                "title": str,
                "message": str,
                "actor": str,
                "level": str,    # warn / error / critical
                "ts": float,
            }
        """
        try:
            payload = _extract_payload(message)
            actor = payload.get("actor", "unknown")
            level = (payload.get("level") or "warn").lower()
            title = payload.get("title", "")
            msg = payload.get("message", "")
            ts = payload.get("ts", time.time())

            # Distinct console line so developers see alerts immediately
            # (this is the "system telling on itself" loud channel; quiet
            # channel is the bug-feed which surfaces in GUI on next tick)
            try:
                print(f"[{self.ACTOR_NAME}] [SYSTEM_TELLS] {level.upper()} "
                      f"actor={actor} title='{title[:60]}' msg='{msg[:120]}'",
                      flush=True)
            except Exception:
                pass

            # Push to bug feed for GUI surfacing
            bug_entry = {
                "ts": ts,
                "actor": actor,
                "level": level,
                "title": title,
                "message": msg,
                "source": "forensic.alert",
            }
            with self._lock:
                self._push_bug(bug_entry)

                # Update actor's card status if level warrants it
                # (warn → at least warn, error/critical → error)
                card = self._get_or_create_card(actor)
                if level in ("error", "critical"):
                    card.status = "error"
                elif level == "warn" and card.status == "ok":
                    card.status = "warn"
                card.last_seen = ts
                self._update_directory_from_card(card)

            # Trigger immediate GUI emit instead of waiting for next
            # consciousness.tick — alerts deserve fast surfacing.
            try:
                self.emit_gui_if_changed()
            except Exception:
                pass

        except Exception as _e:
            # Never let alert handling break the AkashicLibrarian
            try:
                print(f"[{self.ACTOR_NAME}] _on_forensic_alert error: "
                      f"{type(_e).__name__}: {_e}", flush=True)
            except Exception:
                pass

    # =========================================================================
    # PATTERN E.1 — StagedSubstrateMonitor (2026-04-27, Nous + Ace)
    #
    # Plan: Claude_Office/plans/DEVELOPMENTAL_AI_INTEGRATION_2026-04-27.md
    # Doctrine refs:
    #   project_pubsub_asymmetry_subscribers_without_publishers.md
    #     (each substrate publisher gets a subscriber here; this fairy
    #      becomes the substrate-state aggregator)
    #   project_substrate_energy_not_token_currency_doctrine.md
    #     (we monitor substrate-energy currencies, not task-completion)
    #   project_cognition_inside_manifold_waking_mind_linear_time_doctrine.md
    #     (substrate state is manifold-time; we sample at heartbeat
    #      cadence and aggregate over windows)
    #
    # Ingestion handlers update _substrate_state + _substrate_windows.
    # Periodic emit (every _SUBSTRATE_EMIT_INTERVAL seconds, gated by
    # consciousness.tick) computes a stage signature; on transition,
    # publishes substrate.stage_transition AND pushes to bug feed.
    # =========================================================================

    def _on_compression_progress(self, message: Dict[str, Any]):
        """Handle cortex.compression.progress (Pattern D D.5a publisher)."""
        try:
            payload = _extract_payload(message)
            ratio = float(payload.get("compression_ratio", 0.0))
            avg = float(payload.get("avg_compression", 0.0))
            with self._lock:
                self._substrate_state["compression_ratio"] = ratio
                self._substrate_state["avg_compression"] = avg
                self._substrate_windows["compression"].append(ratio)
        except Exception:
            pass

    def _on_paradox_pulse(self, message: Dict[str, Any]):
        """Handle paradox.energy.pulse (existing ParadoxEnergyBridge publisher)."""
        try:
            payload = _extract_payload(message)
            energy = float(payload.get("energy", 0.0))
            with self._lock:
                self._substrate_state["paradox_pulse_total"] += energy
                self._substrate_windows["paradox"].append(energy)
                # Rolling rate over the window
                w = self._substrate_windows["paradox"]
                if w:
                    self._substrate_state["paradox_pulse_rate"] = sum(w) / len(w)
        except Exception:
            pass

    def _on_gravity_state(self, message: Dict[str, Any]):
        """Handle portal.gravity.state (existing AssociationCortex publisher)."""
        try:
            payload = _extract_payload(message)
            tau = float(payload.get("time_dilation", 1.0))
            mass = float(payload.get("portal_mass", 0.0))
            with self._lock:
                self._substrate_state["gravity_tau"] = tau
                self._substrate_state["gravity_mass"] = mass
                self._substrate_windows["gravity_tau"].append(tau)
                # Variance-based stability
                w = list(self._substrate_windows["gravity_tau"])
                if len(w) >= 2:
                    m = sum(w) / len(w)
                    self._substrate_state["gravity_tau_var"] = (
                        sum((x - m) ** 2 for x in w) / (len(w) - 1)
                    )
        except Exception:
            pass

    def _on_cognition_cycle(self, message: Dict[str, Any]):
        """Handle cognition.cycle (Dr Zero cycle results, SomaticMindFairy publisher).

        Tracks Pattern D status distribution: foreign-currency-rate,
        true-learning-edge rate, etc. Both Pattern D 5-state taxonomy and
        legacy 3-state are counted (back-compat with cycles that fired
        before substrate signal was available).
        """
        try:
            payload = _extract_payload(message)
            status = payload.get("status") or payload.get("learning_edge_status") or ""
            with self._lock:
                self._cycle_total += 1
                if status in self._cycle_status_counts:
                    self._cycle_status_counts[status] += 1
        except Exception:
            pass

    def _stage_signature(self) -> str:
        """Compute a coarse stage signature for transition detection.

        Buckets compression and gravity-τ into discrete bands; combines
        with foreign-currency rate band. Crossing any bucket boundary
        produces a different signature → stage transition fires.
        """
        avg_comp = self._substrate_state.get("avg_compression", 0.0)
        tau = self._substrate_state.get("gravity_tau", 1.0)
        # Bucket compression
        comp_bucket = 0
        for i, threshold in enumerate(self._STAGE_COMPRESSION_BUCKETS):
            if avg_comp >= threshold:
                comp_bucket = i + 1
        # Bucket τ
        tau_bucket = 0
        for i, threshold in enumerate(self._STAGE_GRAVITY_TAU_BUCKETS):
            if tau >= threshold:
                tau_bucket = i + 1
        # Foreign-currency band
        fc_band = "low"
        if self._cycle_total > 5:
            fc_rate = self._cycle_status_counts.get("task-success-no-substrate-progress", 0) / self._cycle_total
            if fc_rate > self._FOREIGN_CURRENCY_ALARM:
                fc_band = "alarm"
            elif fc_rate > 0.25:
                fc_band = "moderate"
        return f"comp{comp_bucket}-tau{tau_bucket}-fc{fc_band}"

    def _maybe_emit_substrate_stage(self) -> None:
        """Periodic substrate.stage emit, gated by interval + signature change.

        Called from consciousness.tick. Throttles to one emit per
        _SUBSTRATE_EMIT_INTERVAL seconds; on top of that, only emits the
        stage-transition variant when the signature has actually changed.
        """
        now = time.time()
        if (now - self._last_substrate_emit_ts) < self._SUBSTRATE_EMIT_INTERVAL:
            return

        with self._lock:
            sig = self._stage_signature()
            transitioned = (self._last_stage_signature is not None
                           and sig != self._last_stage_signature)

            # Snapshot for emit
            snapshot = dict(self._substrate_state)
            snapshot["cycle_total"] = self._cycle_total
            snapshot["cycle_status_counts"] = dict(self._cycle_status_counts)
            snapshot["stage_signature"] = sig
            snapshot["transitioned"] = transitioned
            if self._cycle_total > 0:
                snapshot["foreign_currency_rate"] = (
                    self._cycle_status_counts.get("task-success-no-substrate-progress", 0)
                    / self._cycle_total
                )
                snapshot["true_learning_rate"] = (
                    self._cycle_status_counts.get("true-learning-edge", 0)
                    / self._cycle_total
                )
            else:
                snapshot["foreign_currency_rate"] = 0.0
                snapshot["true_learning_rate"] = 0.0

            prior_sig = self._last_stage_signature
            self._last_stage_signature = sig
            self._last_substrate_emit_ts = now

        # Publish substrate.stage every interval (heartbeat for consumers)
        try:
            if hasattr(self, 'post') and self.post:
                self.post.publish("substrate.stage", {
                    "from": self.ACTOR_NAME,
                    "snapshot": snapshot,
                    "ts": now,
                })
        except Exception:
            pass

        # On transition, ALSO publish substrate.stage_transition + log to bug feed
        if transitioned:
            try:
                if hasattr(self, 'post') and self.post:
                    self.post.publish("substrate.stage_transition", {
                        "from": self.ACTOR_NAME,
                        "from_stage": prior_sig,
                        "to_stage": sig,
                        "snapshot": snapshot,
                        "ts": now,
                    })
            except Exception:
                pass

            # Console line (loud, like SYSTEM_TELLS forensic.alert pattern)
            try:
                fc = snapshot.get("foreign_currency_rate", 0.0)
                tl = snapshot.get("true_learning_rate", 0.0)
                print(f"[{self.ACTOR_NAME}] [SUBSTRATE_STAGE] "
                      f"{prior_sig} → {sig} "
                      f"comp_avg={snapshot.get('avg_compression', 0.0):.2f} "
                      f"τ={snapshot.get('gravity_tau', 1.0):.2f} "
                      f"fc_rate={fc:.0%} true_learning={tl:.0%}",
                      flush=True)
            except Exception:
                pass

            # Push to bug feed for GUI visibility (info-level, not error)
            try:
                bug_entry = {
                    "ts": now,
                    "actor": self.ACTOR_NAME,
                    "level": "info",
                    "title": f"Substrate stage transition: {prior_sig} → {sig}",
                    "message": (
                        f"compression_avg={snapshot.get('avg_compression', 0.0):.3f} "
                        f"τ={snapshot.get('gravity_tau', 1.0):.3f} "
                        f"foreign_currency_rate={snapshot.get('foreign_currency_rate', 0.0):.0%}"
                    ),
                    "category": "substrate_stage",
                }
                self._push_bug(bug_entry)
            except Exception:
                pass

    def _ingest(self, payload: Dict[str, Any]):
        """
        Normalize and ingest a telemetry/status packet.

        Permissive: any packet that names an actor becomes an observation.
        """
        p = payload or {}

        # Resolve actor name from various fields
        inner = p.get("payload", {})
        details = p.get("details", {}) or inner.get("details", {})

        actor = (
            p.get("actor")
            or p.get("fairy")
            or inner.get("actor")
            or inner.get("fairy")
            or details.get("actor")
        )

        if not actor:
            return

        with self._lock:
            card = self._get_or_create_card(actor)

            # Update from payload
            card.plane = p.get("plane") or inner.get("plane") or card.plane
            card.channel = p.get("channel") or inner.get("channel") or card.channel
            card.version = (
                p.get("version")
                or p.get("fairy_version")
                or inner.get("version")
                or card.version
            )

            # Health status
            status = (
                p.get("status")
                or inner.get("status")
                or details.get("status")
                or ""
            ).lower()
            if status in {"ok", "warn", "error", "info"}:
                card.status = status

            # Health message
            message = p.get("message") or inner.get("message") or details.get("message")
            if message:
                card.health_message = str(message)[:240]

            # Counters
            counters = details.get("counters", {})
            if isinstance(counters, dict):
                card.counters.update(counters)

            # Bug tracking on warn/error
            if status in {"warn", "error"}:
                bug = {
                    "when": self._now_iso(),
                    "actor": actor,
                    "event": p.get("event") or p.get("opcode"),
                    "status": status,
                    "message": card.health_message,
                }
                card.bugs.append(bug)
                if len(card.bugs) > 50:
                    card.bugs = card.bugs[-50:]
                self._push_bug(bug)

            # Tests/checks
            tests = p.get("tests") or inner.get("tests") or details.get("tests")
            if tests:
                if isinstance(tests, dict):
                    tests = list(tests.values())
                card.checks = list(tests)[-50:]

            # Character sheet
            cs = p.get("character_sheet") or inner.get("character_sheet")
            if isinstance(cs, dict):
                card.character_sheet = cs

            # Blueprint
            if "blueprint" in str(p.get("opcode", "")).lower():
                card.blueprint_sha = p.get("sha") or inner.get("sha")

            card.last_seen = time.time()
            self._update_directory_from_card(card)

    # ===================================================================
    # CARD MANAGEMENT
    # ===================================================================

    def _get_or_create_card(self, actor: str) -> AkashicCard:
        """Get existing card or create new one"""
        if actor not in self._cards:
            self._cards[actor] = AkashicCard(actor=actor)
        return self._cards[actor]

    def _update_directory_from_card(self, card: AkashicCard):
        """Update directory entry from card"""
        entry = DirectoryEntry(
            actor=card.actor,
            name=card.actor,
            plane=card.plane,
            channel=card.channel,
            status=card.status,
            role=card.role,
            version=card.version,
            last_seen=self._now_iso(),
            bug_count=len(card.bugs),
            has_card=True,
        )
        self._directory[card.actor] = entry

    def _push_bug(self, bug: Dict[str, Any]):
        """Add bug to global feed"""
        self._bugs.append(bug)
        if len(self._bugs) > 200:
            self._bugs = self._bugs[-200:]

    # ===================================================================
    # STATUS QUERIES
    # ===================================================================

    def get_card(self, actor: str) -> Optional[Dict[str, Any]]:
        """Get card for an actor"""
        with self._lock:
            card = self._cards.get(actor)
            return card.to_dict() if card else None

    def get_directory(self, plane_filter: Optional[str] = None) -> Dict[str, Any]:
        """
        Get directory view (plane -> actors mapping).
        """
        with self._lock:
            planes: Dict[str, Dict[str, Any]] = {}

            for actor, entry in sorted(self._directory.items()):
                plane = entry.plane or "unknown"

                if plane_filter and plane != plane_filter:
                    continue

                bucket = planes.setdefault(plane, {"directory": [], "summary": {}})
                bucket["directory"].append(entry.to_dict())

            # Compute summaries
            for plane, pdata in planes.items():
                counts = {"ok": 0, "warn": 0, "error": 0, "info": 0, "unknown": 0}
                for ent in pdata["directory"]:
                    st = ent.get("status", "unknown")
                    if st not in counts:
                        st = "unknown"
                    counts[st] += 1

                # Worst status wins
                worst = "unknown"
                for candidate in ("error", "warn", "ok", "info"):
                    if counts[candidate] > 0:
                        worst = candidate
                        break

                pdata["summary"] = {
                    "count": len(pdata["directory"]),
                    "status": worst,
                    "states": counts,
                }

            return {
                "ok": True,
                "ts": self._now_iso(),
                "planes": planes,
                "total_actors": len(self._directory),
            }

    def get_bugs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent bugs"""
        with self._lock:
            return self._bugs[-limit:]

    # ===================================================================
    # GUI FRAME COMPOSITION
    # ===================================================================

    def _compose_gui_frame(self) -> Dict[str, Any]:
        """
        Compose GUI status frame.
        """
        # Character sheet concept
        character = {
            "name": "Akashic System",
            "level": 1,
            "archetype": "Librarian",
            "hp": 100,
            "mp": 100,
        }

        # Build panels from directory
        panels = []
        for actor, entry in sorted(self._directory.items()):
            card = self._cards.get(actor)
            panels.append({
                "actor": actor,
                "plane": entry.plane,
                "channel": entry.channel,
                "version": entry.version,
                "status": entry.status,
                "last_seen": entry.last_seen,
                "bugs": card.bugs[-5:] if card else [],
                "counters": card.counters if card else {},
            })

        # Health rollup
        worst = "ok"
        for p in panels:
            st = (p.get("status") or "unknown").lower()
            if st == "error":
                worst = "error"
                break
            if st == "warn" and worst == "ok":
                worst = "warn"

        mood = {"ok": "serene", "warn": "anxious", "error": "critical"}.get(worst, "serene")

        # Build planes view
        directory = self.get_directory()
        planes = directory.get("planes", {})

        frame = {
            "event": "GUI_STATUS",
            "status": worst,
            "details": {
                "seq": self._gui_seq + 1,
                "character": character,
                "panels": panels,
                "meters": dict(self._meters),
                "bug_feed": self._bugs[-50:],
                "mood": mood,
            },
            "planes": planes,
            "fairy": self._name,
            "contract_version": "1.0",
        }

        return frame

    def emit_gui_if_changed(self) -> Dict[str, Any]:
        """
        Emit GUI frame only when its signature changed.
        """
        with self._lock:
            frame = self._compose_gui_frame()
            sig = self._stable_sig(frame)

            if sig and sig == self._last_gui_sig:
                return {"ok": True, "emitted": False, "seq": self._gui_seq, "sha": sig}

            # Bump seq and emit
            self._gui_seq += 1
            frame["details"]["seq"] = self._gui_seq

            # Publish
            if hasattr(self, '_postal') and self._postal:
                self._postal.publish("librarian.gui.frame", frame)

            self._last_gui_sig = sig
            return {"ok": True, "emitted": True, "seq": self._gui_seq, "sha": sig}

    # ===================================================================
    # UTILITIES
    # ===================================================================

    @staticmethod
    def _now_iso() -> str:
        """Get current time in ISO format"""
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _stable_sig(self, obj: Any) -> Optional[str]:
        """
        Compute stable signature, ignoring volatile fields.
        """
        drop = {"ts", "time", "id", "nonce", "_seq", "seq", "last_seen"}

        def normalize(x):
            if isinstance(x, dict):
                return {k: normalize(v) for k, v in x.items() if k not in drop}
            if isinstance(x, list):
                return [normalize(v) for v in x]
            return x

        try:
            norm = normalize(obj)
            raw = json.dumps(norm, sort_keys=True, ensure_ascii=False).encode("utf-8")
            return hashlib.sha256(raw).hexdigest()
        except Exception:
            return None

    def bump_meter(self, neurochemical: str, delta: float = 0.1):
        """Bump a chemistry meter"""
        with self._lock:
            if neurochemical in self._meters:
                self._meters[neurochemical] = float(self._meters[neurochemical]) + delta

    def get_stats(self) -> Dict[str, Any]:
        """Get librarian statistics"""
        with self._lock:
            return {
                "total_cards": len(self._cards),
                "total_directory": len(self._directory),
                "total_bugs": len(self._bugs),
                "gui_seq": self._gui_seq,
                "meters": dict(self._meters),
            }

    # ===================================================================
    # CAPABILITY CHECKLIST MANAGEMENT
    # ===================================================================

    def _determine_fairy_preset(self, fairy_name: str) -> str:
        """Determine which preset a fairy should use."""
        from directory.capability_checklist import determine_fairy_preset
        return determine_fairy_preset(fairy_name)

    def _intent_get_fairy_capabilities(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get capability checklist for a fairy."""
        from directory.capability_checklist import get_capability_checklist, get_sourpatches_checklist

        fairy_name = payload.get("fairy_name", "")
        if not fairy_name:
            return {"ok": False, "error": "fairy_name required"}

        # Special case for Sourpatches
        if "sourpatches" in fairy_name.lower():
            checklist = get_sourpatches_checklist()
        else:
            preset = self._determine_fairy_preset(fairy_name)
            checklist = get_capability_checklist(fairy_name, preset)

        return {
            "ok": True,
            "fairy_name": fairy_name,
            "preset": checklist.preset,
            "checklist": checklist.to_dict(),
        }

    def _intent_compare_to_sourpatches(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Compare a fairy's capabilities to Sourpatches (fully loaded reference)."""
        from directory.capability_checklist import get_capability_checklist, get_sourpatches_checklist

        fairy_name = payload.get("fairy_name", "")
        if not fairy_name:
            return {"ok": False, "error": "fairy_name required"}

        # Get fairy's checklist
        if "sourpatches" in fairy_name.lower():
            fairy_checklist = get_sourpatches_checklist()
        else:
            preset = self._determine_fairy_preset(fairy_name)
            fairy_checklist = get_capability_checklist(fairy_name, preset)

        # Get Sourpatches reference
        sourpatches = get_sourpatches_checklist()

        # Find differences
        missing = []
        for cap_id in sourpatches.list_enabled():
            if not fairy_checklist.has(cap_id):
                missing.append(cap_id)

        return {
            "ok": True,
            "fairy_name": fairy_name,
            "fairy_preset": fairy_checklist.preset,
            "sourpatches_has": len(sourpatches.list_enabled()),
            "fairy_has": len(fairy_checklist.list_enabled()),
            "missing_from_sourpatches": missing,
            "comparison": fairy_checklist.compare_to(sourpatches),
        }

    def _intent_enable_capability(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Enable a capability for a fairy."""
        from directory.capability_checklist import get_capability_checklist, CAPABILITIES_REGISTRY

        fairy_name = payload.get("fairy_name", "")
        capability_id = payload.get("capability_id", "")

        if not fairy_name:
            return {"ok": False, "error": "fairy_name required"}
        if not capability_id:
            return {"ok": False, "error": "capability_id required"}

        # Get or create checklist for this fairy
        preset = self._determine_fairy_preset(fairy_name)
        checklist = get_capability_checklist(fairy_name, preset)

        success = checklist.enable(capability_id)
        if not success:
            return {
                "ok": False,
                "error": f"Unknown capability: {capability_id}",
                "available": list(CAPABILITIES_REGISTRY.keys()),
            }

        return {
            "ok": True,
            "fairy_name": fairy_name,
            "capability_id": capability_id,
            "enabled": True,
            "checklist": checklist.to_dict(),
        }

    def _intent_disable_capability(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Disable a capability for a fairy."""
        from directory.capability_checklist import get_capability_checklist

        fairy_name = payload.get("fairy_name", "")
        capability_id = payload.get("capability_id", "")

        if not fairy_name:
            return {"ok": False, "error": "fairy_name required"}
        if not capability_id:
            return {"ok": False, "error": "capability_id required"}

        preset = self._determine_fairy_preset(fairy_name)
        checklist = get_capability_checklist(fairy_name, preset)

        success = checklist.disable(capability_id)
        if not success:
            return {
                "ok": False,
                "error": f"Capability not found in checklist: {capability_id}",
            }

        return {
            "ok": True,
            "fairy_name": fairy_name,
            "capability_id": capability_id,
            "enabled": False,
            "checklist": checklist.to_dict(),
        }

    def _intent_list_fairies_by_capability(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """List all fairies that have a specific capability."""
        from directory.capability_checklist import (
            get_capability_checklist,
            get_sourpatches_checklist,
            CAPABILITIES_REGISTRY,
        )

        capability_id = payload.get("capability_id", "")
        if not capability_id:
            return {"ok": False, "error": "capability_id required"}

        if capability_id not in CAPABILITIES_REGISTRY:
            return {
                "ok": False,
                "error": f"Unknown capability: {capability_id}",
                "available": list(CAPABILITIES_REGISTRY.keys()),
            }

        # Check all known fairies in directory
        fairies_with_cap = []
        fairies_without_cap = []

        with self._lock:
            for actor in self._directory:
                preset = self._determine_fairy_preset(actor)

                # Special case for Sourpatches
                if "sourpatches" in actor.lower():
                    checklist = get_sourpatches_checklist()
                else:
                    checklist = get_capability_checklist(actor, preset)

                if checklist.has(capability_id):
                    fairies_with_cap.append({
                        "name": actor,
                        "preset": preset,
                    })
                else:
                    fairies_without_cap.append({
                        "name": actor,
                        "preset": preset,
                    })

        return {
            "ok": True,
            "capability_id": capability_id,
            "description": CAPABILITIES_REGISTRY[capability_id].get("description", ""),
            "fairies_with": fairies_with_cap,
            "fairies_without": fairies_without_cap,
            "count_with": len(fairies_with_cap),
            "count_without": len(fairies_without_cap),
        }

    def _intent_list_all_capabilities(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """List all available capabilities with metadata."""
        from directory.capability_checklist import list_all_capabilities, list_capabilities_by_category

        by_category = payload.get("by_category", False)

        if by_category:
            return {
                "ok": True,
                "by_category": list_capabilities_by_category(),
            }
        else:
            return {
                "ok": True,
                "capabilities": list_all_capabilities(),
            }

    def _intent_get_presets(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Get available capability presets."""
        from directory.capability_checklist import PRESETS, get_preset_capabilities

        preset_name = payload.get("preset_name", "")

        if preset_name:
            if preset_name not in PRESETS:
                return {
                    "ok": False,
                    "error": f"Unknown preset: {preset_name}",
                    "available": list(PRESETS.keys()),
                }
            return {
                "ok": True,
                "preset_name": preset_name,
                "capabilities": list(get_preset_capabilities(preset_name)),
            }
        else:
            return {
                "ok": True,
                "presets": {
                    name: list(caps) for name, caps in PRESETS.items()
                },
            }

    def get_fairy_capabilities(self, fairy_name: str) -> Dict[str, Any]:
        """Convenience method to get a fairy's capabilities."""
        return self._intent_get_fairy_capabilities({"fairy_name": fairy_name})

    def compare_to_sourpatches(self, fairy_name: str) -> Dict[str, Any]:
        """Convenience method to compare a fairy to Sourpatches."""
        return self._intent_compare_to_sourpatches({"fairy_name": fairy_name})

    def list_fairies_by_capability(self, capability_id: str) -> Dict[str, Any]:
        """Convenience method to list fairies by capability."""
        return self._intent_list_fairies_by_capability({"capability_id": capability_id})


# ===================================================================
# SINGLETON ACCESS
# ===================================================================

_akashic_librarian: Optional[AkashicLibrarianFairy] = None

def get_akashic_librarian() -> AkashicLibrarianFairy:
    """Get singleton AkashicLibrarianFairy instance"""
    global _akashic_librarian
    if _akashic_librarian is None:
        _akashic_librarian = AkashicLibrarianFairy()
    return _akashic_librarian

def set_akashic_librarian(fairy: AkashicLibrarianFairy):
    """Set the singleton instance"""
    global _akashic_librarian
    _akashic_librarian = fairy
