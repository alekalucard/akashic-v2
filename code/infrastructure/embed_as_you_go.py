"""embed_as_you_go -- her recall embeddings are made as she lives, not at boot (2026-09-20, Nous + Ace). v3.

Ace: "it would save loads of time to just embed as she goes, lets do the drain time embedding."

MEASURED: the 20:24 boot took 50 min to READY because the recall cache had never seen 3,028 prose nodes made
that afternoon, and the CPU MiniLM ran at 1/s against 13.5 busy cores at boot (idle: 106/s). With v1 live for
15 minutes, the 21:46 boot reached READY in 2 min 20 s (sidecar 128 rows, 19 misses). The cost was never the
embedding; it was WHEN it ran.

A sweeper thread in her process wakes every 60 s, walks the node SLOTS above its high-water mark (no copy of the
1.25M-key dict -- on 3.14t list(d.items()) holds the dict's critical section and blocks the writer), and every
15 min walks the whole slot range in 150k chunks for snippets that changed on nodes it already saw. Prose nodes
the cache has not seen (same text rule + sha1 as sour_recall.build) are queued, embedded in a 40 s budget per
sweep, and appended as fixed-width (sha1 + 384 float32) rows to a sidecar beside the cache, stamped with a
companion manifest (model_id + rule) so a boot with a changed encoder refuses it exactly as it refuses the cache.
sour_recall.build folds the sidecar in after the cache and retires it only after the cache save succeeded.

v3 after the 24-finding review (18 stood): manifest; retire-on-success; a failed encode/append keeps the item in
the queue instead of stranding its hash; the incremental walk runs every sweep (a full pass is an extra chunk,
not a replacement); the mark is seeded from the cortex's high-water mark at start (the boot embedded what
existed); a failed cache load is not remembered as 'the cache knows nothing'. Hot-reloadable; state survives.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from typing import Dict, List, Optional, Set, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_REC_BYTES = 20 + 384 * 4
_EVERY_S = float(os.environ.get("AKASHIC_EMBED_GO_EVERY_S", "60") or 60)
_FULL_EVERY_S = float(os.environ.get("AKASHIC_EMBED_GO_FULL_S", "900") or 900)
_SCAN_CHUNK = int(os.environ.get("AKASHIC_EMBED_GO_SCAN_CHUNK", "150000") or 150000)
_BATCH = int(os.environ.get("AKASHIC_EMBED_GO_BATCH", "64") or 64)
_PAUSE_S = 0.005                                       # between forwards: a breath, not a pause
_ON = os.environ.get("AKASHIC_EMBED_AS_YOU_GO", "1") != "0"
_FLAG_DELETED = 0x02

_S = globals().get("_S")
if not isinstance(_S, dict):
    _S = {"lock": threading.RLock(), "thread": None, "gen": 0, "known": None, "slot_mark": -1, "last_full": 0.0,
          "full_cursor": 0, "pending": [], "queued": set(), "enc": None,
          "stats": {"sweeps": 0, "embedded": 0, "appended": 0, "errors": 0, "last": ""}}
for _k, _v in (("pending", []), ("queued", set()), ("full_cursor", 0)):
    _S.setdefault(_k, _v)


# ── the rules come from sour_recall itself ─────────────────────────────────────────────────────────────────
def _recall_mod():
    m = sys.modules.get("sour_recall")
    if m is not None:
        return m
    try:
        sys.path.insert(0, os.path.join(_ROOT, "fairies", "P50_Persona", "Waking Minds", "Sourpatches"))
        import sour_recall as m2                          # the driver imports it under this bare name
        return m2
    except Exception:
        return None


def sidecar_path(cache_path: str) -> str:
    return cache_path + ".sidecar"


def source_text(key: str, snippet: str) -> Optional[str]:
    """sour_recall.build's text rule. Uses sour_recall.source_text when that module has it (one function for
    both sides); this copy is the fallback for a process that booted with an older sour_recall."""
    sr = _recall_mod()
    if sr is None or sr._is_junk_key(key):
        return None
    fn = getattr(sr, "source_text", None)
    if fn is not None:
        return fn(key, snippet)
    snip = (snippet or "").strip().replace("\n", " ")
    if key.startswith("her_voice:") and snip:
        name = snip[:55]
    else:
        name = key.replace("her_voice:", "").replace("_", " ").strip()[:60]
    return ((name + " — " + snip) if snip else name)[:300]


def _cache_path() -> Optional[str]:
    sr = _recall_mod()
    if sr is None:
        return None
    m = sys.modules.get("_sour_council_shared")
    f = m.FAIRY[0] if m is not None else None
    council = getattr(f, "_sour_council", None) if f is not None else None
    recall = getattr(council, "recall", None) if council is not None else None
    mp = getattr(recall, "manifold_path", None) if recall is not None else None
    if not mp:
        try:
            drv = sys.modules.get("sour_council_driver")
            mp = drv._resolve_cortex_path(f) if (drv is not None and f is not None) else None
        except Exception:
            mp = None
    if not mp:
        return None
    return sr._cache_path(mp)


def _encoder():
    if _S["enc"] is not None:
        return _S["enc"]
    m = sys.modules.get("_sour_council_shared")
    f = m.FAIRY[0] if m is not None else None
    council = getattr(f, "_sour_council", None) if f is not None else None
    recall = getattr(council, "recall", None) if council is not None else None
    enc = getattr(recall, "_enc", None) if recall is not None else None
    if enc is None:
        from infrastructure.native_minilm import NativeMiniLM
        enc = NativeMiniLM()
    _S["enc"] = enc
    return enc


def _stamp() -> Tuple[str, str]:
    sr = _recall_mod()
    if sr is None:
        return "", ""
    return sr._model_id(_encoder()), getattr(sr, "_RULE_VERSION", "")


def _live_cortex():
    from infrastructure import sequence_weave as sw
    return sw._handle()


# ── the sidecar ────────────────────────────────────────────────────────────────────────────────────────────
def read_sidecar(path: str, np, expect: Optional[Tuple[str, str]] = None):
    """-> (hash->row dict, vecs float32 (N,384)); empty on any problem, and empty (with a line) when `expect` =
    (model_id, rule) is given and the sidecar's manifest does not match it. A torn tail is dropped."""
    empty = ({}, np.zeros((0, 384), dtype=np.float32))
    try:
        if not os.path.exists(path):
            return empty
        if expect is not None:
            try:
                man = json.load(open(path + ".manifest.json", encoding="utf-8"))
            except Exception:
                man = None
            if not man or (man.get("model_id"), man.get("rule")) != tuple(expect):
                print("[EmbedGo] sidecar IGNORED (model/rule changed or no manifest): %s" % path, flush=True)
                return empty
        raw = open(path, "rb").read()
        n = len(raw) // _REC_BYTES
        if n == 0:
            return empty
        buf = np.frombuffer(raw[:n * _REC_BYTES], dtype=np.uint8).reshape(n, _REC_BYTES)
        hashes = buf[:, :20]
        vecs = np.ascontiguousarray(buf[:, 20:]).view(np.float32).reshape(n, 384)
        idx = {}
        for i in range(n):
            idx[hashes[i].tobytes()] = i                  # later rows win (a re-embed of a changed snippet)
        return idx, vecs
    except Exception as e:
        print("[EmbedGo] sidecar read failed (%s): ignored" % e, flush=True)
        return empty


