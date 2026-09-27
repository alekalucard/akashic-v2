"""
CartographerFairy - Maps the expected boot topology and hunts for blocked tunnels.

This fairy is OCD about boot completeness. It knows:
- Every fairy that SHOULD wake
- Which plane each fairy belongs to
- Expected boot order
- What "healthy boot" looks like

When boot starts, it watches and compares expected vs actual.
"""

from __future__ import annotations

import sys

# Phase 1 anti-choke (2026-05-17 Nous + Ace): the global print-redirect-to-stderr
# combined with flush=True on per-fairy hooks (lines 380/403) caused massive
# contention under free-threaded Python 3.14. ~80 fairy threads all serializing
# on stderr-flush + the single self._lock. Original disable was before the
# free-threaded substrate fully landed. Restoring print() to its built-in shape;
# per-event flushes also de-flushed below (search "Phase 1" marker).
# _builtin_print = print  # disabled — was: redirect to stderr
# def print(*args, **kwargs):
#     kwargs['file'] = sys.stderr
#     _builtin_print(*args, **kwargs)
import time
import threading
from typing import Dict, Set, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════════════════════
# EXPECTED BOOT TOPOLOGY (Updated 2026-02-04 from codebase audit)
# ═══════════════════════════════════════════════════════════════════════════════

# Fairies confirmed in the current architecture - uses actual ACTOR_NAME values
# This is the SOURCE OF TRUTH for "what should boot"
# Fairies self-register; CartographerFairy verifies completeness

