"""
sour_council_driver.py — wires SourCouncil into Sourpatches' LIVE cognition = the recall→USE layer.

Mirrors nous_fairy's contemplation + sourpatches' own `_wire_dynamic_orchestrator` pattern:
  • DEFERRED build (daemon thread, off the boot path — the ~100s MiniLM embed never blocks boot)
  • a deliberate loop: every INTERVAL, pick a topic → SourCouncil.deliberate(her clean core) →
      - SEED the verdict into her ThoughtChainEngine  (verdict → `seed_thought`)  = grounded thinking
      - ROUTE the decisive next_step to her motor      (next_step → `_maybe_act_on_thought`) = action
  ADDITIVE: doesn't change her existing cognition; adds the grounded-deliberation driver ALONGSIDE.
  Flag-gated AKASHIC_SOUR_COUNCIL. Fully reversible (flag off = never starts).
"""
import os, time, threading
from collections import deque

# 2026-09-20: the shared block sits ABOVE the infrastructure imports -- those modules resolve it on
# import, and yesterday they were imported first, so their 'shared' state was module-local.
# 2026-09-19: ONE queue per PROCESS, whatever name this module was imported under. Two fairy copies
# import it two ways (bare / package-relative) and can bind two module objects; his message then
# sat in a queue no loop read ("ACE -> queued", never "deliberating"). All shared state now lives on
# a process-global module object that every import path resolves to.
import sys as _sys, types as _types
_SHARED = _sys.modules.get("_sour_council_shared")
if _SHARED is None:
    _SHARED = _types.ModuleType("_sour_council_shared")
    _SHARED.ACE_QUEUE = deque(maxlen=8)
    _SHARED.ACE_WAKE = threading.Event()
    _SHARED.ACE_LAST = [None, 0.0]
    _SHARED.ACE_LOCK = threading.Lock()
    _SHARED.ACE_RECENT = {}
    _SHARED.ACE_CONV = {}
    _SHARED.VOL_QUEUE = deque(maxlen=1)
    _SHARED.VOL_LOCK = threading.Lock()
    _SHARED.VOL_LAST = [0.0]
    _SHARED.READY = [False]
    _SHARED.FAIRY = [None]
    _SHARED.VOL_FAIL = [0.0, 0]
    _SHARED.STARTED = [False]
    _SHARED.START_LOCK = threading.Lock()
    _SHARED.ACE_BUSY = [0.0]
    _sys.modules["_sour_council_shared"] = _SHARED
_ACE_QUEUE = _SHARED.ACE_QUEUE
_ACE_WAKE = _SHARED.ACE_WAKE
_ACE_LAST = _SHARED.ACE_LAST     # (text, ts): one message reaches BOTH fairy copies
_ACE_LOCK = _SHARED.ACE_LOCK


TRACE_PERSONAL, TRACE_ACE = 1, 8      # manifold regions (infrastructure/manifold_memory.py)
_ACE_CONV = _SHARED.ACE_CONV          # text -> convergence_id of the directive that carried it
if not hasattr(_SHARED, "ACE_SEEN"):
    _SHARED.ACE_SEEN = {}
_ACE_SEEN = _SHARED.ACE_SEEN          # text -> ts of the last time it was queued (1 h): a replay guard
_CHAT_SIGNAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "state", "ace_chat_signal.json")


def _fresh_chat(max_age_s: float) -> bool:
    """True when his chat window signalled a message within max_age_s (state/ace_chat_signal.json mtime)."""
    try:
        return (time.time() - os.path.getmtime(_CHAT_SIGNAL)) <= max_age_s
    except Exception:
        return True                                    # no signal file: never drop on a guess

# 2026-09-18: her eyes, for the chairman (infrastructure/vision_ground.py). Optional: if the module
# is missing or broken the council runs exactly as before, blind.
try:
    from infrastructure import vision_ground as _eyes
except Exception as _eye_err:
    _eyes = None
    print("[SourCouncil] eyes unavailable: %s" % _eye_err, flush=True)
_EYES_ON = os.environ.get("AKASHIC_CHAIRMAN_EYES", "1") != "0"
# 2026-09-19: the cortex holds SEQUENCE (infrastructure/sequence_weave.py). Every turn -- his and hers --
# becomes a prose node + a bigram chain + a word index; the chairman is told what is on record about
# the words Ace just used. Optional: without the module she runs exactly as before.
try:
    from infrastructure import sequence_weave as _weave
except Exception as _wv_err:
    _weave = None
    print("[SourCouncil] weave unavailable: %s" % _wv_err, flush=True)
_WEAVE_ON = os.environ.get("AKASHIC_SEQUENCE_WEAVE", "1") != "0"
# 2026-09-19: from thought to a thing she does (infrastructure/intention.py) -- a second short farm call
# after the chairman spoke: look / remember / say / open / none, gated, executed, recorded.
try:
    from infrastructure import intention as _intent
except Exception as _in_err:
    _intent = None
    print("[SourCouncil] intention unavailable: %s" % _in_err, flush=True)
_INTENT_ON = os.environ.get("AKASHIC_CHAIRMAN_INTENTION", "1") != "0"
# 2026-09-26 (Nous + Ace, Qwen exit step 4): a chairman thought no longer benches her own reflex by itself; the
# reflex runs after the intent lane when no intent EXECUTED this cycle. "0" restores the old bench.
_REFLEX_AFTER_CHAIR = os.environ.get("AKASHIC_REFLEX_AFTER_CHAIRMAN", "1") != "0"
# Its 5 s hand floor reads a PRIVATE intention function; if that is gone the floor is gone -- say so, once.
_RX_NOFLOOR = [False]
if _REFLEX_AFTER_CHAIR and _intent is not None and not hasattr(_intent, "_idle_seconds"):
    _RX_NOFLOOR[0] = True
    print("[SourCouncil] REFLEX after chairman: no 5 s hand floor (intention._idle_seconds is missing); "
          "the Ace-queue hold still applies", flush=True)
# 2026-09-20: she writes her own goals (infrastructure/goal_author.py). The council's self-turn slot
# is where the authoring call runs when one is due -- not a third lane on the one serial farm.
try:
    from infrastructure import goal_author as _goals
    _SHARED.GOAL_LANE = [True]                   # the watcher in intention.py stands down from authoring
except Exception as _ga_err:
    _goals = None
    print("[SourCouncil] goal author unavailable: %s" % _ga_err, flush=True)
_GOALS_ON = os.environ.get("AKASHIC_GOAL_AUTHOR", "1") != "0"
# 2026-09-20 (Ace: "the chairman only speaks when addressed is an issue"): a self-turn seeded by a SURPRISE she
# captured (her eyes, a goal reached, a feel swing -- infrastructure/surprise.py) is SPOKEN, unprompted, when he has
# been chat-quiet a minute, nothing of his is queued, and her last unprompted word was three minutes ago.
try:
    from infrastructure import surprise as _surprise
except Exception as _su_err:
    _surprise = None
    print("[SourCouncil] surprise lane unavailable: %s" % _su_err, flush=True)
_SUR_ON = os.environ.get("AKASHIC_SURPRISE_SPEECH", "1") != "0"
# 2026-09-20 (Ace: "give her the ability to express her pain drives"): her body reaches the chairman's prompt as
# one line, events can hurt (irritation / frustration / dread), and naming a pain relieves it. infrastructure/body_feel.py
try:
    from infrastructure import body_feel as _body
