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
  carry exactly is left out and counted as "refused" -- never coerced).
- Bound: at most MAX_MOMENTS moments and MAX_BYTES bytes of moments. If the bound forces a drop, the
  moments with the LOWEST "significance" go first -- the score the binder already computes
  (MomentBinderFairy._score_significance, stored on each moment as "significance"). Equal scores are
  broken by the moment's random "tracer" id, never by its age. Kept moments stay in HOLD order.
- Atomic: temp file in the same directory, fsync, os.replace. The seed's other keys are left as they are.
- Never creates a seed: absent / unreadable / non-object seed -> nothing is written.
- The only reader is restore_into() below (its own switch, AKASHIC_MOMENT_HOLD_RESTORE): MomentBinderFairy.on_boot puts
  the saved moments back into an EMPTY HOLD, exactly as saved, once per saved set. No consolidation is wired.

Import has no side effects (stdlib only, no threads, no I/O).
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from typing import Any, Dict, List, Optional

SWITCH = "AKASHIC_MOMENT_HOLD_SAVE"
RESTORE_SWITCH = "AKASHIC_MOMENT_HOLD_RESTORE"
MARKER_KEEP = 100             # consumed-set ids kept in the marker file (one per shutdown)
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


_ITEM_INDENT = 8   # seed{ mind_pools{ moment_hold{ moments[ item: each item line sits 4 levels (indent=2) deep


def _written_size(m: Dict[str, Any]) -> int:
    """Bytes this moment adds to the moments array as _atomic_write_json writes it: its indent=2 text, every line
    indented _ITEM_INDENT more, plus the ',\n' separator."""
    text = json.dumps(m, indent=2)
    return len(text) + _ITEM_INDENT * (text.count("\n") + 1) + 2


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
    sizes = {i: _written_size(moments[i]) for i in idx}
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
        try:                                   # make the rename itself durable (POSIX; no-op elsewhere)
            dfd = os.open(d, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass
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
        held = _snapshot(binder)
        moments, refused = [], []
        for m in held:   # a moment JSON cannot carry exactly (or not a dict) is left out (counted), never altered
            try:
                if not isinstance(m, dict):
                    raise TypeError("not a moment dict")
                moments.append(_exact_copy(m))
            except Exception:
                refused.append(str(m.get("tracer", "?")) if isinstance(m, dict) else "?")
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
            "held": len(held),
            "saved": len(kept),
            "dropped": dropped,
            "refused": len(refused),
            "refused_tracers": refused[:60],
            "drop_rule": "lowest significance first (MomentBinderFairy._score_significance); ties by tracer",
            "saved_ts": time.time(),
            "from_fairy": BINDER_NAME,
        }
        _atomic_write_json(seed_path, seed)
        return "saved %d of %d held moments (dropped %d, refused %d)" % (len(kept), len(held), dropped, len(refused))
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


# ---- READER (W12b, 2026-10-29) -- OFF unless AKASHIC_MOMENT_HOLD_RESTORE=1 ------------------------------------------
# MomentBinderFairy.on_boot -> restore_into(self, <code>/state/dream_seed.json, <code>/state/moment_hold_restored.json).
# - Restores only into an EMPTY hold (anything already there would be interleaved/evicted = changed); else skip + log.
# - Never more than the hold's own cap (deque maxlen); a saved set larger than the cap is skipped whole, never cut.
# - Moments go back as saved: same dicts (JSON), same oldest-first order, appended to binder._episodic_buffer.
# - Once per saved set: the set's id (sha256 of its saved_ts + moments) is written to a SIDECAR marker BEFORE the hold
#   is filled. A crash after the mark loses that restore at worst; it can never double it. The seed is never written
#   (DreamSeedFairy.on_boot re-saves dream_seed.json non-atomically at boot, dream_seed_fairy.py:327/343, so an in-place
#   mark could be overwritten by its stale copy). Nothing is deleted.
# - No consolidation: restored tracers are added to binder._consolidated_tracers, so the 60 s rememberer and the day-store
#   capture (fairy.py _consolidate_episodic) skip them. They still persist to the episodic manifold when they roll off,
#   as every HOLD moment does (fairy.py:678-693) -- they never reached it before the shutdown, so that is not a repeat.

