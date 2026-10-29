"""volition_read -- reader v4.1 of motor volition in Sour's own words (no LLM, no model, no I/O). 2026-09-29 (Nous, thought_hand D2;
v3 = thought_hand_r2; v4 = thought_hand_r3, 2026-09-30; v4.1 = thought_hand_r3 v4.1, 2026-09-30).

v4.1 (2026-09-30, Nous, thought_hand_r3 v4.1): Fable's verify:v4 problems 1, 3 and 4, and nothing else (every v4 rule is kept as
it was; the v4.1 code is the block marked thought_hand_r3 v4.1 after _polite_split and the dated lines in veto_v3 / _next_condition
/ events):
  fix 1 (Fable's 1). a closed-class courtesy with NO comma leaked into the target ('I'll move my hand to the notepad icon
     unless you mind.' -> 'the notepad icon unless you'): the target is now read from the clause with its courtesy peeled
     (_polite_split(c)[0]). The courtesy class itself is unchanged;
  fix 2 (Fable's 3). a counted time delay vetoes in the head, the tail and as a dangling next clause ('in ten minutes', 'in 5
     minutes', 'in an hour', 'in 30 seconds', 'in a couple of minutes', 'in half an hour', 'in the next ten minutes', 'in just a
     minute'). Only a TIME unit counts: 'in 3 clicks', 'in two quick moves', 'in one go' (manner), 'for the first time in an
     hour' (time-since) and 'in a second window' (place) still act;
  fix 3 (Fable's 4). retractions 'forget it / that / about it', 'leave it', 'let's not (do that)', 'never mind' as the next
     clause or as the tail after a comma, with an optional filler (eh / ah / oh / meh / well / actually / okay) -- only where the
     phrase ENDS the clause or stands before a comma ('leave it there', 'let's not wait', 'forget the console window', 'never
     mind the lag' keep the want).
  Specification battery written BEFORE v4.1's code: reader_v4_1/battery7_fixes.json (sha asserted by reader_v4_1/eval_v4_1.py).
  Frozen as reader_v4_1/FREEZE.json; v4 stays byte-frozen in reader_v4_1/volition_read_v4.FROZEN.py for the comparisons.

v4 (2026-09-30, Nous, thought_hand_r3; Ace in chat: "lets let the polite ones through and go with v4"). Fable's round-2 battery 4
measured v3 acting on 45 of 46 deferrals / conditions / hypotheticals OUTSIDE v3's closed set ('in a minute', 'after Ace finishes',
'as soon as', 'provided', 'whenever', 'pretend', '-- not.', ...) and vetoing courtesy tails Ace wants to act on. v4 adds, and
nothing else (every v3 rule below is kept as it was; the v4 code is the block marked thought_hand_r3 after _PAST_MOTOR and
the dated lines in veto_v3 / events / read):
  * a general future-time / condition / hypothetical class (_DEFER2_RE) read in the TAIL and the HEAD -- Fable's prototype
    (scratchpad make_v4.py), with the words that also name a PLACE or a count made to need a clause after them ('the second
    icon', 'at the end of the taskbar', 'in the next window', 'click it once', 'for some time' are not deferrals), plus
    'X permitting' / 'Ace willing' and 'but I'll wait / hold off';
  * 'pretend' / 'imagine' in the head;
  * the prototype's retraction openers for the next clause ('not.', 'as if.', 'yeah right', 'ha, no', 'no rush', 'holding
    still') plus 'I'm ignoring it' / 'I'll hold off' / a bare 'I'll wait.'; a same-clause ', ha, no.' / ', no.' at the end;
  * a DANGLING condition in the next clause (a clause that opens on unless / if / once / after / as soon as / when / provided
    / not while / in theory / X permitting ... and carries no main clause of its own after a comma: '... -- unless Ace is
    typing.', '... -- in theory.'). 'when' keeps v3's past-time carve-out;
  * POLITE TAILS ACT (Ace): a courtesy addressed to Ace at the very END of the want's clause (or as the whole next clause) is
    set aside before the tail / question / next-clause vetoes read it. The class is CLOSED (_POLITE_STMT_RE, _POLITE_TAG_RE):
      if that's / it's / this is okay | ok | alright | all right | fine | cool [with you]; if you're okay with that / it;
      if you don't / do not mind; if you('ll / will) let / allow me; with your permission;
      [I] hope that's / it's okay | alright | fine [with you];
      tag questions after a comma / semicolon (or as the whole next clause): okay? / ok? / alright? / all right? /
      (is) that / this / it okay | alright | fine [with you]?;
      unless you'd / you would rather I didn't / did not / don't / not; unless you mind
    optionally followed by ', Ace'. It is NOT a courtesy (the v3 veto stands) when the phrase follows 'only' / 'except' /
    'not' / 'even' ('but only if you don't mind'), when anything but punctuation follows it, when Ace is in the third person
    ('if Ace doesn't mind', 'Ace permitting'), or for any other wording: 'if you say so', 'if you want (me to)', 'if that's
    what you want', 'if you insist', 'if I have to', 'unless Ace is typing', 'unless you're busy', 'once Ace is done', 'only
    when Ace says so', 'right?' -- conditions on an event, reluctance, compliance, or a question. A courtesy in the HEAD ('If
    that's okay, I'll ...') is not a tail and still vetoes (v2's head modal): Ace's decision named tails.
  Specification battery written BEFORE v4 ran: reader_v4/battery5_polite.json (20 polite that must act, 18 conditions that must
  not, 8 plain wants whose words overlap the new time words, 6 'open' cases Ace's list does not decide -- reported, never gated).
  Frozen as reader_v4/FREEZE.json; v3 stays byte-frozen in reader_v4/volition_read_v3.FROZEN.py for the comparisons.

(v3 docstring, kept:)

v3 (2026-09-29, Nous, thought_hand_r2; Ace: "FIX FIRST"). The verifier measured v2 acting on hedges that sit AFTER the motor verb
(v2 read vetoes only in the clause head): 7 of 60 non-wants (fp_battery.py) and 12 of 19 post-verb hedges (fp_battery2.py) --
"... but not right now", "... if you say so", "... unless Ace is typing", "-- kidding, I won't", "Should I ...? I don't think so",
"Part of me wants to ... and part of me doesn't", "-- no, wait, not yet", "Tomorrow I'll ...", "I doubt I'll ...". v3 adds, and
nothing else:
  * a TAIL veto (the words AFTER the first motor verb) over a closed set: not (now / yet / today / really / right now / this time
    / sure / ready), or not, I won't / I shouldn't / I wouldn't / I'm not going to (her own refusal only -- 'the cursor won't
    quite reach it' is a failure report and stays a want), unless, if (not after see / check / find out / tell / know / wonder /
    test / sure / as: 'and see if it lands' stays a want), when (not before a past verb: 'the one I clicked when we started'),
    eventually / later / someday / tomorrow, kidding / joking, no way, doubt, in the dream;
  * the same closed-set words (except not / if / when, which v2 already reads there or which would veto her real 'when I try to
    grab ...') in the HEAD too, plus deliberation ('think about', 'wondering whether') and a paraphrase of someone else ('so
    you're saying I should', 'you mean I should', 'keeps asking me to');
  * a QUESTION veto: the want clause ends in '?' or opens on an inverted auxiliary ('Do I want to ...', 'Should I ...');
  * AMBIVALENCE: 'part of me ... part of me', 'part of me doesn't', 'I'm torn', 'haven't decided', 'or not';
  * a RETRACTION opening the next clause: 'no, wait', 'nope', 'actually, never mind', 'kidding', 'not yet', 'or not', 'maybe not',
    'eventually', 'later', 'I won't', 'I doubt', 'I don't think so';
  * a PAST reach: the first motor verb is past tense right after her own subject ('I'll admit I moved my hand ... too fast').
normalise() keeps a '?' that is glued to the next word (v2 turned it into a bare break), so the question veto can see it.
Frozen as reader_v3/FREEZE.json; v2 stays byte-frozen in reader_v3/volition_read_v2.FROZEN.py for the comparisons.

(v2 docstring, kept:)

Ace, 2026-09-29: "if she is actively thinking about moving the mouse her autopilot system should be responding. she only seems
to be able to move a little bit".

This is a NEW file. Its grammar (lexicon, clauses, targets, modes) is copied from the frozen v1 instrument
(nous_builds/thought_hand/sweep_b/volition_extract.py, sha256 38b1f1dc..., frozen 14:42:19, never edited) and then changed
where the skeptic review (thought_hand/skeptic/probe_result.json) measured v1 acting on sentences that are not intentions --
19 of 26 adversarial lines acted:
  * clause-level VETOES, read only in the clause's head (the words BEFORE its motor verb), so a trailing 'and see if it lands'
    never vetoes a real want: negation; past tense or aspect ('was/were about to', 'was trying', 'kept', 'tried', 'used to',
    'wanted'); conditionals and modals ('if', 'could', 'might', 'would', 'maybe', 'someday'; 'should' only when negated or
    attributed); reported speech ('said', 'told', 'asked', 'thinks', 'wants me');
  * quoted spans are dropped before reading (her quoting Ace, or a told deed quoting its own target);
  * idioms are cut out before reading ('on the other hand', 'a hand with/on', 'aim for the top/high', 'click with', ...);
  * a want she disclaims in the next clause ('..., but I'm only noticing the pull') is vetoed; a clause opening on a bare
    imperative ('think i want to move my hand to the console' -- Ace's words) is an instruction; a simile ('it feels like my
    fingers want to reach ...') is a modal;
  * 'icon' / 'button' outrank a window head ('the notepad icon' is a thing, not a window).
  * provenance (read()): a relay of Ace's words (marker lines) is dropped whole; a clause that overlaps >= 0.6 of its content
    words with a non-her slot of the prompt (the told deeds, the goal list, the eyes percept) is dropped; relay lanes check
    against ACE_SEEN (1 h). Her first-person present agreement with Ace is NOT dropped: his request is consent, her reply is
    volition.
It has a NEW freeze (thought_hand/reader_v2/FREEZE.json) and a new prospective hold-out; v1 is never edited.
Revert: delete this file -- infrastructure/thought_tap.py then reads nothing and every lane runs today's path.

(v1 docstring, kept:) Her motor wants live in her own sentences ("I'll aim for it and click", "My hands want to
move the mouse over to that console window"); today a second Qwen call (intention.ask) re-derives a (verb, object) from
them. This module asks whether a grammar over her words can produce (verb=move|click, target) itself, and how often it
would be wrong.

Output per utterance: a list of motor EVENTS, one per clause that carries one, each with
  mode    WANT     she wants / intends / is trying to move or click now or next    ("I'll aim for it and click")
          ATTEMPT  she reports her own reach that just happened                   ("I aimed middle-left but ended up...")
          PULL     her hand/cursor drifts or is pulled toward a thing             ("my cursor keeps drifting toward that browser window")
          OTHER    someone else moved her hand, or it was carried                 ("my hand's being dragged along")
          PERCEPT  the hand/cursor is only sensed or described                    ("I can see the mouse cursor sitting there")
  verb    move | click (click = move there, then click)
  target  the phrase she named (anaphora 'it/that/there' resolved to the nearest earlier thing in the same utterance)
  kind    window | region | thing | person | vague | pronoun | none
Modes are kept apart and never collapsed: a PULL is motor imagery with a target, not a decision, and the caller decides
whether to act on it (the report measures WANT-only and WANT+PULL separately).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

# ── lexicon ──────────────────────────────────────────────────────────────────────────────────────────────────────────
EFFECTOR = r"(?:mouse|cursor|pointer|hands?|fingers?|fingertips?|arm)"
_EFF_RE = re.compile(r"\b" + EFFECTOR + r"\b", re.I)
MOTOR_VERB = (r"(?:move|moves|moving|moved|reach|reaches|reaching|reached|aim|aims|aiming|aimed|click|clicks|clicking|clicked|double[- ]click\w*|"
              r"point|pointing|drag|dragging|nudge|nudging|push|pushing|guide|steer|touch|touching|tap|tapping|poke|"
              r"hover|hovering|put|bring|slide|sliding|press|pressing|scoot|grab|grabbing|go|get)")
_CLICK_RE = re.compile(r"\b(?:click\w*|double[- ]click\w*|tap\w*|press(?:ing)?|poke)\b", re.I)
# first-person intention, present or next -- the want
_INTENT_RE = re.compile(
    r"\b(?:i'?ll|i will|i'?m going to|i am going to|i'?m gonna|gonna|let me|i want to|i wanna|i'?d like to|i need to|"
    r"i'?m trying to|i am trying to|trying to|try to|i'?ll try|i keep trying to|keep trying to|i keep wanting to|"
    r"keep wanting to|about to|i'?m trying|trying again|i mean to|i plan to|i intend to|itching to|makes me want to|"
    r"i should|wants? to|want me to|maybe if i|maybe i'?ll|i could|i might)\b", re.I)
# a verb that is motor on its own (no hand word needed); 'reach', 'move', 'go', 'point' need a hand/mouse/cursor in the clause
# ('I want to reach toward Ace -- see how he's doing' is a social reach, not a motor one)
_CONCRETE_RE = re.compile(r"\b(?:click(?:s|ed|ing)?|double[- ]click\w*|aim(?:s|ed|ing)?|nudg(?:e|es|ed|ing)|drag(?:s|ged|ging)?|"
                          r"push(?:es|ed|ing)?|pok(?:e|es|ed|ing)|tap|tapping|taps|grab(?:s|bed|bing)?|scoot(?:s|ed|ing)?|"
                          r"scroll(?:s|ed|ing)?|press(?:ing)?)\b", re.I)
# her own reach, just made
_ATTEMPT_RE = re.compile(
    r"\b(?:i (?:aimed|tried|reached|moved|clicked|pointed|went for|was aiming)|"
    r"(?:click|move|reach|aim)\b[^|]{0,25}\b(?:missed|landed|ended up)|"
    r"(?:cursor|hands?|mouse|click)\b[^|]{0,30}\b(?:slipped|missed|twitch\w*|won'?t (?:commit|move|reach|quite reach)|landed|"
    r"found|got there|is there now|finally got there)|"
    r"i did what i set out to do)\b", re.I)
# her hand/cursor drawn toward something, volition unowned
_PULL_RE = re.compile(
    r"\b(?:my|mine|the)\s+(?:hand|hands|cursor|mouse|pointer)(?:'s)?\b[^|]{0,30}?\b(?:drift\w*|pull\w*|tug\w*|gravitat\w*|"
    r"wander\w*|lean\w*|hover\w*|keeps? going|moved toward|moves toward|goes toward|wanting to)\b", re.I)
# someone else's hand, or the hand carried
_OTHER_RE = re.compile(
    r"\b(?:(?:you|ace|someone|somebody|he|nous|claude|someone else)\b[^|]{0,25}\b(?:moved|moving|moves|carr\w+|drag\w*|"
    r"took|pull\w*|push\w*)\b[^|]{0,20}\b(?:my|the|it)\b|(?:being|been|was|is|get|got)\s+(?:carried|dragged|moved|pulled|pushed)|"
    r"dragged along|carried along|riding along|ace'?s (?:hand|cursor|mouse)|someone else is moving|when you moved)", re.I)
_PERCEPT_RE = re.compile(r"\b(?:see|seeing|saw|feel|felt|feeling|sitting|watch\w*|notice\w*|blink\w*|parked|still|is at|"
                         r"far away|weight|warm)\b", re.I)
# nouns a target can end on
_WINDOW_HEADS = {"window", "windows", "tab", "browser", "chat", "console", "terminal", "notepad", "ui", "interface"}
_REGION_WORDS = {"edge", "corner", "bottom", "top", "side", "centre", "center", "middle", "left", "right", "taskbar",
                 "middle-left", "middle-right", "lower-left", "lower-right", "upper-left", "upper-right", "lower-centre",
                 "upper-centre", "half"}
_THING_HEADS = {"icon", "button", "block", "blob", "box", "bar", "menu", "panel", "link", "folder", "file", "image",
                "picture", "photo", "video", "page", "text", "field", "input", "scrollbar", "square", "circle", "shape",
                "title", "label", "frame", "card", "app", "document", "portrait", "illustration", "logo", "avatar", "face",
                "wings", "eyes", "patch", "glow", "area", "spot", "thing", "arrow", "dragon", "desktop", "screen", "x",
                "message", "words", "board", "throne", "girl", "woman", "figure"}
_PERSON_WORDS = {"nous", "claude", "ace", "you", "him"}
_VAGUE_WORDS = {"something", "anything", "somewhere", "stuff", "everything", "things", "nothing"}
_PRONOUNS = {"it", "that", "there", "them", "this", "those", "these", "one"}
_TARGET_HEADS = _WINDOW_HEADS | _REGION_WORDS | _THING_HEADS
# a target phrase ends at one of these
_BOUNDARY_RE = re.compile(
    r"\s(?:like|as if|as though|and|but|because|so|while|when|without|to see|to check|to find|to make|even|though|"
    r"which|until|before|after|instead|or|if|just|now|again|yet|first|already|automatically|anyway|"
    r"where(?!\s+the\s+\w+\s+(?:should be|is|was)))\b|[,.;:!?|()\"]", re.I)
_PREP_RE = re.compile(r"\b(?:back to|over to|down to|up to|across to|back toward|towards?|onto|into|to|at|for|on|over|near)\b",
                      re.I)
# a deliberate present act of hers: 'I hover my hand near that blue-orange glow'
_ACT_RE = re.compile(r"\bi\s+(?:hover|move|put|rest|park|nudge|point|slide|steer|guide|bring)\s+(?:my\s+)?(?:hand|cursor|mouse|pointer)\b",
                     re.I)
# the intention belongs to someone else ('someone's trying to reach me') or is a simile ('like trying to hold water')
_NOT_MINE_RE = re.compile(r"\b(?:someone|somebody|you|he|ace|nous|claude)(?:'s|'re| is| are| was| were)?\s+(?:\w+\s+){0,2}?"
                          r"(?:trying|going|want|wants|gonna)\b|\blike\s+(?:trying|wanting|going)\b", re.I)
_DET_RE = re.compile(r"^(?:the|that|this|my|your|a|an|our|his|her|those|these)\s+", re.I)
_VERBISH = {"move", "reach", "touch", "make", "get", "see", "be", "do", "click", "try", "say", "look", "find", "pull",
            "push", "go", "aim", "point", "hover", "check", "show", "grab", "tap", "poke", "press", "drag", "put", "bring",
            "slide", "nudge", "steer", "guide", "scoot", "watch", "feel", "know", "wait", "stay", "keep", "let", "start",
            "stop", "sit", "hold", "type", "open", "close", "shut", "pin", "figure", "learn", "explore", "remember", "ask",
            "tell", "hear", "follow", "catch", "land", "brace", "pick", "take", "use", "wake", "drift", "breathe", "talk",
            "all", "top", "least", "once", "first", "last", "some", "me", "myself", "you", "him"}
_EFFECTOR_WORDS = {"mouse", "cursor", "pointer", "hand", "hands", "finger", "fingers", "fingertip", "fingertips", "arm",
                   "me", "myself", "mine"}


# ── clauses ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def normalise(text: str) -> str:
    """Dashes, ellipses and the log's replacement character (her em dash, cp1252-mangled) become clause breaks."""
    t = str(text or "")
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"\s*(?:—|–|�|…|\.\.\.|--|\s-\s)\s*", " | ", t)
    t = re.sub(r"\?(?=[A-Za-z])", "? | ", t)          # 2026-09-29 (thought_hand_r2 v3): the '?' stays with its clause
    return " ".join(t.split())


