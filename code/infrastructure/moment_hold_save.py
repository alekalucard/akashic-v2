"""
W12 MOMENT HOLD -> DREAM SEED (Nous, 2026-10-29). OFF unless AKASHIC_MOMENT_HOLD_SAVE=1.

MomentBinderFairy keeps her last <= 60 moments in memory only (the HOLD, fairies/P30_Cognition/
MomentBinderFairy/fairy.py: EPISODIC_BUFFER_MAX / _episodic_buffer). A moment reaches the episodic
manifold only when it rolls OFF the HOLD, so every exit dropped the whole HOLD: MomentBinderFairy.on_die
has no caller anywhere in the tree, and its on_shutdown (the template's) saves nothing of it.

This module hands the HOLD, AS IT IS, to the dream seed that shutdown_system() has just written
(state/dream_seed.json, server.py _capture_dream_seed). It is called from shutdown_system() Phase 2,
right after that write, on every shutdown path (HTTP route, reboot, Ctrl+C).

- Content: each moment dict is carried unchanged (a JSON round trip of the same dict; a value JSON cannot
  carry exactly makes the hand-off refuse, it is never coerced).
- Bound: at most MAX_MOMENTS moments and MAX_BYTES bytes of moments. If the bound forces a drop, the
  moments with the LOWEST "significance" go first -- the score the binder already computes
  (MomentBinderFairy._score_significance, stored on each moment as "significance"). Equal scores are
  broken by the moment's random "tracer" id, never by its age. Kept moments stay in HOLD order.
- Atomic: temp file in the same directory, fsync, os.replace. The seed's other keys are left as they are.
- Never creates a seed: absent / unreadable / non-object seed -> nothing is written.
- Nothing at boot reads mind_pools["moment_hold"] yet (see docs/nous/W12/SUMMARY.md); no reader is added here.

Import has no side effects (stdlib only, no threads, no I/O).
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from typing import Any, Dict, List, Optional

SWITCH = "AKASHIC_MOMENT_HOLD_SAVE"
SEED_KEY = "moment_hold"
MAX_MOMENTS = 60              # = MomentBinderFairy.EPISODIC_BUFFER_MAX: the HOLD never holds more, so nothing drops today
MAX_BYTES = 2 * 1024 * 1024   # moments' serialized size; a moment is ~1-3 KB (text <= 900 chars, <= 22 tags)
BINDER_NAME = "MomentBinderFairy"


def switch_on() -> bool:
    return os.environ.get(SWITCH, "0") == "1"


def _snapshot(binder) -> List[Dict[str, Any]]:
    """The HOLD as a list, oldest first. The binder appends outside its lock (fairy.py, _maybe_emit_moment), so a
    concurrent append can make list() raise 'deque mutated during iteration': retry."""
    buf = getattr(binder, "_episodic_buffer", None)
    if buf is None:
        return []
    lock = getattr(binder, "_moment_lock", None)
    last = None
    for _ in range(5):
        try:
            if lock is not None:
                with lock:
                    return list(buf)
            return list(buf)
        except RuntimeError as e:
            last = e
            time.sleep(0.01)
    raise last


def _exact_copy(m: Any) -> Any:
    """A JSON copy of the moment that must compare equal to it; otherwise refuse (never coerce)."""
    c = json.loads(json.dumps(m, allow_nan=False))
    if c != m:
        raise ValueError("moment does not survive JSON unchanged (tracer=%r)" % (
            m.get("tracer") if isinstance(m, dict) else None))
    return c


def _sig(m: Dict[str, Any]) -> float:
    try:
        return float(m.get("significance", 0.0) or 0.0)
    except Exception:
        return 0.0


def select(moments: List[Dict[str, Any]], max_n: int = MAX_MOMENTS, max_bytes: int = MAX_BYTES):
    """-> (kept, dropped_count). Drops lowest significance first (ties: tracer id), keeps HOLD order."""
    idx = list(range(len(moments)))
    # removal order: lowest significance first; ties by tracer string (random hex), never by position/age
    removal = sorted(idx, key=lambda i: (_sig(moments[i]), str(moments[i].get("tracer", ""))))
    removed = set()
    r = 0
    while len(idx) - len(removed) > max_n:
        removed.add(removal[r])
        r += 1
    sizes = {i: len(json.dumps(moments[i])) for i in idx}
    total = sum(sizes[i] for i in idx if i not in removed)
    while total > max_bytes and r < len(removal):
        i = removal[r]
        r += 1
        if i in removed:
            continue
        removed.add(i)
        total -= sizes[i]
    kept = [moments[i] for i in idx if i not in removed]
    return kept, len(removed)


def _atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".dream_seed.", suffix=".tmp", dir=d)
    try:
        try:
            os.chmod(tmp, os.stat(path).st_mode & 0o7777)   # keep the seed's own permissions
        except OSError:
            pass
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def hand_off(binder, seed_path: str, max_n: int = MAX_MOMENTS, max_bytes: int = MAX_BYTES) -> str:
    """Write the binder's HOLD into seed_path's mind_pools[SEED_KEY]. -> one status line. Never raises."""
    try:
        if not switch_on():
            return "off"
        if binder is None:
            return "skipped: no MomentBinderFairy instance"
        moments = [_exact_copy(m) for m in _snapshot(binder)]
        if not os.path.isfile(seed_path):
            return "skipped: no dream seed at %s (not created)" % seed_path
        with open(seed_path, "r", encoding="utf-8") as f:
            seed = json.load(f)
        if not isinstance(seed, dict):
            return "skipped: dream seed is not a JSON object (left as is)"
        pools = seed.get("mind_pools")
        if pools is None:
            pools = seed["mind_pools"] = {}
        if not isinstance(pools, dict):
            return "skipped: dream seed mind_pools is not an object (left as is)"
        kept, dropped = select(moments, max_n, max_bytes)
        pools[SEED_KEY] = {
            "moments": kept,
            "held": len(moments),
            "saved": len(kept),
            "dropped": dropped,
            "drop_rule": "lowest significance first (MomentBinderFairy._score_significance); ties by tracer",
            "saved_ts": time.time(),
            "from_fairy": BINDER_NAME,
        }
        _atomic_write_json(seed_path, seed)
        return "saved %d of %d held moments (dropped %d)" % (len(kept), len(moments), dropped)
    except Exception as e:
        return "error: %s: %s" % (type(e).__name__, str(e)[:160])


def find_binder(system) -> Optional[Any]:
    """The live MomentBinderFairy from SYSTEM.directory records (metadata['fairy_instance']); never instantiates one."""
    d = getattr(system, "directory", None)
    if d is None:
        return None
    try:
        rec = d.get_fairy(BINDER_NAME) if callable(getattr(d, "get_fairy", None)) else None
        inst = (rec.metadata or {}).get("fairy_instance") if rec is not None else None
        if inst is not None:
            return inst
    except Exception:
        pass
    try:
        for rec in d.list_fairies():
            inst = (rec.metadata or {}).get("fairy_instance") if rec.metadata else None
            if inst is not None and getattr(inst, "ACTOR_NAME", None) == BINDER_NAME:
                return inst
    except Exception:
        pass
    return None


def shutdown_hand_off(system, seed_path) -> str:
    """shutdown_system() Phase 2 entry point. OFF -> 'off' and nothing is touched."""
    if not switch_on():
        return "off"
    return hand_off(find_binder(system), str(seed_path))
