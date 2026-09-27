"""
Directory Fairy - The control center of Akashic v2.

Manages fairy registration, system health, and coordination.
Integrates with PostalCore (messaging), TracerPool (recall), and TensorFabric (state).
"""

import importlib
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Add paths for v2 imports
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "postal_core" / "python"))
sys.path.insert(0, str(ROOT / "tracer_pool"))  # Go DLL bindings

from postal_core.tensor_fabric import TensorFabric, TensorCoord
from tracer_pool import TracerPool, TracerType

from .registry import FairyRegistry, FairyRecord
from .capability_index import CapabilityIndex
from .health import SystemHealth
from .handlers import RegistrationHandler, HeartbeatHandler, ConsciousnessHandler
from .migration import MigrationManager, FairyScanner

# Direct object registry for liveness checking (2026-02-09)
# This bypasses postal echo round-trips that caused 100 false fairy deaths
#
# FIX 2026-02-14: TWO SEPARATE _CITIZEN_OBJECTS dicts existed!
#   - fairy_template/consolidated.py had one (checked by HeartbeatHandler)
#   - organ_template/Organ_Template_0_3_0.py had another (where all fairies register)
#   HeartbeatHandler was looking in consolidated's empty dict while 90 fairies
#   registered in organ_template's dict → object-level liveness check always failed
#   → false death banners every 5 minutes for SourpatchesFairy, NousFairy, etc.
#
# Solution: Import the organ_template dict (where fairies actually register) and
# also update consolidated's dict to reference the same object. HeartbeatHandler
# gets the dict where fairies actually live.
try:
    from fairies.P00_Autonomic.organ_template.Organ_Template_0_3_0 import (
        _CITIZEN_OBJECTS,
    )
    # Also patch consolidated's reference so any code importing from there gets the same dict
    try:
        import fairy_template.consolidated as _consolidated_mod
        # Point consolidated's _CITIZEN_OBJECTS at the organ_template dict
        # This merges any fairies already registered in consolidated (like DirectoryFairy)
        # into the organ_template dict, then makes both names point to the same object.
        for k, v in _consolidated_mod._CITIZEN_OBJECTS.items():
            if k not in _CITIZEN_OBJECTS:
                _CITIZEN_OBJECTS[k] = v
        _consolidated_mod._CITIZEN_OBJECTS = _CITIZEN_OBJECTS
    except ImportError:
        pass
except ImportError:
    try:
        from fairy_template.consolidated import _CITIZEN_OBJECTS
    except ImportError:
        _CITIZEN_OBJECTS = {}

# ═══════════════════════════════════════════════════════════════════════════════
# FAIRY MANIFEST - Centralized fairy module/class mapping
# ═══════════════════════════════════════════════════════════════════════════════
# This eliminates bloated get_*() functions with duplicate path/import logic
# Add fairies here for centralized management via directory.get_fairy_instance()

FAIRY_MANIFEST = {
    # P00 - Autonomic
    "WakingSequenceFairy": {
        "module": "P00_Autonomic.nervous_system.waking_sequence_fairy",
        "class": "WakingSequenceFairy",
        "plane": "P00",
    },
    "DreamSeedFairy": {
        "module": "fairies.P00_Autonomic.nervous_system.dream_seed_fairy",
        "class": "DreamSeedFairy",
        "plane": "P00",
    },
    "CartographerFairy": {
        "module": "fairies.P00_Autonomic.nervous_system.cartographer_fairy",
        "class": "CartographerFairy",
        "plane": "P00",
    },
    # P30 - Cognition
    "WorkingMemoryHubFairy": {
        "module": "fairies.P30_Cognition.cognition.working_memory_hub_fairy",
        "class": "WorkingMemoryHubFairy",
        "plane": "P30",
    },
    "ActionChainFairy": {
        "module": "fairies.P30_Cognition.ActionChainFairy.fairy",
        "class": "ActionChainFairy",
        "plane": "P30",
    },
    "ManifoldConstrainedCortexFairy": {
        "module": "fairies.P30_Cognition.integration.manifold_constrained_cortex_fairy",
        "class": "ManifoldConstrainedCortexFairy",
        "plane": "P30",
    },
    # [2026-06-24 UMF-consolidation] The "UnconsciousMindFairy" manifest entry was REMOVED:
    # it resolved to the stale v1 P30 module, and the directory loader instantiates+caches
    # BY NAME -> a by-name lookup would spin a 2nd SomaticMindFairy into postal (duplicate mind).
    # Canonical = P20 SomaticMindFairy (blueprint-booted; set as the singleton by
    # server.py: set_somatic_mind(SYSTEM.umf)). By-name callers -> get_somatic_mind().
    "AutonomyFairy": {
        "module": "fairies.P30_Cognition.cognition.autonomy_fairy",
        "class": "AutonomyFairy",
        "plane": "P30",
    },
    # [2026-09-25 P30-autopilot-retired] The "AutopilotFairy" manifest entry was REMOVED: it resolved to
    # P30 autopilot_fairy.py, which had not compiled since at least 2026-05-14 and is now
    # autopilot_fairy.py.disabled. A by-name lookup would instantiate a 2nd live autopilot. It was NOT
    # repointed to P00: P00 AutopilotFairy has no singleton guard, so that would boot a duplicate gate.
    # Canonical = P00 AutopilotFairy (blueprint-booted). Same rule as the 06-24 UMF removal above.
    # P10 - Memory (PREVIOUSLY MISSING - 2026-02-02)
    "BlueprintDiaryHubFairy": {
        "module": "fairies.P10_Memory.BlueprintDiaryHubFairy.fairy",
        "class": "BlueprintDiaryHubFairy",
        "plane": "P10",
    },
    "ForensicScribeFairy": {
        "module": "fairies.P10_Memory.ForensicScribeFairy.fairy",
        "class": "ForensicScribeFairy",
        "plane": "P10",
    },
    "SRMRecallFairy": {
        "module": "fairies.P10_Memory.SRMRecallFairy.fairy",
        "class": "SRMRecallFairy",
        "plane": "P10",
    },
    "SRMMemoryFairy": {
        "module": "fairies.P10_Memory.SRMMemoryFairy.fairy",
        "class": "SRMMemoryFairy",
        "plane": "P10",
    },
    # P20 - Somatic
    "CirculationPumpFairy": {
        "module": "fairies.P20_Somatic.circulation.circulation_pump_fairy",
        "class": "CirculationPumpFairy",
        "plane": "P20",
    },
    # P40 - Sensory
    "ConversationSenseFairy": {
        "module": "fairies.P40_Sensory.ConversationSenseFairy.fairy",
        "class": "ConversationSenseFairy",
        "plane": "P40",
    },
    # Add more fairies as needed...
}


