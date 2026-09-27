"""
Slice 0 telemetry writer — read-only observation of cortex bind / spread / thought-episode
events for the four-piece architectural picture (AER warp / short-term Hebbian / long-term
Hebbian / Dr Zero LEARN).

Plan: Claude_Office/plans/SLICE_0_INSTRUMENTATION.md

Writes JSONL to state/telemetry/slice0/. Thread-safe under Python 3.14 free-threaded.
Sampled to keep overhead negligible at hot bind site. Feature-flagged for instant disable.

Schema versions are emitted with every record so the query tool can adapt.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Mapping, Optional

# ---- Configuration -----------------------------------------------------------

_TELEMETRY_DIR = Path(__file__).resolve().parents[2] / "state" / "telemetry" / "slice0"
_TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)

ENABLED = os.environ.get("SLICE0_TELEMETRY_ENABLED", "1") not in ("0", "false", "False", "")

# Sampling rates (override via env)
BIND_SAMPLE_EVERY = int(os.environ.get("SLICE0_BIND_SAMPLE", "100"))
SPREAD_SAMPLE_EVERY = int(os.environ.get("SLICE0_SPREAD_SAMPLE", "10"))

# AER intensity threshold above which we always-capture regardless of sample rate.
# Calibrated against Sour's healthy waking baseline 2026-05-06: OXY 96%, SER 70%,
# OXY 0.6, etc. — those are the "normal" elevated levels, NOT high-affect moments.
# 0.6 would trip on every bind. 0.85 only triggers on genuinely elevated states
# (acute joy, acute panic, etc.) so sampling actually does its job.
AER_HIGH_INTENSITY = float(os.environ.get("SLICE0_AER_HIGH", "0.85"))

# Rotation: rotate file at this size (bytes) or this age (seconds)
_ROTATE_BYTES = 50 * 1024 * 1024
_ROTATE_AGE_S = 24 * 3600
_RETAIN_DAYS = 7

SCHEMA_VERSION = 1

# ---- Internal state ----------------------------------------------------------

_locks: dict[str, threading.Lock] = {}
_lock_guard = threading.Lock()
_counters: dict[str, int] = {"bind": 0, "spread": 0}


def _file_lock(name: str) -> threading.Lock:
    with _lock_guard:
        lk = _locks.get(name)
        if lk is None:
            lk = threading.Lock()
            _locks[name] = lk
        return lk


def _current_path(stream: str) -> Path:
    """One file per UTC day. Rotation by date keeps lookup simple."""
    day = time.strftime("%Y-%m-%d", time.gmtime())
    return _TELEMETRY_DIR / f"{stream}_{day}.jsonl"


def _rotate_if_needed(path: Path) -> None:
    if not path.exists():
        return
    try:
        st = path.stat()
        if st.st_size > _ROTATE_BYTES:
            ts = time.strftime("%H%M%S", time.gmtime())
            path.rename(path.with_name(f"{path.stem}.{ts}.jsonl"))
    except OSError:
        pass


def _prune_old() -> None:
    """Delete files older than _RETAIN_DAYS. Cheap; runs on every write."""
    cutoff = time.time() - _RETAIN_DAYS * 24 * 3600
    try:
        for p in _TELEMETRY_DIR.iterdir():
            if p.suffix == ".jsonl" and p.stat().st_mtime < cutoff:
                p.unlink()
    except OSError:
        pass


_prune_counter = 0


def _maybe_prune() -> None:
    global _prune_counter
    _prune_counter += 1
    if _prune_counter % 1000 == 0:
        _prune_old()


def _append(stream: str, record: dict) -> None:
    if not ENABLED:
        return
    record.setdefault("schema", SCHEMA_VERSION)
    record.setdefault("ts", time.time())
    record["stream"] = stream
    path = _current_path(stream)
    _rotate_if_needed(path)
    line = json.dumps(record, default=str, ensure_ascii=False) + "\n"
    lock = _file_lock(stream)
    with lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    _maybe_prune()


# ---- AER snapshot helper -----------------------------------------------------

def compact_aer(aer_state: Optional[Mapping[str, float]], top_n: int = 8) -> list[tuple[str, float]]:
    """Compact AER snapshot: top-N bands by intensity. Returns [(band, value), ...]."""
    if not aer_state:
        return []
    try:
        items = [(k, float(v)) for k, v in aer_state.items() if isinstance(v, (int, float))]
        items.sort(key=lambda kv: abs(kv[1]), reverse=True)
        return items[:top_n]
    except Exception:
        return []


def aer_max_intensity(aer_state: Optional[Mapping[str, float]]) -> float:
    if not aer_state:
        return 0.0
    try:
        return max((abs(float(v)) for v in aer_state.values() if isinstance(v, (int, float))), default=0.0)
    except Exception:
        return 0.0


# ---- Public API: bind events -------------------------------------------------

def record_bind(
    pair: tuple[str, str],
    *,
    source: str = "",
    aer: Optional[Mapping[str, float]] = None,
    chemistry: Optional[Mapping[str, float]] = None,
    weight_delta: Optional[float] = None,
    is_new_edge: bool = False,
    extra: Optional[Mapping[str, Any]] = None,
) -> None:
    """Hook 1: cortex bind. Sampled at BIND_SAMPLE_EVERY, plus always for high-AER binds."""
    if not ENABLED:
        return
    _counters["bind"] += 1
    high_aer = aer_max_intensity(aer) >= AER_HIGH_INTENSITY
    if not high_aer and (_counters["bind"] % BIND_SAMPLE_EVERY) != 0:
        return
    rec = {
        "pair": list(pair),
        "source": source,
        "aer_top": compact_aer(aer),
        "chemistry": dict(chemistry) if chemistry else None,
        "weight_delta": weight_delta,
        "is_new_edge": is_new_edge,
        "high_aer": high_aer,
    }
    if extra:
        rec["extra"] = dict(extra)
    _append("bind", rec)


# ---- Public API: spread events -----------------------------------------------

def record_spread(
    seed_keys: list[str],
    *,
    top_visited: list[tuple[str, float]],
    aer: Optional[Mapping[str, float]] = None,
    chemistry_params: Optional[Mapping[str, Any]] = None,
    convergence_count: int = 0,
    wall_ms: float = 0.0,
    extra: Optional[Mapping[str, Any]] = None,
) -> None:
    """Hook 2: spread activation. Sampled at SPREAD_SAMPLE_EVERY, plus always for convergence > 5."""
    if not ENABLED:
        return
    _counters["spread"] += 1
    interesting = convergence_count > 5
    if not interesting and (_counters["spread"] % SPREAD_SAMPLE_EVERY) != 0:
        return
    rec = {
        "seed_keys": list(seed_keys)[:10],
        "top_visited": [(str(k), float(v)) for k, v in top_visited[:20]],
        "aer_top": compact_aer(aer),
        "chemistry_params": dict(chemistry_params) if chemistry_params else None,
        "convergence_count": int(convergence_count),
        "wall_ms": float(wall_ms),
    }
    if extra:
        rec["extra"] = dict(extra)
    _append("spread", rec)


# ---- Public API: thought episodes -------------------------------------------

def record_episode(
    episode_id: str,
    *,
    trigger: str,
    start_ts: float,
    end_ts: float,
    aer_at_start: Optional[Mapping[str, float]] = None,
    aer_at_end: Optional[Mapping[str, float]] = None,
    tracers_active: Optional[list[str]] = None,
    cortex_edge_deltas: Optional[list[dict]] = None,
    extra: Optional[Mapping[str, Any]] = None,
) -> None:
    """Hook 3: thought-episode boundary. Every episode (not high-frequency, no sampling)."""
    if not ENABLED:
        return
    rec = {
        "episode_id": episode_id,
        "trigger": trigger,
        "start_ts": float(start_ts),
        "end_ts": float(end_ts),
        "duration_ms": (float(end_ts) - float(start_ts)) * 1000.0,
        "aer_at_start": compact_aer(aer_at_start),
        "aer_at_end": compact_aer(aer_at_end),
        "tracers_active": list(tracers_active or [])[:50],
        "cortex_edge_deltas": list(cortex_edge_deltas or [])[:100],
    }
    if extra:
        rec["extra"] = dict(extra)
    _append("episode", rec)


# ---- Counters (for debug / introspection) ------------------------------------

def stats() -> dict:
    return {
        "enabled": ENABLED,
        "telemetry_dir": str(_TELEMETRY_DIR),
        "counters": dict(_counters),
        "schema_version": SCHEMA_VERSION,
    }
