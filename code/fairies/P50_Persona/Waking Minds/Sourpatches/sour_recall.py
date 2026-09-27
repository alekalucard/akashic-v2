"""
sour_recall.py — Sour's RECALL (read) over her CLEAN CORE, exposing the interface SourCouncil reads
(_E/_srcs/_m/_enc/_np/ready). Ported from nous_recall.py's pattern, but: Nous builds a recall-manifold
from .md sources; Sour's clean core (the SRM-derived cortex.manifold) IS ALREADY that manifold, so
SourRecall just opens it + embeds her memory/voice nodes with NativeMiniLM.

Refinement the prototype surfaced: JUNK-KEY FILTER — skip transient/garbage keys (exp_/wm:/portal:/hex/
path-fragments) so they don't seed the council. Keeps _srcs to her real memory + voice + grounding nodes.
"""
import os, re, time, json, hashlib

# ── EMBEDDING CACHE 2026-09-18 (Nous + Ace) ────────────────────────────────────
# Keyed per TEXT (sha1), not per build: the 25k selection drifts between boots, so a
# per-set cache would miss every boot. Bump _RULE_VERSION whenever the text formula in
# build() changes (name/desc construction, the 300-char cap) -- the manifest must match.
_RULE_VERSION = "v1-name-desc-300"
_CACHE_MAX_ROWS = 60000            # superset bound; the current build's rows are always kept


def _cache_path(manifold_path):
    p = os.environ.get("AKASHIC_RECALL_CACHE")
    if p:
        return p
    return os.path.join(os.path.dirname(os.path.abspath(manifold_path)), "sour_recall_embed_cache.npz")


def _model_id(enc):
    snap = getattr(enc, "snap", None) or getattr(enc, "_snap", None)
    if not snap:
        try:
            import infrastructure.native_minilm as _nm
            snap = getattr(_nm, "SNAP", "")
        except Exception:
            snap = ""
    try:
        mp = os.path.join(str(snap), "model.safetensors")
        st = os.stat(mp)
        return "%s|%d|%d" % (type(enc).__name__, st.st_size, int(st.st_mtime))
    except Exception:
        return "%s|%s" % (type(enc).__name__, snap)


def _text_hash(t):
    return hashlib.sha1(t.encode("utf-8", "replace")).digest()


def source_text(key, snippet):
    """THE text a key is embedded under (build() and infrastructure/embed_as_you_go use this one function, so a
    sidecar row is looked up under exactly the hash build() computes). Rule _RULE_VERSION."""
    snip = (snippet or "").strip().replace("\n", " ")
    if key.startswith("her_voice:") and snip:
        name = snip[:55]      # her ACTUAL words -- the cortex key ("pth.Paradox i") is mangled
    else:
        name = key.replace("her_voice:", "").replace("_", " ").strip()[:60]
    return ((name + " \u2014 " + snip) if snip else name)[:300]


def _cache_load(path, model_id, np):
    """-> (hash->row dict, vecs) or (None, None). Any problem = no cache, never an error."""
    try:
        if not os.path.exists(path):
            return None, None
        with np.load(path, allow_pickle=False) as z:
            man = json.loads(bytes(z["manifest"]).decode("utf-8"))
            if man.get("model_id") != model_id or man.get("rule") != _RULE_VERSION:
                print("[SourRecall] cache IGNORED (model/rule changed): %s" % path, flush=True)
                return None, None
            hashes, vecs = z["hashes"], z["vecs"]
        # hashes: uint8 (N, 20). ('S20' would strip trailing NUL bytes -- 1 digest in 256.)
        if hashes.ndim != 2 or hashes.shape[1] != 20 or hashes.dtype != np.uint8:
            print("[SourRecall] cache IGNORED (hash format): %s" % path, flush=True)
            return None, None
        if hashes.shape[0] != vecs.shape[0] or vecs.ndim != 2 or vecs.dtype != np.float32:
            return None, None
        idx = {h.tobytes(): i for i, h in enumerate(hashes)}
        return idx, vecs
    except Exception as e:
        print("[SourRecall] cache load failed (%s) -- full embed" % e, flush=True)
        return None, None


