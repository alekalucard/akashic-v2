"""
sequence_weave.py -- the cortex holds SEQUENCE. 2026-09-19 (Nous + Ace).

    "what we want in the cortex is the sequential and linear nodes connected in sequence with edges.
     that would create a thought chain habit ready for recall or to reuse and manipulate ... like the
     wheels on the bus go round and round and then change it to the wheels of the bus go up and down.
     a partial overlay of thought patterns. much like star constellations."            -- Ace, 09-18

Measured before this existed: 99.9% of her 6.88M edges were `coactivate` -- the manifold knew that words
happened NEAR each other, never that they happened IN ORDER; and a night's sleep kept the associations
("named_pyraxia") but lost every sentence, because nothing stored one.

What a turn becomes here (direct calls on the live ManifoldMemory handle -- postal binds drop rel_type):
  * a TURN node   `turn:<speaker>:<ms>`  whose snippet IS the sentence -> SourRecall embeds prose nodes
                  first, so the council can recall what was SAID, not just that words were near.
  * BIGRAM stars  `w1_w2` (unprefixed: his "wheels on the bus" and hers share the same stars), joined
                  in order by REL_FOLLOWED_BY edges. Edges are undirected in this manifold; direction is
                  implicit -- consecutive bigrams overlap by one word, so a walker knows which way is on.
  * WORD stars    `w:<content word>` -> REL_PART_OF -> the turn (the index that answers "what was said
                  about pyraxia").
  * the THREAD    previous turn -> this turn, REL_FOLLOWED_BY: the linear lived conversation, in the cortex.

Overlay is free: weaving "the wheels on the bus go up and down" adds one FOLLOWED_BY branch at `bus_go`;
the walker picks the heavier branch (weight x affect) -- a habit -- and the lighter one is the variation.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Dict, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
INBOX_DIR = os.environ.get("AKASHIC_WEAVE_INBOX") or os.path.join(_ROOT, "state", "weave_inbox")

_STOP = {"the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "is", "are", "was", "were", "be",
         "it", "its", "i", "im", "i'm", "you", "your", "my", "me", "we", "our", "he", "she", "they", "them", "this",
         "that", "these", "those", "for", "with", "as", "by", "from", "so", "if", "then", "than", "do", "does",
         "did", "have", "has", "had", "not", "no", "yes", "just", "like", "up", "down", "out", "about", "into",
         "what", "who", "how", "when", "where", "why", "which", "there", "here", "too", "very", "can", "could",
         "would", "should", "will", "also", "okay", "ok", "oh", "yeah", "lol", "hehe", "aye", "of", "s", "t"}
_MAX_BIGRAMS = 60
_BASE_W = 0.35
_LOCK = threading.Lock()
_LAST_TURN: Dict[str, str] = {}          # thread -> last turn key ("live" = the conversation)
_STATS = {"turns": 0, "bigrams": 0, "edges": 0, "fail": 0}
# Measured 2026-09-19 11:17-11:25: 40 imported sentences per council cycle made the cycle 3-4 MINUTES,
# because link() scans a node's whole neighbour list, and the word index turns 'ace', 'sour', 'nous',
# 'memory', 'system' into hubs with thousands of PART_OF edges. A word that is in every sentence is no
# use for recall anyway: skip the standing hubs and any word seen more than _HUB_MAX times this boot.
_WORD_FREQ: Dict[str, int] = {}
_HUB_MAX = 150
_HUBS = {"ace", "sour", "sourpatches", "nous", "memory", "system", "fairy", "fairies", "cortex", "thought",
         "thoughts", "thinking", "time", "something", "things", "thing", "really", "right", "now", "still",
         "even", "way", "make", "made", "get", "got", "see", "know", "one", "two", "day", "today", "session"}
_SEQ = [0]                         # uniqueness within one millisecond (two fairy copies, fast tests)


def tokens(text: str) -> List[str]:
    t = str(text or "").lower().replace("’", "'")
    ws = re.findall(r"[a-z0-9]+(?:'[a-z]+)?", t)
    return [w.replace("'", "") for w in ws if w]


def bigrams(text: str) -> List[str]:
    ws = tokens(text)
    return ["%s_%s" % (ws[i], ws[i + 1]) for i in range(len(ws) - 1)][:_MAX_BIGRAMS]


def content_words(text: str) -> List[str]:
    out: List[str] = []
    for w in tokens(text):
        if w not in _STOP and len(w) >= 3 and w not in out:
            out.append(w)
    return out[:40]


def _handle():
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
        acf = get_association_cortex()
        am = getattr(acf, "_akashic_cortex_region", None) if acf is not None else None
        if am is None or type(am).__name__ != "ManifoldMemory":
            return None
        return am
    except Exception:
        return None


def weave_turn(text: str, speaker: str, tracer_id: int, affect: Optional[Dict] = None, am=None,
               ts_ms: Optional[int] = None, thread: str = "live", chain: bool = True,
               index_words: int = 40) -> Dict:
    """Write one turn: the sentence as a prose node, its bigram chain (chain=True), its word index, and
    the thread link to the previous turn of the same thread. ts_ms keeps an import's original time."""
    text = " ".join(str(text or "").split())
    if len(text) < 8:
        return {}
    am = am or _handle()
    if am is None:
        return {}
    try:
        from infrastructure.manifold_memory import (NTYPE_ENTITY, REGION_SEMANTIC, REL_FOLLOWED_BY, REL_PART_OF)
        w = _BASE_W
        try:
            v = float((affect or {}).get("valence", 0.0) or 0.0)
            w = min(0.9, _BASE_W + 0.25 * min(1.0, abs(v)))       # felt turns weigh more
        except Exception:
            pass
        ts_ms = int(ts_ms) if ts_ms else int(time.time() * 1000)
        with _LOCK:
            _SEQ[0] = (_SEQ[0] + 1) % 1000
            _n = _SEQ[0]
        turn_key = "turn:%s:%d%03d" % (re.sub(r"[^a-z]", "", speaker.lower())[:8] or "x", ts_ms, _n)
        edges = 0
        with _LOCK:
            if am.upsert_node(turn_key, activation=0.6, count=1, degree=0, coord_str="050.000.000", snippet=text[:600],
                              node_type=NTYPE_ENTITY, region=REGION_SEMANTIC, tracer_id=tracer_id, parent_slot=0) < 0:
                _STATS["fail"] += 1
                return {}
            bg = bigrams(text) if chain else []
            for k in bg:
                am.upsert_node(k, activation=0.5, count=1, degree=0, coord_str="", snippet="",
                               node_type=NTYPE_ENTITY, region=REGION_SEMANTIC, tracer_id=tracer_id, parent_slot=0)
            for a, b in zip(bg, bg[1:]):
                if a != b and am.link(a, b, weight=w, rel_type=REL_FOLLOWED_BY, tracer_id=tracer_id):
                    edges += 1
            if bg and am.link(turn_key, bg[0], weight=0.5, rel_type=REL_FOLLOWED_BY, tracer_id=tracer_id):
                edges += 1
            for cw in content_words(text)[:max(0, int(index_words))]:
                if cw in _HUBS:
                    continue
                _WORD_FREQ[cw] = _WORD_FREQ.get(cw, 0) + 1
                if _WORD_FREQ[cw] > _HUB_MAX:
                    continue
                wk = "w:" + cw
                am.upsert_node(wk, activation=0.5, count=1, degree=0, coord_str="", snippet="",
                               node_type=NTYPE_ENTITY, region=REGION_SEMANTIC, tracer_id=tracer_id, parent_slot=0)
                if am.link(wk, turn_key, weight=0.4, rel_type=REL_PART_OF, tracer_id=tracer_id):
                    edges += 1
            prev = _LAST_TURN.get(thread)
            if prev and prev != turn_key and am.link(prev, turn_key, weight=0.5, rel_type=REL_FOLLOWED_BY, tracer_id=tracer_id):
                edges += 1
            _LAST_TURN[thread] = turn_key
            _STATS["turns"] += 1
            _STATS["bigrams"] += len(bg)
            _STATS["edges"] += edges
        return {"turn": turn_key, "bigrams": len(bg), "edges": edges, "weight": round(w, 2)}
    except Exception as e:
        _STATS["fail"] += 1
        print("[Weave] failed: %s" % e, flush=True)
        return {}


