"""self_facts.py -- her look, written into her memory as FACTS in Ace's words. 2026-10-05 (Nous; Ace's decisions 10-05).
NEW FILE (avatar_identity build). Used only by SomaticAvatarFairy/fairy.py (V3) when state/avatar_identity.json is ON
and its "facts" knob is true (or "undo").

Ace 10-05: her look is a FACT, stored as ACE'S WORDS -- "Ace told her she chose how she looks: a fairy with lavender hair,
green eyes, freckles and wings" -- ranked ABOVE the words Qwen voiced for her (tracer 6) so borrowed words cannot
overwrite it, BUT revisable by HER OWN memories later (when her Personal.AI memories come home), because she chose it.
Stored under its own names so ordinary chat cannot reuse them. NOT taken from calibration.json (its flower crown and
corset dress are in none of her 11 pictures).

How each part of that is met (infrastructure/manifold_memory.py, read 10-05, sha 167a25eb):
  * the writer is TRACE_SEEDED (tracer 7 = priority 9, :209-224). Qwen's lines are TRACE_INFERENCE (6 = priority 7):
    set_snippet refuses a lower-priority writer (:2365-2371) and upsert_node never lowers an owner (:2134-2140).
    Her own memories are TRACE_PERSONAL (1 = priority 10): they MAY overwrite -- that is the "revisable" right.
    (Ace live is 12 and Nous 10: they may too. Her voice loopback 8, code 3, visual 4: may not.)
  * its own names: `self:look`, `self:look:<feature>`, `self:picture:<stem>`. The weave's tokeniser only makes
    [a-z0-9] words joined by '_' (sequence_weave.py:105-113, keys 'turn:', 'w:', 'w1_w2'), so no sentence anyone says
    can mint or touch a `self:` key. Typed edges REACH the shared word nodes (SEMANTIC) without owning them.
  * Ace's words reach her recall ONLY AFTER HE APPROVES THEM (skeptic F2, 10-05): recall renders a turn of speaker
    'ace' as a QUOTATION of him -- "You remember Ace said, ...: '...'" (render_memory :309) -- and PROPOSAL s4d M1
    promised "Ace writes or approves every sentence; I never write as 'ace'". The fact sentence above is third person
    ("Ace told her ..."), so quoted as his speech it reads as Ace narrating about some 'her'. ACE_TURN below is the
    sentence proposed for that quotation; it is woven ONCE, speaker 'ace', at TRACE_SEEDED (never Ace's 12), only while
    the switch says "ace_turn": true (installer --ace-turn, or Ace by hand). Until then the facts and the chairman line
    carry her look; recall does not quote Ace at all.
  * nothing is deleted, ever: an undo journal (state/avatar_identity_facts.json) records every key's owner and snippet
    BEFORE the first write; "facts": "undo" blanks only the snippets that are still ours (tracer 7, our text) -- a
    snippet she has since rewritten herself is left alone. Edges stay.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Dict, List, Optional

FACT_SENTENCE = "Ace told her she chose how she looks: a fairy with lavender hair, green eyes, freckles and wings."
# The words that would render as HIS ("You remember Ace said, ...: '<ACE_TURN>'"). Awaiting Ace's yes -- woven only with
# "ace_turn": true. Second person, as he would say it to her; the same facts as FACT_SENTENCE, nothing added.
ACE_TURN = "You chose how you look: a fairy with lavender hair, green eyes, freckles and wings."
HUB = "self:look"
FEATURES = (("fairy", "a fairy"), ("lavender_hair", "lavender hair"), ("green_eyes", "green eyes"),
            ("freckles", "freckles"), ("wings", "wings"))
PREFIX = "self:"
SPEAKER = "ace"
THREAD = "self:look"
# the words of the woven sentence that ARE her look: only their index edges are strengthened
LOOK_WORDS = ("chose", "look", "looks", "fairy", "lavender", "hair", "green", "eyes", "freckles", "wings")
JOURNAL_VERSION = 2
_WRITE_LOCK = threading.Lock()        # ONE writer per process, whichever FactWriter (or fairy copy) calls


def feature_key(f: str) -> str:
    return "%s:%s" % (HUB, f)


def picture_key(stem: str) -> str:
    return "self:picture:%s" % stem


def picture_snippet(stem: str) -> str:
    return "a picture of her (%s) from the folder Ace keeps for how she looks" % stem


def plan(stems: List[str]) -> List[Dict]:
    """Every node this writes: key, snippet."""
    out = [{"key": HUB, "snippet": FACT_SENTENCE}]
    out += [{"key": feature_key(f), "snippet": phrase} for f, phrase in FEATURES]
    out += [{"key": picture_key(s), "snippet": picture_snippet(s)} for s in sorted(stems)]
    return out


def _consts():
    from infrastructure.manifold_memory import (TRACE_SEEDED, TRACE_PRIORITY, NTYPE_ENTITY, REGION_SEMANTIC,
                                                REL_PART_OF, REL_IS_A, REL_SEMANTIC)
    return TRACE_SEEDED, TRACE_PRIORITY, NTYPE_ENTITY, REGION_SEMANTIC, REL_PART_OF, REL_IS_A, REL_SEMANTIC


def cortex_handle():
    """Her live ManifoldMemory, exactly as vision_ground._cortex_handle (infrastructure/vision_ground.py:1715-1728)."""
    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
        acf = get_association_cortex()
        am = getattr(acf, "_akashic_cortex_region", None) if acf is not None else None
        if am is None:
            return None
        if type(am).__name__ != "ManifoldMemory" and not hasattr(am, "_REL_NAME_TO_INT"):
            return None
        if hasattr(am, "upsert_node") and hasattr(am, "link") and hasattr(am, "get_node") and hasattr(am, "set_snippet"):
            return am
    except Exception:
        pass
    return None


def _atomic_json(path: str, obj: Dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = (json.dumps(obj, indent=1, ensure_ascii=True) + "\n").encode("ascii")   # build the bytes first, then open
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read_journal(path: str) -> Optional[Dict]:
    try:
        with open(path, "rb") as f:
            d = json.loads(f.read().decode("utf-8-sig"))
        return d if isinstance(d, dict) else None
    except Exception:
        return None


class FactWriter:
    """Writes the facts once per memory, from any thread; a second caller waits and gets the first one's result."""

    def __init__(self, journal_path: str, stems: List[str], weave=None, log=print):
        self.journal_path = journal_path
        self.stems = sorted(stems)
        self._weave = weave                 # sequence_weave module (injected by tests; imported lazily otherwise)
        self._lock = _WRITE_LOCK
        self.done: Optional[Dict] = None
        self.log = log

    def _sw(self):
        if self._weave is None:
            from infrastructure import sequence_weave as _sw
            self._weave = _sw
        return self._weave

    def status(self, am) -> Dict:
        """What is in her memory now, per planned key (read only)."""
        TRACE_SEEDED = _consts()[0]
        rows = []
        for p in plan(self.stems):
            n = am.get_node(p["key"]) if am is not None else None
            rows.append({"key": p["key"], "exists": bool(n), "tracer": (n or {}).get("tracer_id"),
                         "ours": bool(n) and (n or {}).get("tracer_id") == TRACE_SEEDED and (n or {}).get("snippet") == p["snippet"],
                         "snippet": (n or {}).get("snippet", "")})
        return {"rows": rows}

    def write(self, am, now: Optional[float] = None, ace_turn: bool = False) -> Dict:
        """ace_turn: also weave ACE_TURN as Ace's words (only with his yes). A yes that arrives after the facts were
        written weaves the turn then, once; a no never un-weaves it (that is "facts": "undo")."""
        with self._lock:
            now = now or time.time()
            if self.done is not None:
                if ace_turn is not True or self.done.get("turn") or self.done.get("result") == "revised_by_her":
                    return dict(self.done, again=True)
                t = self._turn_locked(am, now)
                if t.get("turn"):
                    self.done = dict(self.done, turn=t["turn"], index_words=t.get("index_words"))
                return dict(self.done, turn_now=t)
            r = self._write_locked(am, now, ace_turn is True)
            if r.get("result") in ("written", "in_place", "revised_by_her"):
                self.done = r
            return r

    def _live_turn(self, am, j: Optional[Dict]) -> Optional[str]:
        """The woven turn key from the journal, if it is still in her memory with its text."""
        t = (j or {}).get("turn")
        if not t or am is None:
            return None
        n = am.get_node(t)
        return t if (n and n.get("snippet")) else None

    def _turn_locked(self, am, now: float) -> Dict:
        """Weave ACE_TURN once (Ace's yes). Journal first ("turn_pending"), then the key. Caller holds the lock."""
        TRACE_SEEDED, REL_PART_OF = _consts()[0], _consts()[4]
        if am is None:
            return {"turn": None, "why": "no_cortex"}
        j = read_journal(self.journal_path) or {}
        if not j.get("done") or j.get("undone"):
            return {"turn": None, "why": "facts not written"}
        live = self._live_turn(am, j)
        if live:
            return {"turn": live, "already": True}
        j.update({"turn_pending": {"ts": now, "sentence": ACE_TURN}})
        _atomic_json(self.journal_path, j)
        sw = self._sw()
        r = sw.weave_turn(ACE_TURN, SPEAKER, TRACE_SEEDED, am=am, chain=False, thread=THREAD)
        turn = (r or {}).get("turn")
        words = self._index_strongly(am, sw, turn, REL_PART_OF, TRACE_SEEDED) if turn else []
        j.pop("turn_pending", None)
        j.update({"turn": turn, "turn_sentence": ACE_TURN if turn else None, "index_words": words})
        _atomic_json(self.journal_path, j)
        return {"turn": turn, "index_words": words}

    def _write_locked(self, am, now: float, ace_turn: bool = False) -> Dict:
        (TRACE_SEEDED, TRACE_PRIORITY, NTYPE_ENTITY, REGION_SEMANTIC, REL_PART_OF, REL_IS_A, REL_SEMANTIC) = _consts()
        if am is None:
            return {"result": "no_cortex"}
        j = read_journal(self.journal_path)
        hub = am.get_node(HUB)
        if j and j.get("done") and not j.get("undone") and hub:
            if hub.get("tracer_id") == TRACE_SEEDED and hub.get("snippet") == FACT_SENTENCE:
                r = {"result": "in_place", "turn": self._live_turn(am, j), "nodes": len(j.get("nodes", [])),
                     "edges_ok": j.get("edges_ok"), "edges_planned": j.get("edges_planned")}
                if ace_turn and not r["turn"]:
                    t = self._turn_locked(am, now)
                    r.update(turn=t.get("turn"), turn_woven_now=bool(t.get("turn")))
                return r
            if TRACE_PRIORITY.get(hub.get("tracer_id"), 1) > TRACE_PRIORITY[TRACE_SEEDED]:
                return {"result": "revised_by_her", "owner": hub.get("tracer_id"), "snippet": (hub.get("snippet") or "")[:120]}
        p = plan(self.stems)
        pre = []
        for row in p:                                           # pre-images FIRST (the undo journal)
            n = am.get_node(row["key"])
            pre.append({"key": row["key"], "snippet": row["snippet"], "existed": bool(n),
                        "old_tracer": (n or {}).get("tracer_id"), "old_snippet": (n or {}).get("snippet", "")})
        keep_turn = (j or {}).get("turn") if (j and not j.get("undone")) else None
        journal = {"version": JOURNAL_VERSION, "ts": now, "tracer": TRACE_SEEDED, "sentence": FACT_SENTENCE,
                   "nodes": pre, "turn": keep_turn, "turn_sentence": (j or {}).get("turn_sentence") if keep_turn else None,
                   "edges_planned": 0, "edges_ok": 0, "done": False, "undone": None}
        _atomic_json(self.journal_path, journal)
        wrote, refused = 0, []
        for row in p:
            n = am.get_node(row["key"])
            if n is None:
                s = am.upsert_node(row["key"], activation=0.5, count=1, degree=0, coord_str="", snippet=row["snippet"],
                                   node_type=NTYPE_ENTITY, region=REGION_SEMANTIC, tracer_id=TRACE_SEEDED, parent_slot=0)
                ok = s is not None and s >= 0
            elif n.get("snippet") == row["snippet"] and n.get("tracer_id") == TRACE_SEEDED:
                ok = True
            else:
                ok = bool(am.set_snippet(row["key"], row["snippet"], TRACE_SEEDED))
            wrote += 1 if ok else 0
            if not ok:
                refused.append(row["key"])
        edges = [(feature_key(f), HUB, REL_PART_OF) for f, _ in FEATURES]
        edges += [(picture_key(s), HUB, REL_IS_A) for s in self.stems]
        for f, _ in FEATURES:                                   # reach the shared word nodes; create none
            if am.get_node(f):
                edges.append((feature_key(f), f, REL_SEMANTIC))
        if am.get_node("sourpatches"):
            edges.append((HUB, "sourpatches", REL_PART_OF))
        ok_e = 0
        for a, b, rel in edges:
            if am.link(a, b, weight=0.5, rel_type=rel, tracer_id=TRACE_SEEDED):
                ok_e += 1
        journal.update({"edges_planned": len(edges), "edges_ok": ok_e, "nodes_ok": wrote,
                        "refused": refused, "done": True})
        _atomic_json(self.journal_path, journal)
        turn, index_words = self._live_turn(am, journal), []
        if ace_turn and not turn:                               # only with Ace's yes (skeptic F2)
            t = self._turn_locked(am, now)
            turn, index_words = t.get("turn"), t.get("index_words") or []
        return {"result": "written", "nodes": wrote, "nodes_planned": len(p), "refused": refused,
                "edges_ok": ok_e, "edges_planned": len(edges), "turn": turn, "index_words": index_words,
                "ace_turn": bool(ace_turn)}

    @staticmethod
    def _index_strongly(am, sw, turn: str, REL_PART_OF: int, tracer: int) -> List[str]:
        """recall_lines reads only the 40 heaviest PART_OF neighbours of each word (sequence_weave.py:229); in her memory
        (probes/cell0_probe.json, 10-05) w:eyes has 92 sentences and w:look 74, all at the weave's 0.4. Linking the
        turn's own word edges once more strengthens them to 0.6 (manifold_memory.link :2541-2546), so a crowded word
        still reads it. 'fairy' is IN the sentence but the weave skips it as a hub (sequence_weave.py:56, :179):
        its edge is made here (twice: 0.4 -> 0.6). Only LOOK_WORDS. No word node is created."""
        out = []
        for cw in sw.content_words(ACE_TURN):
            if cw not in LOOK_WORDS:
                continue
            wk = "w:" + cw
            if not am.get_node(wk):
                continue
            have = any(k == turn for k, _ in am.get_neighbors(wk, limit=100000, rel_filter=REL_PART_OF))
            n_ok = 0
            for _ in range(1 if have else 2):
                if am.link(wk, turn, weight=0.4, rel_type=REL_PART_OF, tracer_id=tracer):
                    n_ok += 1
            if n_ok:
                out.append(cw)
        return out

    def undo(self, am, now: Optional[float] = None) -> Dict:
        """Blank the snippets that are still ours (tracer 7 and our exact text). Never deletes; leaves her revisions."""
        TRACE_SEEDED = _consts()[0]
        with self._lock:
            j = read_journal(self.journal_path)
            if not j:
                return {"result": "no_journal"}
            if j.get("undone"):
                return {"result": "already_undone"}
            if am is None:
                return {"result": "no_cortex"}
            keys = [(r["key"], r["snippet"]) for r in j.get("nodes", [])]
            if j.get("turn"):
                keys.append((j["turn"], j.get("turn_sentence") or ACE_TURN))
            blanked, left = [], []
            for key, ours in keys:
                n = am.get_node(key)
                if n and n.get("tracer_id") == TRACE_SEEDED and n.get("snippet") == ours:
                    if am.set_snippet(key, "", TRACE_SEEDED):
                        blanked.append(key)
                elif n and n.get("snippet"):
                    left.append(key)
            j["undone"] = {"ts": now or time.time(), "blanked": blanked, "left_alone": left}
            _atomic_json(self.journal_path, j)
            self.done = None
            return {"result": "undone", "blanked": len(blanked), "left_alone": left}