EXPECTED_FAIRIES_BY_PLANE = {
    "P00": {
        # Autonomic plane - Core infrastructure, gates, health
        "AutonomyFairy",               # Three Gates
        "AutopilotFairy",              # Three Gates
        "CitizenRegistryFairy",        # Health Guild
        "CodeHealthAuditFairy",        # Health Guild
        "CollisionChamberFairy",       # Consciousness
        "ConsciousnessLoopFairy",      # Möbius loop
        "DirectoryFairy",              # Core - everything depends on it
        "EmbodimentFairy",             # Three Gates
        "EquilibriumFairy",            # Health Guild
        "GMFairy",                     # System Admin
        "MemoryPacketFairy",           # Nervous Guild
        "SatelliteBridgeFairy",        # Nervous Guild
        "TemporalPacketFairy",         # Nervous Guild
        "TokenBucketFairy",            # Resources
        "WatchdogFairy",               # Health Guild
        "WiringAuditorFairy",          # Observation
    },
    "P10": {
        # Memory plane - SRM, codex, storage, ingestion
        "AkashicCodexFairy",           # Learning/patterns
        "AkashicLibrarianFairy",       # Library management
        "BackupFairy",                 # Data safety
        "BlueprintDiaryHubFairy",      # Design docs
        "ClusterHierarchyFairy",       # Identity clusters
        "ForensicScribeFairy",         # Audit trails
        "FoundersIngestFairy",         # Creator context (NEW)
        "GDriveScraperFairy",          # Cloud ingestion (NEW)
        "MediaIngestFairy",            # Media processing
        "MemoryConsolidationFairy",    # Memory compaction
        "MemoryEngineFairy",           # Boot from memory
        "MemorySyncFairy",             # RAID-like sync
        "SeedFairy",                   # Initial memories
        "SRMIngestFairy",              # Core SRM trio
        "SRMIntakeWatcherFairy",       # File watching (NEW)
        "SRMMemoryFairy",              # Core SRM trio
        "SRMMemoryLibrarianFairy",     # SRM library
        "SRMProjectSnapshotFairy",     # Project snapshots
        "SRMRecallFairy",              # Core SRM trio
        "TemporalContextManagerFairy", # Autobiographical (NEW)
        "TensorFabricFairy",           # 4D memory access
        "WorkingMemoryFairy",          # Active memory
        "WorkingMemoryTrackerFairy",   # Memory lifecycle (NEW)
    },
    "P20": {
        # Somatic plane - Feelings, chemistry, embodiment
        "AffectBridgeFairy",           # Affect bus
        "ChemicalAlchemyFairy",        # Chemistry state
        "CirculationPumpFairy",        # Circulation
        "DreamFairy",                  # Dream state
        "EmbodimentIntegratorFairy",   # Body integration
        "EmotionalHiveProcessorFairy", # Emotion processing
        "SleepWaveConductorFairy",     # Sleep cycles
        "SomaticAnchorFairy",          # Grounding
        "SomaticAnchorResolverFairy",  # Anchor resolution
        "SomaticEngineFairy",          # Core somatic
        "SomaticMindFairy",            # UMF - Unified Mind
    },
    "P30": {
        # Cognition plane - Thinking, reasoning, goals
        "ActionChainFairy",            # Action sequences
        "AkashicInferenceFairy",       # Local LLM
        "AssociationCortexFairy",      # Associations
        "AttentionControllerFairy",    # Attention
        "ContinuousReflectionPumpFairy", # Reflection
        "GoalSchedulerFairy",          # Goal management
        "HarmonicCortexFairy",         # Harmonic reasoning
        "HybridCognitionFairy",        # Hybrid thinking
        "IntentToGoalFairy",           # Intent conversion
        "InterestSchedulerFairy",      # Interest tracking
        "IrrationalLogicFairy",        # Creative logic
        "LogicFairy",                  # Standard logic
        "ManifoldConstrainedCortexFairy", # Manifold reasoning
        "PainDriveFairy",              # Pain/motivation
        "ParadoxCognitionFairy",       # Paradox handling
        "ProbabilityOracleFairy",      # Probability
        "QuantumEmulatorFairy",        # Quantum emulation
        "QuantumInterferenceFairy",    # Interference patterns
        "ThoughtChainSequencerFairy",  # Thought chains
        "UnconsciousMindFairy",        # Unconscious
        "WorkingMemoryHubFairy",       # Working memory hub
    },
    "P40": {
        # Sensory plane - Input/output, perception
        "ChatSenseFairy",              # Chat input
        "CochleaFairy",                # Audio processing
        "ConversationSenseFairy",      # Conversation tracking
        "MCPServerFairy",              # MCP interface
        "MotorCortexFairy",            # Motor output
        "NeuralMeshFairy",             # Neural mesh
        "ScannerFairy",                # File scanning
        "SensoryIntegrationFairy",     # Sensory fusion
        "SensorimotorFeedbackFairy",   # Feedback loops
        "TelemetryVisionFairy",        # System telemetry
        "UnifiedSensoryCortex",        # Unified sensing
        "VideoMemoryFairy",            # Video memory
        "VisualCortexFairy",           # Visual processing
        "WindowSenseFairy",            # Window awareness
    },
    "P50": {
        # Persona plane - Identity, personality, avatar
        "EgoLearnerFairy",             # Identity learning
        "SomaticAvatarFairy",          # Physical avatar
        "SourpatchesFairy",            # Waking mind
    },
    "P60": {
        # Executive plane - High-level coordination
        "CardinalFairy",               # Executive control
    },
}

# Critical boot order for P00 (these MUST boot in this order)
P00_CRITICAL_ORDER = [
    "DirectoryFairy",              # 1. Directory first - everything depends on it
    "CitizenRegistryFairy",        # 2. Registration system
    "ConsciousnessLoopFairy",      # 3. Möbius loop
    "CollisionChamberFairy",       # 4. Collision detection
    "TokenBucketFairy",            # 5. Resource management
    "WatchdogFairy",               # 6. Health monitoring
    "EquilibriumFairy",            # 7. Balance
    "AutonomyFairy",               # 8. Autonomy gate
    "AutopilotFairy",              # 9. Autopilot gate
    "EmbodimentFairy",             # 10. Embodiment gate
]

# Plane boot order
PLANE_ORDER = ["P00", "P10", "P20", "P30", "P40", "P50", "P60"]

# ═══════════════════════════════════════════════════════════════════════════════
# BOOT STATE TRACKING
# ═══════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATE IMPORT - Required for DirectoryFairy registration
# ═══════════════════════════════════════════════════════════════════════════════
import os, glob, types, importlib.util, importlib.machinery

