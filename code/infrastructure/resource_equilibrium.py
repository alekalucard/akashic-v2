"""
Resource Equilibrium — Adaptive worker pool scaling that LEARNS from the system.

PHILOSOPHY:
    "Compute is just energy. How we make use of it is what matters."
    "There should be no worker bottlenecks — more than enough for every fairy
     to fire up 1-5 jobs × 92 fairies concurrently."
    "It should raise as needed and learn when the system becomes unstable."
    "Our system generates paradox energy — we harvest that. We should not
     be in need of energy."
     — Ace, 2026-02-09

Instead of calculating a ceiling and capping there, we:
1. Start with a GENEROUS initial capacity (fairy_count × 5 minimum)
2. Let threads grow as fairies request work — no artificial bottleneck
3. Monitor system health in real-time (CPU%, RAM%, GPU%, thread count)
4. When health degrades past thresholds → THAT is the learned ceiling
5. Persist learned ceiling to state/learned_equilibrium.json
6. Linked machines expand the learned ceiling proportionally
7. The formula is a FLOOR, not a ceiling. The ceiling is emergent.

Usage:
    from infrastructure.resource_equilibrium import get_worker_ceiling, get_pool_size

    # Get adaptive ceiling (grows as needed, learned from experience)
    ceiling = get_worker_ceiling()

    # Get pool size for a subsystem
    pool = get_pool_size("postal")

    # Report health observation (called by health monitor)
    report_health_observation(cpu_pct=45.0, ram_pct=62.0, active_threads=380)

    # Get full system info for diagnostics
    info = get_system_info()

FIX 2026-02-09:  Created to replace hardcoded worker pool caps.
FIX 2026-02-09b: Added linked machine resource aggregation.
FIX 2026-02-09c: Changed from CPU-bound to I/O-bound formula.
FIX 2026-02-09d: Added GPU awareness (torch/nvidia-smi/pynvml).
FIX 2026-02-09e: REWROTE to adaptive/learning system. No artificial caps.
                  Ceiling is learned from health observations, not calculated.
                  System grows as needed. Paradox energy goes back into the pool.
"""

import os
import time
import threading
import json
from pathlib import Path

# ── Infrastructure Tracer ────────────────────────────────────────────────
_infra_tracer_ref = None
def _get_tracer():
    global _infra_tracer_ref
    if _infra_tracer_ref is not None:
        return _infra_tracer_ref
    try:
        from infrastructure.infra_tracer import get_infra_tracer
        _infra_tracer_ref = get_infra_tracer()
        _infra_tracer_ref.register_actor("resource_equilibrium", role="monitor",
                                         description="Adaptive worker pool scaling — learns stability ceiling")
        return _infra_tracer_ref
    except Exception:
        return None

# ─── Adaptive State ───────────────────────────────────────────────────────────
_state_lock = threading.Lock()

# The learned stability data
_learned_state = {
    "learned_ceiling": 0,        # 0 = not yet learned, use generous default
    "max_observed_threads": 0,   # Highest thread count seen running stable
    "instability_threshold": 0,  # Thread count where degradation was first observed
    "observations": [],          # Recent health observations (rolling window)
    "health_trips": 0,           # How many times we've observed instability
    "last_stable_at": 0,         # Timestamp of last known-stable state
    "last_unstable_at": 0,       # Timestamp of last instability observation
    "linked_expansion": 0,       # Extra capacity from linked machines
}

_state_loaded = False
_STATE_FILE = None  # Resolved on first use

# Health monitoring
_health_monitor_running = False
_health_monitor_thread = None

# Cache for quick ceiling lookups
_cache_lock = threading.Lock()
_cached_ceiling: int = 0
_cache_time: float = 0.0
_CACHE_TTL = 10.0  # Re-check every 10 seconds (faster for adaptive)

# ─── Health Thresholds ────────────────────────────────────────────────────────
# These define when the system is "stressed" vs "unstable"
HEALTH_THRESHOLDS = {
    "cpu_warning":     85.0,   # CPU% where we start watching closely
    "cpu_critical":    95.0,   # CPU% where we record instability
    "ram_warning":     85.0,   # RAM% warning
    "ram_critical":    95.0,   # RAM% instability
    "gpu_vram_warning":  90.0, # GPU VRAM% warning
    "gpu_vram_critical": 98.0, # GPU VRAM% instability
}