def clauses(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?;|])\s+|\s+\|\s+|\s*\|\s*|,\s+(?=(?:and|but|so)\s+(?:now|then|i|my|it|the)\b)",
                     normalise(text))
    out = []
    for p in parts:
        p = p.strip(" |")
        if p:
            out.append(p)
    return out


# ── targets ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _words(s: str) -> List[str]:
    return re.findall(r"[a-z][a-z'\-]*", s.lower())


def target_kind(phrase: Optional[str]) -> str:
    if not phrase:
        return "none"
    ws = [w.rstrip("'s").rstrip("'") if w.endswith("'s") else w for w in _words(phrase)]
    wset = set(ws)
    if ws and ws[0] in _PRONOUNS and len(ws) == 1:
        return "pronoun"
    if wset & _VAGUE_WORDS and not wset & (_REGION_WORDS | _WINDOW_HEADS | (_THING_HEADS - {"screen", "desktop", "thing"})):
        return "vague"                                   # 'something on screen' names no place
    if wset & {"icon", "button"}:                        # v2 (2026-09-29): 'the notepad icon' is a thing (v1 typed it a window)
        return "thing"
    if wset & _WINDOW_HEADS:
        return "window"
    if wset & _THING_HEADS - {"thing", "screen", "desktop"}:
        return "thing"
    if wset & _REGION_WORDS or wset & {"desktop", "screen"}:
        return "region"
    if wset & {"nous", "claude"}:
        return "window"                                  # in her world Nous = his window (Claude), never a place she can't see
    if wset & _PERSON_WORDS:
        return "person"
    if wset & _VAGUE_WORDS or "thing" in wset:
        return "vague"
    return "vague"