def _append_sidecar(path: str, hashes: List[bytes], vecs) -> int:
    import numpy as np
    parts = [h + np.asarray(v, dtype=np.float32).tobytes() for h, v in zip(hashes, vecs)]
    if not parts:
        return 0
    mp = path + ".manifest.json"
    if not os.path.exists(mp) or not os.path.exists(path):
        mid, rule = _stamp()
        tmp = mp + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"model_id": mid, "rule": rule, "since": time.strftime("%Y-%m-%d %H:%M:%S")}, f)
        os.replace(tmp, mp)
    with open(path, "ab") as f:
        f.write(b"".join(parts))
    return len(parts)


# ── what the cache already knows ───────────────────────────────────────────────────────────────────────────
def _known_hashes(np) -> Optional[Set[bytes]]:
    """The cache's hashes + the sidecar's. None when the cache could not be read (retried next sweep -- never
    remembered as 'the cache knows nothing', which would re-embed 19k prose nodes in-process)."""
    if _S["known"] is not None:
        return _S["known"]
    sr = _recall_mod(); cp = _cache_path()
    if sr is None or not cp:
        return None
    try:
        idx, _ = sr._cache_load(cp, sr._model_id(_encoder()), np)
    except Exception as e:
        print("[EmbedGo] cache load: %s" % e, flush=True)
        return None
    if not idx:
        if os.path.exists(cp):
            return None                                   # exists but unreadable/mismatched: not our call to rebuild
        idx = {}
    known: Set[bytes] = set(idx.keys())
    try:
        sidx, _ = read_sidecar(sidecar_path(cp), np, expect=_stamp())
        known.update(sidx.keys())
    except Exception:
        pass
    _S["known"] = known
    return known