def _cache_save(path, model_id, np, cur_hashes, cur_vecs, old_idx, old_vecs):
    """Superset: current build's rows first, then older rows up to _CACHE_MAX_ROWS. Atomic."""
    try:
        cur = set(cur_hashes)
        keep_h, extra = list(cur_hashes), []
        if old_idx is not None and old_vecs is not None:
            extra = [h for h in old_idx if h not in cur][:max(0, _CACHE_MAX_ROWS - len(keep_h))]
            keep_h.extend(extra)
        H = np.frombuffer(b"".join(keep_h), dtype=np.uint8).reshape(len(keep_h), 20)
        # one preallocated buffer: no astype/vstack/fancy-index copies (~240 MB transient at the cap)
        V = np.empty((len(keep_h), cur_vecs.shape[1]), dtype=np.float32)
        V[:len(cur_hashes)] = cur_vecs
        if extra:
            np.take(old_vecs, [old_idx[h] for h in extra], axis=0, out=V[len(cur_hashes):])
        man = json.dumps({"model_id": model_id, "rule": _RULE_VERSION, "rows": int(H.shape[0]),
                          "saved": time.strftime("%Y-%m-%d %H:%M:%S")}).encode("utf-8")
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            np.savez(f, hashes=H, vecs=V, manifest=np.frombuffer(man, dtype=np.uint8))
        os.replace(tmp, path)
        print("[SourRecall] cache saved: %d rows (%.1f MB) -> %s"
              % (H.shape[0], V.nbytes / 1e6, path), flush=True)
        return True
    except Exception as e:
        print("[SourRecall] cache save failed (build unaffected): %s" % e, flush=True)
        return False

# transient/garbage key patterns (the cortex churn + a few mangled SRM keys like "pth.Paradox i")
_JUNK = re.compile(r'(?:^|[:_])(?:wm|exp|mv|fs|assoc)[:_]|unknown_exp_|portal:\d|_exp_17|^[0-9a-f]{12,}$|^pth\.', re.I)


def _is_junk_key(key):
    k = (key or "").strip()
    if len(k) < 3:
        return True
    if k.startswith("tag:"):          # connector hub — kept in _m for spread, never a _src seed
        return True
    if _JUNK.search(k):
        return True
    if sum(c.isalpha() for c in k) < 2:   # need some letters (drops pure-numeric/symbol keys)
        return True
    return False