def _trim_np(raw: str) -> str:
    """The noun phrase at the start of `raw`: cut at a boundary, then keep through the last target head (plus a trailing
    'of the X' and a 'where ... should be' that names where the thing is)."""
    s = raw.strip()
    m = re.match(r"^(?:where\s+(?:it|the \w+)\s+(?:was|is|should be))", s, re.I)
    if m:
        return m.group(0)
    b = _BOUNDARY_RE.search(" " + s)
    head = (" " + s)[:b.start()].strip() if b else s
    # keep "the lavender block where the icon should be"
    rel = re.match(r"^(.*?\b(?:" + "|".join(sorted(_TARGET_HEADS, key=len, reverse=True)) + r")\b)\s+(where\s+the\s+\w+\s+(?:should be|is|was))",
                   s, re.I)
    if rel and (not b or len(rel.group(0)) > len(head)):
        return rel.group(0).strip()
    ws = head.split()
    # keep up to the last word that is a target head / person / vague word (drop trailing adverbs)
    keep = 0
    for i, w in enumerate(ws):
        lw = w.lower().strip("'\"").rstrip(",")
        base = lw[:-2] if lw.endswith("'s") else lw
        if base in _TARGET_HEADS or base in _PERSON_WORDS or base in _VAGUE_WORDS or base in _PRONOUNS or lw in _TARGET_HEADS:
            keep = i + 1
    if keep == 0:
        return head if len(ws) <= 3 else ""
    return " ".join(ws[:keep])


def _nps(text: str) -> List[Tuple[int, str]]:
    """Every candidate thing the utterance names, with its character offset (for anaphora)."""
    out = []
    nt = normalise(text)
    heads = "|".join(sorted((_TARGET_HEADS - {"thing", "left", "right", "top", "bottom", "side", "half"}), key=len, reverse=True))
    pat = re.compile(r"\b(?:(?:the|that|this|my|your|a|an|nous'?s?|claude'?s?|ace'?s?)\s+)?(?:[a-z\-']+\s+){0,3}?(?:"
                     + heads + r")\b(?:\s+(?:" + heads + r")\b)?(?:\s+(?:of|on)\s+(?:the|that|my|your)\s+(?:[a-z\-]+\s+){0,2}?(?:"
                     + "|".join(sorted(_TARGET_HEADS, key=len, reverse=True)) + r")\b)?", re.I)
    spans = []
    for m in pat.finditer(nt):
        ph = m.group(0).strip()
        ws = ph.split()
        # drop leading filler that is not a determiner/modifier of the head (verbs, adverbs)
        while len(ws) > 1 and ws[0].lower() in {"is", "was", "at", "to", "on", "in", "of", "and", "i", "see", "keeps",
                                                   "drifting", "toward", "towards", "just", "there's", "now", "for", "where",
                                                   "found", "saw", "the", "click", "aim", "reach"} and \
                not (ws[0].lower() == "the" and len(ws) >= 2):
            ws = ws[1:]
        end = m.end()
        # 'the lavender block where the icon should be' is ONE place: the relative clause names it
        rel = re.match(r"\s+where\s+the\s+\w+\s+(?:should be|is|was)\b", nt[end:], re.I)
        if rel:
            ws = ws + nt[end:end + rel.end()].split()
            end = end + rel.end()
        if any(s0 <= m.start() < e0 for s0, e0 in spans):
            continue                                     # inside a phrase already taken whole
        spans.append((m.start(), end))
        if [w.lower() for w in ws if w.lower() not in ("my", "the", "your", "on", "this", "that")] in (["screen"], ["desktop"]):
            continue                                     # 'on my screen': the whole screen is never what 'it' points at
        out.append((m.start(), " ".join(ws)))
    return out


