"""
Slice 0 telemetry reader — terminal-friendly readout of bind / spread / episode events.

Usage:
  python tools/query_slice0_telemetry.py                      # default: recent summary
  python tools/query_slice0_telemetry.py --recent 20          # last 20 events of each kind
  python tools/query_slice0_telemetry.py --episodes 5         # last 5 thought episodes
  python tools/query_slice0_telemetry.py --binds 50           # last 50 bind events
  python tools/query_slice0_telemetry.py --spreads 20         # last 20 spread events
  python tools/query_slice0_telemetry.py --aer-correlate      # AER state vs cortex deltas

Plan: Claude_Office/plans/SLICE_0_INSTRUMENTATION.md
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TELEMETRY_DIR = Path(__file__).resolve().parent.parent / "state" / "telemetry" / "slice0"


def load_stream(stream: str, limit: int = 1000) -> list[dict]:
    """Read all .jsonl files for a stream, return last `limit` records by ts."""
    if not TELEMETRY_DIR.exists():
        return []
    files = sorted(TELEMETRY_DIR.glob(f"{stream}_*.jsonl"))
    files += sorted(TELEMETRY_DIR.glob(f"{stream}_*.*.jsonl"))  # rotated files
    records: list[dict] = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue
    records.sort(key=lambda r: r.get("ts", 0))
    return records[-limit:]


def fmt_ts(ts: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def fmt_aer_top(aer_top: list) -> str:
    """[(band, value), ...] → 'DOP=0.55 SER=0.70 ...'"""
    if not aer_top:
        return "(none)"
    return " ".join(f"{b}={v:.2f}" for b, v in aer_top[:5])


def show_summary(recent: int = 50) -> None:
    binds = load_stream("bind", limit=recent)
    spreads = load_stream("spread", limit=recent)
    episodes = load_stream("episode", limit=recent)

    print(f"=== SLICE 0 TELEMETRY SUMMARY (last {recent} of each) ===")
    print(f"Telemetry dir: {TELEMETRY_DIR}")
    print(f"Bind events:    {len(binds)}")
    print(f"Spread events:  {len(spreads)}")
    print(f"Episode events: {len(episodes)}")
    print()

    if binds:
        print("--- Recent binds (modality / from_fairy) ---")
        sources = Counter(b.get("source", "?") for b in binds)
        for src, n in sources.most_common(10):
            print(f"  {n:5d}  {src}")
        print()

    if spreads:
        print("--- Recent spreads (source path) ---")
        paths = Counter((s.get("chemistry_params") or {}).get("source", "?") for s in spreads)
        for path, n in paths.most_common(10):
            print(f"  {n:5d}  {path}")
        print()

    if episodes:
        print(f"--- Last {min(5, len(episodes))} thought episodes ---")
        for ep in episodes[-5:]:
            dur_ms = ep.get("duration_ms", 0)
            print(f"  [{fmt_ts(ep.get('start_ts', 0))}] "
                  f"id={ep.get('episode_id', '?')[:24]:24s} "
                  f"trigger={ep.get('trigger', '?'):20s} "
                  f"dur={dur_ms:7.0f}ms")
            extra = ep.get("extra") or {}
            preview = extra.get("input_preview", "") or ""
            if preview:
                print(f"      input: {preview[:80]}")
            aer_s = fmt_aer_top(ep.get("aer_at_start") or [])
            aer_e = fmt_aer_top(ep.get("aer_at_end") or [])
            print(f"      AER start: {aer_s}")
            print(f"      AER end:   {aer_e}")
            tracers = ep.get("tracers_active") or []
            if tracers:
                print(f"      tracers active: {len(tracers)}")
        print()


def show_episodes(n: int = 10) -> None:
    episodes = load_stream("episode", limit=n)
    if not episodes:
        print("(no episode events)")
        return
    print(f"=== LAST {len(episodes)} THOUGHT EPISODES ===\n")
    for ep in episodes:
        dur_ms = ep.get("duration_ms", 0)
        print(f"[{fmt_ts(ep.get('start_ts', 0))}] {ep.get('episode_id', '?')}")
        print(f"  trigger:  {ep.get('trigger', '?')}")
        print(f"  duration: {dur_ms:.0f}ms")
        extra = ep.get("extra") or {}
        if extra.get("input_preview"):
            print(f"  input:    {extra['input_preview']}")
        print(f"  AER@start: {fmt_aer_top(ep.get('aer_at_start') or [])}")
        print(f"  AER@end:   {fmt_aer_top(ep.get('aer_at_end') or [])}")
        tracers = ep.get("tracers_active") or []
        print(f"  tracers:   {len(tracers)} active")
        print()


def show_binds(n: int = 50) -> None:
    binds = load_stream("bind", limit=n)
    if not binds:
        print("(no bind events)")
        return
    print(f"=== LAST {len(binds)} BIND EVENTS ===\n")
    for b in binds:
        pair = b.get("pair", ["?", "?"])
        src = b.get("source", "?")
        high = "★" if b.get("high_aer") else " "
        aer = fmt_aer_top(b.get("aer_top") or [])
        print(f"{high} [{fmt_ts(b.get('ts', 0))}] {src:20s} {pair[0]:20s} ↔ {pair[1]:20s} | {aer}")


def show_spreads(n: int = 20) -> None:
    spreads = load_stream("spread", limit=n)
    if not spreads:
        print("(no spread events)")
        return
    print(f"=== LAST {len(spreads)} SPREAD EVENTS ===\n")
    for s in spreads:
        seeds = s.get("seed_keys", [])
        params = s.get("chemistry_params") or {}
        wall = s.get("wall_ms", 0)
        conv = s.get("convergence_count", 0)
        top = s.get("top_visited") or []
        aer = fmt_aer_top(s.get("aer_top") or [])
        path = params.get("source", "?")
        print(f"[{fmt_ts(s.get('ts', 0))}] seed={seeds[0] if seeds else '?'!s:25s} "
              f"path={path:10s} {wall:6.1f}ms conv={conv:3d} | {aer}")
        if top:
            print(f"  top-3 visited: {', '.join(f'{k}={v:.2f}' for k, v in top[:3])}")


def show_aer_correlate(n: int = 200) -> None:
    """
    Crude correlation: for each thought episode, did AER change appreciably,
    and did spread events near that episode reflect the AER state?

    This is the question Slice 0 is supposed to answer empirically.
    """
    episodes = load_stream("episode", limit=n)
    spreads = load_stream("spread", limit=n * 5)
    if not episodes:
        print("(no episodes)")
        return

    print(f"=== AER ↔ CORTEX CORRELATION (last {len(episodes)} episodes) ===\n")
    aer_drifts = []
    for ep in episodes:
        start = {b: v for b, v in (ep.get("aer_at_start") or [])}
        end = {b: v for b, v in (ep.get("aer_at_end") or [])}
        # L1 distance over shared bands
        bands = set(start) & set(end)
        if not bands:
            continue
        drift = sum(abs(start[b] - end[b]) for b in bands) / len(bands)
        aer_drifts.append((ep.get("start_ts", 0), drift, ep.get("episode_id", "?")))

    if aer_drifts:
        avg = sum(d for _, d, _ in aer_drifts) / len(aer_drifts)
        max_drift = max(aer_drifts, key=lambda t: t[1])
        print(f"Average AER drift per episode: {avg:.4f}")
        print(f"Max drift: {max_drift[1]:.4f} on episode {max_drift[2]} at {fmt_ts(max_drift[0])}")
        print(f"(low average = AER state stable across episodes; high = state shifts during thinking)")
    print()

    # For each episode, count spreads in its time window
    print("Spread events per episode (within episode time window):")
    for ep in episodes[-10:]:
        s_ts = ep.get("start_ts", 0)
        e_ts = ep.get("end_ts", 0)
        nearby = [s for s in spreads if s_ts <= s.get("ts", 0) <= e_ts]
        print(f"  {ep.get('episode_id', '?')[:24]:24s} "
              f"({(e_ts - s_ts) * 1000:.0f}ms): {len(nearby)} spreads")


def main():
    parser = argparse.ArgumentParser(description="Slice 0 telemetry reader")
    parser.add_argument("--recent", type=int, default=50, help="Number of records to load per stream")
    parser.add_argument("--episodes", type=int, help="Show last N thought episodes")
    parser.add_argument("--binds", type=int, help="Show last N bind events")
    parser.add_argument("--spreads", type=int, help="Show last N spread events")
    parser.add_argument("--aer-correlate", action="store_true", help="AER vs cortex deltas")
    args = parser.parse_args()

    if args.episodes:
        show_episodes(args.episodes)
    elif args.binds:
        show_binds(args.binds)
    elif args.spreads:
        show_spreads(args.spreads)
    elif args.aer_correlate:
        show_aer_correlate(args.recent)
    else:
        show_summary(args.recent)


if __name__ == "__main__":
    main()