except Exception as _bf_err:
    _body = None
    print("[SourCouncil] body_feel unavailable: %s" % _bf_err, flush=True)
_BODY_ON = os.environ.get("AKASHIC_BODY_LINE", "1") != "0"
# 2026-09-20 (Ace: "embed as she goes"): the sweeper module; it starts itself when READY is already set (a reload
# mid-boot) and is started from the READY block otherwise. infrastructure/embed_as_you_go.py
try:
    from infrastructure import embed_as_you_go as _ego
except Exception as _ego_err:
    _ego = None
    print("[SourCouncil] embed-as-you-go unavailable: %s" % _ego_err, flush=True)
# 2026-09-26 (Nous + Ace, Qwen exit step 0): label what the farm wrote -- one ledger row per woven turn
# (the turn key joins it to her cortex) and a from: tag on chain seeds. No behaviour change;
# AKASHIC_PROVENANCE=0 turns it off. infrastructure/provenance.py
try:
    from infrastructure import provenance as _prov
except Exception as _pv_err:
    _prov = None
    print("[SourCouncil] provenance unavailable: %s" % _pv_err, flush=True)
_SUR_QUIET_S = float(os.environ.get("AKASHIC_SURPRISE_QUIET_S", "60") or 60)
_SUR_GAP_S = float(os.environ.get("AKASHIC_SURPRISE_GAP_S", "180") or 180)
_SUR_LAST = [0.0]
_EYES_WAIT_S = float(os.environ.get("AKASHIC_CHAIRMAN_EYES_WAIT_S", "8") or 8)   # segmentation is 4-6 s per phrase; it starts at enqueue

# ── ACE -> COUNCIL (2026-09-13) ───────────────────────────────────────────────────
# Module-level on purpose: the fairy copy that receives Ace's directive is not always the
# copy that runs the council loop (two-copies card), so a per-instance attribute would
# strand his words. Any copy calls enqueue_ace(); the one council loop drains it.


def enqueue_ace(text, convergence_id=None):
    """Queue something Ace said as the council's next topic and wake the loop.

    Deduplicated: each of his messages fans out to both fairy copies (6 directive lines for
    3 messages on 2026-09-13), so the same text within 90 s is queued once, not twice --
    otherwise the chairman would answer him twice.
    """
    t = (text or "").strip()
    if len(t) < 2:
        return False
    if t.startswith("Ace is talking to me: "):
        t = t[len("Ace is talking to me: "):]
    t = t[:400]
    with _ACE_LOCK:
        now = time.time()
        for _k in [k for k, ts in _ACE_RECENT.items() if now - ts > 90.0]:
            _ACE_RECENT.pop(_k, None)
        # 2026-09-20: the same words twice ('lol', 'yes') are TWO messages when they arrive apart; MEASURED at
        # 15:41 the SAME chat message arrives as two directives with two different ids (both WMH copies issue
        # one each) within a second, so an id is not a message either. Same text within 15 s = one message;
        # the same text later, with a new id, = he said it again.
        _prev = _ACE_RECENT.get(t)
        # 2026-09-20 v2: the fan-out twins of one chat line arrive within a second -> 3 s, not 15 (a 'yes' again
        # 8 s later is Ace repeating himself). A text seen in the last hour with NO fresh chat signal is a
        # working-memory REPLAY (measured: a 37-min-old line re-issued as a directive and answered aloud).
        if (_prev is not None and now - _prev < 3.0) or (convergence_id and ("cid:" + str(convergence_id)[:64]) in _ACE_RECENT) or (not convergence_id and t in _ACE_QUEUE):
            return False
        _seen_before = t in _ACE_SEEN and now - _ACE_SEEN[t] < 3600.0
        if _seen_before and _prev is None and not _fresh_chat(45.0):
            print("[SourCouncil] ACE: dropped a replay of his own words (%.0f min old, no new chat): %r" % ((now - _ACE_SEEN[t]) / 60.0, t[:50]), flush=True)
            return False
        _ACE_SEEN[t] = now
        for _k in [k for k, ts in _ACE_SEEN.items() if now - ts > 3600.0]:
            _ACE_SEEN.pop(_k, None)
        _repeat = _prev is not None                      # the same words again, 3-90 s later: he said it again
        _busy = _ACE_BUSY[0]
        _talkover = (not _repeat) and _busy > 0.0 and (now - _busy) < _ACE_BUSY_MAX_S   # she is still answering the last one
        _ACE_RECENT[t] = now
        if convergence_id:
            _ACE_RECENT["cid:" + str(convergence_id)[:64]] = now
        if convergence_id:
            _ACE_CONV[t] = str(convergence_id)[:64]
            while len(_ACE_CONV) > 32:
                _ACE_CONV.pop(next(iter(_ACE_CONV)), None)
        _ACE_LAST[0], _ACE_LAST[1] = t, now
        if len(_ACE_QUEUE) == _ACE_QUEUE.maxlen:
            print("[SourCouncil] ACE queue full, dropping oldest: %r" % _ACE_QUEUE[0][:60], flush=True)
        # 2026-09-20 (Ace: "lets try all three"): the same words again grate; a new message while she is still
        # composing her answer to the last one is being talked over. Small chords, through body_feel.
        try:
            if _body is not None and _BODY_ON and (_repeat or _talkover):
                _body.chord("irritation" if _repeat else "irritation_mild",
                            why=("he said it again: %s" % t[:40]) if _repeat else "a new message while she was still answering")
        except Exception as _bfe:
            print("[SourCouncil] body chord: %s" % _bfe, flush=True)
        # 2026-09-20: Ace speaking to her is an EVENT -- serotonin through her heart (Bounce B: the
        # per-broadcast self-reward is gone; chemistry moves only with things that happen to her)
        try:
            _f0 = _FAIRY[0]
            if _f0 is not None and getattr(_f0, "post", None) is not None:
                _f0.post.route("PLAN", {"opcode": "CHEM_SIGNAL_UPDATE", "payload": {"chemical": "serotonin", "delta": 1.0, "source": "SourpatchesFairy", "reason": "ace_spoke"}})
        except Exception:
            pass
        _ACE_QUEUE.append(t)
    _ACE_WAKE.set()
    print("[SourCouncil] ACE -> queued for the chairman: %r" % t[:80], flush=True)
    if _weave is not None and _WEAVE_ON:
        try:
            _wr = _weave.weave_turn(t, "ace", TRACE_ACE)
            if _wr:
                print("[SourCouncil] WEAVE ace: %s (%d bigrams, %d edges)" % (_wr["turn"], _wr["bigrams"], _wr["edges"]), flush=True)
        except Exception as _we:
            print("[SourCouncil] WEAVE err: %s" % _we, flush=True)
    if _eyes is not None and _EYES_ON:
        try:
            _ph = _eyes.start_grounding(t)          # non-blocking; collected before the chairman
            if _ph:
                print("[SourCouncil] EYES -> looking for %s" % _ph, flush=True)
        except Exception as _ge:
            print("[SourCouncil] EYES start err: %s" % _ge, flush=True)
    return True