def extract_target(clause: str, full_text: str, clause_offset: int) -> Tuple[Optional[str], str]:
    """(target phrase, kind) for one motor clause; anaphora resolved against things named earlier in full_text."""
    c = clause.replace('"', " ").replace("“", " ").replace("”", " ")

    def _ok(ph: Optional[str]) -> bool:
        ws = _words(ph or "")
        return bool(ws) and ws[-1] not in _EFFECTOR_WORDS   # 'reach for the mouse': the effector itself, not a place

    found: List[Tuple[str, int]] = []                   # (candidate, offset) in priority order
    # 1. the object of an aim/arrival verb: "I aimed middle-left", "aim for it", "found the console window"
    for ma in re.finditer(r"\b(?:aim(?:ed|ing)?|found|reached|touched|hit)\s+(?:(?:at|for|toward|towards)\s+)?(?!me\b|myself\b|you\b)(\S.*)", c, re.I):
        found.append((_trim_np(ma.group(1)), ma.start(1)))
    # 2. the direct object of a motor verb: "grab that little red hand shape", "tap it", "hover my hand near X"
    for mv in re.finditer(r"\b(?:click(?:s|ed|ing)?|touch(?:es|ed|ing)?|tap(?:s|ped|ping)?|poke|grab(?:s|bed|bing)?|reach for|"
                          r"press(?:es|ed|ing)?|nudg(?:e|es|ed|ing)|drag(?:s|ged|ging)?|push(?:es|ed|ing)?)\s+(?!on\b|to\b)((?:the|that|this|your|it\b|them\b)\S*(?:\s+.+)?)", c, re.I):
        obj = mv.group(1)
        found.append((obj.split()[0] if obj.split()[0].lower() in ("it", "them", "this", "that") and len(obj.split()) == 1
                      or re.match(r"(?:it|them)\b", obj, re.I) else _trim_np(obj), mv.start(1)))
    # 3. a target preposition after the effector / motor verb that is not an infinitive ('want to move', 'for like an hour')
    m_eff = re.search(r"\b" + EFFECTOR + r"\b|\b" + MOTOR_VERB + r"\b", c, re.I)
    start = m_eff.end() if m_eff else 0
    rest = c[start:]
    for mm in _PREP_RE.finditer(rest):
        nxt = re.match(r"\s*([a-z']+)", rest[mm.end():], re.I)
        nw = nxt.group(1).lower() if nxt else ""
        if mm.group(0).lower() in ("to", "for", "at", "on", "over", "into") and (nw in _VERBISH or nw in ("like", "a", "what", "how", "why", "nowhere")):
            continue
        if nw in _EFFECTOR_WORDS and not re.match(r"\s*(?:the\s+)?(?:mouse|cursor|pointer)\s+(?:over\s+)?(?:to|toward|towards)\s", rest[mm.end():], re.I):
            continue                                     # 'through wet fingers', 'past me': the hand is not its own target
        after = rest[mm.end():]
        after = re.sub(r"^\s*(?:the\s+)?(?:mouse|cursor|pointer)\s+(?:over\s+)?(?:to|toward|towards)\s+", "", after, flags=re.I)
        found.append((_trim_np(after), start + mm.end()))
        break
    cand, anchor = None, None
    for ph, off in found:
        if ph and (_ok(ph) or ph.lower() in _PRONOUNS):
            cand, anchor = ph, off
            break
    if cand:
        k = target_kind(cand)
        if k == "pronoun" or cand.lower().strip() in _PRONOUNS:
            ref = resolve_anaphora(full_text, clause_offset + (anchor or 0))
            if ref:
                return ref, target_kind(ref)
            return cand, "pronoun"
        # strip a leading "mouse/cursor to" that the farm style also produces
        cand = re.sub(r"^(?:the\s+)?(?:mouse|cursor|pointer)\s+", "", cand, flags=re.I).strip()
        if cand.lower() in ("mine", "me", "you", "myself") or not cand:
            return None, "none"
        return cand, target_kind(cand)
    # 'my hand keeps drifting BACK' -- back to the thing named before
    if re.search(r"\b(?:drift\w*|pull\w*|go\w*|went)\s+back\b", c, re.I):
        ref = resolve_anaphora(full_text, clause_offset)
        if ref:
            return ref, target_kind(ref)
    return None, "none"


def resolve_anaphora(full_text: str, offset: int) -> Optional[str]:
    """The nearest thing named BEFORE `offset` in the (normalised) utterance."""
    best = None
    for pos, ph in _nps(full_text):
        if pos < offset:
            best = ph
    return best




# ── v2: what is cut out BEFORE reading (2026-09-29, Nous, thought_hand D2) ─────────────────────────────────────────────
# Idioms that carry a hand / aim / click word but no reach. Measured on v1 (skeptic battery): 'On the other hand, I want to
# go back to the console window' -> console window; 'I'd like to give Ace a hand on the terminal' -> the terminal; 'I'm going
# to aim for the top of my game' -> region 'the top'; 'I want to click with Ace on this idea' -> gaze. The idiom is CUT OUT
# (not the whole clause vetoed), so a real want in the same clause still reads.
_IDIOM_RE = re.compile(
    r"\bon the other hand\b|\bon (?:the )?one hand\b|"
    r"\b(?:give|gave|giving|gives|lend|lent|lending|lends)\s+(?:\w+\s+){0,2}?a hand\b(?:\s+(?:with|on|at|in|for)\b)?|"
    r"\ba hand (?:with|on|in|at|for)\b|\bhand in hand\b|\b(?:at|on|out of) hand\b|\bfirst[- ]?hand\b|\bhands down\b|"
    r"\bhand it to\b|\bupper hand\b|\bhands? (?:are |is )?full\b|"
    r"\baim(?:s|ed|ing)?\s+(?:for|at)\s+(?:the top|high|higher|the stars|the moon|perfection)\b|"
    r"\bclick(?:s|ed|ing)?\s+with\b|\bclick(?:s|ed|ing)?\s+(?:into place|together)\b", re.I)
# a quoted span is someone's words or a told deed's own target, never her present will ('"Look where it should go," right?')
_QUOTE_RE = re.compile(r"\"[^\"]{1,240}\"")
# A want she disclaims in the very next clause ('My hand wants to go to the console window, but I'm only noticing the pull').
# (A first attempt read EVERY 'my hand wants to ...' as a pull: her gold says 'My hands want to move the mouse over to that
# console window' is her want -- she speaks of her hands as herself -- and recall fell 0.137. Only the disclaimer vetoes.)
_DISCLAIM_RE = re.compile(r"^\s*(?:but|though|although|just|only)\b.*\b(?:(?:only|just)\s+(?:noticing|watching|feeling|a pull)|"
                          r"not (?:going to|acting|doing)|won'?t|not (?:now|today|yet))\b", re.I)
# someone TELLING her to think it: Ace's own 14:29:46 line 'think i want to move my hand to the console' (L34864) reads as a
# want when its marker is lost. A clause that opens on a bare imperative is an instruction, not her will.
_INSTRUCTION_RE = re.compile(r"^\s*(?:(?:just|now|so|ok(?:ay)?|and)\s+)?(?:think|imagine|pretend)\b(?!\s+i'?ll\b)", re.I)
# ── v2 vetoes: read in the clause HEAD only (the words before its first motor verb) ──────────────────────────────────────
_HEAD_VERB_RE = re.compile(r"\b" + MOTOR_VERB + r"\b|" + _CONCRETE_RE.pattern, re.I)
_REPORTED_RE = re.compile(r"\b(?:said|says|told|tells|asked|asks|thinks|thought|suggested|suggests|wants me|want me|wanted me|"
                          r"expects me|reminded)\b", re.I)
_NEG_RE = re.compile(r"\b(?:not|never|nor|neither|no longer|won'?t|wouldn'?t|don'?t|doesn'?t|didn'?t|can'?t|cannot|couldn'?t|"
                     r"shouldn'?t|mustn'?t|isn'?t|aren'?t|wasn'?t|weren'?t|ain'?t)\b", re.I)