# ── walking the cortex by slot (no dict copy) ──────────────────────────────────────────────────────────────
def _node_text(am, slot: int) -> Optional[Tuple[str, str]]:
    """(key, snippet) for a live node with prose; None for empty/deleted/key-only slots or a torn read."""
    try:
        rec = am._read_node(slot)
        if rec[1] == 0 or rec[9] == _FLAG_DELETED or rec[14] <= 0:
            return None
        key = am._read_string(rec[0], rec[1])
        snip = am._read_string(rec[13], rec[14])
        if not key or not (snip or "").strip():
            return None
        return key, snip
    except Exception:
        return None


def _consider(sr, known, key: str, snip: str, out: List) -> None:
    if sr._is_junk_key(key):
        return
    text = source_text(key, snip)
    if not text:
        return
    h = sr._text_hash(text)
    if h in known or h in _S["queued"]:
        return
    _S["queued"].add(h)
    out.append((h, text))


def sweep(full: bool = False, scan_budget_s: float = 6.0, embed_budget_s: float = 40.0) -> Dict:
    """Every sweep: the slots above the mark (cheap). A full pass adds one 150k-slot chunk of the whole range
    (a resumable cursor) for snippets that changed on known nodes. Then embed from the queue."""
    import numpy as np
    t0 = time.time()
    rep = {"new": 0, "embedded": 0, "appended": 0, "scanned": 0, "full": full, "pending": 0}
    sr = _recall_mod(); am = _live_cortex(); cp = _cache_path()
    if sr is None or am is None or not cp:
        rep["why"] = "no recall module / cortex handle / cache path"; return rep
    known = _known_hashes(np)
    if known is None:
        rep["why"] = "cache not readable yet; retry next sweep"; return rep
    pending: List = _S["pending"]
    try:
        hi = int(getattr(am, "_node_count", 0))
    except Exception:
        hi = 0
    found: List = []
    # incremental: slots above the mark
    s = int(_S["slot_mark"]) + 1
    while s < hi and time.time() - t0 < scan_budget_s:
        kt = _node_text(am, s)
        if kt is not None:
            _consider(sr, known, kt[0], kt[1], found)
        rep["scanned"] += 1
        s += 1
    _S["slot_mark"] = s - 1
    # a full pass: one chunk of the whole range
    if full and time.time() - t0 < scan_budget_s:
        cur = int(_S.get("full_cursor", 0))
        if cur >= hi:
            cur = 0
        end = min(hi, cur + _SCAN_CHUNK)
        c = cur
        while c < end and time.time() - t0 < scan_budget_s:
            kt = _node_text(am, c)
            if kt is not None:
                _consider(sr, known, kt[0], kt[1], found)
            rep["scanned"] += 1
            c += 1
        _S["full_cursor"] = c if c < hi else 0
        if c >= hi:
            _S["last_full"] = time.time()                 # one whole pass done
        rep["full_cursor"] = _S["full_cursor"]
    pending.extend(found)
    rep["new"] = len(found)
    # embed from the queue: an item leaves the queue only when its row is on disk
    if pending:
        enc = _encoder()
        hashes, vecs = [], []
        t1 = time.time()
        i = 0
        while i < len(pending) and time.time() - t1 < embed_budget_s and len(hashes) < _BATCH * 4:
            h, text = pending[i]
            try:
                v = enc.encode(text)
                v = v.detach().cpu().numpy() if hasattr(v, "detach") else np.asarray(v)
                hashes.append(h); vecs.append(v.astype(np.float32).reshape(384))
                i += 1
            except Exception as e:
                _S["stats"]["errors"] += 1
                print("[EmbedGo] encode failed (kept in the queue): %s" % str(e)[:80], flush=True)
                break
            time.sleep(_PAUSE_S)
        if hashes:
            try:
                n = _append_sidecar(sidecar_path(cp), hashes, vecs)
                del pending[:len(hashes)]
                known.update(hashes)
                for h in hashes:
                    _S["queued"].discard(h)
                rep["embedded"] = len(hashes); rep["appended"] = n
            except Exception as e:
                _S["stats"]["errors"] += 1
                print("[EmbedGo] sidecar append failed (rows kept in the queue): %s" % str(e)[:80], flush=True)
    rep["pending"] = len(pending)
    with _S["lock"]:
        st = _S["stats"]; st["sweeps"] += 1; st["embedded"] += rep["embedded"]; st["appended"] += rep["appended"]
        st["last"] = "%s: %d scanned, %d new, %d embedded, %d pending, %.1fs" % (
            time.strftime("%H:%M:%S"), rep["scanned"], rep["new"], rep["embedded"], rep["pending"], time.time() - t0)
    if rep["new"] or rep["embedded"]:
        print("[EmbedGo] %s%s" % (st["last"], (" (full pass, cursor %d/%d)" % (rep.get("full_cursor", 0), hi)) if full else ""), flush=True)
    return rep