# 2026-09-20 (Ace): Nous's build notes are not for her recall -- a digest line "Nous wrote: ... Dr. Zero ..." became
# a doctor she hunted for five hours. Speakers listed here are skipped by the reader and held by the drainer.
_RECALL_EXCLUDE = {s.strip() for s in os.environ.get("AKASHIC_WEAVE_RECALL_EXCLUDE", "nous").split(",") if s.strip()}
HELD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state", "weave_inbox_nous_held")


def recall_lines(text: str, am=None, limit: int = 3, max_age_s: Optional[float] = None) -> List[Dict]:
    """Sentences on record that share content words with `text`, most recent first, with who said them.
    Turns by an excluded speaker (Nous's build notes) are never returned."""
    am = am or _handle()
    if am is None:
        return []
    try:
        from infrastructure.manifold_memory import REL_PART_OF
        seen: Dict[str, int] = {}
        for cw in content_words(text)[:8]:
            for k, wt in am.get_neighbors("w:" + cw, limit=40, rel_filter=REL_PART_OF):
                if str(k).startswith("turn:"):
                    seen[k] = seen.get(k, 0) + 1
        if not seen:
            return []
        now_ms = int(time.time() * 1000)

        def _ts(k):
            try:
                return int(k.rsplit(":", 1)[1]) // 1000      # key = <ms><3-digit seq>
            except Exception:
                return 0
        ranked = sorted(seen.items(), key=lambda kv: (-kv[1], -_ts(kv[0])))
        out: List[Dict] = []
        for k, hits in ranked:
            if max_age_s is not None and (now_ms - _ts(k)) / 1000.0 > max_age_s:
                continue
            n = am.get_node(k) or {}
            snip = (n.get("snippet") or "").strip()
            if not snip:
                continue
            who = k.split(":")[1] if k.count(":") >= 2 else "?"
            if who in _RECALL_EXCLUDE:
                continue
            out.append({"turn": k, "who": who, "text": snip, "age_s": max(0, (now_ms - _ts(k)) / 1000.0), "hits": hits})
            if len(out) >= limit:
                break
        return out
    except Exception as e:
        print("[Weave] recall failed: %s" % e, flush=True)
        return []