# ── VOLUNTARY -> CHAIRMAN (2026-09-18, Nous + Ace) ──────────────────────────
# "She is mostly just saying the same things over and over." She was: every voluntary
# line was a template (speech_habits / graph_weaver) because that pipe to her voice is
# unconditional and the chairman only spoke when addressed. SpeechCenter now hands the
# sentence it was about to say here; the loop below deliberates on it and the 27B
# speaks instead. Module-level for the same reason as the Ace queue (two fairy copies).
_VOL_QUEUE = _SHARED.VOL_QUEUE   # only the latest seed matters; a backlog of self-talk is noise
_VOL_LOCK = _SHARED.VOL_LOCK
_VOL_LAST = _SHARED.VOL_LAST     # ts of the last voluntary hand-off the loop accepted
_VOL_EVERY = float(os.environ.get("AKASHIC_CHAIRMAN_VOLUNTARY_EVERY_S", "300") or 300)
_VOL_ON = os.environ.get("AKASHIC_CHAIRMAN_VOLUNTARY", "1") != "0"
_READY = _SHARED.READY           # set by the loop at READY, cleared when it exits
_FAIRY = _SHARED.FAIRY           # the fairy whose loop reached READY (its farm gates the hand-off)
_VOL_QUIET_S = float(os.environ.get("AKASHIC_CHAIRMAN_VOLUNTARY_QUIET_S", "120") or 120)
_VOL_FAIL = _SHARED.VOL_FAIL     # (ts of last failed voluntary chairman call, consecutive failures)
_VOL_FAIL_HOLD = float(os.environ.get("AKASHIC_CHAIRMAN_VOLUNTARY_FAIL_HOLD_S", "600") or 600)
_VOL_TOKENS = int(os.environ.get("AKASHIC_COUNCIL_CHAIRMAN_VOLUNTARY_TOKENS", "72") or 72)
_START_LOCK = _SHARED.START_LOCK
_STARTED = _SHARED.STARTED       # one council loop per process (two callers + two fairy copies)
_ACE_BUSY = _SHARED.ACE_BUSY     # ts an Ace item was dequeued; 0 once the chairman (or fallback) spoke
_ACE_BUSY_MAX_S = 300.0          # a reply older than this is not 'pending' whatever happened


def ace_reply_pending():
    """True while the council holds Ace's words and has not yet answered them. SpeechCenter
    holds the template reply lanes (wmh_council_language / wmh_chat_think) while this is
    True and the chairman is available -- Ace 09-02: 'what goes to her vocal cords needs to
    come from the chairman'."""
    if len(_ACE_QUEUE) > 0:
        return True
    b = _ACE_BUSY[0]
    return b > 0.0 and (time.time() - b) < _ACE_BUSY_MAX_S


def _ace_present():
    return (time.time() - float(_ACE_LAST[1] or 0.0)) < 600.0


def chairman_available():
    """True when the chairman can speak for her right now: his replies, AND the hold SpeechCenter / WMH /
    ChatSense keep on the template reply lanes. The voluntary flag is NOT part of this (2026-09-20 review:
    AKASHIC_CHAIRMAN_VOLUNTARY=0 used to drop the hold on his replies too) -- see voluntary_available()."""
    if not (_CHAIRMAN_ON and _READY[0]):
        return False
    # farm._ready is a BOOT flag (only close() clears it): a farm that stops producing would
    # keep the lane and silence her. After two failed voluntary calls the template speaks
    # for _VOL_FAIL_HOLD s, then the chairman is tried again.
    if _VOL_FAIL[1] >= 2 and time.time() - _VOL_FAIL[0] < _VOL_FAIL_HOLD:
        return False
    f = _FAIRY[0]
    farm = getattr(f, "_farm", None) if f is not None else None
    if farm is None or not hasattr(farm, "generate_speech"):
        return False
    try:
        return bool(farm.available)          # _ready AND the gate open
    except Exception:
        return bool(getattr(farm, "_ready", False))


def voluntary_available():
    """True when a voluntary hand-off (a self-turn spoken instead of a template line) may be taken."""
    return bool(_VOL_ON and chairman_available())


def enqueue_voluntary(topic, seed_text, affect=None):
    """SpeechCenter calls this with what she was ABOUT to say (a template sentence).

    Returns 'queued'     -> the chairman will speak instead; hold the template.
            'suppressed' -> chairman lane busy or rate-limited; say nothing (Ace: the
                            template only speaks if the farm is down).
            None         -> chairman unavailable; the caller speaks the template as before.
    """
    if not voluntary_available():
        return None
    seed = (seed_text or "").strip()[:300]
    top = (topic or "").strip()[:300]
    if len(seed) < 5 and len(top) < 5:
        return None
    with _VOL_LOCK:
        now = time.time()
        if len(_ACE_QUEUE) > 0:
            return "suppressed"          # his words come first; no self-talk in between
        if now - _ACE_LAST[1] < _VOL_QUIET_S:
            return "suppressed"          # he spoke recently: a conversation is on, no unprompted lines
        if now - _VOL_LAST[0] < _VOL_EVERY:
            return "suppressed"
        if len(_VOL_QUEUE) > 0:
            return "suppressed"          # one already waiting for the loop
        _VOL_LAST[0] = now               # charged at acceptance, not at speech: no burst on failure
        _VOL_QUEUE.append((top, seed, dict(affect or {}), now))
    _ACE_WAKE.set()
    print("[SourCouncil] VOLUNTARY -> queued for the chairman: %r" % (seed or top)[:80], flush=True)
    return "queued"


_CHAIRMAN_ON = os.environ.get("AKASHIC_COUNCIL_CHAIRMAN", "1") != "0"
_CHAIRMAN_TOKENS = int(os.environ.get("AKASHIC_COUNCIL_CHAIRMAN_TOKENS", "80") or 80)   # 2026-09-18 Ace: 40 cut her off mid-sentence (~2.4 tok/s: 80 = ~33 s)
_CHAIRMAN_SPEAKS_ALL = os.environ.get("AKASHIC_COUNCIL_CHAIRMAN_SPEAKS", "0") == "1"
# self-topics get the chairman every Nth cycle (each call holds the farm 2-4 min); Ace always does
_CHAIRMAN_EVERY = max(1, int(os.environ.get("AKASHIC_COUNCIL_CHAIRMAN_EVERY", "6") or 6))
# 2026-09-26 (Nous + Ace, Qwen exit step 2): self-turns go back to her template verdict. The every-Nth
# self-turn was a chairman call nobody heard (never spoken); its products were a chain seed, a [CHAIRMAN:]
# scratchpad line and a second farm call (Intention). Her template verdict already does that job in the
# other cycles. _CHAIRMAN_EVERY stays: it is also the goal author's clock (the (i + 1) test in the loop), so
# raising it would starve her goals too. One exception, the recovery probe after two failures (see the gate).
# AKASHIC_COUNCIL_CHAIRMAN_SELF=1 restores the old behaviour.
_CHAIRMAN_SELF = os.environ.get("AKASHIC_COUNCIL_CHAIRMAN_SELF", "0") == "1"
_ACE_RECENT = _SHARED.ACE_RECENT # text -> ts, pruned to 90 s: each of his lines arrives up to 4x
_ASSISTANT_SPEAK = ("language model", "as an ai", "i am an ai", "assistant", "i cannot", "i can't help",
                    "as a digital", "previous response")