import threading as _threading
_RESTORE_LOCK = _threading.Lock()   # one restore at a time in this process: a saved set goes into ONE binder only


def restore_switch_on() -> bool:
    return os.environ.get(RESTORE_SWITCH, "0") == "1"


def _set_id(block: Dict[str, Any]) -> str:
    import hashlib
    raw = json.dumps({"saved_ts": block.get("saved_ts"), "moments": block.get("moments")},
                     sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_marker(marker_path: str) -> Dict[str, Any]:
    if not os.path.isfile(marker_path):
        return {"consumed": []}
    with open(marker_path, "r", encoding="utf-8") as f:
        d = json.load(f)        # unreadable marker -> raises -> restore refused (cannot prove "not yet restored")
    if not isinstance(d, dict) or not isinstance(d.get("consumed"), list):
        raise ValueError("marker is not {'consumed': [...]}")
    return d


def restore_into(binder, seed_path: str, marker_path: str) -> str:
    """Put mind_pools['moment_hold'] back into the binder's HOLD. -> one status line. Never raises."""
    try:
        if not restore_switch_on():
            return "off"
        if binder is None:
            return "skipped: no binder"
        if not os.path.isfile(seed_path):
            return "skipped: no dream seed"
        with open(seed_path, "r", encoding="utf-8") as f:
            seed = json.load(f)
        pools = seed.get("mind_pools") if isinstance(seed, dict) else None
        block = pools.get(SEED_KEY) if isinstance(pools, dict) else None
        if not isinstance(block, dict):
            return "nothing to restore (no %s in the seed)" % SEED_KEY
        moments = block.get("moments")
        if not isinstance(moments, list) or not moments:
            return "nothing to restore (no moments)"
        if not all(isinstance(m, dict) for m in moments):
            return "skipped: saved set has a non-moment entry (left as is)"
        sid = _set_id(block)
        with _RESTORE_LOCK:
            return _restore_locked(binder, block, moments, sid, seed_path, marker_path)
    except Exception as e:
        return "error: %s: %s" % (type(e).__name__, str(e)[:160])


def _restore_locked(binder, block, moments, sid, seed_path, marker_path) -> str:
    """Under _RESTORE_LOCK: check the marker, then (under the binder's lock) mark first and fill second."""
    try:
        marker = _read_marker(marker_path)
        if any(isinstance(c, dict) and c.get("id") == sid for c in marker["consumed"]):
            return "skipped: this saved set was already restored (%s)" % sid[:12]
        buf = getattr(binder, "_episodic_buffer", None)
        lock = getattr(binder, "_moment_lock", None)
        if buf is None or lock is None:
            return "skipped: binder has no hold"
        if getattr(binder, "_epi_persister", None) is None:
            # without the episodic persister a moment that rolls off the hold is dropped unpersisted (fairy.py append
            # site): restoring now could lose a restored moment, so leave the set unconsumed for a later boot
            return "skipped: no episodic persister (restored moments could roll off unpersisted)"
        with lock:
            if len(buf) != 0:
                return "skipped: hold already has %d moment(s) -- restore only into an empty hold" % len(buf)
            cap = buf.maxlen
            if cap is not None and len(moments) > cap:
                return "skipped: %d saved > hold cap %d (never cut)" % (len(moments), cap)
            # 1) mark consumed (atomic) -- 2) only then fill the hold
            marker["consumed"] = (marker["consumed"] + [{
                "id": sid, "restored_ts": time.time(), "count": len(moments),
                "saved_ts": block.get("saved_ts"), "seed_path": os.path.abspath(seed_path)}])[-MARKER_KEEP:]
            _atomic_write_json(marker_path, marker)
            buf.extend(moments)
            done = getattr(binder, "_consolidated_tracers", None)
            if isinstance(done, set):
                done.update(m.get("tracer") for m in moments)
        return "restored %d moment(s) (set %s)" % (len(moments), sid[:12])
    except Exception as e:
        return "error: %s: %s" % (type(e).__name__, str(e)[:160])