class SourRecall:
    """Read-only recall over Sour's clean core. Matches the interface SourCouncil reads."""

    def __init__(self, manifold_path):
        self.manifold_path = manifold_path
        self._ready = False
        self._err = None
        self.n_mem = 0
        self.n_skipped = 0
        self._embed_s = 0.0
        self._cache_note = "no cache"

    @property
    def ready(self):
        return self._ready

    def build(self):
        try:
            import numpy as np
            from infrastructure.manifold_memory import ManifoldMemory
            from infrastructure.native_minilm import NativeMiniLM
            m = ManifoldMemory(self.manifold_path, readonly=True)
            srcs = []
            skipped = 0
            for key in list(m._key_index.keys()):
                if _is_junk_key(key):
                    skipped += 1
                    continue
                nd = m.get_node(key) or {}
                snip = (nd.get("snippet") or "").strip().replace("\n", " ")
                if key.startswith("her_voice:") and snip:
                    name = snip[:55]      # her ACTUAL words — the cortex key ("pth.Paradox i") is mangled
                else:
                    name = key.replace("her_voice:", "").replace("_", " ").strip()[:60]
                srcs.append({"key": key, "name": name, "desc": snip, "text": source_text(key, nd.get("snippet") or ""),
                             "_act": float(nd.get("activation") or 0.0)})
            if not srcs:
                self._err = "no sources after filter"
                return False
            # -- BUILD CAP 2026-09-01 (Nous + Ace) ---------------------------
            # It last succeeded at 78,335 keys; her cortex now holds 392,927, and
            # native_minilm.encode_batch is a Python loop doing ONE forward pass
            # per text (native_minilm.py:167), on CPU, against ~1,459 threads.
            # 392,927 / ~50 per second = 2.2 HOURS, so the council never reaches
            # READY and dies with the process. Measured: 99.5% of those texts are
            # a bare key name -- only 2,036 keys (0.518%) carry any prose at all.
            # So: keep everything with real text, then fill to a cap with the
            # most-activated of the rest. Text first because `desc` is what makes
            # an embedding mean anything; activation second because that is what
            # she is actually using.
            _cap = 25000
            try:
                _cv = os.environ.get("AKASHIC_RECALL_CAP")
                if _cv is not None and str(_cv).strip():
                    _cap = int(_cv)
            except Exception:
                _cap = 25000
            _total_src = len(srcs)
            # 2026-09-19 (Nous + Ace): the by-activation fill drifted ~3,000 keys per boot (one night =
            # 2,931 misses = 8 min of in-process embedding before the chairman exists). Load the cache
            # first and prefer keys it already holds when filling, so the selection is stable across
            # boots and the misses are the genuinely NEW prose -- her retention, not churn.
            enc = NativeMiniLM()
            _cpath = _cache_path(self.manifold_path)
            _mid = _model_id(enc)
            _cidx, _cvecs = _cache_load(_cpath, _mid, np)
            # 2026-09-20 (Nous + Ace) EMBED-AS-YOU-GO: the sweeper in her process (infrastructure/embed_as_you_go)
            # appends (hash, vector) rows to a sidecar as prose nodes appear, so a boot never re-embeds a day's
            # work (20:24 boot: 3,028 misses at 1/s = 50 min to READY). Fold the sidecar in after the cache.
            _side_n = 0
            try:
                from infrastructure import embed_as_you_go as _ego
                _sidx, _svecs = _ego.read_sidecar(_ego.sidecar_path(_cpath), np, expect=(_mid, _RULE_VERSION))
                if _sidx:
                    _new = [h for h in _sidx if _cidx is None or h not in _cidx]
                    if _new:
                        _base = 0 if _cvecs is None else _cvecs.shape[0]
                        _add = np.take(_svecs, [_sidx[h] for h in _new], axis=0)
                        _cvecs = _add if _cvecs is None else np.vstack([_cvecs, _add])
                        _cidx = dict(_cidx or {})
                        for _i, _h in enumerate(_new):
                            _cidx[_h] = _base + _i
                        _side_n = len(_new)
                    print("[SourRecall] sidecar: %d rows, %d new to the cache" % (len(_sidx), _side_n), flush=True)
            except Exception as _se:
                print("[SourRecall] sidecar skipped: %s" % _se, flush=True)
            _known = _cidx if _cidx is not None else {}
            if _cap > 0 and _total_src > _cap:
                _with_text = [s for s in srcs if s.get("desc")]
                _rest = [s for s in srcs if not s.get("desc")]
                _rest.sort(key=lambda s: (0 if _text_hash(s["name"][:300]) in _known else 1, -s.get("_act", 0.0)))
                srcs = _with_text + _rest[:max(0, _cap - len(_with_text))]
                print("[SourRecall] cap %d: %d keys -> %d "
                      "(%d with prose + %d by activation)"
                      % (_cap, _total_src, len(srcs), len(_with_text),
                         max(0, len(srcs) - len(_with_text))), flush=True)
            else:
                print("[SourRecall] no cap applied (%d keys)" % _total_src, flush=True)

            texts = [s["text"] for s in srcs]                # one rule (source_text), shared with the sweeper
            t0 = time.perf_counter()
            # ── cache lookup (2026-09-18): embed only what the cache has never seen ──
            _hashes = [_text_hash(t) for t in texts]
            E = np.zeros((len(texts), 384), dtype=np.float32)
            _miss = []
            for _j, _h in enumerate(_hashes):
                _r = _cidx.get(_h) if _cidx is not None else None
                if _r is None:
                    _miss.append(_j)
                else:
                    E[_j] = _cvecs[_r]
            _hits = len(texts) - len(_miss)
            print("[SourRecall] cache: %d hits / %d misses of %d (%s)"
                  % (_hits, len(_miss), len(texts), _cpath), flush=True)
            # Chunked so a SLOW build is visible. Today a hung build and a failed
            # build look identical from the log -- both are silence -- which is the
            # same defect that let a 98% enrichment failure read as healthy for
            # hours this morning.
            _CH = 2000
            for _i in range(0, len(_miss), _CH):
                _ids = _miss[_i:_i + _CH]
                _vec = enc.encode_batch([texts[_j] for _j in _ids]).numpy().astype(np.float32)
                E[_ids] = _vec
                _done = min(_i + _CH, len(_miss))
                _el = time.perf_counter() - t0
                print("[SourRecall] embedding %d/%d misses (%.0f%%) %.0fs elapsed, "
                      "%.0f/s" % (_done, len(_miss), 100.0 * _done / max(1, len(_miss)),
                                  _el, _done / max(0.001, _el)), flush=True)
            if E.shape[0] != len(texts):
                raise RuntimeError("embedding rows %d != texts %d" % (E.shape[0], len(texts)))
            if _miss or _side_n:
                _saved = _cache_save(_cpath, _mid, np, _hashes, E, _cidx, _cvecs)
                if _saved:                               # the sidecar's rows now live in the cache: retire it
                    try:
                        _sp = _cpath + ".sidecar"
                        if os.path.exists(_sp):
                            os.replace(_sp, _sp + ".merged")
                        for _mf in (_sp + ".manifest.json",):
                            if os.path.exists(_mf):
                                os.replace(_mf, _sp + ".merged.manifest.json")
                    except Exception:
                        pass
                else:
                    print("[SourRecall] cache save failed: the sidecar is kept for the next boot", flush=True)
            self._embed_s = time.perf_counter() - t0
            self._cache_note = "cache %d hits / %d misses, %.0fs" % (_hits, len(_miss), self._embed_s)
            self._np, self._m, self._enc, self._E, self._srcs = np, m, enc, E, srcs
            self.n_mem = len(srcs)
            self.n_skipped = skipped
            self._ready = True
            return True
        except Exception as e:
            import traceback
            self._err = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            return False