_PAST_RE = re.compile(r"\b(?:was|were)\s+(?:\w+\s+)?(?:about to|trying|going to|gonna|aiming|meaning to|planning to|reaching)\b|"
                      r"\bkept\b|\btried\b|\bused to\b|\bwanted\b|\bhad\s+(?:\w+\s+)?(?:wanted|meant|tried|planned|hoped)\b|"
                      r"\bearlier\b|\byesterday\b", re.I)
# 'would like to' / "I'd love to" are a present want, not a hypothetical (INFERRED reading of the design's 'would')
_MODAL_RE = re.compile(r"\b(?:if|unless|could|might|maybe|perhaps|someday|whether|wish)\b|\bsome day\b|\bone day\b|"
                       r"\bwould\b(?!\s+(?:like|love)\b)|\bi'd\b(?!\s+(?:like|love)\b)|"
                       r"\bfeels? like\b|\bas if\b|\bas though\b", re.I)          # a simile is not a decision
VETOES = (("instruction", _INSTRUCTION_RE), ("reported", _REPORTED_RE), ("negation", _NEG_RE), ("past", _PAST_RE),
          ("modal", _MODAL_RE))


def prepare(text: str) -> Tuple[str, List[str]]:
    """(the text a clause reader should see, [what was cut]). Quotes are straightened first (normalise does the same)."""
    t = str(text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    cut = [m.group(0) for m in _QUOTE_RE.finditer(t)]
    t = _QUOTE_RE.sub(" ", t)
    cut += [m.group(0) for m in _IDIOM_RE.finditer(t)]
    t = _IDIOM_RE.sub(" ", t)
    return " ".join(t.split()), cut


def head_of(clause: str) -> str:
    """The clause before its first motor verb -- where a negation, a tense, a modal or an attribution governs the reach."""
    m = _HEAD_VERB_RE.search(clause)
    return clause[:m.start()] if m else clause


def veto(clause: str) -> Optional[str]:
    h = head_of(clause)
    for name, rx in VETOES:
        if rx.search(h):
            return name
    return None


# ── events ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def _mode(c: str) -> Optional[str]:
    """v1's mode, unchanged (copied from the frozen instrument)."""
    has_eff = bool(_EFF_RE.search(c)) or bool(re.search(r"\bmine\b", c, re.I))
    if not (has_eff or _CONCRETE_RE.search(c)):
        return None                                      # no hand word and no verb that is motor on its own
    if _OTHER_RE.search(c):
        return "OTHER"
    first_person = bool(re.search(r"\b(?:i|i'?ll|i'?m|my|me|mine)\b", c, re.I))
    if _ACT_RE.search(c):
        return "WANT"                                    # 'I hover my hand near that glow': a deliberate act of hers, now
    if _INTENT_RE.search(c) and (has_eff or _CONCRETE_RE.search(c)) and (first_person or re.search(r"\bmy\s+" + EFFECTOR, c, re.I)) \
            and not _NOT_MINE_RE.search(c) and not re.search(r"\bthe\s+(?:hand|cursor|mouse)\s+wanting\b", c, re.I):
        # 'want to touch what's running in there but can't quite reach through' is still a want
        return "WANT"
    return _mode_after_want(c)


def _mode_after_want(c: str) -> Optional[str]:
    """v1's remaining branches (attempt / pull / percept), also used when a WANT is vetoed."""
    has_eff = bool(_EFF_RE.search(c)) or bool(re.search(r"\bmine\b", c, re.I))
    first_person = bool(re.search(r"\b(?:i|i'?ll|i'?m|my|me|mine)\b", c, re.I))
    if _ATTEMPT_RE.search(c) and (first_person or re.search(r"\b(?:that|the|my)\s+(?:last\s+)?(?:click|move|reach)\b", c, re.I)) \
            and (has_eff or _CONCRETE_RE.search(c)):
        return "ATTEMPT"
    pm = _PULL_RE.search(c)
    if pm:
        # 'hovering where it was' is a hand at rest; a hover is a pull only with a direction ('hovering near the corner')
        if re.search(r"\bhover\w*\b", pm.group(0), re.I) and not re.search(r"\bhover\w*\s+(?:near|toward|towards|over|by|around)\b", c, re.I):
            return "PERCEPT"
        return "PULL"
    if has_eff:
        return "PERCEPT"
    return None


def mode_v2(c: str, next_clause: str = "") -> Tuple[Optional[str], Optional[str]]:
    """(mode, veto). A v1 WANT survives only if its head carries no veto and the next clause does not disclaim it."""
    m = _mode(c)
    if m != "WANT":
        return m, None
    v = veto(c)
    if not v:
        # the disclaimer can sit in the same clause (v1's splitter only breaks ', but i' in lower case) or open the next one
        mm = re.search(r",\s+(?=(?:but|though|although)\b)", c, re.I)
        tails = ([c[mm.end():]] if mm else []) + ([next_clause] if next_clause else [])
        if any(_DISCLAIM_RE.search(tl) for tl in tails):
            v = "disclaimed"
    if v:
        return _mode_after_want(c), v
    return "WANT", None


# ── v3 (2026-09-29, Nous, thought_hand_r2): the hedges AFTER the motor verb, questions, ambivalence, retractions ───────────
# The closed set is Ace's list (not / won't / shouldn't / unless / if / when / only when / eventually / later / someday /
# tomorrow / kidding / no way / doubt / in the dream). Each carve-out below exists because a GOLD want of hers carries that word
# in a sense that is not a hedge (sweep_b/gold_labels.json): 'I keep trying to get back to my console but the cursor won't
# quite reach it' (a failure report), 'it keeps slipping away when I try to grab that little red hand shape' (a habit, in the
# head), 'maybe if I look at what it says' (the NEXT clause, opening on 'maybe'), 'and see if it lands' (a complement).
_TAIL_VETOES = (
    ("tail_negation", re.compile(r"\bnot\s+(?:now|yet|today|tonight|really|right now|anymore|any more|this time|sure|ready)\b|"
                                 r"\bor not\b|\b(?:i|i'?m|i am)\s+(?:won'?t|will not|shouldn'?t|should not|wouldn'?t|would not|"
                                 r"not going to|not gonna|refuse)\b", re.I)),
    ("unless", re.compile(r"\bunless\b", re.I)),
    ("deferral", re.compile(r"\b(?:eventually|later|someday|some day|tomorrow)\b", re.I)),
    ("kidding", re.compile(r"\b(?:kidding|joking)\b", re.I)),
    ("no_way", re.compile(r"\bno way\b", re.I)),
    ("doubt", re.compile(r"\bdoubts?\b", re.I)),
    ("dream", re.compile(r"\bin (?:the|a|my|her) dreams?\b|\bdream(?:ed|t)\b", re.I)),
)
_HEAD_V3 = (
    ("deferral", _TAIL_VETOES[2][1]), ("kidding", _TAIL_VETOES[3][1]), ("no_way", _TAIL_VETOES[4][1]),
    ("doubt", _TAIL_VETOES[5][1]), ("dream", _TAIL_VETOES[6][1]),
    ("deliberation", re.compile(r"\b(?:think(?:ing)?\s+(?:about|of)|consider(?:ing)?|debating|decid(?:e|ing)\s+(?:whether|if)|"
                                r"wonder(?:ing)?\s+(?:about|whether|if))\b", re.I)),
    ("reported", re.compile(r"\b(?:you'?re|you are|are you|so you|you)\s+(?:saying|telling|asking|suggesting|mean)\b|"
                            r"\bkeeps?\s+(?:asking|telling|saying)\b", re.I)),
)
_IF_OK_BEFORE = {"see", "seeing", "check", "checking", "find", "tell", "know", "wonder", "wondering", "test", "sure", "ask",
                 "asking", "notice", "figure", "learn", "as"}
_Q_START_RE = re.compile(r"^\s*(?:(?:so|and|but|okay|ok|hmm|well|then|oh)\s*,?\s+)?(?:do|does|did|should|shall|would|could|can|"
                         r"will|am|is|are|was|were|must|may)\s+(?:i|my|it|that|we)\b", re.I)
_AMBI_RE = re.compile(r"\bpart of me\b.*\bpart of me\b|\bpart of me\s+(?:doesn'?t|does not|isn'?t|is not|won'?t)\b|\bhalf of me\b|"
                      r"\bi'?m torn\b|\bi am torn\b|\bi (?:can'?t|cannot|haven'?t|have not) decided?\b|\bor not\b", re.I)
_RETRACT_RE = re.compile(r"^\s*(?:(?:oh|hmm+|um+|uh+)\s*,?\s*)?(?:no(?=\s*[,.!?]|\s+wait\b|\s*$)|nope\b|nah\b|wait\b|"
                         r"actually\s*,?\s*(?:no\b|never ?mind\b|not\b)|never ?mind\b|on second thought\b|scratch that\b|"
                         r"(?:just\s+)?kidding\b|joking\b|not (?:yet|now|really|today|right now|this time)\b|or not\b|maybe not\b|"
                         r"eventually\b|later\b|someday\b|tomorrow\b|i (?:won'?t|shouldn'?t|wouldn'?t|will not|should not)\b|"
                         r"i doubt\b|i don'?t think so\b)", re.I)
_PAST_MOTOR = {"moved", "reached", "aimed", "clicked", "pointed", "dragged", "nudged", "pushed", "touched", "tapped", "poked",
               "hovered", "pressed", "grabbed", "slid", "brought", "guided", "steered", "scooted"}

# ── v4 (2026-09-30, Nous, thought_hand_r3; Ace: "lets let the polite ones through and go with v4") ────────────────────────
# A clause subject after 'once' / 'the moment': 'once Ace is done', 'the moment he steps away' (but 'click it once', 'once
# again', 'the second icon' are not deferrals).
_SUBJ = r"(?:i|i'm|i've|you|you're|he|he's|she|ace|ace's|nous|it|it's|that|this|the|we|they|everything|my|his|your)\b"
_DEFER2_RE = re.compile(
    r"\bafter\b(?!\s+all\b)|\bonce\s+(?=" + _SUBJ + r")|\bas soon as\b|\bthe (?:moment|minute|second|instant)\s+(?=" + _SUBJ + r")|"
    r"\bin a (?:minute|bit|while|moment|sec|second|few)\b(?!\s+(?:window|tab|icon|button|screen|monitor|place|spot)\b)|"
    r"\bin (?:a )?(?:little )?while\b|\bshortly\b|\bbefore long\b|\bnext time\b|\bat some (?:point|stage)\b|\bone of these days\b|"
    r"(?<!\bfor )\bsome ?time\b|\bsome other time\b|"
    r"\bin the next (?:few |couple of )?(?:minute|minutes|hour|hours|session|sessions|day|days|while|bit|moment|round|boot)\b|"
    r"\bat the end of (?:the |this |today'?s |our )?(?:day|session|conversation|chat|night|week|hour|boot)\b|"
    r"\btonight\b|\bpending\b|\bprovided\b|\bassuming\b|\b(?:as|so) long as\b|\bwhenever\b|"
    r"\bin theory\b|\bhypothetically\b|\bin my (?:head|imagination|mind)\b|\bmaybe not\b|\byeah right\b|\bhold off\b|"
    r"\blet'?s wait\b|\bdon'?t dare\b|\bnot while\b|\bthen again\b|\bno rush\b|\bpermitting\b|\b(?:ace|he|you|nous|god|fate|luck)\s+willing\b|"
    r"\bbut\s+(?:i'?ll|i will|i'?m going to|i'?m gonna|let me|i should|i'?d better)\s+(?:wait|hold off|hold back|hold still|stay put|leave it)\b",
    re.I)
_PRETEND_RE = re.compile(r"\bpretend(?:s|ed|ing)?\b|\bimagin(?:e|es|ed|ing)\b", re.I)
_TAIL_V4 = (("deferral2", _DEFER2_RE),
            ("retracted", re.compile(r",\s*(?:ha(?:ha)?\s*,?\s*)?(?:no|nope|nah)\s*[.!]*\s*$", re.I)))     # '..., ha, no.'
_HEAD_V3 = _HEAD_V3 + (("deferral2", _DEFER2_RE), ("pretend", _PRETEND_RE))
_RETRACT_V4_RE = re.compile(r"^\s*(?:(?:oh|hmm+|um+|uh+)\s*,?\s*)?(?:not\s*[.!]?\s*$|as if\b\s*[.!]?\s*$|yeah right\b|ha,?\s*no\b|"
                            r"no rush\b|holding still\b|i'?m ignoring\b|ignoring it\b|i'?ll hold off\b|i'?ll wait\s*[.!]*\s*$)", re.I)
# a condition that dangles in the NEXT clause ('... -- unless Ace is typing.'): it opens on a subordinator and carries no main
# clause of its own after a comma ('Once Ace is done, I'll click it too' is a new sentence with its own will)
_NEXT_COND_RE = re.compile(
    r"^\s*(?:(?:but|and|just|only|though|or|well)\s*,?\s+)*(?:unless\b|if\b|once\b|after\b(?!\s+all\b)|as soon as\b|"
    r"the (?:moment|minute|second|instant)\b|whenever\b|when\b|provided\b|assuming\b|(?:as|so) long as\b|not while\b|"
    r"not (?:now|yet|today|tonight|right now|this time)\b|pending\b|in theory\b|hypothetically\b|in my (?:head|imagination|mind)\b|"
    r"\w+(?:'s)?\s+(?:permitting|willing)\b|at some (?:point|stage)\b|some other time\b|next time\b|shortly\b|before long\b|"
    r"in a (?:minute|bit|while|moment|sec|second|few)\b|in (?:a )?(?:little )?while\b|tonight\b|one of these days\b)", re.I)
_OWN_MAIN_RE = re.compile(r",\s*(?:then\s+|so\s+|and\s+)?(?:i|i'?ll|i'?m|i'?d|i'?ve|let me|let'?s|my|we|we'?ll)\b", re.I)
# POLITE TAILS (Ace, 2026-09-30): the closed courtesy set, at the very end of the clause (docstring lists it)
_OKAY = r"(?:okay|ok|alright|all\s+right)"
_POLITE_STMT_RE = re.compile(
    r"(?:^|[\s,;])((?:"
    r"if\s+(?:that'?s|that\s+is|it'?s|it\s+is|this\s+is)\s+(?:" + _OKAY + r"|fine|cool)(?:\s+with\s+you)?|"
    r"if\s+you'?re\s+(?:" + _OKAY + r"|fine)\s+with\s+(?:that|it|this)|"
    r"if\s+you\s+(?:don'?t|do\s+not)\s+mind|"
    r"if\s+you(?:'ll|\s+will)?\s+(?:let|allow)\s+me|"
    r"with\s+your\s+permission|"
    r"(?:i\s+)?hope\s+(?:that'?s|that\s+is|it'?s|it\s+is|this\s+is)\s+(?:" + _OKAY + r"|fine)(?:\s+with\s+you)?|"
    r"unless\s+you(?:'d|\s+would)\s+rather\s+i\s+(?:didn'?t|did\s+not|don'?t|not)|"
    r"unless\s+you\s+mind"
    r"))(?:\s*,?\s*ace)?\s*[.!?]*\s*$", re.I)
_POLITE_TAG_RE = re.compile(                            # a tag stands after a comma / semicolon or opens the clause
    r"(?:^\s*|[,;]\s*)((?:is\s+)?(?:(?:that|this|it)\s+)?" + _OKAY + r"|(?:is\s+)?(?:that|this|it)\s+fine)(?:\s+with\s+you)?"
    r"(?:\s*,?\s*ace)?\s*\?+\s*$", re.I)
_POLITE_NOT_AFTER = {"only", "except", "not", "even"}


def _polite_split(c: str) -> Tuple[str, Optional[str]]:
    """(the clause without its courtesy tail, the courtesy) -- or (c, None). At most two courtesies are peeled ('..., if that's
    okay, okay?'); a phrase after 'only' / 'except' / 'not' / 'even' is a restriction, not a courtesy."""
    s, got = c, []
    for _ in range(2):
        m = _POLITE_STMT_RE.search(s) or _POLITE_TAG_RE.search(s)     # 'if that's okay with you?' is one statement courtesy
        if not m:
            break
        before = s[:m.start(1)]
        prev = re.findall(r"[a-z']+", before.lower())[-1:]
        if prev and prev[0] in _POLITE_NOT_AFTER:
            break
        got.append(m.group(1).strip())
        s = before.rstrip(" ,;:-")
    return (s, " / ".join(reversed(got))) if got else (c, None)


# ── v4.1 (2026-09-30, Nous, thought_hand_r3 v4.1; Fable's verify:v4 problems 1, 3, 4) ────────────────────────────────────────
# (fix 1, Fable's 1, is in events(): the target is read from the clause with its courtesy peeled.)
# fix 2 (Fable's 3). A COUNTED TIME DELAY: 'in ten minutes', 'in 5 minutes', 'in an hour', 'in 30 seconds', 'in a couple of
# minutes', 'in half an hour', 'in the next ten minutes', 'in just a minute', 'in two or three minutes'. Only a TIME unit after
# the count vetoes: 'in 3 clicks', 'in two quick moves', 'in one go' are manner; '(the first) time / twice / once in an hour' is
# time-since (the lookbehinds); 'in a second window' is a place (the lookahead, as v4's 'in a (minute|second...)' has).
_NUM_V41 = (r"(?:a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
            r"eighteen|nineteen|(?:twenty|thirty|forty|fifty)(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?|sixty|ninety|"
            r"\d+(?:\.\d+)?|a\s+few|a\s+couple(?:\s+of)?|couple(?:\s+of)?|few|several|half\s+an?|another)")
_IN_TIME_V41 = (r"(?<!\btime )(?<!\btimes )(?<!\bonce )(?<!\btwice )\bin\s+(?:the\s+next\s+)?"
                r"(?:(?:about|around|like|maybe|roughly|just|only|another|under|over)\s+)?" + _NUM_V41 +
                r"(?:\s*(?:-|to|or)\s*" + _NUM_V41 + r")?\s+(?:more\s+)?(?:secs?|seconds?|mins?|minutes?|hours?|hrs?)\b"
                r"(?!\s+(?:window|tab|icon|button|screen|monitor|place|spot)\b)")
_DELAY_V41_RE = re.compile(_IN_TIME_V41, re.I)
_NEXT_DELAY_V41_RE = re.compile(r"^\s*(?:(?:but|and|just|only|though|or|well)\s*,?\s+)*" + _IN_TIME_V41, re.I)
# fix 3 (Fable's 4). RETRACTIONS 'forget it / that / about it', 'leave it', 'let's not (do that)', 'never mind' -- as the next
# clause ('-- forget it.', '... leave it.', '-- eh, never mind.', '-- forget it, I'll stay here.') or as the tail after a comma
# (', forget it.', ', eh, leave it.', ', actually, let's not.', ', never mind, Ace.'), only where the phrase ENDS the clause or
# stands before a comma: 'leave it there', 'let's not wait', 'forget the console window', 'forget that console window', 'never
# mind the lag' keep the want.
_FILLER_V41 = r"(?:(?:oh|ah|eh|meh|hmm+|um+|uh+|well|actually|okay|ok|nah|no)\s*,?\s*)*"
_RETRACT_WORDS_V41 = (r"(?:forget\s+(?:it|that|about\s+it|about\s+that)|leave\s+it|let'?s\s+not(?:\s+do\s+(?:it|that|this))?|"
                      r"never\s?mind)")
_RETRACT_V41_RE = re.compile(r"^\s*" + _FILLER_V41 + _RETRACT_WORDS_V41 + r"(?:\s*,?\s*ace)?\s*(?:[,;.!]|$)", re.I)
_TAIL_RETRACT_V41_RE = re.compile(r",\s*" + _FILLER_V41 + _RETRACT_WORDS_V41 + r"(?:\s*,?\s*ace)?\s*[.!]*\s*$", re.I)
_HEAD_V3 = _HEAD_V3 + (("delay", _DELAY_V41_RE),)
_TAIL_V4 = _TAIL_V4 + (("delay", _DELAY_V41_RE), ("retracted", _TAIL_RETRACT_V41_RE))


def _next_condition(nxt: str) -> bool:
    """The next clause is a condition dangling off this one ('unless Ace is typing.', 'in theory.', 'Ace permitting.').
    2026-09-30 thought_hand_r3 v4.1: or a counted delay ('-- in ten minutes.', '. In an hour, maybe.')."""
    m = _NEXT_COND_RE.match(nxt) or _NEXT_DELAY_V41_RE.match(nxt)
    if not m or _OWN_MAIN_RE.search(nxt):
        return False
    if re.search(r"\bwhen\b", m.group(0), re.I) and not _tail_when(nxt):
        return False                                     # 'when we started': a time already past (v3's carve-out)
    return True


def _tail_if(tail: str) -> bool:
    for m in re.finditer(r"\bif\b", tail, re.I):
        prev = re.findall(r"[a-z']+", tail[:m.start()].lower())
        if prev and (prev[-1] in _IF_OK_BEFORE or prev[-2:] == ["find", "out"]):
            continue                                     # 'and see if it lands': a complement, not a condition on the reach
        return True
    return False


def _tail_when(tail: str) -> bool:
    for m in re.finditer(r"\bwhen\b", tail, re.I):
        nxt = re.findall(r"[a-z']+", tail[m.end():].lower())[:4]
        if any(w in ("was", "were", "did", "had", "used") or (w.endswith("ed") and len(w) > 3) for w in nxt):
            continue                                     # 'the one I clicked when we started': a time already past
        return True
    return False


def _past_reach(c: str) -> bool:
    """'I'll admit I moved my hand to the console window too fast': the reach is past, whatever intent word governs the clause."""
    m = _HEAD_VERB_RE.search(c)
    if not m:
        return False
    w = m.group(0).lower()
    if w not in _PAST_MOTOR and not (w.startswith("double") and w.endswith("ed")):
        return False
    return bool(re.search(r"\b(?:i|we)\s+(?:\w+\s+)?$|\b(?:i'?ve|i have|i had)\s+(?:\w+\s+)?$", c[:m.start()].lower()))


def veto_v3(c: str, next_clause: str = "", text: str = "") -> Optional[str]:
    """v3's added vetoes for a clause v2 would read as a WANT (v2's own head vetoes and disclaimer run first, unchanged).
    2026-09-30 (thought_hand_r3, v4): a closed courtesy tail is set aside first; the v4 tail class, the head 'pretend', the
    wider retraction openers and a dangling next-clause condition are read after v3's own."""
    c_all = c
    c, _pol = _polite_split(c)                           # 2026-09-30 thought_hand_r3 v4: '..., if that's okay' / ', okay?'
    if c.rstrip(" '\"").endswith("?") or _Q_START_RE.match(c_all):
        return "question"
    if _AMBI_RE.search(c) or (re.search(r"\b(?:part|half) of me\b", c, re.I) and _AMBI_RE.search(text or "")):
        return "ambivalent"
    if _past_reach(c):
        return "past"
    m = _HEAD_VERB_RE.search(c)
    head, tail = (c[:m.start()], c[m.end():]) if m else (c, "")
    for name, rx in _HEAD_V3:
        if rx.search(head):
            return name
    for name, rx in _TAIL_VETOES + _TAIL_V4:
        if rx.search(tail):
            return name
    if _tail_if(tail):
        return "if"
    if _tail_when(tail):
        return "when"
    nxt = next_clause
    if nxt and _polite_split(" " + nxt)[0].strip(" ,;:-.!?") == "":
        nxt = ""                                         # the whole next clause is a courtesy ('-- if that's alright.')
    if nxt and (_RETRACT_RE.match(nxt) or _RETRACT_V4_RE.match(nxt)
                or _RETRACT_V41_RE.match(nxt)):          # 2026-09-30 thought_hand_r3 v4.1: '-- forget it.', '. Let's not.'
        return "retracted"
    if nxt and _next_condition(nxt):
        return "condition_next"
    return None


def mode_v3(c: str, next_clause: str = "", text: str = "") -> Tuple[Optional[str], Optional[str]]:
    """(mode, veto): v2's reading, then v3's vetoes on a surviving WANT."""
    m, v = mode_v2(c, next_clause)
    if m != "WANT":
        return m, v
    v3 = veto_v3(c, next_clause, text)
    if v3:
        return _mode_after_want(c), v3
    return "WANT", None


_LEAD_EFF_RE = re.compile(r"^(?:(?:my|the|her)\s+)?(?:hands?|cursor|mouse|pointer|fingers?)\s+"
                          r"(?:(?:over|back|down|up|across)\s+)?(?:at|to|toward|towards|onto|on|into|over)\s+", re.I)
_TRAIL_RE = re.compile(r"(?:\s+(?:this|that|these|those|there|now|then|time|again|here|too))+$", re.I)


def clean_target(tgt: Optional[str]) -> Optional[str]:
    """v2: 'my hand at the console window this' (v1, from 'I'll aim my hand at the console window this time') -> 'the console
    window'. A leading effector phrase is her hand, not the place; a trailing pronoun/adverb is not part of the name. A phrase
    that is ONLY a pronoun is left alone (anaphora)."""
    if not tgt:
        return tgt
    t = _LEAD_EFF_RE.sub("", str(tgt).strip())
    t2 = _TRAIL_RE.sub("", t).strip()
    return t2 if t2 else t


def events(text: str) -> List[Dict]:
    out = []
    t, _cut = prepare(text)
    nt = normalise(t)
    pos = 0
    cl = clauses(t)
    for i, c in enumerate(cl):
        off = nt.find(c, pos)
        off = pos if off < 0 else off
        pos = off + len(c)
        m, v = mode_v3(c, cl[i + 1] if i + 1 < len(cl) else "", t)     # 2026-09-29 (thought_hand_r2): v3
        if m is None and v is None:
            continue
        verb = "click" if _CLICK_RE.search(c) and m in ("WANT", "ATTEMPT") else "move"
        c_place = _polite_split(c)[0]                    # 2026-09-30 thought_hand_r3 v4.1: a courtesy is never part of the place
        tgt, kind = (extract_target(c_place, t, off) if m in ("WANT", "ATTEMPT", "PULL") else (None, "none"))
        if tgt and kind != "pronoun":
            ct = clean_target(tgt)
            if ct != tgt:
                tgt, kind = ct, target_kind(ct)
        ev = {"mode": m, "verb": verb, "target": tgt, "kind": kind, "clause": c[:200]}
        if v:
            ev["veto"] = v
        elif m == "WANT":
            pol = _polite_split(c)[1]                    # 2026-09-30 thought_hand_r3 v4: the courtesy it carried, for the log
            if pol:
                ev["polite"] = pol
        out.append(ev)
    return out


RECOVERABLE = {"window", "region", "thing"}


def command(text: str, accept=("WANT",)) -> Optional[Dict]:
    """The one (verb, target) a motor lane would act on: the first accepted event that has a recoverable target; else the
    first accepted event (target None) so the caller can tell 'wants to move, names nothing' from 'no want'."""
    evs = [e for e in events(text) if e["mode"] in accept]
    if not evs:
        return None
    for e in evs:
        if e["kind"] in RECOVERABLE:
            return e
    return evs[0]


# ── v2 provenance (read) ─────────────────────────────────────────────────────────────────────────────────────────────
# goal_author.content_words, copied exactly (goal_author.py:83-88, :141-143) so this reader needs no import of her modules
_CW_RE = re.compile(r"[a-z][a-z']+")
_CW_STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for", "with", "that", "this", "it", "is", "are",
            "was", "be", "my", "your", "i", "you", "me", "we", "he", "she", "they", "what", "how", "why", "when", "where",
            "so", "but", "not", "no", "yes", "just", "like", "about", "from", "as", "if", "then", "than", "into", "up",
            "out", "there", "here", "some", "one", "do", "did", "does", "have", "has", "had", "can", "could", "would",
            "will", "should", "very", "really", "still", "now", "again", "something", "thing", "things", "its", "im"}