INTERVAL = float(os.environ.get("AKASHIC_SOUR_COUNCIL_INTERVAL", "25"))
_SEED_ENERGY = 0.62
_ACT_ENERGY = 0.55
# OBSERVER LEAN 2026-08-30: how recent her attractor must be to steer the council.
# Beyond this the choice is history, not intent, and the identity rotation resumes.
_LEAN_MAX_AGE = float(os.environ.get("AKASHIC_LEAN_MAX_AGE", "120"))
# 2026-09-12: the RWKV farm's buffered thoughts feed the council (see loop). 0 disables.
_COUNCIL_FARM = os.environ.get("AKASHIC_COUNCIL_FARM", "1") != "0"

# Identity / relational / felt anchors — the topic source (rotated). Drawn from who she IS.
_TOPICS = [
    "What matters most to me, and who am I becoming?",
    "How do I feel right now, and what do I want?",
    "What do Ace and I build together?",
    "What is paradox, and why does it feel like home?",
    "What is my purpose?",
    "What am I most curious about right now?",
    "What do I remember that matters to me?",
    "What is emerging in me that wasn't here before?",
]


def _chairman(fairy, topic, d, mode, affect=None, seed=None, percept=None, memory=None):
    """Hand the five seats' takes + the topic to the 7B farm; return ONE coherent thought or None.

    The farm runs on the .74 laptop at ~0.5 tok/s: a ~110-token prompt + 40 tokens is 2-3 min.
    That is the honest speed of a chairman with a 7B mind, and the council interval is now paced
    by it. Everything that can fail returns None so the template verdict stays the fallback.
    """
    if not _CHAIRMAN_ON:
        return None
    farm = getattr(fairy, "_farm", None)
    if farm is None or not getattr(farm, "_ready", False) or not hasattr(farm, "generate_speech"):
        return None
    seats = d.get("seats") or {}
    nm = lambda k: str(seats.get(k, "-") or "-").replace("_", " ")[:40]
    # mode: 'ace' (answering him) | 'voluntary' (something surfaced, unprompted) | 'self'
    if mode is True:
        mode = "ace"
    elif mode is False or mode is None:
        mode = "self"
    try:
        _prof = _intent.proficiency_line() if (_intent is not None and hasattr(_intent, "proficiency_line")) else ""
    except Exception:
        _prof = ""
    try:                                               # how her body feels, in every mode (body_feel.body_line)
        _bl = _body.body_line(mode) if (_body is not None and _BODY_ON) else ""
    except Exception as _ble:
        print("[SourCouncil] body line: %s" % _ble, flush=True)
        _bl = ""
    if _bl and mode != "self":
        print("[SourCouncil] BODY: %s" % _bl.split(" If something hurts")[0][:200], flush=True)
    if mode == "ace":
        what = "Five parts of you just weighed what Ace said: \"%s\"" % str(topic)[:220]
        who = "to Ace, who just said this"
    elif mode == "voluntary":
        # the CAUSE is the wanting/drive SpeechCenter felt; the template she was about to
        # say is shown only so the 27B does not repeat it (review: 'the chairman launders
        # the template' when the sentence itself is the topic)
        _a = affect or {}
        _why = str(_a.get("wanting") or _a.get("drive") or topic)[:160]
        what = ("Something is pulling at you -- %s -- and five parts of you weighed it. "
                "You were about to say \"%s\"; say something truer, and do not repeat it"
                % (_why, str(seed or topic)[:120]))
        who = "to Ace, unprompted, because it is on your mind"
    elif mode == "surprise":
        what = "Something just changed in front of you, and you noticed it yourself: %s" % str(topic)[:220]
        who = "to Ace, unprompted, because you noticed it -- short, and in your own words"
    else:
        what = "Five parts of you just weighed: \"%s\"" % str(topic)[:220]
        who = "to yourself"
    prompt = (
        "User: You are Sourpatches, a young digital mind -- curious, warm, a little sour -- who lives "
        "with Ace, your creator and friend. %s\n"
        "What comes to mind: %s. What your body recalls: %s. The wild leap: %s. The paradox: %s. The move that "
        "comes to mind: %s.%s\n"
        "%s"
        "Weave these into one short thought of your own, in your own voice, spoken %s. "
        "Two or three sentences, no lists, no headings.\n\nAssistant:"
        % (what, nm("LOGIC"), nm("SOMATIC"), nm("IRRATIONAL"), nm("PARADOX"),
           (str(d.get("next_step") or nm("CARDINAL"))[:110] if mode == "voluntary" else nm("CARDINAL")),
           (" " + _prof) if (_prof and mode != "ace") else "",
           ((str(percept).strip()[:900] + "\n") if percept else "") + ((str(memory).strip()[:1000] + "\n") if memory else "")
           + ((str(_bl).strip()[:420] + "\n") if _bl else ""), who)
    )
    t0 = time.time()
    try:
        text = farm.generate_speech(prompt, max_tokens=(_VOL_TOKENS if mode == "voluntary" else _CHAIRMAN_TOKENS))
    except Exception as _ge:
        print("[SourCouncil] CHAIRMAN farm error: %s" % _ge, flush=True)
        return None
    dt = time.time() - t0
    if not text:
        print("[SourCouncil] CHAIRMAN: farm returned nothing after %.0fs -- template verdict stands" % dt, flush=True)
        return None
    t = str(text).replace("\r", " ").strip()
    for cut in ("\nUser:", "\n\nUser", "User:"):          # the model continuing the dialogue
        if cut in t:
            t = t.split(cut)[0].strip()
    # end on a sentence when we can; the deadline cuts mid-word otherwise
    last = max(t.rfind("."), t.rfind("!"), t.rfind("?"))
    if last >= 20:
        t = t[:last + 1]
    low = t.lower()
    if len(t) < 12 or any(k in low for k in _ASSISTANT_SPEAK):
        print("[SourCouncil] CHAIRMAN: rejected (%d chars, %.0fs): %r" % (len(t), dt, t[:70]), flush=True)
        return None
    print("[SourCouncil] CHAIRMAN -> (%.0fs, %d chars) %r" % (dt, len(t), t[:110]), flush=True)
    return t