def walk(start: str, am=None, max_len: int = 30, tracer_ids: Optional[set] = None) -> Tuple[List[str], List[str]]:
    """Follow FOLLOWED_BY edges forward from a bigram star, heaviest branch first (direction = word overlap).
    Returns (words, branch_points)."""
    am = am or _handle()
    if am is None:
        return [], []
    from infrastructure.manifold_memory import REL_FOLLOWED_BY
    cur = start
    words = cur.split("_") if "_" in cur else [cur]
    branches: List[str] = []
    seen = {cur}
    for _ in range(max_len):
        tail = cur.rsplit("_", 1)[-1]
        nxt = [(k, wt) for k, wt in am.get_neighbors(cur, limit=30, rel_filter=REL_FOLLOWED_BY, tracer_ids=tracer_ids)
               if "_" in str(k) and str(k).split("_", 1)[0] == tail and k not in seen and not str(k).startswith("turn:")]
        if not nxt:
            break
        nxt.sort(key=lambda kv: -kv[1])
        if len(nxt) > 1:
            branches.append("%s -> {%s}" % (cur, ", ".join(k for k, _ in nxt[:3])))
        cur = nxt[0][0]
        seen.add(cur)
        words.append(cur.split("_", 1)[1])
    return words, branches


def sentence_cut(text: str, n: int = 240) -> str:
    """Cut at the last sentence end within n characters; failing that at the last word, marked. Never mid-word.
    2026-09-20 -- Sour: "my memories are like they came through a wood chipper". They were: every quote she was
    handed back was sliced at 160 characters wherever the 160th fell ('you wrote your own brain seed which could')."""
    t = " ".join(str(text or "").split())
    if len(t) <= n:
        return t
    head = t[:n]
    m = max(head.rfind(". "), head.rfind("! "), head.rfind("? "), head.rfind(".\""), head.rfind("!\""), head.rfind("?\""))
    if m >= int(n * 0.45):
        return head[:m + 1]
    return head.rsplit(" ", 1)[0] + "..."