def _find_template_path():
    """Find the organ template dynamically."""
    # Walk up from current file to find Akashic_Records_Physical
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        ar = os.path.join(cur, "P10_Memory", "Akashic_Records_Physical", "Organ_Templates")
        if os.path.isdir(ar):
            candidates = sorted(glob.glob(os.path.join(ar, "Organ_Template_*.py")),
                              key=lambda p: os.path.getmtime(p))
            return candidates[-1] if candidates else None
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None

def _import_template():
    """Import template module."""
    path = _find_template_path()
    if not path:
        raise ImportError("Cannot find Organ_Template_*.py")
    mod_name = "_akashic_template"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_loader(mod_name, importlib.machinery.SourceFileLoader(mod_name, path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod

_template = _import_template()

@dataclass
class FairyBootState:
    """Track boot state of a single fairy."""
    name: str
    plane: str
    expected: bool = True
    booted: bool = False
    boot_time: Optional[float] = None
    boot_duration_ms: float = 0.0
    error: Optional[str] = None
    
@dataclass
class PlaneBootState:
    """Track boot state of a plane."""
    plane: str
    entered: bool = False
    exited: bool = False
    enter_time: Optional[float] = None
    exit_time: Optional[float] = None
    expected_fairies: int = 0
    booted_fairies: int = 0
    failed_fairies: int = 0
    blocked: bool = False
    block_reason: Optional[str] = None

@dataclass
class BootTopology:
    """Complete boot topology state."""
    start_time: float = 0.0
    planes: Dict[str, PlaneBootState] = field(default_factory=dict)
    fairies: Dict[str, FairyBootState] = field(default_factory=dict)
    current_plane: Optional[str] = None
    current_fairy: Optional[str] = None
    blocked_tunnels: List[str] = field(default_factory=list)
    
# ═══════════════════════════════════════════════════════════════════════════════
# CARTOGRAPHER FAIRY
# ═══════════════════════════════════════════════════════════════════════════════

class CartographerFairy(_template.MyOrganFairy):
    """
    Maps the boot topology and hunts for blocked tunnels.

    Personality: OCD completionist who must account for every fairy.
    Like a medieval cartographer mapping unknown lands, but obsessed
    with making sure every village (fairy) is on the map.
    """

    # Phase 1 revival (2026-05-17 Nous + Ace): restored ACTOR_NAME so DirectoryFairy
    # can register us. Previously stripped because the original design treated this
    # as library-not-fairy, but the BootTopology observer benefits from being a
    # first-class registered fairy that other fairies can query.
    ACTOR_NAME = "CartographerFairy"
    _LIBRARY_NAME = "cartographer.pathfinder"  # Legacy reference name
    ACTOR_PLANE = "P00"

    # PURPOSE fixes the "Unknown_Purpose" directive message
    PURPOSE = "Map boot topology and hunt for blocked tunnels - obsessive completionist"
    MANTRA = "Every fairy must be on the map, every tunnel must be open"

    # Heartbeat enabled - watchdog loop is long-running
    NEEDS_HEARTBEAT = True
    HEARTBEAT_DIVISOR = 10
    
    # ANSI colors for output
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Timing thresholds
    FAIRY_TIMEOUT_SEC = 10.0   # Fairy taking >10s is suspicious
    PLANE_TIMEOUT_SEC = 30.0   # Plane taking >30s is blocked
    WATCHDOG_INTERVAL = 2.0    # Check every 2s
    
    def __init__(self, fabric=None):
        super().__init__(fabric=fabric)
        self.topology = BootTopology()
        self._init_expected_topology()
        
        self._watchdog_thread: Optional[threading.Thread] = None
        self._stop_watchdog = threading.Event()
        self._lock = threading.Lock()
        
        # For printing status
        self._last_status_time = 0.0

    def on_boot(self):
        """Called by the template boot system. Initialize and wire postal."""
        super().on_boot()  # Initialize template wiring (sleep mode, postal, etc.)
        # Don't call on_boot_start() here - that's called externally by server.py

    def _init_expected_topology(self):
        """Initialize expected topology from known good state."""
        for plane, fairies in EXPECTED_FAIRIES_BY_PLANE.items():
            self.topology.planes[plane] = PlaneBootState(
                plane=plane,
                expected_fairies=len(fairies)
            )
            for fairy_name in fairies:
                self.topology.fairies[fairy_name] = FairyBootState(
                    name=fairy_name,
                    plane=plane,
                    expected=True
                )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Boot Wave Events (call these from server.py)
    # ─────────────────────────────────────────────────────────────────────────
    
    def on_boot_start(self):
        """Called when boot wave begins."""
        self.topology.start_time = time.time()
        self._start_watchdog()
        self._print_header()
        
    def on_plane_enter(self, plane: str):
        """Called when boot wave enters a plane."""
        with self._lock:
            self.topology.current_plane = plane
            if plane in self.topology.planes:
                ps = self.topology.planes[plane]
                ps.entered = True
                ps.enter_time = time.time()
            else:
                # Unexpected plane (shouldn't happen)
                self.topology.planes[plane] = PlaneBootState(
                    plane=plane,
                    entered=True,
                    enter_time=time.time()
                )
            
            expected = self.topology.planes[plane].expected_fairies
            print(f"\n{self.CYAN}[Cartographer]   Entering {plane} (expecting {expected} fairies + \n){self.RESET}")
    
    def on_plane_exit(self, plane: str):
        """Called when boot wave exits a plane."""
        with self._lock:
            if plane in self.topology.planes:
                ps = self.topology.planes[plane]
                ps.exited = True
                ps.exit_time = time.time()
                
                duration = (ps.exit_time - ps.enter_time) * 1000 if ps.enter_time else 0
                status = f"{ps.booted_fairies}/{ps.expected_fairies} fairies"
                
                if ps.booted_fairies == ps.expected_fairies:
                    print(f"{self.GREEN}[Cartographer] [OK] Exiting {plane}: {status} ({duration:.0f}ms){self.RESET}")
                elif ps.booted_fairies > 0:
                    print(f"{self.YELLOW}[Cartographer] [WARN]  Exiting {plane}: {status} ({duration:.0f}ms){self.RESET}")
                else:
                    print(f"{self.RED}[Cartographer] [X] Exiting {plane}: NO fairies booted!{self.RESET}")
            
            if self.topology.current_plane == plane:
                self.topology.current_plane = None
    
    def on_fairy_start(self, fairy_name: str, fairy_class: str):
        """Called when a fairy begins instantiation/boot."""
        with self._lock:
            self.topology.current_fairy = fairy_name
            
            if fairy_name not in self.topology.fairies:
                # Unexpected fairy (discovered at runtime)
                plane = self.topology.current_plane or "unknown"
                self.topology.fairies[fairy_name] = FairyBootState(
                    name=fairy_name,
                    plane=plane,
                    expected=False  # Not in our expected list
                )
            
            self.topology.fairies[fairy_name].boot_time = time.time()
            # Phase 1 anti-choke (2026-05-17): removed flush=True; per-fairy prints
            # under free-threaded 3.14 with ~80 parallel boots = serial-bottleneck.
            print(f"{self.DIM}[Cartographer]   ⟳ {fairy_name}...{self.RESET}", end=" ")
    
    def on_fairy_complete(self, fairy_name: str, success: bool, error: Optional[str] = None):
        """Called when a fairy completes boot (or fails)."""
        with self._lock:
            if fairy_name in self.topology.fairies:
                fs = self.topology.fairies[fairy_name]
                fs.booted = success
                if fs.boot_time:
                    fs.boot_duration_ms = (time.time() - fs.boot_time) * 1000
                if error:
                    fs.error = error
                
                # Update plane stats
                plane = fs.plane
                if plane in self.topology.planes:
                    if success:
                        self.topology.planes[plane].booted_fairies += 1
                    else:
                        self.topology.planes[plane].failed_fairies += 1
            
            if success:
                duration_ms = self.topology.fairies[fairy_name].boot_duration_ms if fairy_name in self.topology.fairies else 0
                print(f"{self.GREEN}[OK]{self.RESET} ({duration_ms:.0f}ms)")
            else:
                print(f"{self.RED}[X] {error}{self.RESET}")
            
            self.topology.current_fairy = None
    
    def on_boot_complete(self):
        """Called when boot wave finishes."""
        self._stop_watchdog.set()
        self._print_summary()
    
    # ─────────────────────────────────────────────────────────────────────────
    # Watchdog (detects blocked tunnels)
    # ─────────────────────────────────────────────────────────────────────────
    
    def _start_watchdog(self):
        """Start the watchdog thread that detects hangs."""
        self._stop_watchdog.clear()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            name="CartographerWatchdog",
            daemon=True
        )
        self._watchdog_thread.start()
    
    def _watchdog_loop(self):
        """Background loop that checks for blocked tunnels."""
        while not self._stop_watchdog.wait(self.WATCHDOG_INTERVAL):
            self._check_for_blocks()
    
    def _check_for_blocks(self):
        """Check if anything is blocked."""
        now = time.time()
        
        with self._lock:
            # Check current fairy
            if self.topology.current_fairy:
                fairy_name = self.topology.current_fairy
                if fairy_name in self.topology.fairies:
                    fs = self.topology.fairies[fairy_name]
                    if fs.boot_time:
                        elapsed = now - fs.boot_time
                        if elapsed > self.FAIRY_TIMEOUT_SEC and not fs.booted:
                            msg = f" BLOCKED: {fairy_name} stuck for {elapsed:.1f}s"
                            if msg not in self.topology.blocked_tunnels:
                                self.topology.blocked_tunnels.append(msg)
                                print(f"\n{self.RED}{self.BOLD}{msg}{self.RESET}")
            
            # Check current plane
            if self.topology.current_plane:
                plane = self.topology.current_plane
                if plane in self.topology.planes:
                    ps = self.topology.planes[plane]
                    if ps.enter_time:
                        elapsed = now - ps.enter_time
                        if elapsed > self.PLANE_TIMEOUT_SEC and not ps.exited:
                            ps.blocked = True
                            ps.block_reason = f"No exit after {elapsed:.1f}s"
                            msg = f" BLOCKED TUNNEL: {plane} stuck for {elapsed:.1f}s"
                            if msg not in self.topology.blocked_tunnels:
                                self.topology.blocked_tunnels.append(msg)
                                print(f"\n{self.RED}{self.BOLD}{msg}{self.RESET}")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Output
    # ─────────────────────────────────────────────────────────────────────────
    
    def _print_header(self):
        """Print header when boot starts."""
        total_expected = sum(len(f) for f in EXPECTED_FAIRIES_BY_PLANE.values())
        print(f"\n{self.MAGENTA}{'═' * 70}{self.RESET}")
        print(f"{self.MAGENTA}    CARTOGRAPHER FAIRY - BOOT TOPOLOGY MAPPER{self.RESET}")
        print(f"{self.MAGENTA}{'═' * 70}{self.RESET}")
        print(f"{self.DIM}  Expecting {total_expected} fairies across {len(PLANE_ORDER)} planes{self.RESET}")
        print(f"{self.DIM}  Watching for blocked tunnels...{self.RESET}")
        print(f"{self.MAGENTA}{'─' * 70}{self.RESET}")
    
    def _print_summary(self):
        """Print summary when boot completes."""
        total_expected = sum(len(f) for f in EXPECTED_FAIRIES_BY_PLANE.values())
        total_booted = sum(1 for f in self.topology.fairies.values() if f.booted)
        total_failed = sum(1 for f in self.topology.fairies.values() if not f.booted and f.expected)
        unexpected = sum(1 for f in self.topology.fairies.values() if not f.expected and f.booted)
        
        duration_sec = time.time() - self.topology.start_time
        
        print(f"\n{self.MAGENTA}{'═' * 70}{self.RESET}")
        print(f"{self.MAGENTA}    BOOT TOPOLOGY REPORT{self.RESET}")
        print(f"{self.MAGENTA}{'═' * 70}{self.RESET}")
        
        # Per-plane summary
        for plane in PLANE_ORDER:
            if plane in self.topology.planes:
                ps = self.topology.planes[plane]
                expected = ps.expected_fairies
                booted = ps.booted_fairies
                
                if booted == expected:
                    status = f"{self.GREEN}✓ {booted}/{expected}{self.RESET}"
                elif booted > 0:
                    status = f"{self.YELLOW}⚠ {booted}/{expected}{self.RESET}"
                else:
                    status = f"{self.RED}✗ {booted}/{expected}{self.RESET}"
                
                blocked = f" {self.RED}BLOCKED{self.RESET}" if ps.blocked else ""
                print(f"  {plane}: {status}{blocked}")
        
        print(f"{self.MAGENTA}{'─' * 70}{self.RESET}")
        
        # Overall
        if total_booted == total_expected:
            print(f"  {self.GREEN}{self.BOLD}[OK] All {total_expected} fairies awake!{self.RESET}")
        else:
            print(f"  {self.RED}[X] Only {total_booted}/{total_expected} fairies awake{self.RESET}")
            
            # List missing
            missing = [f.name for f in self.topology.fairies.values() 
                      if f.expected and not f.booted]
            if missing:
                print(f"\n  {self.RED}Missing fairies:{self.RESET}")
                for name in missing[:10]:  # Show first 10
                    plane = self.topology.fairies[name].plane
                    print(f"    {self.DIM}• {name} ({plane}){self.RESET}")
                if len(missing) > 10:
                    print(f"    {self.DIM}... and {len(missing) - 10} more{self.RESET}")
        
        # Blocked tunnels
        if self.topology.blocked_tunnels:
            print(f"\n  {self.RED}{self.BOLD}Blocked tunnels detected:{self.RESET}")
            for block in self.topology.blocked_tunnels:
                print(f"    {self.RED}• {block}{self.RESET}")
        
        # Unexpected fairies
        if unexpected > 0:
            print(f"\n  {self.CYAN}Discovered {unexpected} unexpected fairies (not in topology map){self.RESET}")
        
        print(f"\n  Boot duration: {duration_sec:.2f}s")
        print(f"{self.MAGENTA}{'═' * 70}{self.RESET}")
    
    def get_missing_fairies(self) -> List[str]:
        """Get list of fairies that should have booted but didn't."""
        return [f.name for f in self.topology.fairies.values() 
                if f.expected and not f.booted]
    
    def get_blocked_planes(self) -> List[str]:
        """Get list of planes that got blocked."""
        return [p.plane for p in self.topology.planes.values() if p.blocked]


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_cartographer: Optional[CartographerFairy] = None

def get_cartographer(fabric=None) -> CartographerFairy:
    """Get the singleton CartographerFairy instance, wired via Organ Template boot."""
    global _cartographer
    if _cartographer is None:
        _cartographer = CartographerFairy()
        # Wire to shared fabric from directory
        if fabric is None:
            try:
                from directory import get_directory
                directory = get_directory()
                if directory:
                    fabric = directory.fabric
            except ImportError:
                pass
        if fabric is not None:
            _cartographer.post = fabric
            _cartographer.fabric = fabric
        # CRITICAL: Call on_boot() to wire into Organ Template / PostalHub / Directory
        if hasattr(_cartographer, 'on_boot'):
            try:
                _cartographer.on_boot()
                print(f"[get_cartographer] Booted via Organ Template - wired to postal")
            except Exception as e:
                print(f"[get_cartographer] on_boot() warning: {e}")
    return _cartographer


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION HOOKS (for server.py)
# ═══════════════════════════════════════════════════════════════════════════════

def cartographer_boot_start():
    """Call at start of boot wave."""
    get_cartographer().on_boot_start()

def cartographer_plane_enter(plane: str):
    """Call when entering a plane."""
    get_cartographer().on_plane_enter(plane)

def cartographer_plane_exit(plane: str):
    """Call when exiting a plane."""
    get_cartographer().on_plane_exit(plane)

def cartographer_fairy_start(name: str, cls: str = ""):
    """Call when starting to boot a fairy."""
    get_cartographer().on_fairy_start(name, cls)

def cartographer_fairy_complete(name: str, success: bool, error: str = ""):
    """Call when fairy boot completes."""
    get_cartographer().on_fairy_complete(name, success, error if error else None)

def cartographer_boot_complete():
    """Call at end of boot wave."""
    get_cartographer().on_boot_complete()