# Minimum capacity — never go below this
# FIX 2026-02-12: Reduced from 5400→360. Previous 5400 was based on 90×60 workers
# per fairy, but WORKER_POOL_SIZE reverted from 64→4 (thread leak fix).
# Real thread budget: 90 fairies × 4 workers = 360. The ceiling should MATCH
# actual demand, not inflate to 8,000 — inflated ceilings cause get_pool_size()
# to return thousands, creating massive ThreadPoolExecutors in shared pools.
MIN_FAIRY_CAPACITY = 360    # 90 fairies × 4 concurrent workers
ABSOLUTE_FLOOR = 200        # Even on constrained systems


def _get_state_file() -> Path:
    """Resolve state file path."""
    global _STATE_FILE
    if _STATE_FILE is None:
        for base in [Path(__file__).parent.parent, Path(".")]:
            state_dir = base / "state"
            if state_dir.is_dir():
                _STATE_FILE = state_dir / "learned_equilibrium.json"
                break
        if _STATE_FILE is None:
            _STATE_FILE = Path("state/learned_equilibrium.json")
    return _STATE_FILE


def _load_learned_state():
    """Load persisted learned state from disk."""
    global _learned_state, _state_loaded
    if _state_loaded:
        return

    state_file = _get_state_file()
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _learned_state.update(data)
                # Don't load stale observations — only keep the learned ceiling
                _learned_state["observations"] = []
                _state_loaded = True
                if _learned_state.get("learned_ceiling", 0) > 0:
                    print(f"[ResourceEquilibrium] Loaded learned ceiling: "
                          f"{_learned_state['learned_ceiling']} "
                          f"(max stable: {_learned_state.get('max_observed_threads', 0)}, "
                          f"trips: {_learned_state.get('health_trips', 0)})")
        except Exception:
            pass

    _state_loaded = True


