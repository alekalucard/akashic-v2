"""
provenance.py -- who wrote what went into her memory. 2026-09-26 (Nous + Ace, Qwen exit step 0).

Her writers stamp an external model's words exactly like her own: the chairman's lines are woven as speaker
"sour" under TRACE_PERSONAL (sour_council_driver._speak), and the farm's buffer words are bound with
origin_fairy="SourpatchesFairy" -> TRACE_PERSONAL (sourpatches_farm._bind_to_cortex). The node and edge
records have no free field for a source (manifold_memory NODE_STRUCT: bytes 48-63 already hold affect
coupling / paradox residue; tracer_id, coord, snippet and key all change recall or decay). So the label
lives HERE: one append-only JSONL row per write, joined to the cortex by the turn key the weave returns.

Nothing reads this file at runtime: it changes no behaviour. AKASHIC_PROVENANCE=0 turns every write off.
AKASHIC_PROVENANCE_PATH moves the file (default <root>/state/provenance.jsonl).
note() never raises and never blocks on anything but its own lock.
"""
import hashlib
import json
import os
import threading
import time

ON = os.environ.get("AKASHIC_PROVENANCE", "1") != "0"
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.environ.get("AKASHIC_PROVENANCE_PATH") or os.path.join(_ROOT, "state", "provenance.jsonl")
FARM = os.environ.get("AKASHIC_FARM_REMOTE", "").strip() or "local"
_LOCK = threading.Lock()
STATS = {"rows": 0, "fail": 0}
_ANNOUNCED = [False]


def note(kind, source, external, text="", **extra):
    """One row. kind: 'turn' (a woven sentence; extra key= is the cortex node key) | 'bind' (words bound as
    coactivate edges; extra words=). source: 'farm:<lane>' for model text, anything else for hers."""
    if not ON:
        return False
    try:
        row = {"ts": round(time.time(), 3), "kind": str(kind), "source": str(source or "unlabelled"),
               "external": bool(external), "farm": FARM}
        if text:
            t = str(text)
            row["sha1"] = hashlib.sha1(t.encode("utf-8", "replace")).hexdigest()[:16]
            row["chars"] = len(t)
        row.update(extra)
        line = (json.dumps(row, ensure_ascii=True, default=str) + "\n").encode("ascii")   # built + encoded BEFORE open
        with _LOCK:
            os.makedirs(os.path.dirname(PATH), exist_ok=True)
            with open(PATH, "ab") as f:                                                  # append: never truncates
                f.write(line)
        STATS["rows"] += 1
        if not _ANNOUNCED[0]:
            _ANNOUNCED[0] = True
            print("[Provenance] labelling external writes -> %s (AKASHIC_PROVENANCE=0 turns it off)" % PATH, flush=True)
        return True
    except Exception:
        STATS["fail"] += 1
        return False