def render_memory(lines: List[Dict], limit: int = 2, quote_chars: int = 240) -> str:
    """One prompt line: what is on record about the words he used -- whole sentences, not chips."""
    parts = []
    for r in lines[:limit]:
        who = {"ace": "Ace said", "sour": "you said", "nous": "Nous wrote", "eyes": "you read on your screen"}.get(r["who"], r["who"] + " said")
        age = r["age_s"]
        when = "just now" if age < 120 else ("%.0f min ago" % (age / 60) if age < 7200 else ("%.0f h ago" % (age / 3600) if age < 172800 else "%.0f days ago" % (age / 86400)))
        parts.append("%s, %s: \"%s\"" % (who, when, sentence_cut(r["text"], quote_chars)))
    return ("You remember " + "; ".join(parts) + ".") if parts else ""


def stats() -> Dict:
    return dict(_STATS)


# ── the inbox: sentences from outside her process ──────────────────────────────
def drop(text: str, speaker: str, tracer_id: int, ts: Optional[float] = None, thread: Optional[str] = None,
         chain: bool = False, affect: Optional[Dict] = None, source: str = "") -> Optional[str]:
    """Producer side (daemon, importers): one JSON file per sentence; the council loop weaves it."""
    text = " ".join(str(text or "").split())
    if len(text) < 8:
        return None
    try:
        os.makedirs(INBOX_DIR, exist_ok=True)
        ts = float(ts or time.time())
        with _LOCK:
            _SEQ[0] = (_SEQ[0] + 1) % 1000
            n = _SEQ[0]
        name = "%013d_%03d_%s.json" % (int(ts * 1000), n, re.sub(r"[^a-z0-9]", "", str(speaker).lower())[:8] or "x")
        path = os.path.join(INBOX_DIR, name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"text": text[:600], "speaker": speaker, "tracer_id": int(tracer_id), "ts": ts,
                       "thread": thread or ("import:" + str(speaker)), "chain": bool(chain),
                       "affect": affect or None, "source": source}, f)
        os.replace(tmp, path)
        return path
    except Exception as e:
        print("[Weave] drop failed: %s" % e, flush=True)
        return None


def drain_inbox(am=None, limit: int = 20, budget_s: float = 6.0) -> int:
    """Consumer side (the council loop, in her process): weave the oldest files -- at most `limit`, at most
    `budget_s` seconds of the loop's time -- and delete them. Returns the count."""
    _t0 = time.time()
    try:
        if not os.path.isdir(INBOX_DIR):
            return 0
        names = sorted(n for n in os.listdir(INBOX_DIR) if n.endswith(".json"))[:max(0, int(limit))]
    except Exception:
        return 0
    if not names:
        return 0
    am = am or _handle()
    if am is None:
        return 0
    done = 0
    for n in names:
        if time.time() - _t0 > budget_s:
            break
        path = os.path.join(INBOX_DIR, n)
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if str(d.get("speaker", "")) in _RECALL_EXCLUDE:              # held, not woven (Ace 2026-09-20)
                try:
                    os.makedirs(HELD_DIR, exist_ok=True)
                    os.replace(path, os.path.join(HELD_DIR, n))
                except Exception:
                    try:
                        os.remove(path)
                    except Exception:
                        pass
                continue
            r = weave_turn(d.get("text", ""), str(d.get("speaker", "x")), int(d.get("tracer_id", 0)),
                           affect=d.get("affect"), am=am, ts_ms=int(float(d.get("ts") or time.time()) * 1000),
                           thread=str(d.get("thread") or "import"), chain=bool(d.get("chain", False)), index_words=14)
            if r:
                done += 1
            os.remove(path)
        except Exception as e:
            print("[Weave] inbox %s failed: %s" % (n, str(e)[:80]), flush=True)
            try:
                os.replace(path, path + ".bad")
            except Exception:
                pass
    if done:
        _STATS["inbox"] = _STATS.get("inbox", 0) + done
        _STATS["inbox_s"] = round(_STATS.get("inbox_s", 0.0) + (time.time() - _t0), 1)
    return done
