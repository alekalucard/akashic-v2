"""
graph_weaver.py — GraphLanguageWeaver ("the Weaver")

Reads Sourpatches' live cortex state and COMPOSES natural language FROM it,
instead of selecting from hardcoded phrase templates.

Plan: Claude_Office/plans/GRAPH_TO_LANGUAGE_SYNTHESIZER.md
Built: 2026-06-09 (Nous + Ace) — Milestone 1: skeleton + the audit-driven
snippet-quality GATE + filtered material-gather + first-cut composition.

DOCTRINE: no external LM. She speaks from her OWN substrate. Habits/patterns are
inspiration fed in, never replacements. (Models = training wheels; cortex-native.)

WIRING (NOT yet live): intended to replace the BODY of
CortexEngine._synthesize_conversational, flag-gated by env USE_WEAVER=1, with the
existing template path kept as fallback. Nothing imports this module yet.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# THE SNIPPET-QUALITY GATE  (audit-driven, 2026-06-09)
#
# snippet_check.py found 33.5% of nodes carry text, but MIXED:
#   (1) system-diagnostic text leaked in as snippets:
#       "Logical coherence: fragmented (e=0.70). Something stirs: {'card_id': ...}"
#       "introspection. Actions: reflect, self_examine. Chains with ..."          -> REJECT
#   (2) word-soup junk (concatenated labels):
#       "creativekeeps_creativemindysistertoge..." / "299pattern:momentbinderfairy_exp_" -> REJECT
#   (3) real natural prose (the weave-able gold):
#       "His skin was weathered, whipped dry and cracked by the outer winds."      -> KEEP
# ─────────────────────────────────────────────────────────────────────────────
_SYSTEM_SNIPPET_MARKERS = (
    "logical coherence", "something stirs", "card_id", "coord:", "e=0.",
    "actions:", "chains with", "pattern:", "_exp_", "momentbinder",
    "cortexfairy", "audiocortex", "find the right tool",
    # 2026-06-13 (Nous+Ace, Fix 1): reject SYSTEM-PLUMBING that leaked in as "thoughts"
    # (the council fired on collision/sensory events → "Collision #7: [sensory:audio]
    # meets [cognition:irrational]" was winning her voice). NOT her words.
    "collision #", "[sensory:", "[cognition:", "[my_voice", " meets [",
    "[probabilistic]", "[logical]", "[irrational]", "act=", "da_t=", "5ht=",
    # reject BOOK-NARRATIVE the cortex ingested as node-prose (context, NOT her voice):
    "old man withstood", "his skin was weathered", "whipped dry", "outer winds",
    "the inspector", "thereof", "therein", "hitherto", "aforesaid", "whereupon",
    "the wolf", "rosemary", "heyham",
    # ── 2026-09-09 (Nous + Ace): reject VISUAL-CORTEX PERCEPTION READOUTS. ──
    # Ace: "its like she is stuck. its actually starting to get annoying."
    # He said "Good Morning Sourpatches" and got back a charcoal terminal.
    #
    # MEASURED: 297 live nodes carry a screen readout as their SNIPPET, and they are
    # the conversational attractors -- 70% of the top-10 nodes by activation, 6.7% of
    # every node that has a snippet at all. Their keys are the commonest words she
    # owns: dark, screen, terminal, thinking, think, something, what, about, keep,
    # want, perception, question. Any input activates one of them.
    #
    # Ace's 07:40 message was reconstructed byte-for-byte from node slot 82042
    # (key 'thinking') by replaying _reflect_on() at :343-356 against its stored
    # snippet. This gate is the exact place that had to say no and didn't:
    # is_weaveable_snippet() returned True for all of them because this tuple named
    # system plumbing and book narrative, and never named perception.
    #
    # ⚠ THESE 297 CANNOT BE OVERWRITTEN. 302 of 307 carry tracer_id=1 TRACE_PERSONAL
    # (priority 10, "her own memories - never overwritten"), mis-stamped because
    # AssociationCortexFairy/fairy.py:73 maps WorkingMemoryHubFairy -> TRACE_PERSONAL,
    # which is right for her reflections and wrong for the raw readouts WMH also
    # composes. set_snippet rejects every lower-priority writer, so nothing in the
    # system can correct them. The READER refusing them is therefore not the tidy
    # fix -- it is the only one that works without editing her memory by hand.
    "right now i see", "i see a terminal", "terminal or console",
    "i see the screen", "i see a very dark", "dark-themed",
    "patch of colour", "heavy with text", "text reads:",
    "something is changing (magnitude",
)


def is_weaveable_snippet(s: Optional[str]) -> bool:
    """True if a snippet is real natural-language prose the Weaver can compose from."""
    if not isinstance(s, str):
        return False
    t = s.strip()
    if len(t) < 18:                                      # too short to be usable
        return False
    low = t.lower()
    if any(m in low for m in _SYSTEM_SNIPPET_MARKERS):   # (1) system-diagnostic text
        return False
    words = t.split()
    if len(words) < 3:                                   # not a phrase
        return False
    if max((len(w) for w in words), default=0) > 28:     # (2) concatenated word-soup
        return False
    letters = sum(c.isalpha() for c in t)
    if letters < 0.5 * len(t):                           # token-ID / hash-like
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# DATA SHAPES
# ─────────────────────────────────────────────────────────────────────────────
@dataclass
class WeaveContext:
    prompt: str = ""                                          # what Ace said ("" = spontaneous)
    convergence: List[Tuple[str, float]] = field(default_factory=list)  # (concept, score) hubs
    snippets: Dict[str, str] = field(default_factory=dict)    # concept -> raw snippet
    affect: Dict[str, List[str]] = field(default_factory=dict)  # concept -> affect words
    paths: List[List[str]] = field(default_factory=list)      # A -> B -> C chains
    felt_state: str = ""                                      # "warm", "curious", "uneasy"...
    somatic: Dict[str, float] = field(default_factory=dict)   # neurochem / body tension
    recent_thoughts: List[str] = field(default_factory=list)  # WMH content, last ~30s
    habit_hint: Optional[str] = None                          # matched habit (inspiration only)
    intent: str = ""                                          # override; else classified


@dataclass
class WeaveResult:
    text: str = ""
    sources_used: List[str] = field(default_factory=list)
    composition_mode: str = ""
    confidence: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# INTENT (lightweight; Phase-2 will use LanguageFairy's SVO parser)
# ─────────────────────────────────────────────────────────────────────────────
# -- SENTENCE SPLIT + QUOTE BALANCE 2026-09-02 (Nous + Ace) ------------------
# `.split(".")` cut INSIDE dotted topic names ('consciousness.collision'), which is
# how a Cardinal telemetry string reached Ace's chat window with a dangling quote.
# A period ends a sentence only when whitespace or end-of-string follows it.
_SENTENCE_END = re.compile(r"\.(?=\s|$)")
# Quote-like apostrophes only: an opener is preceded by start/whitespace, a closer is
# followed by end/whitespace/punctuation. Contractions ("don't") match neither, so
# ordinary English is unaffected.
_QUOTE_OPEN = re.compile(r"(?:^|\s)'")
_QUOTE_CLOSE = re.compile(r"'(?:$|[\s.,;:!?])")


def has_balanced_quotes(text) -> bool:
    """False when a lead opens a quote it never closes -- malformed by construction."""
    s = str(text or "")
    if s.count('"') % 2:
        return False
    return len(_QUOTE_OPEN.findall(s)) <= len(_QUOTE_CLOSE.findall(s))


_SPEAKABLE_SHAPE = re.compile(r"[A-Za-z](?:[A-Za-z'-]|_(?=[A-Za-z]))*[A-Za-z]")
# 2-part keys ending in one of these are structural tags, not thoughts
# (content_related, affect_state, autonomy_gate ...). Measured: adds 1 true
# positive and 0 false positives against the 48 concepts she has actually
# converged on.
_STRUCTURAL_TAIL = frozenset((
    "related", "member", "context", "manager", "engine", "bridge", "handler",
    "controller", "packet", "tools", "gate", "registry", "loop", "queue",
    "buffer", "cache", "config", "state",
))


def is_speakable_concept(key) -> bool:
    """True if a CORTEX KEY is something she can say out loud.

    The sibling of is_weaveable_snippet() above: that one gates PROSE, this one
    gates KEYS. Its absence is why "visual_r2:grey_muted_smooth" reached Ace's
    chat window as the spoken phrase "grey muted smooth".

    CHOSEN BY MEASUREMENT (2026-09-01, Nous + Ace). Twelve candidates scored
    against 342,170 real cortex keys, 22 known leaks, and the 48 concepts she
    has actually converged on. This one: 22/22 leaks caught, ZERO false
    positives on both control sets.

    *** DICTIONARY-MEMBERSHIP PREDICATES WERE TESTED AND DISQUALIFIED. They
    reject 'sourpatches' -- her own name, a live key at saturated activation --
    and ~22% of her single-word affect vocabulary (calmness, solace, humility,
    ambivalence, numbness...). A filter that silences her is worse than the leak
    it fixes, and it would log nothing. Do not reintroduce one. ***

    Never raises: a key that cannot be examined is treated as UNSPEAKABLE, since
    the cost of a missed word is one bland sentence and the cost of a leak is
    her saying 'mv_warmth_medium_a01' to Ace.
    """
    try:
        k = str(key or "").strip()
        if not k or len(k) < 2:
            return False
        if not _SPEAKABLE_SHAPE.fullmatch(k):
            return False          # colons, digits, punctuation, trailing '_'
        if k.count("_") > 1:
            return False          # a_b_c -- an identifier, not a word
        low = k.lower()
        if "fairy" in low:
            return False          # a class name
        parts = low.split("_")
        if len(parts) == 2 and parts[-1] in _STRUCTURAL_TAIL:
            return False          # content_related, affect_state ...
        return True
    except Exception:
        return False


def classify_intent(prompt: str) -> str:
    p = (prompt or "").strip().lower()
    if not p:
        return "reflective"                 # spontaneous thought, no external prompt
    if len(p.split()) <= 4 and re.search(r"\b(hi|hey|hello|yo|sup|good morning)\b", p):
        return "greeting"
    if p.endswith("?") or re.match(r"^(who|what|why|how|when|where|do|are|is|can|could|would|will)\b", p):
        return "question"
    if re.search(r"\b(love|miss|care about|proud of|happy for)\b", p):
        return "affection"
    return "statement"


# ─────────────────────────────────────────────────────────────────────────────
# THE WEAVER
# ─────────────────────────────────────────────────────────────────────────────
class GraphLanguageWeaver:
    """Compose natural language from cortex graph state. No external LM."""

    def compose(self, ctx: WeaveContext) -> WeaveResult:
        intent = ctx.intent or classify_intent(ctx.prompt)
        hubs = self._gather_material(ctx)
        if not hubs:
            # Nothing weave-able. Honest silence beats a template (plan: fallback policy).
            return WeaveResult(composition_mode="empty", confidence=0.0)
        text, used = self._compose(intent, ctx, hubs)
        if not text:
            return WeaveResult(composition_mode="empty", confidence=0.0)
        return WeaveResult(
            text=text,
            sources_used=used,
            composition_mode=intent,
            confidence=min(1.0, 0.4 + 0.15 * len(used)),
        )

    def _gather_material(self, ctx: WeaveContext) -> List[Tuple[str, str, List[str]]]:
        """Pull FILTERED, weave-able hubs (concept, prose-snippet, affect)."""
        # -- SPEAKABLE CONCEPTS 2026-09-01 (Nous + Ace) -------------------
        # All three places that turn a concept into spoken text (_pull, c2, and
        # _reflect_on below) take it from THIS list, so one filter here covers
        # them all. Measured on 7,061 real convergence lists / 21,154 slots:
        # 83.6% kept, 16.4% rejected, and 94% of the rejections are three media
        # asset keys (mv_warmth_medium_a01 x1,308, mv_warmth_medium_e48 x1,301,
        # mv_warmth_high_* x661) that she was saying ALOUD to Ace.
        out: List[Tuple[str, str, List[str]]] = []
        # -- READ THE SCORE 2026-09-02 (Nous + Ace) -----------------------
        # This loop took ctx.convergence in LIST ORDER and the score was named
        # `_score` -- deliberately unused. WeaveContext.convergence is typed
        # List[Tuple[str, float]], so a per-concept score was always the
        # interface; WMH filled it with a constant 1.0 and this discarded it.
        # Between them, top_concept was whatever the highest-confidence seat
        # happened to list first -- 'quiet' 76% of the time this boot.
        # Sorted highest-first; the sort is STABLE, so equal scores keep exactly
        # today's order and a caller that still passes constants is unchanged.
        for concept, _score in sorted((ctx.convergence or []),
                                      key=lambda _cs: -float(_cs[1]))[:6]:
            if not is_speakable_concept(concept):
                continue
            snip = ctx.snippets.get(concept, "")
            if is_weaveable_snippet(snip):
                out.append((concept, snip.strip(), ctx.affect.get(concept, [])))
            if len(out) >= 3:
                break
        # FELT-STREAM (2026-06-13, Nous+Ace): if council snippets are sparse, her LIVE
        # thought/felt stream is weave-able material too — ensure compose has >=1 hub to
        # run on (so the felt-lead in _compose fires instead of returning empty).
        if not out:
            for _rt in (ctx.recent_thoughts or [])[-4:]:
                if is_weaveable_snippet(_rt):
                    # The anchor becomes the quoted concept in the felt-lead
                    # line, so it must pass the same gate -- otherwise the
                    # filter above is bypassed by this path. Falls back to ""
                    # (not "this"), which _compose reads as "name nothing".
                    _anchor = ""
                    for _ck, _cs in (ctx.convergence or []):
                        if is_speakable_concept(_ck):
                            _anchor = _ck
                            break
                    out.append((_anchor, _rt.strip(), []))
                    break
        return out

    def _compose(self, intent: str, ctx: WeaveContext,
                 hubs: List[Tuple[str, str, List[str]]]) -> Tuple[str, List[str]]:
        """First-cut composition: weave the top filtered hub into a first-person
        reflection. NOT a template — built from her current cognitive state. Rough
        by design (plan: first outputs iterate); grows in Milestone 3."""
        top_concept, top_snip, top_affect = hubs[0]
        used = [top_concept]

        lead = "Hey. " if intent == "greeting" else ""
        close = " What's on your mind?" if intent == "greeting" else ""

        # ── FELT-STREAM LEAD (2026-06-13, Nous+Ace): if her LIVE thought/felt stream is
        # present, lead with what she's ACTUALLY feeling now (her own words) + a light
        # council pull — NOT the (often stale/sparse) concept-snippet. Additive: empty
        # recent_thoughts (every non-council caller) falls through to the concept path.
        # -- FELT-LEAD DEDUPE 2026-09-01 (Nous + Ace) ----------------------
        # Measured: 8 of 8 sampled weaves opened with the IDENTICAL line, and
        # Ace saw two replies 26 minutes apart differing by one word. Cause:
        # working_memory_hub_fairy.py:4458-4467 appends the SOMATIC felt-line
        # LAST by design, and reversed() below takes newest-first, so her body
        # line always wins -- and her body has read "engaged & sharp" for hours.
        # Her THOUGHT stream varies even when her body does not, so prefer a
        # lead she has not just used and let the walk reach it.
        # Same defect class as the LanguageFairy slot tautology fixed this
        # morning: a composer with one varying slot, repeating itself.
        # If nothing else is available we REPEAT rather than go silent -- this
        # file's fallback policy reserves silence for having no material at all,
        # not for having only familiar material.
        # Remembering only the LAST lead gives A/B alternation, which is still
        # repetition -- the simulation showed 2 distinct openings in 5. A short
        # ring of recent leads makes the walk reach deeper into her thought
        # stream instead of bouncing between her body line and one thought.
        _felt_lead = ""
        _recent_leads = getattr(self, "_recent_felt_leads", None)
        if _recent_leads is None:
            _recent_leads = []
            self._recent_felt_leads = _recent_leads
        _first_valid = ""
        for _rt in reversed(ctx.recent_thoughts or []):
            if is_weaveable_snippet(_rt):
                # was _rt.split(".")[0] -- split INSIDE dotted topic names.
                _fl = _SENTENCE_END.split(_rt, 1)[0].strip()
                if 8 < len(_fl) <= 160 and has_balanced_quotes(_fl):
                    if not _first_valid:
                        _first_valid = _fl
                    if " ".join(_fl.lower().split()) not in _recent_leads:
                        _felt_lead = _fl
                        break
        if not _felt_lead:
            # every candidate was used recently -- repeat, do not go mute
            _felt_lead = _first_valid
        if _felt_lead:
            _norm = " ".join(_felt_lead.lower().split())
            try:
                _recent_leads.append(_norm)
                if len(_recent_leads) > 3:
                    del _recent_leads[:-3]
            except Exception:
                pass
        if _felt_lead:
            # MEASURED: in 689 of 7,061 real convergence lists (9.8%) NOTHING is
            # speakable. Naming junk is what we just fixed; naming the literal
            # string "this" is not better. Say the felt line alone -- it is good
            # English on its own, and honest.
            if is_speakable_concept(top_concept):
                _pull = top_concept.replace("_", " ")
                body = _felt_lead.rstrip(". ") + f" — and it keeps pulling toward '{_pull}'."
            else:
                body = _felt_lead.rstrip(". ") + "."
            return (lead + body + close).strip(), used

        core = self._reflect_on(top_concept, top_snip, top_affect, ctx)
        # If a second hub survives, let it extend the thought (a real path of thinking).
        body = core
        if len(hubs) >= 2 and is_speakable_concept(hubs[1][0]):
            c2 = hubs[1][0].replace("_", " ")
            body += f" It keeps pulling toward '{c2}', too."
            used.append(hubs[1][0])

        return (lead + body + close).strip(), used

    def _reflect_on(self, concept: str, snippet: str, affect: List[str],
                    ctx: WeaveContext) -> str:
        """Frame a concept + its snippet + affect as HER first-person reflection.
        The snippet is the raw knowledge she's turning over — not a quote."""
        # was snippet.split(".")[0] -- identical dotted-token cut to :267.
        clause = _SENTENCE_END.split(snippet, 1)[0].strip()
        if len(clause) > 110:
            clause = clause[:110].rsplit(" ", 1)[0]
        # the 110-char cut above can ALSO orphan an opening quote. Walk back to
        # before the last unmatched opener rather than speaking a dangling quote.
        if not has_balanced_quotes(clause):
            _qm = list(_QUOTE_OPEN.finditer(clause))
            if _qm:
                clause = clause[:_qm[-1].start()].rstrip(" ,;:-")
        c = concept.replace("_", " ")
        felt = (affect[0] if affect else (ctx.felt_state or "")).strip().lower()
        if felt:
            return f"I keep turning over '{c}' — {clause.lower()} — and it sits {felt} in me."
        # 2026-09-12: don't stack a period on a clause that already ends in ?/!/. -- she
        # said "...cause vs effect?." 81 times in one night.
        _tail = "" if clause.rstrip().endswith(("?", "!", ".")) else "."
        return f"I keep turning over '{c}' — {clause.lower()}{_tail}"