class DirectoryFairy:
    """
    The control center of Akashic v2.

    Manages:
    - Fairy registration and discovery
    - System health aggregation
    - Capability-based routing
    - Consciousness state monitoring

    Integrates with:
    - TensorFabric: 4D tensor state and messaging
    - TracerPool: Universal tracing for perfect recall
    """

    ACTOR_NAME = "DirectoryFairy"
    ACTOR_PLANE = "P00"
    ACTOR_CHANNEL = "directory"

    def __init__(self, fabric: Optional[TensorFabric] = None, v1_root: Optional[str] = None):
        # Core systems
        self.fabric = fabric or TensorFabric()
        self.pool = TracerPool.global_instance()

        # Registry and indexes
        self.registry = FairyRegistry()
        self.capability_index = CapabilityIndex()

        # Health aggregator
        self.health = SystemHealth(fabric=self.fabric, pool=self.pool)

        # Migration manager (for plug-and-play v1 fairy migration)
        self._v1_root = v1_root
        self._migration_manager: Optional[MigrationManager] = None
        if v1_root:
            self._migration_manager = MigrationManager(self.registry, Path(v1_root))

        # Handlers
        self._registration_handler = RegistrationHandler(
            registry=self.registry,
            capability_index=self.capability_index,
            pool=self.pool,
        )
        self._heartbeat_handler = HeartbeatHandler(
            registry=self.registry,
            citizen_objects=_CITIZEN_OBJECTS,
        )
        self._consciousness_handler = ConsciousnessHandler(fabric=self.fabric)

        # State
        self._root_tracer = None
        self._running = False
        self._boot_time = None

        # FIX 2026-02-13: Liveness tracking — DirectoryFairy needs _last_tick and
        # _tick_count so HeartbeatHandler._check_citizen_liveness() can verify it's
        # alive via direct object inspection. Without these, DirectoryFairy only
        # relied on postal echo for liveness — postal drops → false death → cascade.
        self._last_tick = 0.0
        self._tick_count = 0

        # FIX 2026-02-13: Register in _CITIZEN_OBJECTS for object-level liveness.
        # HeartbeatHandler checks _last_tick on objects in this dict. Without this,
        # DirectoryFairy was invisible to the PRIMARY liveness mechanism and could
        # only be verified via SECONDARY postal echo (which drops silently).
        _CITIZEN_OBJECTS[self.ACTOR_NAME] = self

        # Background thread for dead fairy checks
        self._check_thread = None
        self._check_interval = 10.0  # seconds

        # Centralized fairy instance cache (lazy loaded)
        self._fairy_instances: Dict[str, Any] = {}
        self._instance_lock = threading.Lock()

    def _publish_fairy_error(self, fairy_name: str, plane: str, error: str, error_type: str) -> None:
        """Publish fairy error to fabric for ForensicScribe/TracerDaemon to capture."""
        try:
            self.fabric.publish("fairy.error", {
                "fairy": fairy_name,
                "plane": plane,
                "error": error,
                "type": error_type,
                "context": "directory",
                "ts": time.time(),
            })
            # Also publish to telemetry for broader capture
            self.fabric.publish("telemetry.error", {
                "type": f"fairy_{error_type}",
                "fairy": fairy_name,
                "plane": plane,
                "message": error,
                "ts": time.time(),
            })
        except Exception:
            pass  # Don't fail operation due to error publishing failure

    def on_boot(self) -> Dict[str, Any]:
        """
        Boot the Directory control center.

        Sets up:
        - Identity registration with tracer pool
        - Postal subscriptions
        - Background health checks
        """
        if self._running:
            return {"ok": False, "error": "already_running"}

        self._boot_time = time.time()

        # Register our identity
        self.pool.register_identity(
            function_name=self.ACTOR_NAME,
            plane=self.ACTOR_PLANE,
            channel=self.ACTOR_CHANNEL,
            aliases=["Directory", "DirFairy"],
        )

        # Create root tracer
        self._root_tracer = self.pool.create_tracer(
            tracer_type=TracerType.FAIRY_WORK,
            fairy_name=self.ACTOR_NAME,
            cluster_id="cluster_directory_control",
            intent="fairy_lifecycle",
        )
        self.pool.start(self._root_tracer.id)

        # ─── SELF-REGISTRATION ───────────────────────────────────────────
        # FIX 2026-02-06: DirectoryFairy was never registering itself in its own
        # registry! This meant it had no FairyRecord, so heartbeat tracking didn't
        # work for it. The watchdog correctly flagged it as stale (173s silence).
        # Ace noted: "in the old ebook system the directory fairy was a clone and
        # had its own heartbeat also. no idea why it dont now"
        self.register_fairy(
            name=self.ACTOR_NAME,
            plane=self.ACTOR_PLANE,
            channel=self.ACTOR_CHANNEL,
            capabilities={"directory", "control_center", "routing", "registry"},
            metadata={"fairy_instance": self, "needs_heartbeat": True},
            status="running",
        )
        print(f"[DirectoryFairy] Self-registered in own registry")

        # Subscribe to postal topics
        self.fabric.subscribe("fairy.register", self._on_register, "dir-register")
        self.fabric.subscribe("fairy.unregister", self._on_unregister, "dir-unregister")
        self.fabric.subscribe("fairy.heartbeat", self._on_heartbeat, "dir-heartbeat")
        self.fabric.subscribe("consciousness.heartbeat", self._on_consciousness, "dir-consciousness")

        # === ROUTING TABLE SUBSCRIPTIONS (Phase 2 - Postal Backbone) ===
        self.fabric.subscribe("fairy.subscription.added", self._on_subscription_added, "dir-sub-track")
        self.fabric.subscribe("fairy.state.changed", self._on_state_changed, "dir-state-track")
        # Subscribe to heartbeat.pulse for CNS-style routing AND own liveness echo
        self.fabric.subscribe("heartbeat.pulse", self._on_heartbeat_pulse_for_routing, "dir-heartbeat-router")

        # FIX 2026-02-13: Register with HeartbeatRegistry for DIRECT pulse delivery.
        # DirectoryFairy is the MOST critical fairy — if it dies, the watchdog can't
        # function and UMF starts cascading restarts of every fairy in the system.
        # Postal drops caused DirectoryFairy to go silent → false death cascade.
        # Direct registry delivery ensures DirectoryFairy ALWAYS gets its pulse.
        #
        # IMPORTANT: Use a LIGHTWEIGHT callback here (_on_registry_pulse), NOT the
        # full _on_heartbeat_pulse_for_routing which fans out 82+ postal publishes.
        # Registry.pulse() is synchronous — a slow callback blocks ALL other fairies.
        try:
            from consciousness.heartbeat_registry import get_heartbeat_registry
            _hb_registry = get_heartbeat_registry()
            _hb_registry.register(self.ACTOR_NAME, self._on_registry_pulse)
            print(f"[DirectoryFairy] Registered with HeartbeatRegistry (direct pulse delivery)")
        except ImportError:
            pass  # Registry not available yet, rely on postal

        # Register callback for dead fairies
        self._heartbeat_handler.on_dead_fairy(self._on_dead_fairy)

        # Start background check thread
        self._running = True
        self._check_thread = threading.Thread(target=self._check_loop, daemon=True, name="DirectoryCheck")
        self._check_thread.start()

        # Publish boot event
        coord = TensorCoord(time=0, affect=0, memory=0, cognition=0)
        self.fabric.publish(
            "fairy.booted",
            {
                "fairy": self.ACTOR_NAME,
                "type": "ControlCenter",
                "boot_time": self._boot_time,
            },
            coord=coord,
            affect=0.5,
            priority=0,  # HIGH
        )

        return {
            "ok": True,
            "name": self.ACTOR_NAME,
            "root_tracer": self._root_tracer.id if self._root_tracer else None,
        }

    def on_shutdown(self) -> Dict[str, Any]:
        """Shutdown the Directory control center."""
        if not self._running:
            return {"ok": False, "error": "not_running"}

        self._running = False
        shutdown_results = {}

        # CRITICAL: Shutdown all registered fairies FIRST (before fabric!)
        # This ensures fairies like AssociationCortex can save their state
        # Run in PARALLEL with timeout to avoid slow shutdown
        import concurrent.futures
        print("[Directory] Shutting down registered fairies (parallel)...")

        with self._instance_lock:
            fairies_to_shutdown = [
                (name, instance) for name, instance in self._fairy_instances.items()
                if hasattr(instance, 'on_shutdown')
            ]

        def _shutdown_one(name_instance):
            name, instance = name_instance
            try:
                instance.on_shutdown()
                return (name, "ok")
            except Exception as e:
                return (name, str(e))

        # Parallel shutdown with 5 second total timeout
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(_shutdown_one, fi): fi[0] for fi in fairies_to_shutdown}
            done, not_done = concurrent.futures.wait(futures, timeout=5.0)

            for future in done:
                try:
                    name, result = future.result(timeout=0.1)
                    shutdown_results[name] = result
                except:
                    pass

            for future in not_done:
                name = futures[future]
                shutdown_results[name] = "timeout"
                future.cancel()

        ok_count = sum(1 for v in shutdown_results.values() if v == "ok")
        timeout_count = sum(1 for v in shutdown_results.values() if v == "timeout")
        print(f"[Directory] Fairy shutdown: {ok_count} ok, {timeout_count} timeout")

        # Wait for check thread
        if self._check_thread and self._check_thread.is_alive():
            self._check_thread.join(timeout=2.0)

        # Complete root tracer
        if self._root_tracer:
            self.pool.complete(self._root_tracer.id)

        # Shutdown fabric LAST (after fairies have saved)
        self.fabric.shutdown()

        return {"ok": True, "uptime": time.time() - self._boot_time if self._boot_time else 0, "fairy_shutdowns": shutdown_results}

    # =========================================================================
    # MESSAGE HANDLERS
    # =========================================================================

    def _on_register(self, envelope) -> None:
        """Handle fairy.register messages."""
        tracer = self._create_action_tracer("on_register")
        try:
            result = self._registration_handler.on_register(envelope.payload)
            self.pool.complete(tracer.id)
        except Exception as e:
            self.pool.fail(tracer.id, str(e))

    def _on_unregister(self, envelope) -> None:
        """Handle fairy.unregister messages."""
        tracer = self._create_action_tracer("on_unregister")
        try:
            result = self._registration_handler.on_unregister(envelope.payload)
            self.pool.complete(tracer.id)
        except Exception as e:
            self.pool.fail(tracer.id, str(e))

    _hb_echo_count = 0
    _hb_echo_first_logged = False

    def _on_heartbeat(self, envelope) -> None:
        """Handle fairy.heartbeat messages."""
        self._hb_echo_count += 1
        # DEBUG 2026-02-06: Log first few heartbeat echoes received
        if self._hb_echo_count == 1 or self._hb_echo_count % 2000 == 0:
            try:
                payload = envelope.payload if hasattr(envelope, 'payload') else envelope
                name = payload.get("name", "?") if isinstance(payload, dict) else "?"
                print(f"[DirectoryFairy] _on_heartbeat #{self._hb_echo_count}: fairy={name} envelope_type={type(envelope).__name__}", flush=True)
            except Exception as e:
                print(f"[DirectoryFairy] _on_heartbeat #{self._hb_echo_count}: debug error: {e}", flush=True)
        # No tracer for heartbeats (too noisy)
        self._heartbeat_handler.on_heartbeat(envelope.payload)

    def _on_consciousness(self, envelope) -> None:
        """Handle consciousness.heartbeat messages."""
        self._consciousness_handler.on_consciousness_heartbeat(envelope)

    # =========================================================================
    # ROUTING TABLE HANDLERS (Phase 2 - Postal Backbone Restoration)
    # =========================================================================

    def _on_subscription_added(self, envelope) -> None:
        """Handle fairy.subscription.added — update routing table."""
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            name = payload.get("name")
            topic = payload.get("topic")
            if name and topic:
                self.registry.add_subscription(name, topic)
        except Exception as e:
            print(f"[Directory] subscription tracking error: {e}")

    # State priority for downgrade protection — higher number = more advanced state
    _STATE_PRIORITY = {
        "sleeping": 0, "discovered": 1, "waking": 2, "booting": 3,
        "running": 4, "drowsy": 5, "dreaming": 5,
        "failed": -1, "dead": -1, "error": -1,
    }

    def _on_state_changed(self, envelope) -> None:
        """Handle fairy.state.changed — track fairy lifecycle with downgrade protection.

        FIX 2026-02-06: Postal messages can arrive OUT OF ORDER because the
        PostalCore worker pool processes them asynchronously. A delayed "booting"
        message was overwriting "running" status set by wake_fairy(), causing
        7+ fairies to appear stuck in "booting" forever.

        Now enforces state priority: "booting" can never overwrite "running".
        Only failure states (failed/dead/error) can downgrade from running.
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope
            name = payload.get("name")
            new_state = payload.get("state")
            if not name or not new_state:
                return

            # Get current state for downgrade protection
            record = self.registry.get(name)
            if record:
                current = record.status
                cur_pri = self._STATE_PRIORITY.get(current, 0)
                new_pri = self._STATE_PRIORITY.get(new_state, 0)

                # Allow: forward transitions (higher priority) or failure states
                # Block: backward transitions (e.g. "booting" overwriting "running")
                if new_pri >= 0 and new_pri < cur_pri:
                    # This is a downgrade attempt — likely a late postal message
                    return

            self.registry.set_status(name, new_state)
        except Exception:
            pass

    def _on_registry_pulse(self, pulse_data) -> None:
        """
        LIGHTWEIGHT heartbeat handler for HeartbeatRegistry direct delivery.

        FIX 2026-02-13: This is called synchronously by the HeartbeatRegistry
        during its pulse() iteration. It MUST be fast (< 10ms) because it blocks
        delivery to ALL other fairies.

        Only does:
        1. Update _last_tick/_tick_count (PRIMARY liveness signal)
        2. Self-echo to HeartbeatHandler (keeps us alive in registry)

        Does NOT do the full routing fan-out (_on_heartbeat_pulse_for_routing),
        which publishes to 82+ fairies via postal and can take 500ms+.
        Routing stays on the postal subscription (async, non-blocking).
        """
        try:
            self._tick_count += 1
            self._last_tick = time.time()

            # Self-echo: tell our own HeartbeatHandler we're alive
            beat = pulse_data.get("beat", 0) if isinstance(pulse_data, dict) else 0
            self._heartbeat_handler.on_heartbeat({
                "name": self.ACTOR_NAME,
                "plane": self.ACTOR_PLANE,
                "beat": beat,
                "ts": time.time(),
            })
        except Exception:
            pass  # Must never crash — this is the heartbeat

    def _on_heartbeat_pulse_for_routing(self, envelope) -> None:
        """
        Receive heartbeat.pulse and route to all registered fairies.

        Also echoes DirectoryFairy's OWN heartbeat to keep itself alive in the
        registry. Without this, DirectoryFairy was flagged as stale (173s silence)
        because it never told the heartbeat handler "I'm alive!"

        This is the CNS routing pattern: DirectoryFairy receives ONE heartbeat
        and fans it out to all fairies that need heartbeats, using addressed
        delivery via fairy.heartbeat.routed.<name>.

        This replaces 82 direct subscriptions with 1 subscription + N publishes.
        """
        try:
            payload = envelope.payload if hasattr(envelope, 'payload') else envelope

            # FIX 2026-02-13: Update _last_tick and _tick_count for object-level
            # liveness. HeartbeatHandler._check_citizen_liveness() reads these
            # directly from our Python object in _CITIZEN_OBJECTS.
            self._tick_count += 1
            self._last_tick = time.time()

            # ─── SELF-ECHO: Keep DirectoryFairy alive in its own registry ───
            # FIX 2026-02-06: DirectoryFairy was never echoing its own heartbeat,
            # causing it to appear stale/dead in watchdog monitoring.
            beat = payload.get("beat", 0) if isinstance(payload, dict) else 0
            self._heartbeat_handler.on_heartbeat({
                "name": self.ACTOR_NAME,
                "plane": self.ACTOR_PLANE,
                "beat": beat,
                "ts": time.time(),
            })

            # Get all fairies that need heartbeats
            needing = self.registry.get_fairies_needing_heartbeat()

            # Fan out the heartbeat to each fairy individually
            for fairy_name in needing:
                try:
                    # FIX 2026-02-06: Use ADDRESSED topic per-fairy instead of
                    # flat "fairy.heartbeat.routed" which caused O(N²) delivery.
                    # Before: 82 publishes × 82 subscribers = 6,724 deliveries/tick.
                    # After:  82 publishes × 1 subscriber each = 82 deliveries/tick.
                    self.fabric.publish(
                        f"fairy.heartbeat.routed.{fairy_name}",
                        {
                            "target": fairy_name,
                            "beat": payload.get("beat", 0),
                            "ts": payload.get("ts", time.time()),
                            "source": "directory_router",
                        },
                        priority=1,
                    )
                except Exception:
                    pass  # Don't let one failure stop all routing

        except Exception as e:
            print(f"[Directory] heartbeat routing error: {e}")

    def _on_dead_fairy(self, fairy: FairyRecord) -> None:
        """Callback when a fairy is detected as dead.

        NOTE (2026-02-09): With direct object liveness checking, this should
        rarely fire for false positives. Only fires when a fairy is TRULY gone.
        We double-check against _CITIZEN_OBJECTS before declaring death.
        """
        # Double-check: is the fairy actually dead via object check?
        obj = _CITIZEN_OBJECTS.get(fairy.name)
        if obj:
            last_tick = getattr(obj, '_last_tick', 0)
            tick_count = getattr(obj, '_tick_count', 0)
            if last_tick and (time.time() - last_tick) < self._heartbeat_handler.timeout_sec:
                # Object is alive! Don't declare death — resurrect instead.
                self.registry.set_status(fairy.name, "running")
                fairy.last_heartbeat = last_tick
                print(f"[Directory] _on_dead_fairy BLOCKED for {fairy.name}: "
                      f"object alive (tick={tick_count}, age={time.time() - last_tick:.1f}s)")
                return

        # Actually dead — remove from capability index
        self.capability_index.remove(fairy.name)

        # Publish notification
        self.fabric.publish(
            "fairy.dead",
            {"name": fairy.name, "plane": fairy.plane, "last_heartbeat": fairy.last_heartbeat},
            priority=0,  # HIGH
        )

    # =========================================================================
    # BACKGROUND TASKS
    # =========================================================================

    def _check_loop(self) -> None:
        """Background loop for periodic health checks."""
        while self._running:
            # Stop checking during shutdown - fairies dying is expected
            try:
                from P00_Autonomic.nervous_system.shared_postal_hub import is_global_shutdown
                if is_global_shutdown():
                    break
            except ImportError:
                pass

            try:
                # Check for dead fairies
                dead = self._heartbeat_handler.check_dead_fairies()
                if dead:
                    for fairy in dead:
                        self._on_dead_fairy(fairy)

            except Exception:
                pass  # Don't crash the check loop

            time.sleep(self._check_interval)

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    def register_fairy(
        self,
        name: str,
        plane: str,
        channel: str = "",
        capabilities: Optional[Set[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: str = "booting",
    ) -> Dict[str, Any]:
        """Programmatic fairy registration.

        Args:
            name: Fairy name (required)
            plane: Plane code P00-P60 (required)
            channel: Communication channel
            capabilities: Set of capability strings
            metadata: Additional metadata dict
            status: Initial status (booting, sleeping, running, etc.)
        """
        merged_metadata = dict(metadata or {})

        # ═══════════════════════════════════════════════════════════════════
        # PRESERVE fairy_instance on re-registration (2026-02-23).
        #
        # ROOT CAUSE FIX: PRE-REGISTER (Phase 4) stores fairy_instance in
        # metadata. AUTO-REGISTER (Phase 4b scan_and_register) then re-
        # registers the same fairy with source_file/class_name metadata but
        # NO fairy_instance. Since registry.register() OVERWRITES the
        # record, the fairy_instance is lost. Later, when UMF tries to
        # restart the fairy, it can't find the instance → fairy stuck.
        #
        # Fix: Merge metadata — preserve fairy_instance from existing record.
        # Also preserve the higher-trust status (e.g., don't demote "running"
        # to "sleeping" during re-registration).
        # ═══════════════════════════════════════════════════════════════════
        existing = self.registry.get(name)
        if existing:
            # Preserve fairy_instance if new metadata doesn't provide one
            if (existing.metadata.get("fairy_instance")
                    and "fairy_instance" not in merged_metadata):
                merged_metadata["fairy_instance"] = existing.metadata["fairy_instance"]

            # Merge other existing metadata (don't lose data from PRE-REGISTER)
            for k, v in existing.metadata.items():
                if k not in merged_metadata:
                    merged_metadata[k] = v

            # Don't demote status: if fairy is already running/booting,
            # don't overwrite with "sleeping" from spec registration
            if existing.status in ("running", "booting", "waking", "initializing"):
                status = existing.status

            # Merge capabilities
            if existing.capabilities and not capabilities:
                capabilities = existing.capabilities

        record = FairyRecord(
            name=name,
            plane=plane,
            channel=channel,
            capabilities=capabilities or set(),
            metadata=merged_metadata,
            status=status,
        )
        self.registry.register(record)
        if record.capabilities:
            self.capability_index.add(name, record.capabilities)
        return {"ok": True, "name": name}

    def get_fairy(self, name: str) -> Optional[FairyRecord]:
        """Get a fairy record (metadata) by name."""
        return self.registry.get(name)

    def get_fairy_instance(self, name: str) -> Optional[Any]:
        """
        Get or create a fairy instance by name - THE CENTRALIZED SINGLETON FACTORY.

        This eliminates bloated get_*() functions in every fairy file.
        The Directory handles:
        1. Lazy import from FAIRY_MANIFEST
        2. Singleton instance management
        3. Wiring to fabric
        4. Calling on_boot() for postal registration

        Args:
            name: Fairy name (must be in FAIRY_MANIFEST or already registered with instance)

        Returns:
            Fairy instance, or None if not found/failed

        Example:
            hub = directory.get_fairy_instance("WorkingMemoryHubFairy")
        """
        import importlib

        # Check cache first
        with self._instance_lock:
            if name in self._fairy_instances:
                return self._fairy_instances[name]

        # Check if instance is stored in registry metadata
        record = self.registry.get(name)
        if record and record.metadata.get("fairy_instance"):
            instance = record.metadata["fairy_instance"]
            with self._instance_lock:
                self._fairy_instances[name] = instance
            return instance

        # Look up in manifest
        manifest_entry = FAIRY_MANIFEST.get(name)
        if not manifest_entry:
            print(f"[Directory] Fairy '{name}' not in FAIRY_MANIFEST")
            return None

        module_path = manifest_entry["module"]
        class_name = manifest_entry["class"]
        plane = manifest_entry.get("plane", "P00")

        try:
            # Dynamic import
            module = importlib.import_module(module_path)
            fairy_class = getattr(module, class_name, None)
            if not fairy_class:
                print(f"[Directory] Class '{class_name}' not found in {module_path}")
                return None

            # Create instance with fabric - try fabric= first (Organ Template & FairyBase),
            # then post= (old style), then no args as last resort
            instance = None
            for kwarg in [{"fabric": self.fabric}, {"post": self.fabric}, {}]:
                try:
                    instance = fairy_class(**kwarg)
                    if kwarg:
                        print(f"[Directory] {name} created with {list(kwarg.keys())[0]}=")
                    break
                except TypeError:
                    continue

            if instance is None:
                print(f"[Directory] Failed to instantiate {name} - all kwarg patterns failed")
                return None

            # Wire to fabric
            if hasattr(instance, 'post') and instance.post is None:
                instance.post = self.fabric
            if hasattr(instance, 'fabric') and instance.fabric is None:
                instance.fabric = self.fabric

            # Call on_boot() to wire into postal/directory
            if hasattr(instance, 'on_boot'):
                try:
                    instance.on_boot()
                    print(f"[Directory] {name} booted via Organ Template")
                except Exception as e:
                    print(f"[Directory] {name} on_boot() warning: {e}")

            # Cache and register
            with self._instance_lock:
                self._fairy_instances[name] = instance

            # Update registry with instance
            if record:
                record.metadata["fairy_instance"] = instance
                record.status = "running"
            else:
                # Auto-register if not yet registered
                self.register_fairy(
                    name=name,
                    plane=plane,
                    capabilities=getattr(instance, 'capabilities', set()),
                    metadata={"fairy_instance": instance},
                    status="running",
                )

            return instance

        except Exception as e:
            print(f"[Directory] Failed to create {name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def find_by_capability(self, capability: str) -> List[str]:
        """Find fairies with a specific capability."""
        return self.capability_index.find(capability)

    def find_by_capabilities(self, capabilities: Set[str], match_all: bool = False) -> List[str]:
        """Find fairies with given capabilities."""
        if match_all:
            return self.capability_index.find_all(capabilities)
        else:
            return self.capability_index.find_any(capabilities)

    def list_fairies(self, plane: Optional[str] = None, status: Optional[str] = None) -> List[FairyRecord]:
        """List registered fairies with optional filters."""
        if plane:
            fairies = self.registry.list_by_plane(plane)
        elif status:
            fairies = self.registry.list_by_status(status)
        else:
            fairies = self.registry.list_all()
        return fairies

    def list_all(self) -> List[FairyRecord]:
        """List all registered fairies (alias for list_fairies with no filters)."""
        return self.list_fairies()

    def system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        return {
            "directory": {
                "name": self.ACTOR_NAME,
                "running": self._running,
                "uptime": time.time() - self._boot_time if self._boot_time else 0,
                "root_tracer": self._root_tracer.id if self._root_tracer else None,
            },
            "health": self.health.aggregate(self.registry),
            "registry": self.registry.stats(),
            "capabilities": self.capability_index.stats(),
        }

    def quick_status(self) -> Dict[str, Any]:
        """Get quick status (minimal computation)."""
        return {
            "running": self._running,
            "fairies": self.registry.count(),
            "health": self.health.quick_check(self.registry),
        }

    # =========================================================================
    # SLEEP CONTROL - Plug-and-play fairy management
    # =========================================================================

    def put_to_sleep(self, name: str) -> Dict[str, Any]:
        """Put a fairy to sleep."""
        success = self.registry.put_to_sleep(name)
        if success:
            self.fabric.publish(
                "fairy.sleep",
                {"name": name, "action": "sleep"},
                priority=1,
            )
        return {"ok": success, "name": name, "state": "sleeping" if success else None}

    def wake_fairy(self, name: str) -> Dict[str, Any]:
        """Wake a sleeping fairy.

        If the fairy instance is stored in metadata['fairy_instance'],
        this will also call boot() on it.
        """
        record = self.registry.get(name)
        if not record:
            return {"ok": False, "name": name, "error": "Fairy not found"}

        success = self.registry.wake_fairy(name)
        if success:
            # Publish wake event
            self.fabric.publish(
                "fairy.wake",
                {"name": name, "action": "wake"},
                priority=1,
            )

            # If fairy instance is stored in metadata, boot it
            # Note: Fairy.boot() will publish its own "fairy.booted" event
            fairy_instance = record.metadata.get("fairy_instance")
            if fairy_instance:
                # Try boot() first, then on_boot() as fallback
                boot_method = None
                if hasattr(fairy_instance, "boot"):
                    boot_method = fairy_instance.boot
                elif hasattr(fairy_instance, "on_boot"):
                    boot_method = fairy_instance.on_boot

                if boot_method:
                    try:
                        boot_result = boot_method()
                        # Treat None as success (some on_boot methods don't return anything)
                        if boot_result is None or boot_result:
                            self.registry.set_status(name, "running")
                            return {"ok": True, "name": name, "state": "running"}
                        else:
                            # Boot failed - get the actual error from the fairy
                            self.registry.set_status(name, "failed")
                            actual_error = getattr(fairy_instance, "_error", None) or "boot() returned False"
                            print(f"[Directory] {name} boot failed: {actual_error}")
                            # Publish error for ForensicScribe
                            self._publish_fairy_error(name, record.plane or "", actual_error, "boot_failed")
                            return {"ok": False, "name": name, "state": "failed", "error": actual_error}
                    except Exception as e:
                        self.registry.set_status(name, "failed")
                        print(f"[Directory] {name} boot exception: {e}")
                        # Publish error for ForensicScribe
                        self._publish_fairy_error(name, record.plane or "", str(e), "boot_exception")
                        return {"ok": False, "name": name, "state": "failed", "error": str(e)}
                else:
                    # No boot method - mark as running (passive fairy)
                    self.registry.set_status(name, "running")
                    return {"ok": True, "name": name, "state": "running"}

        # FIX 2026-02-20: If wake succeeded (status set to "waking") but there's
        # no fairy_instance, the fairy can NEVER reach "running" — it has no code
        # to boot. Reset to "sleeping" instead of leaving stuck in "waking" forever.
        # This prevents ghost entries in The Bad column of the dashboard.
        if success:
            fairy_instance = record.metadata.get("fairy_instance")
            if not fairy_instance:
                self.registry.set_status(name, "sleeping")
                return {"ok": False, "name": name, "state": "sleeping",
                        "error": "No fairy_instance — cannot boot, returning to sleep"}

        return {"ok": success, "name": name, "state": "waking" if success else None}

    def resurrect_fairy(self, name: str) -> Dict[str, Any]:
        """Resurrect a FAILED/dead fairy.

        Uses the proper state transition: FAILED -> INITIALIZING -> RUNNING
        Unlike wake_fairy() which only works for sleeping/dreaming,
        this handles fairies that crashed or timed out during boot.

        The caller (UMF) is responsible for actually calling on_boot()
        after this returns ok=True, or can pass reboot=True to auto-boot.
        """
        record = self.registry.get(name)
        if not record:
            return {"ok": False, "name": name, "error": "Fairy not found"}

        success = self.registry.resurrect_fairy(name)
        if not success:
            return {"ok": False, "name": name, "error": f"Cannot resurrect (status={record.status})"}

        # Publish resurrect event
        try:
            self.fabric.publish(
                "fairy.resurrect",
                {"name": name, "action": "resurrect", "previous_status": record.status},
                priority=1,
            )
        except Exception:
            pass

        return {"ok": True, "name": name, "state": "initializing"}

    def list_sleeping(self) -> List[FairyRecord]:
        """List all sleeping fairies."""
        return self.registry.list_sleeping()

    def list_awake(self) -> List[FairyRecord]:
        """List all awake fairies."""
        return self.registry.list_awake()

    # =========================================================================
    # MIGRATION API - Plug-and-play v1 fairy migration
    # =========================================================================

    def scan_v1_fairies(self) -> Dict[str, List[Dict[str, Any]]]:
        """Scan v1 for fairies that can be migrated."""
        if not self._migration_manager:
            return {"error": "No v1 root configured"}
        return self._migration_manager.scan()

    def register_v1_fairy(
        self,
        name: str,
        plane: str,
        channel: str = "",
        capabilities: Optional[Set[str]] = None,
        source_path: Optional[str] = None,
        start_sleeping: bool = True,
    ) -> Dict[str, Any]:
        """Register a v1 fairy (starts sleeping by default)."""
        record = self.registry.register_migrated(
            name=name,
            plane=plane,
            channel=channel,
            capabilities=capabilities or set(),
            source_path=source_path or "",
            start_sleeping=start_sleeping,
        )
        if record.capabilities:
            self.capability_index.add(name, record.capabilities)

        # Publish migration event
        self.fabric.publish(
            "fairy.migrated",
            {
                "name": name,
                "plane": plane,
                "status": record.status,
                "source_version": "v1",
            },
            priority=1,
        )

        return {"ok": True, "name": name, "status": record.status}

    def migration_status(self) -> Dict[str, Any]:
        """Get migration status."""
        if self._migration_manager:
            return self._migration_manager.migration_status()

        # Manual count if no manager
        migrated = self.registry.list_migrated()
        return {
            "total_migrated": len(migrated),
            "sleeping": len([f for f in migrated if f.is_dormant()]),
            "awake": len([f for f in migrated if f.status == "running"]),
        }

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _create_action_tracer(self, intent: str):
        """Create a tracer for a directory action."""
        return self.pool.create_tracer(
            tracer_type=TracerType.FAIRY_ACTION,
            fairy_name=self.ACTOR_NAME,
            cluster_id="cluster_directory_control",
            intent=intent,
        )


# Singleton access
_DIRECTORY_INSTANCE: Optional[DirectoryFairy] = None
_DIRECTORY_LOCK = threading.Lock()


def get_directory() -> Optional[DirectoryFairy]:
    """Get the global Directory instance."""
    return _DIRECTORY_INSTANCE


def set_directory(directory: DirectoryFairy) -> None:
    """Set the global Directory instance."""
    global _DIRECTORY_INSTANCE
    with _DIRECTORY_LOCK:
        _DIRECTORY_INSTANCE = directory