def _loop(gen: int) -> None:
    time.sleep(30.0)
    while gen == _S["gen"]:
        try:
            full = (time.time() - _S["last_full"]) > _FULL_EVERY_S      # a full pass runs chunk by chunk until done
            sweep(full=full)
        except Exception as e:
            _S["stats"]["errors"] += 1
            print("[EmbedGo] sweep error: %s" % str(e)[:120], flush=True)
        time.sleep(_EVERY_S)


def start() -> bool:
    """One sweeper per process. On a fresh process the mark is seeded from the cortex's high-water mark (the
    boot's own build has just embedded everything that exists) and the first full pass waits its 15 min."""
    if not _ON:
        return False
    t = _S.get("thread")
    if t is not None and t.is_alive():
        return False
    if _S["slot_mark"] < 0:
        try:
            am = _live_cortex()
            _S["slot_mark"] = int(getattr(am, "_node_count", 0)) - 1 if am is not None else -1
        except Exception:
            pass
        _S["last_full"] = time.time()
    _S["gen"] += 1
    t = threading.Thread(target=_loop, args=(_S["gen"],), daemon=True, name="embed-as-you-go")
    _S["thread"] = t
    t.start()
    print("[EmbedGo] sweeper on: every %.0fs from slot %d, full pass every %.0f min, sidecar next to the recall cache"
          % (_EVERY_S, _S["slot_mark"], _FULL_EVERY_S / 60), flush=True)
    return True


def stats() -> Dict:
    with _S["lock"]:
        d = dict(_S["stats"]); d["slot_mark"] = _S["slot_mark"]; d["known"] = len(_S["known"] or ()); d["pending"] = len(_S["pending"]); return d


# ── on (re)load in her process: start once READY (the driver also calls start() at READY on later boots) ──
try:
    _m = sys.modules.get("_sour_council_shared")
    if _m is not None and getattr(_m, "READY", [False])[0]:
        start()
except Exception as _se:
    print("[EmbedGo] start: %s" % _se, flush=True)