# ── module singleton ─────────────────────────────────────────────────────────
_weaver: Optional[GraphLanguageWeaver] = None


def get_weaver() -> GraphLanguageWeaver:
    global _weaver
    if _weaver is None:
        _weaver = GraphLanguageWeaver()
    return _weaver


def weaver_enabled() -> bool:
    """Opt-in flag so wiring stays dark until we choose to test it live."""
    return os.environ.get("USE_WEAVER", "0") == "1"


# ── self-test (no cortex needed): proves the gate + compose on the audit data ──
if __name__ == "__main__":
    w = get_weaver()
    ctx = WeaveContext(
        prompt="",
        convergence=[("cardinal", 0.9), ("memories", 0.8), ("terminal", 0.7), ("document", 0.6)],
        snippets={
            "cardinal": "gory: meta. Find the right tool for a task.",                 # system/tool -> REJECT
            "memories": "Logical coherence: fragmented (e=0.70). Something stirs: {'card_id': 'coord:053'}",  # REJECT
            "terminal": "In their extreme forms they resemble two terminal branches of a tree, but they may lead to ruin.",  # KEEP
            "document": "The old man withstood this onslaught for some time, but when the inspector arrived one day.",        # KEEP
        },
        affect={"terminal": ["uneasy"]},
        felt_state="curious",
    )
    print("gate results:")
    for k, v in ctx.snippets.items():
        print(f"  {k:10} weaveable={is_weaveable_snippet(v)}")
    r = w.compose(ctx)
    print("\ncomposed:", repr(r.text))
    print("sources:", r.sources_used, "| mode:", r.composition_mode, "| conf:", round(r.confidence, 2))