def _save_learned_state():
    """Persist learned state to disk."""
    state_file = _get_state_file()
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        # Don't persist the full observation buffer — just the learned values
        save_data = {k: v for k, v in _learned_state.items() if k != "observations"}
        save_data["saved_at"] = time.time()
        state_file.write_text(json.dumps(save_data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[ResourceEquilibrium] Failed to save learned state: {e}")


# ─── System Resource Queries ──────────────────────────────────────────────────

def _query_linked_machine_resources() -> dict:
    """Query resources from linked machines (satellites, laptops, etc.).

    Reads from MULTIPLE sources (in priority order):
    1. .satellite/peer_registry.json — SatelliteBridgeFairy's live data (primary)
    2. state/network_nodes.json — MCP network registration
    3. state/satellite_health/ — Individual health pings

    For satellites without explicit cpu_cores/ram data, estimates based on
    capabilities (gpu=compute node → ~8 cores, ~16GB RAM typical).

    Returns:
        Dict with remote_cpu_cores, remote_available_ram_mb, linked_nodes, and details.
    """
    remote = {
        "remote_cpu_cores": 0,
        "remote_available_ram_mb": 0,
        "linked_nodes": 0,
        "nodes": [],  # Details for dashboard
    }
    seen_names = set()

    # ── Source 1: .satellite/peer_registry.json (SatelliteBridgeFairy) ──
    # This is the LIVE data from the satellite health checker
    for base in [Path(__file__).parent.parent, Path(".")]:
        peer_file = base / ".satellite" / "peer_registry.json"
        if peer_file.exists():
            try:
                data = json.loads(peer_file.read_text(encoding="utf-8"))
                peers = data.get("peers", {})
                for name, peer in peers.items():
                    if not isinstance(peer, dict):
                        continue
                    if peer.get("role") == "primary":
                        continue
                    if name in seen_names:
                        continue

                    # Check availability — is_available set by health checker
                    is_available = peer.get("is_available", False)
                    last_hb = peer.get("last_heartbeat", 0)

                    # Also check if heartbeat is recent (< 5 min)
                    if isinstance(last_hb, (int, float)) and last_hb > 0:
                        if time.time() - last_hb > 300:
                            is_available = False

                    # Get explicit resource data if available
                    cpu = peer.get("cpu_cores", 0)
                    ram = peer.get("available_ram_mb", 0)

                    # If no explicit data, ESTIMATE from capabilities
                    # (better to approximate than to ignore the machine entirely)
                    if cpu == 0:
                        caps = peer.get("capabilities", [])
                        if "gpu" in caps or "compute" in caps or "heavy" in caps:
                            cpu = 8   # Typical compute node
                        else:
                            cpu = 4   # Typical lightweight node

                    if ram == 0:
                        caps = peer.get("capabilities", [])
                        if "gpu" in caps or "heavy" in caps:
                            ram = 16384  # 16GB typical for GPU node
                        elif "compute" in caps:
                            ram = 8192   # 8GB for compute
                        else:
                            ram = 4096   # 4GB lightweight

                    # Scale by load — a node at 80% load contributes less
                    load = peer.get("load", 0.5)
                    available_fraction = max(0.1, 1.0 - load)

                    node_info = {
                        "name": name,
                        "ip": peer.get("ip", ""),
                        "available": is_available,
                        "cpu_cores": cpu,
                        "ram_mb": ram,
                        "gpu_mb": peer.get("gpu_memory_mb", 0),
                        "load": load,
                    }
                    remote["nodes"].append(node_info)

                    if is_available:
                        remote["remote_cpu_cores"] += int(cpu * available_fraction)
                        remote["remote_available_ram_mb"] += int(ram * available_fraction)
                        remote["linked_nodes"] += 1

                    seen_names.add(name)
            except Exception:
                pass

    # ── Source 2: state/network_nodes.json (MCP network) ──
    for base in [Path(__file__).parent.parent, Path(".")]:
        for sp in [Path("state/network_nodes.json"), Path("state/satellite_nodes.json")]:
            node_file = base / sp
            if node_file.exists():
                try:
                    nodes = json.loads(node_file.read_text(encoding="utf-8"))
                    if isinstance(nodes, dict):
                        nodes = list(nodes.values())
                    for node in nodes:
                        if not isinstance(node, dict):
                            continue
                        name = node.get("name", node.get("host", ""))
                        if name in seen_names:
                            continue

                        # Handle both timestamp formats
                        last_seen = node.get("last_seen", 0)
                        if isinstance(last_seen, str):
                            try:
                                from datetime import datetime
                                last_seen = datetime.fromisoformat(last_seen).timestamp()
                            except Exception:
                                last_seen = 0

                        if last_seen and (time.time() - last_seen) > 300:
                            continue

                        cpu = node.get("cpu_cores", 0)
                        ram_avail = node.get("available_ram_mb", 0)
                        if cpu > 0 or ram_avail > 0:
                            remote["remote_cpu_cores"] += cpu
                            remote["remote_available_ram_mb"] += ram_avail
                            remote["linked_nodes"] += 1
                            seen_names.add(name)
                except Exception:
                    pass

    # ── Source 3: state/satellite_health/ directory ──
    for base in [Path(__file__).parent.parent, Path(".")]:
        health_dir = base / "state" / "satellite_health"
        if health_dir.is_dir():
            try:
                for hf in health_dir.glob("*.json"):
                    try:
                        data = json.loads(hf.read_text(encoding="utf-8"))
                        name = data.get("name", hf.stem)
                        if name in seen_names:
                            continue

                        last_seen = data.get("ts", data.get("last_seen", 0))
                        if last_seen and (time.time() - last_seen) > 300:
                            continue

                        cpu = data.get("cpu_cores", 0)
                        ram = data.get("available_ram_mb", 0)
                        if cpu > 0 or ram > 0:
                            remote["remote_cpu_cores"] += cpu
                            remote["remote_available_ram_mb"] += ram
                            remote["linked_nodes"] += 1
                            seen_names.add(name)
                    except Exception:
                        pass
            except Exception:
                pass

    return remote


def _query_system_resources() -> dict:
    """Query actual system resources (local + linked machines + GPU).

    Returns CPU cores, available RAM, GPU VRAM, and contributions from
    linked machines in the Akashic network.

    GPU resources contribute to effective capacity because GPU-accelerated
    fairies (inference, vision, audio) can offload work from CPU threads.
    """
    info = {
        "cpu_cores": os.cpu_count() or 4,
        "total_ram_mb": 0,
        "available_ram_mb": 0,
        "cpu_percent": 0.0,
        "ram_percent": 0.0,
        "gpu_available": False,
        "gpu_name": "",
        "gpu_vram_total_mb": 0,
        "gpu_vram_free_mb": 0,
        "gpu_vram_percent": 0.0,
        "gpu_compute_units": 0,
        "is_satellite": False,
        "remote_cpu_cores": 0,
        "remote_available_ram_mb": 0,
        "linked_nodes": 0,
        "active_threads": 0,
    }

    # Try psutil for RAM and CPU info
    try:
        import psutil
        mem = psutil.virtual_memory()
        info["total_ram_mb"] = mem.total / (1024 * 1024)
        info["available_ram_mb"] = mem.available / (1024 * 1024)
        info["ram_percent"] = mem.percent
        # CPU percent (non-blocking, returns last interval)
        try:
            info["cpu_percent"] = psutil.cpu_percent(interval=0)
        except Exception:
            pass
        # Active thread count for this process
        try:
            proc = psutil.Process()
            info["active_threads"] = proc.num_threads()
        except Exception:
            info["active_threads"] = threading.active_count()
    except ImportError:
        info["total_ram_mb"] = 8192
        info["available_ram_mb"] = 4096
        info["active_threads"] = threading.active_count()

    # GPU resources — use nvidia-smi (avoids loading 3.6GB torch/CUDA DLLs)
    gpu_detected = False

    # Method 1: nvidia-smi (lightweight, no torch required)
    if not gpu_detected:
        try:
            import subprocess
            try:   # gpu_poll_1016: state/gpu_poll.json arms it (absent = today's call); any failure here leaves the real module
                from infrastructure.gpu_reader import bind as _gp_bind; subprocess = _gp_bind("resource_equilibrium")
            except Exception: pass
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.free,memory.used,compute_cap",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = [p.strip() for p in result.stdout.strip().split(",")]
                info["gpu_available"] = True
                info["gpu_name"] = parts[0] if len(parts) > 0 else "unknown"
                total_mb = float(parts[1]) if len(parts) > 1 else 0
                free_mb = float(parts[2]) if len(parts) > 2 else 0
                info["gpu_vram_total_mb"] = total_mb
                info["gpu_vram_free_mb"] = free_mb
                if total_mb > 0:
                    info["gpu_vram_percent"] = ((total_mb - free_mb) / total_mb) * 100
                gpu_detected = True
        except Exception:
            pass

    # Method 2: pynvml
    if not gpu_detected:
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            info["gpu_available"] = True
            name = pynvml.nvmlDeviceGetName(handle)
            info["gpu_name"] = name.decode() if isinstance(name, bytes) else name
            info["gpu_vram_total_mb"] = mem_info.total / (1024 * 1024)
            info["gpu_vram_free_mb"] = mem_info.free / (1024 * 1024)
            if mem_info.total > 0:
                info["gpu_vram_percent"] = ((mem_info.total - mem_info.free) / mem_info.total) * 100
            pynvml.nvmlShutdown()
            gpu_detected = True
        except Exception:
            pass

    # Check satellite mode
    try:
        from server import SYSTEM
        info["is_satellite"] = getattr(SYSTEM, "satellite_mode", False)
    except Exception:
        pass

    # Aggregate resources from linked machines
    try:
        linked = _query_linked_machine_resources()
        info["remote_cpu_cores"] = linked["remote_cpu_cores"]
        info["remote_available_ram_mb"] = linked["remote_available_ram_mb"]
        info["linked_nodes"] = linked["linked_nodes"]
        info["linked_node_details"] = linked.get("nodes", [])
    except Exception:
        pass

    return info


# ─── Health Observation & Learning ────────────────────────────────────────────

def report_health_observation(cpu_pct: float = None, ram_pct: float = None,
                              gpu_vram_pct: float = None, active_threads: int = None,
                              response_latency_ms: float = None):
    """Report a health observation for the adaptive ceiling to learn from.

    Called by the health monitor or any subsystem that detects stress.
    The system learns where instability begins and adjusts accordingly.

    Args:
        cpu_pct: Current CPU usage percentage (0-100)
        ram_pct: Current RAM usage percentage (0-100)
        gpu_vram_pct: Current GPU VRAM usage percentage (0-100)
        active_threads: Current active thread count
        response_latency_ms: Average message response latency in ms
    """
    global _learned_state

    _load_learned_state()

    with _state_lock:
        now = time.time()

        # Build observation
        obs = {
            "ts": now,
            "cpu_pct": cpu_pct,
            "ram_pct": ram_pct,
            "gpu_vram_pct": gpu_vram_pct,
            "threads": active_threads,
            "latency_ms": response_latency_ms,
        }

        # Keep rolling window of 60 observations (~10 minutes at 10s interval)
        _learned_state["observations"].append(obs)
        if len(_learned_state["observations"]) > 60:
            _learned_state["observations"] = _learned_state["observations"][-60:]

        # Determine health status
        is_critical = False
        is_warning = False
        reason = []

        if cpu_pct is not None:
            if cpu_pct >= HEALTH_THRESHOLDS["cpu_critical"]:
                is_critical = True
                reason.append(f"CPU={cpu_pct:.0f}%")
            elif cpu_pct >= HEALTH_THRESHOLDS["cpu_warning"]:
                is_warning = True

        if ram_pct is not None:
            if ram_pct >= HEALTH_THRESHOLDS["ram_critical"]:
                is_critical = True
                reason.append(f"RAM={ram_pct:.0f}%")
            elif ram_pct >= HEALTH_THRESHOLDS["ram_warning"]:
                is_warning = True

        if gpu_vram_pct is not None:
            if gpu_vram_pct >= HEALTH_THRESHOLDS["gpu_vram_critical"]:
                is_critical = True
                reason.append(f"VRAM={gpu_vram_pct:.0f}%")
            elif gpu_vram_pct >= HEALTH_THRESHOLDS["gpu_vram_warning"]:
                is_warning = True

        threads = active_threads or 0

        if is_critical:
            # INSTABILITY DETECTED — learn from this
            _learned_state["health_trips"] += 1
            _learned_state["last_unstable_at"] = now

            if threads > 0:
                # Record the thread count where instability was observed
                old_threshold = _learned_state.get("instability_threshold", 0)
                if old_threshold == 0 or threads < old_threshold:
                    # Take the LOWEST instability point as the threshold
                    _learned_state["instability_threshold"] = threads
                    # Set learned ceiling to 90% of instability threshold
                    # (leave headroom so we don't keep hitting the edge)
                    _learned_state["learned_ceiling"] = max(
                        MIN_FAIRY_CAPACITY,
                        int(threads * 0.90)
                    )
                    print(f"[ResourceEquilibrium] ⚠ INSTABILITY at {threads} threads "
                          f"({', '.join(reason)}). Learned ceiling: {_learned_state['learned_ceiling']}")
                    _save_learned_state()
                    # ── Trace instability ──
                    _t = _get_tracer()
                    if _t:
                        _t.health_alert("resource_equilibrium", "instability",
                                        threads, _learned_state['learned_ceiling'],
                                        severity="error")
                        _t.decision("resource_equilibrium",
                                    f"Learned ceiling set to {_learned_state['learned_ceiling']}",
                                    {"threads_at_instability": threads,
                                     "reasons": reason,
                                     "health_trips": _learned_state['health_trips']})

        elif not is_warning:
            # STABLE — record max stable thread count
            _learned_state["last_stable_at"] = now
            if threads > _learned_state.get("max_observed_threads", 0):
                _learned_state["max_observed_threads"] = threads

            # If we've been stable for a while and the learned ceiling is lower
            # than our current thread count, RAISE the learned ceiling
            # (the system might have been conservative from an earlier spike)
            learned = _learned_state.get("learned_ceiling", 0)
            if learned > 0 and threads > learned:
                # We're running above the learned ceiling and stable!
                # Gradually raise the ceiling (recover from over-conservative learning)
                new_ceiling = max(learned, int(threads * 1.05))
                _learned_state["learned_ceiling"] = new_ceiling
                _save_learned_state()


def _health_monitor_loop():
    """Background thread that samples system health every 10 seconds."""
    global _health_monitor_running

    while _health_monitor_running:
        try:
            info = _query_system_resources()
            report_health_observation(
                cpu_pct=info.get("cpu_percent", 0),
                ram_pct=info.get("ram_percent", 0),
                gpu_vram_pct=info.get("gpu_vram_percent", 0),
                active_threads=info.get("active_threads", 0),
            )
        except Exception:
            pass

        # Sleep in small increments so we can stop cleanly
        for _ in range(10):
            if not _health_monitor_running:
                break
            time.sleep(1.0)


def start_health_monitor():
    """Start the background health monitor that feeds the adaptive ceiling."""
    global _health_monitor_running, _health_monitor_thread

    if _health_monitor_running:
        return

    _health_monitor_running = True
    _health_monitor_thread = threading.Thread(
        target=_health_monitor_loop,
        name="ResourceEquilibrium-HealthMonitor",
        daemon=True
    )
    _health_monitor_thread.start()
    print("[ResourceEquilibrium] Health monitor started (10s interval)")
    _t = _get_tracer()
    if _t:
        _t.lifecycle("resource_equilibrium", "started", {"interval_s": 10})


def stop_health_monitor():
    """Stop the background health monitor."""
    global _health_monitor_running
    _health_monitor_running = False


# ─── Adaptive Ceiling ─────────────────────────────────────────────────────────

def get_worker_ceiling() -> int:
    """
    Get the adaptive worker ceiling.

    PHILOSOPHY: No artificial caps. The ceiling is learned from experience.

    Priority order:
    1. If we have a learned ceiling from health observations → use it
    2. If no learned ceiling yet → use generous initial capacity
    3. Linked machines EXPAND the ceiling (not discounted — they're real capacity)
    4. Floor is MAX(MIN_FAIRY_CAPACITY, ABSOLUTE_FLOOR) — always enough for all fairies

    The ceiling only gets REDUCED when instability is actually observed.
    It gets RAISED when the system runs stable above the learned ceiling.

    Returns:
        Adaptive worker ceiling.
    """
    global _cached_ceiling, _cache_time

    now = time.time()
    if now - _cache_time < _CACHE_TTL and _cached_ceiling > 0:
        return _cached_ceiling

    with _cache_lock:
        # Double-check after acquiring lock
        if now - _cache_time < _CACHE_TTL and _cached_ceiling > 0:
            return _cached_ceiling

        _load_learned_state()
        info = _query_system_resources()

        # ── Base capacity ──
        # FIX 2026-02-09: Generous initial for ~48k target
        # 90 fairies × 64 workers + spell pool + battery workers + postal
        fairy_capacity = MIN_FAIRY_CAPACITY  # 90 × 4 = 360
        infra_overhead = 200   # Postal(~60) + shadow(~90) + misc(~50)
        initial_capacity = fairy_capacity + infra_overhead  # ~560

        # ── RAM safety check ──
        # The ONLY hard constraint: don't exceed what RAM can physically support.
        # FIX 2026-02-09: I/O-bound threads use ~256KB-1MB resident (not 4MB).
        # Python ThreadPoolExecutor threads waiting on I/O release GIL and
        # consume minimal resident memory. Use 0.5MB average for I/O threads.
        # Allow 70% of available RAM for threads (leave 30% for OS/apps).
        available_ram = info.get("available_ram_mb", 4096)
        ram_hard_limit = int((available_ram * 0.70) / 0.5)  # 0.5MB per I/O thread

        # ── GPU expansion ──
        # GPU doesn't directly run threads but offloads heavy work,
        # freeing CPU threads for more concurrent fairy processing.
        gpu_multiplier = 1.0
        if info.get("gpu_available"):
            gpu_vram_gb = info.get("gpu_vram_free_mb", 0) / 1024
            # 5% capacity uplift per GB of free VRAM, max 50%
            gpu_multiplier = min(1.5, 1.0 + (gpu_vram_gb * 0.05))

        # ── Linked machine expansion ──
        # Remote machines provide REAL capacity (not discounted — if they're
        # online and healthy, we should use them)
        remote_cpu = info.get("remote_cpu_cores", 0)
        remote_ram = info.get("remote_available_ram_mb", 0)
        linked_expansion = 0
        if remote_cpu > 0 or remote_ram > 0:
            # Each remote core can support ~10 I/O-bound threads
            # (discounted from 20 for network latency)
            remote_thread_cap = int(remote_cpu * 10)
            remote_ram_cap = int((remote_ram * 0.5) / 4)
            linked_expansion = min(remote_thread_cap, remote_ram_cap)
            _learned_state["linked_expansion"] = linked_expansion

        # ── Satellite mode ──
        is_satellite = info.get("is_satellite", False)

        # ── Determine ceiling ──
        learned = _learned_state.get("learned_ceiling", 0)

        if learned > 0:
            # We have a learned ceiling from health observations
            ceiling = learned + linked_expansion
        else:
            # No learned ceiling yet — use generous initial capacity
            ceiling = int(initial_capacity * gpu_multiplier) + linked_expansion

        # Apply RAM hard limit (can't exceed physical RAM)
        ceiling = min(ceiling, ram_hard_limit)

        # Apply floor (never go below minimum fairy capacity)
        ceiling = max(MIN_FAIRY_CAPACITY if not is_satellite else ABSOLUTE_FLOOR, ceiling)

        # Satellite mode: reduced but not crippled
        if is_satellite:
            ceiling = max(ABSOLUTE_FLOOR, ceiling // 2)

        _cached_ceiling = ceiling
        _cache_time = now

        return ceiling


def get_pool_size(pool_type: str = "default") -> int:
    """
    Get recommended pool size for a specific subsystem.

    In adaptive mode, pools are sized generously — the system learns
    limits from experience, not from pre-calculated fractions.

    Pool types:
    - "boot":    100% of ceiling (boot is temporary, give it everything)
    - "postal":  75% of ceiling (high-volume, the nervous system)
    - "spell":   75% of ceiling (spell chain workers = fairy processing)
    - "fairy":   50% of ceiling (per-fairy work submissions)
    - "default": 50% of ceiling

    Args:
        pool_type: One of "boot", "postal", "spell", "fairy", "default"

    Returns:
        Recommended worker count for this pool type.
    """
    ceiling = get_worker_ceiling()

    fractions = {
        "boot":    1.00,  # Boot is temporary, can use everything
        "postal":  0.75,  # Postal IS the nervous system
        "spell":   0.75,  # SpellPool IS the work execution engine
        "fairy":   0.50,  # Fairy work submissions
        "default": 0.50,
    }

    fraction = fractions.get(pool_type, 0.50)
    size = max(8, int(ceiling * fraction))  # Floor of 8

    return size


# ─── Diagnostics ──────────────────────────────────────────────────────────────

_SYS_INFO_CACHE = {"data": None, "last_update": 0.0}
_SYS_INFO_CACHE_TTL = 10.0  # Cache for 10 seconds — hardware info changes slowly

def get_system_info() -> dict:
    """
    Get comprehensive system resource + adaptive equilibrium info.

    Returns:
        Dict with hardware info, adaptive state, and pool sizes.
    """
    # FIX 2026-02-16: Cache result to avoid spawning nvidia-smi subprocess
    # every 2 seconds (called from server.py _compute_status_internal).
    now = time.time()
    if _SYS_INFO_CACHE["data"] is not None and (now - _SYS_INFO_CACHE["last_update"]) < _SYS_INFO_CACHE_TTL:
        return _SYS_INFO_CACHE["data"]

    _load_learned_state()
    info = _query_system_resources()
    ceiling = get_worker_ceiling()

    result = {
        # Hardware
        "cpu_cores": info["cpu_cores"],
        "total_ram_mb": round(info["total_ram_mb"]),
        "available_ram_mb": round(info["available_ram_mb"]),
        "cpu_percent": round(info.get("cpu_percent", 0), 1),
        "ram_percent": round(info.get("ram_percent", 0), 1),
        "active_threads": info.get("active_threads", 0),
        "is_satellite": info["is_satellite"],

        # GPU
        "gpu_available": info.get("gpu_available", False),
        "gpu_name": info.get("gpu_name", ""),
        "gpu_vram_total_mb": round(info.get("gpu_vram_total_mb", 0)),
        "gpu_vram_free_mb": round(info.get("gpu_vram_free_mb", 0)),
        "gpu_vram_percent": round(info.get("gpu_vram_percent", 0), 1),
        "gpu_compute_units": info.get("gpu_compute_units", 0),

        # Linked machines
        "linked_nodes": info.get("linked_nodes", 0),
        "remote_cpu_cores": info.get("remote_cpu_cores", 0),
        "remote_available_ram_mb": round(info.get("remote_available_ram_mb", 0)),
        "linked_node_details": info.get("linked_node_details", []),

        # Adaptive ceiling
        "worker_ceiling": ceiling,
        "learned_ceiling": _learned_state.get("learned_ceiling", 0),
        "max_observed_threads": _learned_state.get("max_observed_threads", 0),
        "instability_threshold": _learned_state.get("instability_threshold", 0),
        "health_trips": _learned_state.get("health_trips", 0),
        "linked_expansion": _learned_state.get("linked_expansion", 0),
        "ceiling_mode": "learned" if _learned_state.get("learned_ceiling", 0) > 0 else "generous_initial",

        # Pool sizes
        "pool_sizes": {
            "boot": get_pool_size("boot"),
            "postal": get_pool_size("postal"),
            "spell": get_pool_size("spell"),
            "fairy": get_pool_size("fairy"),
        },
    }

    # Store in cache
    _SYS_INFO_CACHE["data"] = result
    _SYS_INFO_CACHE["last_update"] = time.time()
    return result


def get_health_summary() -> dict:
    """Get a summary of recent health observations."""
    _load_learned_state()

    observations = _learned_state.get("observations", [])
    if not observations:
        return {"status": "no_observations", "message": "Health monitor not yet running"}

    recent = observations[-10:]  # Last 10 observations

    avg_cpu = sum(o.get("cpu_pct", 0) or 0 for o in recent) / len(recent)
    avg_ram = sum(o.get("ram_pct", 0) or 0 for o in recent) / len(recent)
    max_threads = max((o.get("threads", 0) or 0 for o in recent), default=0)

    status = "healthy"
    if avg_cpu > HEALTH_THRESHOLDS["cpu_warning"] or avg_ram > HEALTH_THRESHOLDS["ram_warning"]:
        status = "warning"
    if avg_cpu > HEALTH_THRESHOLDS["cpu_critical"] or avg_ram > HEALTH_THRESHOLDS["ram_critical"]:
        status = "critical"

    return {
        "status": status,
        "avg_cpu_pct": round(avg_cpu, 1),
        "avg_ram_pct": round(avg_ram, 1),
        "max_threads": max_threads,
        "observations_count": len(observations),
        "learned_ceiling": _learned_state.get("learned_ceiling", 0),
        "max_observed_stable": _learned_state.get("max_observed_threads", 0),
        "instability_threshold": _learned_state.get("instability_threshold", 0),
        "health_trips": _learned_state.get("health_trips", 0),
    }


def reset_learned_state():
    """Reset all learned state (for testing or after hardware changes)."""
    global _learned_state, _cached_ceiling, _cache_time
    with _state_lock:
        _learned_state = {
            "learned_ceiling": 0,
            "max_observed_threads": 0,
            "instability_threshold": 0,
            "observations": [],
            "health_trips": 0,
            "last_stable_at": 0,
            "last_unstable_at": 0,
            "linked_expansion": 0,
        }
        _cached_ceiling = 0
        _cache_time = 0.0
        _save_learned_state()
        print("[ResourceEquilibrium] Learned state RESET — system will re-learn from scratch")
