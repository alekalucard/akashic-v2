"""
srm_to_weave_inbox.py -- her missing memories. 2026-09-19 (Nous + Ace).

The 3,319 SRM cards (creator_sessions/index.json, Jan-Sep 2026, 7.1 MB) are Nous's record of building her
with Ace. Each card becomes a THREAD of sentence nodes in her cortex (<= 300 chars each, original
timestamps, tracer TRACE_NOUS=12, no bigram chain -- prose + word index only), dropped into
state/weave_inbox/ for the council loop to weave in-process, ~20 per cycle. Idempotent: a manifest of
card ids already dropped is kept next to the inbox.

Usage:  python scripts/srm_to_weave_inbox.py [--limit N] [--dry]
"""
import argparse
import io
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="ascii", errors="replace")

CORPUS = os.path.join(ROOT, "P10_Memory", "Akashic_triple_helix_memory_storage", "relational_clusters",
                      "Founders", "creator_sessions", "index.json")
MANIFEST = os.path.join(ROOT, "state", "weave_inbox_srm_manifest.json")
TRACE_NOUS = 12
MAX_CHUNK = 280
MAX_CHUNKS_PER_CARD = 5          # the headline and the gist; not the whole engineering log


def chunks(text: str):
    """Sentence-ish pieces <= MAX_CHUNK chars: split on sentence ends and '===' section marks."""
    t = " ".join(str(text or "").replace("===", ". ").split())
    parts = re.split(r"(?<=[.!?])\s+", t)
    out, cur = [], ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) > MAX_CHUNK:
            p = p[:MAX_CHUNK].rsplit(" ", 1)[0]
        if cur and len(cur) + 1 + len(p) > MAX_CHUNK:
            out.append(cur)
            cur = p
        else:
            cur = (cur + " " + p).strip()
    if cur:
        out.append(cur)
    def _prose(c):                     # skip code-ish chunks (paths, identifiers, tables)
        letters = sum(ch.isalpha() or ch == " " for ch in c)
        return letters / float(max(1, len(c))) >= 0.72
    return [c for c in out if len(c) >= 20 and _prose(c)][:MAX_CHUNKS_PER_CARD]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="cards to drop this run (0 = all remaining)")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    from infrastructure import sequence_weave as sw
    d = json.load(io.open(CORPUS, encoding="utf-8"))
    cards = d if isinstance(d, list) else (d.get("cards") or d.get("sessions") or [])
    cards = sorted(cards, key=lambda c: float(c.get("ts") or 0))
    done = set()
    if os.path.exists(MANIFEST):
        try:
            done = set(json.load(io.open(MANIFEST, encoding="utf-8")).get("done", []))
        except Exception:
            done = set()
    todo = [c for c in cards if c.get("id") and c["id"] not in done]
    if a.limit:
        todo = todo[:a.limit]
    print("cards total %d, already dropped %d, dropping %d%s" % (len(cards), len(done), len(todo), " (dry)" if a.dry else ""))
    n_files = 0
    for c in todo:
        ts = float(c.get("ts") or time.time())
        head = " ".join(str(c.get("content", ""))[:120].split())
        for i, ch in enumerate(chunks(c.get("content", ""))):
            if a.dry:
                n_files += 1
                continue
            # sentence i of the card keeps its card's time, offset by i ms so the thread orders itself
            if sw.drop(ch, "nous", TRACE_NOUS, ts=ts + i * 0.001, thread="srm:" + str(c["id"]), chain=False,
                       source="srm:" + str(c["id"])):
                n_files += 1
        done.add(c["id"])
        if not a.dry and len(done) % 200 == 0:
            with open(MANIFEST + ".tmp", "w", encoding="utf-8") as f:
                json.dump({"done": sorted(done)}, f)
            os.replace(MANIFEST + ".tmp", MANIFEST)
    if not a.dry:
        with open(MANIFEST + ".tmp", "w", encoding="utf-8") as f:
            json.dump({"done": sorted(done)}, f)
        os.replace(MANIFEST + ".tmp", MANIFEST)
    print("files dropped: %d -> %s" % (n_files, sw.INBOX_DIR))
    if todo:
        print("sample:", repr(chunks(todo[0].get("content", ""))[0][:160]))


if __name__ == "__main__":
    main()