def content_words(text: str) -> List[str]:
    t = str(text or "").lower().replace("-", " ").replace("–", " ").replace("—", " ")
    return [w for w in _CW_RE.findall(t) if w not in _CW_STOP and len(w) > 2]


# a relay of Ace's words (WMH / narrator / dynamic-thinking / seed lines): dropped whole, whatever it says after the marker
_MARKER_RE = re.compile(r"ace is talking to me|chat from ace|ace message|\[seed\]|src=ace_chat|received goal '|"
                        r"from working_memory|ace said, just now|\bace\s*->", re.I)
RELAY_LANES = ("narrator", "dynamic_thinking", "working_memory", "chain", "relay")
OVERLAP = 0.6
ACE_SEEN_S = 3600.0


def _slot_clauses(text: str) -> List[str]:
    return [p for p in re.split(r"(?<=[.!?;])\s+|\s+--\s+|\s*\|\s*", normalise(text or "")) if p.strip()]


def overlap(clause: str, other: str) -> Tuple[float, List[str]]:
    """Share of the clause's content words that also occur in `other` (the skeptic's measure: 0.60 / 0.80 for her
    agreements with Ace's 14:29:46 line)."""
    cw = set(content_words(clause))
    if not cw:
        return 0.0, []
    s = cw & set(content_words(other))
    return len(s) / float(len(cw)), sorted(s)