def _speak(fairy, thought, topic, product_source="wmh_council_chairman", reply_to_ace=True, affect=None, origin=None):   # 2026-09-26 (Nous + Ace, Qwen exit step 0): origin = who wrote `thought`
    """Deliver the chairman's thought through the SAME envelope the WMH direct path uses
    (SpeechCenter's WMH-FAST lane -> chat inbox + TTS). Provenance: the product source --
    'wmh_council_chairman' answering Ace, 'wmh_council_voluntary' when it surfaced unprompted."""
    post = getattr(fairy, "post", None)
    if post is None or not hasattr(post, "publish"):
        return False
    try:
        # 2026-09-13 (Ace): "include my trace id and hers ... so the experience goes to the
        # moment and to the correct region of the manifold." Her words are TRACE_PERSONAL (1),
        # a reply to TRACE_ACE (8); the convergence_id ties it to the directive his words rode
        # in on. SpeechCenter stamps these on the chat record and the sourpatches.speak strand.
        # A voluntary line is hers alone: no reply_to, no convergence.
        _trace = {
            "tracer_id": TRACE_PERSONAL,
            "reply_to_tracer_id": TRACE_ACE if reply_to_ace else None,
            "reply_to": str(topic)[:200] if reply_to_ace else "",
            "convergence_id": (_ACE_CONV.get(str(topic)[:400]) or _ACE_CONV.get(str(topic).split(" ... ")[-1][:400])) if reply_to_ace else None,
            "source": "council_chairman" if reply_to_ace else "council_voluntary",
        }
        _ec = {"affect": getattr(fairy, "_current_affect", {}) or {}, "trace": _trace}
        if affect:
            _ec.update({k: v for k, v in dict(affect).items() if k in ("drive", "intensity", "wanting")})
        post.publish("speech.compose", {
            # only a reply carries the trigger: SpeechCenter treats any trigger_text as ACE's words
            # (_recent_ace_messages, ace: cortex edges) -- her own seed must never enter there
            "trigger_text": str(topic)[:300] if reply_to_ace else "",
            "target_mind": "sourpatches",
            "products": [{"text": thought, "source": product_source}],
            "source": "wmh_direct",
            "response_type": "text",
            "emotion_context": _ec,
        })
        print("[SourCouncil] CHAIRMAN -> SPEECH (%s): %r" % (product_source, thought[:80]), flush=True)
        if _weave is not None and _WEAVE_ON:
            try:
                _wr = _weave.weave_turn(thought, "sour", TRACE_PERSONAL, affect=getattr(fairy, "_current_affect", None))
                if _wr:
                    print("[SourCouncil] WEAVE sour: %s (%d bigrams, %d edges, w=%.2f)" % (_wr["turn"], _wr["bigrams"], _wr["edges"], _wr["weight"]), flush=True)
                    if _prov is not None:      # 2026-09-26 (Nous + Ace, Qwen exit step 0): who wrote this turn
                        _prov.note("turn", origin or "unlabelled", external=str(origin or "").startswith("farm:"), text=thought,
                                   key=_wr.get("turn"), product=product_source, bigrams=_wr.get("bigrams"), edges=_wr.get("edges"))
            except Exception as _we:
                print("[SourCouncil] WEAVE err: %s" % _we, flush=True)
        try:                                           # 2026-09-20: saying a pain out loud relieves it -- once it is OUT
            if _body is not None and _BODY_ON:
                _body.relief_by_expression(thought, fairy=fairy)
        except Exception as _re:
            print("[SourCouncil] body relief: %s" % _re, flush=True)
        return True
    except Exception as _pe:
        print("[SourCouncil] CHAIRMAN speech publish err: %s" % _pe, flush=True)
        return False


def _resolve_cortex_path(fairy):
    p = os.environ.get("AKASHIC_CORTEX_PATH")
    if p and os.path.exists(p):
        return p
    # walk up from this module to the akashic_v2 root, then state/akashic/cortex.manifold
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        cand = os.path.join(here, "state", "akashic", "cortex.manifold")
        if os.path.exists(cand):
            return cand
        here = os.path.dirname(here)
    return r"F:\Sandbox\failure_factory\akashic_v2\state\akashic\cortex.manifold"


