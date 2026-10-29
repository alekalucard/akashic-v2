"""
Break room -- who is NOT doing anything (W10, 2026-10-29 Nous).

Read-only report over HeartbeatRegistry: citizens / registered fairies with no
real heartbeat delivery in the last N beats, with name and plane.

Data only exists when AKASHIC_LIVENESS_FROM_DELIVERY=1 (see heartbeat_registry.py):
then the registry records, per fairy, the beat whose callback actually returned
(_last_delivered_beat). With the switch OFF the report says so and lists only the
fairies that cannot be delivered to at all (citizens with no callback).

Nothing here writes to the registry, starts threads, or opens sockets. The registry
persists nothing to disk and exposes no endpoint, so there are two ways to use it:

  in-process:  from consciousness.break_room import break_room, format_report
               print(format_report(break_room(get_heartbeat_registry(), n_beats=10)))

  offline CLI: dump once in-process   ->  dump_snapshot(get_heartbeat_registry(), "snap.json")
               then read the file     ->  python code/consciousness/break_room.py snap.json --beats 10

The CLI never attaches to a running process; it only reads the snapshot file.
"""

import json
import sys
from typing import Any, Dict, List, Optional


def snapshot(registry, citizens: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Copy (read-only) what the break-room report needs out of a HeartbeatRegistry."""
    if citizens is None:
        try:
            from fairy_template.citizen_registry import _CITIZEN_OBJECTS as citizens
        except ImportError:
            citizens = {}
    try:
        cit_items = tuple(citizens.items())
    except Exception:
        cit_items = ()
    planes = dict(getattr(registry, "_fairy_planes", {}) or {})
    cit_planes = {}
    for name, obj in cit_items:
        cit_planes[name] = (planes.get(name) or getattr(obj, "ACTOR_PLANE", "")
                            or getattr(obj, "plane", "") or "")
    with registry._lock:
        cb_names = list(registry._callbacks.keys())
    return {
        "liveness_from_delivery": bool(getattr(registry, "_liveness_from_delivery", False)),
        "beat": int(getattr(registry, "_liveness_beat", 0) or 0),
        "callbacks": cb_names,
        "planes": planes,
        "citizens": cit_planes,
        "last_delivered_beat": dict(getattr(registry, "_last_delivered_beat", {}) or {}),
        "error_counts": {k: v for k, v in dict(getattr(registry, "_error_counts", {})).items() if v},
        "in_flight": sorted(getattr(registry, "_in_flight", set()) or ()),
    }


def dump_snapshot(registry, path: str, citizens: Optional[Dict[str, Any]] = None) -> str:
    """Write snapshot(registry) to `path` as JSON. Only runs when YOU call it."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot(registry, citizens), f, indent=1, sort_keys=True)
    return path


def break_room(source, n_beats: int = 10, citizens: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fairies with no real delivery in the last `n_beats` beats.

    `source` is a HeartbeatRegistry or a snapshot dict. Returns
    {"switch_on", "beat", "n_beats", "napping": [{name, plane, last_beat, beats_since, why}], "note"}.
    """
    snap = source if isinstance(source, dict) else snapshot(source, citizens)
    on = bool(snap.get("liveness_from_delivery"))
    beat = int(snap.get("beat", 0) or 0)
    cbs = set(snap.get("callbacks", []))
    cit = dict(snap.get("citizens", {}))
    planes = dict(snap.get("planes", {}))
    last = dict(snap.get("last_delivered_beat", {}))
    errs = dict(snap.get("error_counts", {}))
    busy = set(snap.get("in_flight", []))
    napping: List[Dict[str, Any]] = []
    for name in sorted(cbs | set(cit)):
        plane = planes.get(name) or cit.get(name, "") or ""
        if name not in cbs:
            napping.append({"name": name, "plane": plane, "last_beat": None,
                            "beats_since": None, "why": "citizen with no heartbeat callback"})
            continue
        if not on:
            continue  # no delivery data collected while the switch is off
        lb = last.get(name)
        if lb is None:
            why = "never delivered"
        elif beat - int(lb) > n_beats:
            why = f"no delivery in {beat - int(lb)} beats"
        else:
            continue
        if name in busy:
            why += " (callback still running)"
        if errs.get(name):
            why += f" ({errs[name]} callback errors)"
        napping.append({"name": name, "plane": plane, "last_beat": lb,
                        "beats_since": None if lb is None else beat - int(lb), "why": why})
    napping.sort(key=lambda r: (r["plane"] or "~", r["name"]))
    note = "" if on else ("AKASHIC_LIVENESS_FROM_DELIVERY is OFF: no per-beat delivery data; "
                          "only fairies with no callback at all are listed.")
    return {"switch_on": on, "beat": beat, "n_beats": n_beats, "napping": napping, "note": note}


def format_report(rep: Dict[str, Any]) -> str:
    lines = [f"BREAK ROOM @ beat {rep['beat']} (window {rep['n_beats']} beats): "
             f"{len(rep['napping'])} napping"]
    if rep.get("note"):
        lines.append("  NOTE: " + rep["note"])
    for r in rep["napping"]:
        lines.append(f"  {r['plane'] or '???':4} {r['name']:40} {r['why']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Break-room report from a HeartbeatRegistry snapshot file.")
    ap.add_argument("snapshot", help="JSON written by break_room.dump_snapshot()")
    ap.add_argument("--beats", type=int, default=10, help="window N (default 10)")
    ap.add_argument("--json", action="store_true", help="print JSON instead of text")
    a = ap.parse_args(argv)
    with open(a.snapshot, "r", encoding="utf-8") as f:
        snap = json.load(f)
    rep = break_room(snap, n_beats=a.beats)
    print(json.dumps(rep, indent=1) if a.json else format_report(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