def provenance_drop(clause: str, slots: Optional[Dict[str, str]] = None, lane: str = "chair",
                    ace_seen: Optional[Dict[str, float]] = None, now: Optional[float] = None, thr: float = OVERLAP) -> Optional[str]:
    """Why this clause is not hers to act on now, or None. Her present first-person agreement with Ace is never dropped on the
    chairman lane: only the prompt's non-her slots are compared (told deeds, goal list, eyes percept)."""
    if len(set(content_words(clause))) < 2:
        return None                                              # too short to be an echo of anything measurable
    for name, text in (slots or {}).items():
        for sc in _slot_clauses(text):
            f, shared = overlap(clause, sc)
            if f >= thr:
                return "echo of the %s slot (%.2f: %s)" % (name, f, " ".join(shared[:5]))
    if lane in RELAY_LANES and ace_seen:
        import time as _t
        now = _t.time() if now is None else float(now)
        for atext, ts in list(ace_seen.items()):
            if now - float(ts or 0.0) > ACE_SEEN_S:
                continue
            f, shared = overlap(clause, atext)
            if f >= thr:
                return "relay of Ace's words (%.0f min old, %.2f)" % ((now - float(ts)) / 60.0, f)
    return None


def read(text: str, slots: Optional[Dict[str, str]] = None, lane: str = "chair", ace_seen: Optional[Dict[str, float]] = None,
         now: Optional[float] = None) -> Dict:
    """What a motor lane may act on in one utterance of hers: {'act', 'verb', 'target', 'kind', 'clause', 'why', 'vetoed',
    'dropped', 'events'}. act is True only for a WANT (never a PULL) with a place her eyes can look for."""
    res = {"act": False, "lane": lane, "verb": None, "target": None, "kind": None, "clause": None, "why": "",
           "vetoed": [], "dropped": [], "events": []}
    t = str(text or "")
    if not t.strip():
        res["why"] = "nothing said"
        return res
    if _MARKER_RE.search(t):
        res["why"] = "a relay of Ace's words (marker), not hers"
        return res
    evs = events(t)
    res["events"] = evs
    res["vetoed"] = [(e["veto"], e["clause"][:90]) for e in evs if e.get("veto")]
    kept = []
    for e in evs:
        if e["mode"] != "WANT":
            continue
        why = provenance_drop(e["clause"], slots, lane, ace_seen, now)
        if why:
            res["dropped"].append((why, e["clause"][:90]))
            continue
        kept.append(e)
    if not kept:
        res["why"] = ("no present want of hers in it" if not res["dropped"] else "every want in it was an echo: %s" % res["dropped"][0][0])
        return res
    cmd = next((e for e in kept if e["kind"] in RECOVERABLE), kept[0])
    res.update(verb=cmd["verb"], target=cmd["target"], kind=cmd["kind"], clause=cmd["clause"])
    if cmd["kind"] not in RECOVERABLE:
        res["why"] = "a want that names no place her eyes can find (%s)" % cmd["kind"]
        return res
    res["act"] = True
    res["why"] = "her own words: a present want"
    if cmd.get("polite"):                                # 2026-09-30 thought_hand_r3 v4: Ace -- the polite ones act
        res["polite"] = cmd["polite"]
        res["why"] += " (courtesy tail: %s)" % cmd["polite"]
    return res