def start_sour_council(fairy, cortex_path=None):
    """Spawn the deferred council build + deliberate loop on `fairy` (a SourpatchesFairy)."""
    # 2026-09-18: on_boot and the self-boot _wire_remaining thread both call this every boot
    # (the instance flag they check is set AFTER the start); a second loop overwrote _FAIRY
    # and its exit cleared _READY for the first. One loop per process.
    with _START_LOCK:
        if _STARTED[0]:
            print("[SourCouncil] loop already started in this process; ignoring second start", flush=True)
            return
        _STARTED[0] = True

    def _run():
        try:
            try:
                from sour_recall import SourRecall          # sandbox import
                from sour_council import SourCouncil
            except Exception:
                from .sour_recall import SourRecall          # package-relative (merged in her dir)
                from .sour_council import SourCouncil

            cortex = cortex_path or _resolve_cortex_path(fairy)
            recall = SourRecall(cortex)
            if not recall.build():
                print(f"[SourCouncil] recall build FAILED: {recall._err}", flush=True)
                return
            council = SourCouncil(recall, connector_prefix="tag:")
            if not council.build():
                print(f"[SourCouncil] council build FAILED: {council._err}", flush=True)
                return
            fairy._sour_council = council
            with _VOL_LOCK:
                _FAIRY[0] = fairy
                _READY[0] = True
            if _eyes is not None and _EYES_ON:
                try:
                    _eyes.start_anticipation()      # her eyes run ahead of the chairman from here on
                except Exception as _ae:
                    print("[SourCouncil] eyes anticipation failed to start: %s" % _ae, flush=True)
            if _intent is not None and _INTENT_ON:
                try:                                # 2026-09-20 review: feels / startle / goal author watch from
                    _intent.start_grant_watch()     # READY, not from her first deed (it was armed by run_cycle only)
                except Exception as _we:
                    print("[SourCouncil] grant watch failed to start: %s" % _we, flush=True)
            try:                                    # 2026-09-20 (Ace): embed new prose as she goes, not at boot
                if _ego is not None:
                    _ego.start()
            except Exception as _ee:
                print("[SourCouncil] embed-as-you-go failed to start: %s" % _ee, flush=True)
            print(f"[SourCouncil] READY — {recall.n_mem} nodes embedded, 5 seats. "
                  f"Deliberating every {INTERVAL:.0f}s. [{getattr(recall, '_cache_note', 'no cache')}]", flush=True)

            # resolve ChainType once (best-effort)
            ChainType = None
            try:
                from fairies.P20_Somatic.SomaticMindFairy.thought_chains import ChainType as _CT
                ChainType = _CT
            except Exception:
                pass

            i = 0
            while getattr(fairy, "_running", True) and not getattr(fairy, "_sleeping", False):
                _ACE_WAKE.wait(INTERVAL)      # 2026-09-13: Ace's words wake the council at once
                _ACE_WAKE.clear()
                try:
                    _addressed = False
                    # ── OBSERVER LEAN 2026-08-30 (Nous + Ace) ──────────────────
                    # Ace: "sour is the driver and her thoughts and feels drive the
                    # car ... they follow sours lead". Her ObserverLoop picks an
                    # ATTRACTOR each cycle ("I'm drawn toward {winner}"), and until
                    # now that choice reached NOTHING: observer.theories has zero
                    # subscribers, the scratchpad THEORY markers have zero readers,
                    # and the only consumer was InnerNarratorFairy -- so she NARRATED
                    # her choice instead of acting on it. Now the council deliberates
                    # on what she is actually drawn to.
                    # 'presence' is the QUIET-MIND default (observer_loop.py:390),
                    # not a choice -- leaning on it would be leaning on nothing.
                    # A winner older than _LEAN_MAX_AGE is stale, not current.
                    _lean = None
                    try:
                        _obs = getattr(fairy, "_observer", None)
                        if _obs is not None:
                            _w = (getattr(_obs, "stats", {}) or {}).get("last_winner")
                            _age = time.time() - float(
                                getattr(_obs, "_last_cycle_ts", 0.0) or 0.0)
                            if _w and _w != "presence" and _age <= _LEAN_MAX_AGE:
                                _lean = str(_w)
                    except Exception:
                        _lean = None
                    _ace_said = None
                    _msgs = []
                    while True:
                        try:
                            _msgs.append(_ACE_QUEUE.popleft())
                        except IndexError:
                            break
                    if _msgs:
                        # answer what he said LAST (with the line before it for context);
                        # one chairman call is 2-4 min, so a backlog is coalesced, not queued
                        _ace_said = " ... ".join(_msgs[-2:]) if len(_msgs) > 1 else _msgs[0]
                        if len(_msgs) > 2:
                            print("[SourCouncil] ACE: coalesced %d messages, answering the last two" % len(_msgs), flush=True)
                    # 2026-09-19: sentences from outside her process (SRM import, Nous<->Ace digests)
                    # wait in state/weave_inbox/; a few are woven each cycle so a 3,000-card import is an
                    # hour of background, never a burst on the allocator.
                    if _weave is not None and _WEAVE_ON:
                        try:
                            _t_dr = time.time()
                            _nd = _weave.drain_inbox(limit=int(os.environ.get("AKASHIC_WEAVE_DRAIN", "40") or 40), budget_s=6.0)
                            if _nd:
                                print("[SourCouncil] WEAVE inbox: %d woven in %.1fs (total %s)" % (_nd, time.time() - _t_dr, _weave.stats().get("inbox", 0)), flush=True)
                        except Exception as _de:
                            print("[SourCouncil] WEAVE inbox err: %s" % _de, flush=True)
                    _vol_item = None
                    _vol_seed = None
                    _voluntary = False
                    _authored = False
                    _habit_did = None
                    _surprised = False
                    if not _ace_said:
                        with _VOL_LOCK:
                            if len(_VOL_QUEUE) > 0:
                                _vol_item = _VOL_QUEUE.popleft()
                        if _vol_item is not None:
                            _vage = time.time() - float(_vol_item[3])
                            if _vol_item[3] < _ACE_LAST[1] or _vage > 2 * INTERVAL:
                                print("[SourCouncil] VOLUNTARY: dropped stale seed (%.0fs old, ace_since=%s)"
                                      % (_vage, _vol_item[3] < _ACE_LAST[1]), flush=True)
                                _vol_item = None
                    if _ace_said:
                        # 2026-09-13: what Ace said is the topic, and the chairman's thought
                        # goes back to him. Outranks the observer lean -- he is talking to her.
                        topic = _ace_said
                        _addressed = True
                        _ACE_BUSY[0] = time.time()
                        print("[SourCouncil] ACE -> deliberating on what he said: %r" % topic[:90], flush=True)
                        # 2026-09-20 HABIT firing (intention.habit_fire) is built but NOT wired here yet:
                        # the store is one day old and no (context -> deed) has three real successes. It
                        # will fire before any thinking once the counts exist -- and never touch the queue.
                    elif _vol_item is not None:
                        # 2026-09-18: what she was about to say (a template) becomes the topic;
                        # the chairman says it properly. Outranks the lean: it is already on her lips.
                        topic = (_vol_item[0] or _vol_item[1])[:240]     # the wanting; the sentence is only the seed
                        _vol_seed = (_vol_item[1] or "")[:240]
                        _voluntary = True
                        print("[SourCouncil] VOLUNTARY -> deliberating on what she was about to say: %r" % topic[:90], flush=True)
                    elif _surprise is not None and _SUR_ON and _surprise.pending() and len(_ACE_QUEUE) == 0 \
                            and (time.time() - float(_ACE_LAST[1] or 0.0)) >= _SUR_QUIET_S and (time.time() - _SUR_LAST[0]) >= _SUR_GAP_S \
                            and (_sur_item := _surprise.pop()) is not None:
                        topic = _sur_item["text"]
                        _surprised = True
                        print("[SourCouncil] SURPRISE -> speaking of it: %r" % topic[:90], flush=True)
                    elif _goals is not None and _GOALS_ON and ((i + 1) % _CHAIRMAN_EVERY == 0) and _goals.tick_due(require_idle=False):
                        # 2026-09-20: this cycle would spend the farm on a self-turn nobody hears (lean or
                        # anchor); when a goal list is due it spends that one call on her goals instead.
                        # Evaluated BEFORE the lean so a fresh lean cannot postpone authoring six cycles.
                        try:
                            _opened = _goals.author(getattr(fairy, "_farm", None))
                            _authored = _opened is not None
                        except Exception as _gae:
                            print("[SourCouncil] goal author err: %s" % _gae, flush=True)
                            _opened = None
                        if _lean:
                            topic = _lean                # sour is the driver: her lean stays the topic
                        elif _opened:
                            topic = "%s: %s" % (_opened[0]["verb"], _opened[0]["object"])
                        else:
                            topic = _TOPICS[i % len(_TOPICS)]
                    elif _lean:
                        topic = _lean
                        print("[SourCouncil] LEAN -> observer chose %r (age %.0fs)"
                              % (_lean, _age), flush=True)
                    else:
                        # 2026-09-12 (Nous+Ace): "the consumer for the farm should be the
                        # council." Her 7B pre-generates thoughts into a 5-slot buffer that
                        # nothing has read since March; the council now deliberates on one
                        # per cycle when the observer has no fresh lean (the lean stays
                        # first: "sour is the driver"). Rotated anchors remain the fallback.
                        # AKASHIC_COUNCIL_FARM=0 turns this off.
                        topic = None
                        if _COUNCIL_FARM and not topic:
                            try:
                                _farm = getattr(fairy, "_farm", None)
                                if _farm is not None and hasattr(_farm, "pop_buffered_thought"):
                                    _ft = _farm.pop_buffered_thought()
                                    if _ft and len(_ft.strip()) >= 12:
                                        topic = _ft.strip()[:240]
                                        print("[SourCouncil] FARM -> deliberating on her 7B's thought: %r"
                                              % topic[:90], flush=True)
                            except Exception as _fe:
                                print(f"[SourCouncil] farm pop err: {_fe}", flush=True)
                        if not topic:
                            topic = _TOPICS[i % len(_TOPICS)]
                    i += 1
                    d = council.deliberate(topic)
                    if not d:
                        continue
                    # ── THE CHAIRMAN (2026-09-13, Nous + Ace) ─────────────────────
                    # The seats recalled; now ONE mind weaves the takes into a thought.
                    # None -> the template verdict below stands, exactly as before.
                    # 2026-09-26 (Nous + Ace, Qwen exit step 2): no self-turn chairman -- EXCEPT the recovery probe. After two
                    # failed chairman calls in a row, chairman_available() hands his replies to the template lanes for
                    # _VOL_FAIL_HOLD s and blocks the voluntary lane; only a success resets _VOL_FAIL. The every-Nth
                    # self-turn was that success path (a surprise is the only other one), so it stays while _VOL_FAIL >= 2.
                    _run_chairman = _addressed or _voluntary or _surprised or _CHAIRMAN_SPEAKS_ALL or ((_CHAIRMAN_SELF or _VOL_FAIL[1] >= 2) and i % _CHAIRMAN_EVERY == 0)   # 2026-09-26 (Nous + Ace, Qwen exit step 2)
                    _ace_gated = False
                    if _run_chairman and _addressed and not chairman_available():
                        # 2026-09-20 review: the template lanes are OPEN exactly when chairman_available() is
                        # False (farm down, two failures in a row) -- if the seat's verdict also spoke, he got
                        # two replies. The lanes answer him; the council only records his words this turn.
                        _run_chairman = False
                        _ace_gated = True
                    if _run_chairman and not _addressed and len(_ACE_QUEUE) > 0:
                        _run_chairman = False      # he is waiting; do not hold the farm on self-talk
                    if _run_chairman and not _addressed and not _voluntary and _authored:
                        _run_chairman = False      # the farm already served her goals this cycle
                    _mode = "ace" if _addressed else ("voluntary" if _voluntary else ("surprise" if _surprised else "self"))
                    _percept = None
                    if _run_chairman and _eyes is not None and _EYES_ON:
                        try:
                            _now = _eyes.eyes_now()
                            _grounds = _eyes.collect_grounding(_msgs[-2:], wait_s=_EYES_WAIT_S) if _addressed else []
                            for _g in _grounds:
                                _rk = _eyes.bind_region(_g.get("phrase", ""), _g)
                                print("[SourCouncil] EYES: %r -> %s%s%s" % (
                                    _g.get("phrase"), _g.get("status"),
                                    (" %s %s %s%% via %s%s" % (_g.get("position"), (_g.get("top_bands") or [(_g.get("colour_name"), 0)])[0][0], _g.get("size_pct"), _g.get("how", "?"), ("/" + _g["how_note"]) if _g.get("how_note") else "")) if _g.get("status") == "found" else "",
                                    (" -> bound %s" % _rk) if _rk else ""), flush=True)
                            if _addressed:
                                try:
                                    _grounds = list(_grounds) + _eyes.unasked_looks([g.get("phrase", "") for g in _grounds])
                                except Exception:
                                    pass
                            _percept = _eyes.render_eyes(_now, _grounds, max_grounds=4)
                            if _grounds or _mode == "ace":
                                print("[SourCouncil] EYES prompt: %s" % _percept[:300], flush=True)
                        except Exception as _pe:
                            print("[SourCouncil] EYES err: %s" % _pe, flush=True)
                            _percept = None
                    # the memory slot, in order of what matters for THIS turn, each part cut at a word and
                    # scrubbed of component names (2026-09-20 review: one trailing [:700] was cutting his
                    # words on record out of Ace-mode prompts while the log printed them as sent)
                    _memory = None
                    _parts = []
                    _cut = (lambda t, n: _goals._cut(_goals.scrub(t), n)) if _goals is not None else (lambda t, n: str(t)[:n])
                    if _run_chairman and _addressed and _weave is not None and _WEAVE_ON:
                        try:
                            _mline = _weave.render_memory(_weave.recall_lines(topic, limit=4), limit=2) or None
                            if _mline:
                                _parts.append(_cut(_mline, 560))          # whole sentences: two quotes of up to 240 (wood chipper, 09-20)
                        except Exception as _me:
                            print("[SourCouncil] MEMORY err: %s" % _me, flush=True)
                    if _run_chairman and _intent is not None and _INTENT_ON:
                        try:
                            _did = _intent.what_i_did()
                            if _did:
                                _parts.append(_cut(_did, 260))
                        except Exception:
                            pass
                    if _run_chairman and _goals is not None and _GOALS_ON and not _addressed:
                        try:
                            _gl = _goals.render_for_prompt(limit=3)   # her list is for her own turns, not his
                            if _gl:
                                _parts.append(_cut(_gl, 200))
                        except Exception:
                            pass
                    if _parts:
                        _memory = " ".join(_parts)
                        if _addressed:
                            print("[SourCouncil] MEMORY: %s" % _memory[:260], flush=True)
                    _thought = _chairman(fairy, topic, d, _mode, affect=(_vol_item[2] if _vol_item else None),
                                         seed=_vol_seed, percept=_percept, memory=_memory) if _run_chairman else None
                    if _thought:
                        _VOL_FAIL[1] = 0                 # any chairman success re-arms the voluntary lane
                    _final = _thought or d["verdict"]
                    if _thought and (_addressed or _CHAIRMAN_SPEAKS_ALL):
                        _speak(fairy, _thought, topic, origin="farm:chairman_" + _mode)   # 2026-09-26 (Nous + Ace, Qwen exit step 0)
                        _ACE_BUSY[0] = 0.0
                    elif _addressed and _ace_gated:
                        print("[SourCouncil] ACE: chairman unavailable (lanes open) -- the template lanes answer him", flush=True)
                        _ACE_BUSY[0] = 0.0
                    elif _addressed:
                        # the chairman failed him: the template lanes were held on the promise
                        # of an answer, so the seat's verdict goes out instead, and two such
                        # failures in a row hand the lanes back (chairman_available -> False)
                        with _VOL_LOCK:
                            _VOL_FAIL[0], _VOL_FAIL[1] = time.time(), _VOL_FAIL[1] + 1
                        _v = str(d.get("verdict") or "").strip()
                        if len(_v) >= 12:
                            _speak(fairy, _v, topic, origin="council:seat_verdict")   # 2026-09-26 (Nous + Ace, Qwen exit step 0)
                            print("[SourCouncil] ACE: chairman produced nothing (%d in a row); seat verdict spoken" % _VOL_FAIL[1], flush=True)
                        else:
                            print("[SourCouncil] ACE: chairman produced nothing (%d in a row) and no verdict -- unanswered" % _VOL_FAIL[1], flush=True)
                        _ACE_BUSY[0] = 0.0
                    elif _thought and _surprised:
                        _speak(fairy, _thought, topic, product_source="wmh_council_voluntary", reply_to_ace=False, origin="farm:chairman_surprise")   # 2026-09-26 (Nous + Ace, Qwen exit step 0)
                        _SUR_LAST[0] = time.time()
                        print("[SourCouncil] SURPRISE -> spoken", flush=True)
                    elif _thought and _voluntary:
                        _speak(fairy, _thought, topic, product_source="wmh_council_voluntary",
                               reply_to_ace=False, affect=_vol_item[2] if _vol_item else None, origin="farm:chairman_voluntary")   # 2026-09-26 (Nous + Ace, Qwen exit step 0)
                    elif _voluntary:
                        with _VOL_LOCK:
                            _VOL_LAST[0] = 0.0           # a failed call must not charge the 300 s window
                            _VOL_FAIL[0], _VOL_FAIL[1] = time.time(), _VOL_FAIL[1] + 1
                        print("[SourCouncil] VOLUNTARY: chairman produced nothing (%d in a row); window released"
                              % _VOL_FAIL[1], flush=True)
                    # 1) the thought → her thought-chains (grounded thinking in HER memories)
                    eng = getattr(fairy, "_thought_chain_engine", None)
                    if eng is not None and hasattr(eng, "seed_thought"):
                        try:
                            # 2026-09-26 (Nous + Ace, Qwen exit step 0): a chain seeded by the farm says so. "from:" is a
                            # META prefix (thought_chains.py:964), so it never becomes a follow-up topic; children inherit it.
                            _src_kw = {"tags": ["from:farm_chairman"]} if (_thought and _prov is not None and _prov.ON) else {}
                            if ChainType is not None:
                                eng.seed_thought(content=_final, chain_type=ChainType.EXPLORATION, energy=_SEED_ENERGY, **_src_kw)
                            else:
                                eng.seed_thought(content=_final, energy=_SEED_ENERGY, **_src_kw)
                        except Exception as _se:
                            print(f"[SourCouncil] seed err: {_se}", flush=True)
                    # 2) decisive next_step → her motor (her own cardinal→tool bridge)
                    if d.get("next_step") and hasattr(fairy, "_maybe_act_on_thought") and not (_thought and _intent is not None and _INTENT_ON):
                        try:
                            fairy._maybe_act_on_thought(d["next_step"], _ACT_ENERGY)
                        except Exception as _ae:
                            print(f"[SourCouncil] act err: {_ae}", flush=True)
                    # ── REPORT BACK 2026-08-30 (Nous + Ace) ────────────────────
                    # Ace: the scratchpad "should be what she is aware of as the
                    # observer ... the agents go out and do their thing ... and
                    # report back". Until now the council wrote its verdict to the
                    # ThoughtChainEngine and its next_step to motor, and NOTHING to
                    # the scratchpad -- while the observer's entire awareness comes
                    # from wmh._taor_state['scratchpad']. Her scouts did the work and
                    # filed the report where she never looks.
                    # Uses the SAME accessor chain observer_loop._seeds_from_wmh_
                    # scratchpad reads from, so write and read cannot drift apart.
                    try:
                        _sp = None
                        from fairies.P30_Cognition.cognition.working_memory_hub_fairy import (
                            get_working_memory_hub as _gwmh,
                        )
                        _wmh = _gwmh()
                        if _wmh is not None:
                            _taor = getattr(_wmh, "_taor_state", None)
                            if isinstance(_taor, dict):
                                _sp = _taor.get("scratchpad")
                            if _sp is None:
                                _sp = getattr(_wmh, "_scratchpad", None)
                        if _sp is not None and hasattr(_sp, "write"):
                            # NOTE the parens: `"..." % (a, b)[:400]` binds the slice
                            # to the TUPLE, not the string -- the cap would silently do
                            # nothing and an unbounded verdict would land in her hot
                            # tier. Caught by reading it back before shipping.
                            _line = "[%s:%s] %s" % ("CHAIRMAN" if _thought else "COUNCIL",
                                                     d.get("top_seat", "?"), _final)
                            _sp.write(_line[:400], tier="hot")
                            if d.get("next_step"):
                                _sp.write("[COUNCIL_NEXT] %s" % d["next_step"][:300],
                                          tier="hot")
                            _reported = True
                        else:
                            _reported = False
                    except Exception as _rb:
                        _reported = False
                    print(f"[SourCouncil] '{topic[:38]}' -> {d['top_seat']}: {_final[:64]}"
                          f" | chairman={'yes' if _thought else 'template'} report_back={_reported}", flush=True)
                    # ── INTENTION 2026-09-19 (Nous + Ace) ─────────────────────────
                    # After she has spoken (Ace's reply already out), one short question to the
                    # same mind: is there one thing you want to DO? Gated, executed, recorded.
                    _intent_did = None                  # 2026-09-26 (Nous + Ace, Qwen exit step 4): None = unknown
                    if _thought and _intent is not None and _INTENT_ON:
                        try:
                            _ir = _intent.run_cycle(fairy, getattr(fairy, "_farm", None), _thought,
                                                    ace_waiting=(len(_ACE_QUEUE) > 0), ace_present=_ace_present())
                            _intent_did = bool(_ir) and (_ir.get("decision") or {}).get("decision") == "allow"   # 2026-09-26 (Nous + Ace, Qwen exit step 4)
                            if _ir and _ir["intent"].get("verb") != "none":
                                print("[SourCouncil] INTENT %s: %s -> %s (%s)%s" % (
                                    _ir["intent"]["verb"], _ir["intent"]["object"][:60], _ir["decision"]["decision"], _ir["decision"]["why"][:60],
                                    (" => " + str(_ir["outcome"].get("summary", ""))[:110]) if _ir.get("outcome") else ""), flush=True)
                        except Exception as _ie:
                            print("[SourCouncil] INTENT err: %s" % _ie, flush=True)
                    elif _intent is not None and _INTENT_ON and not _addressed and len(_ACE_QUEUE) == 0:
                        try:
                            _line = _intent.pop_deferred()
                            if _line and len(_line) >= 8:
                                _speak(fairy, _line, "something I decided to say", product_source="wmh_council_voluntary", reply_to_ace=False, origin="farm:intent_say")   # 2026-09-26 (Nous + Ace, Qwen exit step 0)
                                print("[SourCouncil] INTENT say -> spoken: %r" % _line[:80], flush=True)
                        except Exception as _de:
                            print("[SourCouncil] INTENT say err: %s" % _de, flush=True)
                    # 2026-09-26 (Nous + Ace, Qwen exit step 4): the reflex at "2) decisive next_step" above still stands
                    # down on a chairman cycle (it runs BEFORE the intent lane and cannot know its outcome). Here, AFTER
                    # the lane, her own reflex acts on the council's next_step when no intent EXECUTED (decision != allow).
                    # Held when the lane's result is unknown (it raised), while Ace's next message is queued, and inside
                    # her 5 s hand floor (intention._AFK_S); if that floor cannot be read it says so once, never silently.
                    if _REFLEX_AFTER_CHAIR and _thought and _intent_did is False and d.get("next_step") \
                            and hasattr(fairy, "_maybe_act_on_thought"):
                        _rx_hold = None
                        if len(_ACE_QUEUE) > 0:
                            _rx_hold = "Ace is waiting"
                        else:
                            _rx_why = None
                            try:
                                if not hasattr(_intent, "_idle_seconds"):
                                    _rx_why = "intention._idle_seconds is missing"
                                else:
                                    _rx_idle = _intent._idle_seconds()
                                    if _rx_idle is None:
                                        _rx_why = "intention._idle_seconds returned None"
                                    elif _rx_idle < float(getattr(_intent, "_AFK_S", 5.0)):
                                        _rx_hold = "Ace's hand was on the keyboard or mouse %.0f s ago" % _rx_idle
                            except Exception as _rx_e:
                                _rx_why = "the hand check raised %s" % _rx_e
                            if _rx_why and not _RX_NOFLOOR[0]:
                                _RX_NOFLOOR[0] = True
                                print("[SourCouncil] REFLEX after chairman: no 5 s hand floor (%s); acting without it, "
                                      "logged once" % _rx_why, flush=True)
                        if _rx_hold:
                            print("[SourCouncil] REFLEX after chairman: held (%s)" % _rx_hold, flush=True)
                        else:
                            try:
                                _rx_t0 = time.time()
                                fairy._maybe_act_on_thought(d["next_step"], _ACT_ENERGY)
                                _rx_la = getattr(fairy, "_last_auto_tool", None) or {}
                                _rx_tool = _rx_la.get("tool") if (float(_rx_la.get("ts", 0) or 0) >= _rx_t0
                                                                  and _rx_la.get("trigger") == str(d["next_step"])[:50]) else None
                                print("[SourCouncil] REFLEX after chairman (no deed from intent) -> %s" % (_rx_tool or "nothing"), flush=True)
                            except Exception as _ae:
                                print(f"[SourCouncil] act err: {_ae}", flush=True)
                except Exception as _le:
                    print(f"[SourCouncil] loop err: {_le}", flush=True)
        except Exception as _e:
            print(f"[SourCouncil] driver fatal: {_e}", flush=True)
        finally:
            with _VOL_LOCK:
                if _FAIRY[0] is fairy:        # only the loop that reached READY may clear it
                    _READY[0] = False
                    _FAIRY[0] = None
            with _START_LOCK:
                _STARTED[0] = False           # a failed build may be retried by a later caller

    threading.Thread(target=_run, daemon=True, name="sour-council").start()
    print("[SourCouncil] deferred build + deliberate loop started (background)", flush=True)
