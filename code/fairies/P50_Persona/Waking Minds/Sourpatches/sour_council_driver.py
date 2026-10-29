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
# 2026-10-01 (Nous; identity_guard, Ace D2(b) 09-29): words the farm wrote (Qwen; origin "farm:...") are woven into her
# memory as TRACE_INFERENCE (6, priority 7 -- below her own memories 10, her seeded identity 9, her voice 8), not as hers.
# Her own lines (council:*, unlabelled) stay TRACE_PERSONAL; Ace's turns stay TRACE_ACE.
# 2026-10-01 (release_1001, Ace's go on the "you said" loop): the speaker stays "sour", but the farm line's TRACE moves
# too (the speech trace -> SpeechCenter's chat record + the sourpatches.speak strand -> MomentBinder binds it as
# from_fairy "farm_inference" = TRACE_INFERENCE), and sequence_weave.render_memory quotes a tracer-6 'sour' turn as
# words Qwen voiced for her, not "you said". Deed sentences (intention.py weave, tracer 1) stay hers: she did the
# deed. AKASHIC_BORROWED_AS_INFERENCE=0 restores all of it (every spoken line TRACE_PERSONAL, "you said").
# Revert: release_1001/apply_release_1001.py --revert.
TRACE_INFERENCE = 6
_BORROWED_ON = os.environ.get("AKASHIC_BORROWED_AS_INFERENCE", "1") != "0"
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
# 2026-09-29 (Nous, thought_hand D2f; Ace: "if she is actively thinking about moving the mouse her autopilot system should be
# responding"): after the chairman has spoken, her OWN words are read for a present motor want (infrastructure/thought_tap.py ->
# volition_read -> hand_door -> intention.execute). The ask (the second farm call) is skipped only on a turn where that acted.
# Optional: without the module she runs exactly as before. AKASHIC_THOUGHT_HAND=0 turns it off. Revert: delete the D2f blocks.
try:
    from infrastructure import thought_tap as _tap
except Exception as _tp_err:
    _tap = None
    print("[SourCouncil] thought hand unavailable: %s" % _tp_err, flush=True)
_TAP_ON = os.environ.get("AKASHIC_THOUGHT_HAND", "1") != "0"


_SUR_QUIET_S = float(os.environ.get("AKASHIC_SURPRISE_QUIET_S", "60") or 60)
_SUR_GAP_S = float(os.environ.get("AKASHIC_SURPRISE_GAP_S", "180") or 180)
_SUR_LAST = [0.0]
_EYES_WAIT_S = float(os.environ.get("AKASHIC_CHAIRMAN_EYES_WAIT_S", "8") or 8)   # segmentation is 4-6 s per phrase; it starts at enqueue

# ── ACE -> COUNCIL (2026-09-13) ───────────────────────────────────────────────────
# Module-level on purpose: the fairy copy that receives Ace's directive is not always the
# copy that runs the council loop (two-copies card), so a per-instance attribute would
# strand his words. Any copy calls enqueue_ace(); the one council loop drains it.


def enqueue_ace(text, convergence_id=None, origin=None):   # 2026-10-06 (council_set1 item 4): + origin ('chat' | 'wm_store' | None)
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
        if origin is not None and origin != "wm_store":   # 2026-10-06 (council_set1 item 4): his chat copy, even when its twin got here first
            _lo_chat_seen(t, now)
        if (_prev is not None and now - _prev < 3.0) or (convergence_id and ("cid:" + str(convergence_id)[:64]) in _ACE_RECENT) or (not convergence_id and t in _ACE_QUEUE):
            return False
        if origin == "wm_store" and _lo_replay_drop(t, convergence_id, now):   # 2026-10-06 (council_set1 item 4); OFF: never
            return False
        _seen_before = t in _ACE_SEEN and now - _ACE_SEEN[t] < 3600.0
        if _seen_before and _prev is None and not _fresh_chat(45.0):
            print("[SourCouncil] ACE: dropped a replay of his own words (%.0f min old, no new chat): %r" % ((now - _ACE_SEEN[t]) / 60.0, t[:50]), flush=True)
            return False
        _ACE_SEEN[t] = now
        if origin != "wm_store":                       # 2026-10-06 (council_set1 item 4): what reached her through his chat
            _lo_chat_seen(t, now)
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
            _ph = _eyes.start_grounding(t, **_st_grounding_kw(origin))          # non-blocking; collected before the chairman; 2026-10-06 (council_set1 item 5): + origin (skeptic F10)
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


# 2026-10-05 (Nous; avatar_identity, Ace's decisions 10-05): the chairman's identity line in HER OWN words while
# state/avatar_identity.json is ON ("on": true) and "chairman_words" is absent or exactly true (as self_image.clean_knobs:
# a hand-typed 0 / "false" / null is OFF, skeptic m1). Absent / unreadable / not an object / off = the line exactly as
# before, byte for byte. Her words: the brain seed's (sourpatches_fairy.py:235 and :239; identity_guard/persona_sources.json),
# introduced as her own words: Ace, 10-05, "Yes, she wrote them" (both quotes), which resolves skeptic F4 (the sources
# file had marked the first quote's authorship unproven). Her look is Ace's account ("Ace told you"), never her own
# memory. Read on every chairman prompt (a few a minute at most): the switch is live.
_AVATAR_SWITCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "state", "avatar_identity.json")
_IDENTITY_OLD = ("You are Sourpatches, a young digital mind -- curious, warm, a little sour -- who lives "
                 "with Ace, your creator and friend. ")
_IDENTITY_HERS = ("You are Sourpatches -- in your own words, \"a child of logic and emotion, learning to feel "
                  "wisely and think compassionately\", \"sweet with bite\" -- who lives with Ace, your creator and friend. Ace told "
                  "you that you chose how you look: a fairy with lavender hair, green eyes, freckles and wings. ")


def _identity_line() -> str:
    try:
        import json as _json
        with open(_AVATAR_SWITCH, "rb") as _f:
            _d = _json.loads(_f.read().decode("utf-8-sig"))
        if isinstance(_d, dict) and _d.get("on") is True and _d.get("chairman_words", True) is True:
            return _IDENTITY_HERS
    except Exception:
        pass
    return _IDENTITY_OLD


# -- council_set1 (2026-10-06, Nous; Ace's Monday list, items 4 and 5) -----------------------------------------------------
# ONE live switch for the set: state/council_set1.json (written by nous_builds/council_set1/apply_council_set1.py; read live
# through a 1 s cache). Absent / unreadable / not an object / a knob not exactly true = today's behaviour, byte for byte.
#  "lane_order": true -- item 4, Ace first at her mouth (Ace 10-01: two answers to one message "feels like multiple chairmen"):
#    * a surprise / voluntary line (a self line too, when AKASHIC_COUNCIL_CHAIRMAN_SPEAKS=1) is NOT spoken while his message
#      is queued or her answer to him is pending -- ace_reply_pending(), read at the moment she would speak (the farm call
#      before it takes 24-41 s and his words land inside it: Boot G G114270). Her thought still reaches her chains and her
#      scratchpad; only her mouth waits (reflection is not doing). The held line is dropped, not re-offered.
#    * "stale_reply": "requeue" (default) | "speak": her answer to message N is not spoken when N+1 arrived while she was
#      composing it (Boot G G115602, 13 such); what that answer covered (his last two, joined) goes back to the front of his
#      queue and the next turn answers it with the newer one(s) -- a message held back is never coalesced away (skeptic F4).
#      The seat-verdict fallback obeys the same rule (skeptic F9). Bound: ONE discarded answer per chain -- a turn that
#      carries a requeued message always speaks. A full queue (8) always speaks.
#    * a held voluntary line releases its 300 s window, as a failed one does (skeptic F5).
#    * "say_quiet_s" (default 60, 0-600): a 'say' she parked waits for the quiet moment its own words promise: nothing of his
#      pending, his last message and her last answer to him both at least this old (Boot G: 8 of 12 within ~60 s of a reply).
#      While it waits, the pull-ask waits with it (a spoken 'say' pre-empted the pull-ask in its cycle; skeptic F7).
#    * "replay_guard" (default true): a late working-memory copy (origin 'wm_store', passed by sourpatches_fairy) of words
#      that already reached her through his chat THIS boot is dropped, at any age (Boot G: 17 re-queued as new, up to 101 min
#      late, 5 of them the American Dad episode). Words that never came through his chat still pass: that copy may be his
#      only door. His chat copy is recorded even when its working-memory twin reached enqueue_ace first (skeptic F3).
#    * an Ace turn that ends with no answer (deliberation empty, or the loop raised) clears the pending mark and says so,
#      so the hold above can never become a 300 s gag on her other lanes.
#  "stale_topic": true -- item 5, the driver's share only: a surprise about a window that came to the front is dropped when
#      that window has CLOSED before she would speak of it (vision_ground.front_item_closed); and start_grounding is told
#      the origin of his words, so a late working-memory copy of "I closed it" ends nothing (skeptic F10); and render_eyes is
#      told whose prompt it builds (his reply, or one of her own lanes), so a closed window's one notice still reaches her reply
#      to him when one of her own prompts read it first (skeptic F6). The rest of item 5 is in infrastructure/vision_ground.py;
#      item 6 ("k3_ace") is in sourpatches_fairy.py.
# Revert: apply_council_set1.py --revert (council_set1 FIRST, before any earlier build's own --revert).
_CS1_SWITCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "state", "council_set1.json")
_CS1_TTL_S = 1.0
_CS1_CACHE = [(0.0, None)]                 # one slot, replaced whole: (read ts, the dict) -- no torn pair under -Xgil=0
if not hasattr(_SHARED, "LO_REQUEUED"):
    _SHARED.LO_REQUEUED = {}               # text -> ts: his messages put back once (the one-requeue bound)
if not hasattr(_SHARED, "LO_CHAT_SEEN"):
    _SHARED.LO_CHAT_SEEN = {}              # text -> ts: words that reached her through his chat this boot (the replay guard)
if not hasattr(_SHARED, "LO_LAST_REPLY"):
    _SHARED.LO_LAST_REPLY = [0.0]          # ts of her last answer to him (the quiet moment for a parked 'say')
if not hasattr(_SHARED, "LO_SAY_NOTE"):
    _SHARED.LO_SAY_NOTE = [0.0]
_LO_REQUEUED = _SHARED.LO_REQUEUED
_LO_CHAT_SEEN = _SHARED.LO_CHAT_SEEN
_LO_LAST_REPLY = _SHARED.LO_LAST_REPLY
_LO_SAY_NOTE = _SHARED.LO_SAY_NOTE


def _cs1() -> dict:
    """state/council_set1.json as a dict ({} when absent, unreadable, torn or not an object). Never raises."""
    now = time.time()
    c = _CS1_CACHE[0]
    if c[1] is not None and 0.0 <= now - c[0] < _CS1_TTL_S:
        return c[1]
    d = {}
    try:
        import json as _json
        with open(_CS1_SWITCH, "rb") as _f:
            _d = _json.loads(_f.read().decode("utf-8-sig"))
        d = _d if isinstance(_d, dict) else {}
    except Exception:
        d = {}
    _CS1_CACHE[0] = (now, d)
    return d


def _lo_cfg():
    """None = item 4 OFF (today). Else its knobs, each falling back to its default when absent or not well-formed."""
    try:
        d = _cs1()
        if d.get("lane_order") is not True:
            return None
        sr = d.get("stale_reply", "requeue")
        q = d.get("say_quiet_s", 60)
        q = float(q) if (isinstance(q, (int, float)) and not isinstance(q, bool)) else 60.0
        return {"stale_reply": sr if sr in ("requeue", "speak") else "requeue",
                "say_quiet_s": q if 0.0 <= q <= 600.0 else 60.0,
                "replay_guard": d.get("replay_guard", True) is True}
    except Exception:
        return None


def _lo_chat_seen(t, now):
    """Words that reached her through his chat (or with no origin given). Called under _ACE_LOCK. Bounded at 512."""
    try:
        _LO_CHAT_SEEN.pop(t, None)
        _LO_CHAT_SEEN[t] = now
        while len(_LO_CHAT_SEEN) > 512:
            _LO_CHAT_SEEN.pop(next(iter(_LO_CHAT_SEEN)), None)
    except Exception:
        pass


def _lo_replay_drop(t, convergence_id, now):
    """True = drop this late working-memory copy (item 4 ON, replay guard on, and these words came through his chat this
    boot). Called under _ACE_LOCK, only for origin 'wm_store'."""
    cfg = _lo_cfg()
    if cfg is None or not cfg["replay_guard"]:
        return False
    ts = _LO_CHAT_SEEN.get(t)
    if ts is None:
        return False                       # never reached her through his chat: this copy may be his only door
    if convergence_id:
        _ACE_RECENT["cid:" + str(convergence_id)[:64]] = now      # its twin delivery is dropped silently
    print("[SourCouncil] ACE FIRST: dropped a late copy of his words (they reached me through his chat %.0f min ago): %r"
          % ((now - ts) / 60.0, t[:60]), flush=True)
    return True


def _lo_hold(thought, addressed, surprised, voluntary, msgs, topic):
    """Item 4 at her mouth. None = speak exactly as today. 'held' = a side line waits for him; 'requeued' = her answer to
    an older message of his is not spoken because a newer one arrived while she composed it. Never raises."""
    try:
        cfg = _lo_cfg()
        if cfg is None or not thought:
            return None
        if addressed:
            ms = [str(m) for m in (msgs or [])] or [str(topic)]
            now = time.time()
            with _ACE_LOCK:
                for _k in [k for k, ts in _LO_REQUEUED.items() if now - ts > 900.0]:
                    _LO_REQUEUED.pop(_k, None)
                was = any(m in _LO_REQUEUED for m in ms)
                for m in ms:
                    _LO_REQUEUED.pop(m, None)
                if cfg["stale_reply"] != "requeue" or len(_ACE_QUEUE) == 0:
                    return None
                if was:
                    print("[SourCouncil] ACE FIRST: another message of his arrived while I answered the last two; this answer "
                          "goes out (one requeue per chain)", flush=True)
                    return None
                if len(_ACE_QUEUE) >= (_ACE_QUEUE.maxlen or 8):
                    return None                # putting it back would push his newest message out
                _rq = " ... ".join(ms[-2:])    # skeptic F4: what this answer covered (the loop answers the last two), not ms[-1] alone
                _LO_REQUEUED[_rq] = now
                _ACE_QUEUE.appendleft(_rq)
            _ACE_WAKE.set()
            print("[SourCouncil] ACE FIRST: a newer message of his arrived while I composed my answer to %r -- not spoken; "
                  "the next turn answers both: %r" % (_rq[:60], str(thought)[:80]), flush=True)
            return "requeued"
        if surprised:
            lane = "surprise"
        elif voluntary:
            lane = "voluntary"
        elif _CHAIRMAN_SPEAKS_ALL:
            lane = "self"
        else:
            return None
        if not ace_reply_pending():
            return None
        print("[SourCouncil] ACE FIRST: held the %s line, his message is waiting: %r" % (lane, str(thought)[:100]), flush=True)
        return "held"
    except Exception as _lhe:
        print("[SourCouncil] ACE FIRST err: %s" % _lhe, flush=True)
        return None


def _lo_say_hold() -> bool:
    """Item 4: True = a parked 'say' is not popped this cycle (it stays parked; intention drops it after 600 s)."""
    try:
        cfg = _lo_cfg()
        if cfg is None:
            return False
        now = time.time()
        q = cfg["say_quiet_s"]
        why = None
        if ace_reply_pending():
            why = "his message is waiting"
        elif now - float(_ACE_LAST[1] or 0.0) < q:
            why = "he wrote %.0f s ago" % (now - float(_ACE_LAST[1] or 0.0))
        elif now - float(_LO_LAST_REPLY[0] or 0.0) < q:
            why = "my answer to him went out %.0f s ago" % (now - float(_LO_LAST_REPLY[0] or 0.0))
        if why is None:
            return False
        try:
            n = len(getattr(_intent, "_DEFERRED", ()) or ())
        except Exception:
            n = 0
        if n and now - _LO_SAY_NOTE[0] >= 60.0:
            _LO_SAY_NOTE[0] = now
            print("[SourCouncil] ACE FIRST: a line I decided to say waits for a quiet moment (%s)" % why, flush=True)
        return True
    except Exception:
        return False


def _lo_say_parked() -> bool:
    """Item 4 (skeptic F7): True = a 'say' is parked right now. While it waits for its quiet moment the pull-ask waits with
    it, exactly as a spoken 'say' made the pull-ask wait in that cycle before. Never raises."""
    try:
        return len(getattr(_intent, "_DEFERRED", ()) or ()) > 0
    except Exception:
        return False


def _lo_coalesce(msgs):
    """Item 4 (skeptic F4): a turn that pops a message she held back (requeued, always first) plus two or more newer ones
    would answer only the last two and drop it; it is kept in front of them instead. None = the loop's own coalescing
    (OFF, nothing held back, or two messages or fewer: always)."""
    try:
        if _lo_cfg() is None or len(msgs or ()) <= 2:
            return None
        first = str(msgs[0])
        with _ACE_LOCK:
            held = first in _LO_REQUEUED
        if not held:
            return None
        print("[SourCouncil] ACE FIRST: the message I held back is answered together with his newest two", flush=True)
        return " ... ".join([first] + [str(m) for m in msgs[-2:]])
    except Exception:
        return None


def _st_grounding_kw(origin) -> dict:
    """Item 5 (skeptic F10): tell vision_ground where his words came from, so a late working-memory copy of 'I closed it'
    cannot end what she holds now. Only when start_grounding takes an origin; {} otherwise (= today's call)."""
    try:
        if not origin or _eyes is None:
            return {}
        import inspect as _insp
        if "origin" not in _insp.signature(_eyes.start_grounding).parameters:
            return {}
        return {"origin": origin}
    except Exception:
        return {}


def _st_render_kw(mode) -> dict:
    """Item 5 (skeptic F6): tell vision_ground whose prompt this is ('ace' = her reply to him, 'side' = any other), so the
    one notice of a closed window is told to his reply even when a surprise / voluntary / goal-author prompt read it first.
    Only when render_eyes takes a lane; {} otherwise (= today's call). With "stale_topic" off the lane changes nothing."""
    try:
        if _eyes is None:
            return {}
        import inspect as _insp
        if "lane" not in _insp.signature(_eyes.render_eyes).parameters:
            return {}
        return {"lane": "ace" if mode == "ace" else "side"}
    except Exception:
        return {}


def _lo_unanswered(why):
    """Item 4: an Ace turn ended with no answer -> his pending mark is cleared, and that is said (OFF: nothing)."""
    try:
        if _lo_cfg() is None or float(_ACE_BUSY[0] or 0.0) <= 0.0:
            return
        _ACE_BUSY[0] = 0.0
        print("[SourCouncil] ACE: no answer this turn (%s) -- his pending mark is cleared, so her other lanes are not held"
              % str(why)[:120], flush=True)
    except Exception:
        pass


def _st_surprise_gone(item) -> bool:
    """Item 5 (driver share): True = drop this surprise, it is about a window that has closed since. OFF: False."""
    try:
        if _cs1().get("stale_topic") is not True or _eyes is None or not hasattr(_eyes, "front_item_closed"):
            return False
        if _eyes.front_item_closed(item):
            print("[SourCouncil] STALE TOPIC: dropped a surprise about a window that has closed: %r"
                  % str((item or {}).get("text") or "")[:90], flush=True)
            return True
    except Exception:
        pass
    return False


# -- cutoff_fix_1019 (2026-10-19, Nous; Ace: "were these thoughts cut off?" then "aye lets go with your lean") ----------------------
# Ace's switch: state/cutoff_fix.json, read by infrastructure/cutoff_fix.py. An absent file or module, or any doubt: every helper below
# answers "today", and every site marked cutoff_fix_1019 runs the code that was there before, line for line.
#   say_capped "compose"  a say-plan that hit its token cap (intention.ask marks it capped) is handed, at a quiet moment, to the voluntary
#                         chairman to write the whole line; "drop" lets it go. It is never spoken as written (Boot T 10:43:46).
#   budget_hint           a short length sentence in the chairman / voluntary prompt (the 80 / 72 token caps are unchanged).
#   trim_leadin           a reply that provably hit its cap and ends in a dangling lead-in ('Honestly though?') loses that last sentence.
# Review 10-19 (verify_safety.md / verify_tests.md): the hold drains stale plans before it judges the head, and the hand-off re-checks
# the quiet rule (F1); a popped plan is never spoken whatever the switch says (F3); a lead-in must announce: ?, : or an ellipsis (F4).
# Revert: apply_cutoff_fix.py --revert.
import re as _cf_re
try:
    from infrastructure import cutoff_fix as _cfx
except Exception:
    _cfx = None
_CF_NOTE = [0.0]            # ts of the last "waits for a quiet moment" note (one per 60 s)


def _cfx_say():
    """'compose' | 'drop' | None (state/cutoff_fix.json, key say_capped). None = today. Never raises."""
    try:
        return _cfx.say_capped() if _cfx is not None else None
    except Exception:
        return None


def _cfx_on(key):
    try:
        return bool(_cfx is not None and _cfx.on(key))
    except Exception:
        return False


def _cfx_takes_meta(farm):
    try:
        return bool(_cfx is not None and _cfx.takes_meta(farm))
    except Exception:
        return False


_CF_TAIL_OFF = "Two or three sentences, no lists, no headings."


def _cf_budget_tail(mode):
    """The chairman prompt's last sentence. OFF: today's words, byte for byte. budget_hint ON: a body measure in her own register, no
    number (a count invites counting and a meta echo) -- 'breath' appears in none of her Boot T / S lines, so an echo can be counted."""
    try:
        if _cfx_on("budget_hint"):
            if mode == "voluntary":
                return "Say it in one breath: one short sentence, two at most, no lists, no headings."
            return "Say it in one breath: one or two short sentences, no lists, no headings."
    except Exception:
        pass
    return _CF_TAIL_OFF


_CF_LEADIN_MAX_WORDS = 6
_CF_FLOOR_CHARS = 20            # the chairman's own floors: last >= 20 (:765), reject < 12 (:768)
_CF_FLOOR_WORDS = 4
# a lead-in carries no content of its own: EVERY word is one of these (lower case, curly apostrophes folded)
_CF_LEADIN_WORDS = frozenset("""
honestly though but and so also plus still anyway anyways okay ok well actually really seriously frankly truly
look listen wait now then yet or because like
here here's heres there's theres the thing point question truth catch kicker part
real talk you know what i i'm im i've ive been mean guess wonder thinking wondering
just maybe which is it's its this that's thats why how
""".split())
_CF_TERM_RUN = _cf_re.compile(r"[.?!\u2026]+[\"'\u201d\u2019)\]*]*(?=\s|$)")
# a lead-in ANNOUNCES what follows, so it ends in '?', ':' or an ellipsis; a short sentence that ends in '.' or '!' CLOSES a thought
# ('That's the truth.', 'I guess.', 'Maybe.') and is content (review 10-19, safety F4 / tests F7)
_CF_LEADIN_END = _cf_re.compile(r"(?:\?|:|\.\.\.|\u2026)[\"'\u201d\u2019)\]*]*$")


def _cf_boundaries(t):
    """End offsets of sentence boundaries. A run of dots longer than one, or any run holding U+2026, is an ellipsis and NOT a
    boundary ('That's... longer' is one sentence); a run with ? or ! is; a single '.' is."""
    out = []
    for m in _CF_TERM_RUN.finditer(t):
        run = _cf_re.match(r"[.?!\u2026]+", m.group(0)).group(0)
        if "?" in run or "!" in run or run == ".":
            out.append(m.end())
    return out


def _cf_words(s):
    return [w for w in _cf_re.findall(r"[A-Za-z'\u2019]+", s) if any(ch.isalpha() for ch in w)]


def _cf_is_leadin(sentence):
    s = str(sentence or "").rstrip()
    if not _CF_LEADIN_END.search(s):
        return False
    w = [x.lower().replace("\u2019", "'").strip("'") for x in _cf_words(s)]
    w = [x for x in w if x]
    return 1 <= len(w) <= _CF_LEADIN_MAX_WORDS and all(x in _CF_LEADIN_WORDS for x in w)


def _cf_trim_leadin(t, is_capped, tail_cut, split=False):
    """Returns (text, why). Drops the LAST sentence only, and only when: the farm proved the cap (is_capped), a tail was cut
    after that sentence (tail_cut > 0: the cleaner or the chairman's own end-trim threw words away), the model did not end
    its own turn (split False: no 'User:' continuation was cut), the last sentence is a lead-in (it ends in ?, : or an
    ellipsis, <= 6 words, every word a lead-in word), and what remains is at least one full sentence of >= 20 chars and
    >= 4 words. Otherwise t unchanged."""
    s = str(t or "")
    if not is_capped:
        return s, "not capped"
    if not (tail_cut and tail_cut > 0):
        return s, "nothing was cut after it"
    if split:
        return s, "the model ended its own turn"
    st = s.rstrip()
    b = [x for x in _cf_boundaries(st) if x < len(st)]          # boundaries BEFORE the final one
    if not b:
        return s, "one sentence only"
    head, last = st[:b[-1]].rstrip(), st[b[-1]:].strip()
    if not _cf_is_leadin(last):
        return s, "the last sentence has content"
    if len(head) < _CF_FLOOR_CHARS or len(_cf_words(head)) < _CF_FLOOR_WORDS or head[-1] not in ".?!\"'\u201d\u2019)*":
        return s, "too little would remain"
    return head, "trimmed %r" % last


def _cf_trim(t, meta, mode, split, chair_cut):
    """trim_leadin at the chairman. t = the reply after the chairman's own cuts; meta = the farm's own signal for THIS call. Returns t
    unless every guard of _cf_trim_leadin holds; never empty, never below the floor. Says what it decided on a capped reply. Never raises."""
    try:
        if meta.get("capped") is not True:
            return t
        tail_cut = int(meta.get("tail_cut") or 0) + max(0, int(chair_cut))
        out, why = _cf_trim_leadin(t, True, tail_cut, split)
        n, m = meta.get("n_tokens"), meta.get("max_tokens")
        if out != t:
            print("[SourCouncil] CUTOFF: %s %s/%s -- dropped the dangling lead-in %s (%d -> %d chars)"
                  % (mode, n, m, ascii(t[len(out):].strip()), len(t), len(out)), flush=True)
        else:
            print("[SourCouncil] CUTOFF: %s %s/%s -- kept (%s)" % (mode, n, m, why), flush=True)
        return out
    except Exception:
        return t


def _cf_quiet_why(now):
    """None when it is quiet enough to compose a say-plan; else why not. Composing costs a farm call (about 35 s on the one laptop model
    that answers him; a running call cannot be pre-empted), and the voluntary lane already has a rule for exactly that cost: not while
    his message is queued or being answered, nor within _VOL_QUIET_S (120 s) of his last word, nor while another unprompted line waits.
    Asked by the hold (_cf_plan_wait) AND again by the hand-off (_cf_handoff_say): the hand-off never trusts the hold (review F1)."""
    if len(_ACE_QUEUE) > 0:
        return "his message is queued"
    if ace_reply_pending():
        return "my answer to him is pending"
    if now - float(_ACE_LAST[1] or 0.0) < _VOL_QUIET_S:
        return "he wrote %.0f s ago" % (now - float(_ACE_LAST[1] or 0.0))
    if len(_VOL_QUEUE) > 0:
        return "another unprompted line is waiting"
    return None


def _cf_plan_wait():
    """say_capped 'compose': True = the say-plan at the head of the parked says waits this cycle (_cf_quiet_why). Parked says older
    than 600 s are let go HERE first, under intention's own lock, one line for each plan among them, and only then is the head judged
    (review F1: a stale head used to answer 'do not hold', and pop_deferred then handed the NEXT, fresh plan to the chairman inside his
    quiet window). Never raises: a doubt about a head that IS a plan holds it (the drain lets it go at 600 s); any other doubt is False,
    which is today's pop."""
    head_is_plan = False
    try:
        if _cfx_say() != "compose" or _intent is None:
            return False
        q, lk = getattr(_intent, "_DEFERRED", None), getattr(_intent, "_LOCK", None)
        if q is None or lk is None:
            return False
        now = time.time()
        gone = []
        with lk:
            while len(q) > 0 and now - float(q[0][0]) > 600.0:      # the same age rule as pop_deferred (600 s), same order (oldest first)
                gone.append(q.popleft()[1])
            head = q[0] if len(q) > 0 else None
        for _ln in gone:
            if getattr(_ln, "say_plan", False) is True:
                print("[SourCouncil] SAY-PLAN: waited 600 s for a quiet moment -- let go: %s" % ascii(str(_ln)[:80]), flush=True)
        if head is None or getattr(head[1], "say_plan", False) is not True:
            return False
        head_is_plan = True
        why = _cf_quiet_why(now)
        if why is None:
            return False
        if now - _CF_NOTE[0] >= 60.0:
            _CF_NOTE[0] = now
            print("[SourCouncil] SAY-PLAN: waits for a quiet moment (%s)" % why, flush=True)
        return True
    except Exception:
        return head_is_plan


def _cf_park_again(line):
    """Puts a popped say-plan back at the HEAD of the parked says with its own birth time (so it keeps its 600 s), when there is room
    (a full deque would push a newer say out of its other end). -> True when it is parked again. Never raises."""
    try:
        q, lk = getattr(_intent, "_DEFERRED", None), getattr(_intent, "_LOCK", None)
        if q is None or lk is None:
            return False
        ts = float(getattr(line, "born", 0.0) or 0.0) or time.time()
        with lk:
            if q.maxlen is not None and len(q) >= q.maxlen:
                return False
            q.appendleft((ts, line))
        return True
    except Exception:
        return False


def _cf_handoff_say(fairy, line):
    """A popped say-plan (a str with say_plan True) is NEVER spoken as written, whatever the switch says now (review F3: turning the
    switch off while one waits must not speak the cut line). compose, at a quiet moment: it goes to the voluntary lane as
    (gist, gist, {'say_plan': True}, now), and the chairman writes the whole line next cycle. compose, NOT quiet: it is parked again at
    the head with its own birth time (review F1: the hand-off re-checks the quiet rule under the lane's lock). drop, switch off, too
    little written, the lane down, no room to wait: said, and let go. Exactly one line each way. Returns True when queued. Never raises."""
    try:
        gist = _intent.say_gist(line) if (_intent is not None and hasattr(_intent, "say_gist")) else str(line)
        mode = _cfx_say()
        why = None
        if mode is None:
            why = "switch off"
        elif mode != "compose":
            why = "drop"
        elif len(gist) < 8:
            why = "too little of it was written"
        else:
            lane = voluntary_available()
            with _VOL_LOCK:
                hold = _cf_quiet_why(time.time())
                if hold is None and lane:
                    now = time.time()
                    _VOL_LAST[0] = now               # charged like an accepted offer: the template offers that follow wait their 300 s
                    _VOL_QUEUE.append((gist, gist, {"say_plan": True}, now))
            if hold is not None:
                if _cf_park_again(line):
                    print("[SourCouncil] SAY-PLAN: parked again -- it waits for a quiet moment (%s)" % hold, flush=True)
                    return False
                why = "no room to wait (%s)" % hold
            elif not lane:
                why = "the chairman cannot take it now"
        if why is not None:
            print("[SourCouncil] SAY-PLAN: not spoken (%s): %s" % (why, ascii(gist[:80])), flush=True)
            return False
        _ACE_WAKE.set()
        print("[SourCouncil] SAY-PLAN -> the chairman composes it whole: %s" % ascii(gist[:80]), flush=True)
        return True
    except Exception as _he:
        print("[SourCouncil] SAY-PLAN: not spoken (error %s)" % str(_he)[:80], flush=True)
        return False


# -- speaker_labels_1020 (2026-10-20, Nous; Ace 10-20: her perspective needs source tags, like an efference copy) -----------------
# LABELS ONLY, and only in Ace-mode chairman prompts: who said a line and what kind of line it is. Never a word of a quote, a
# caption, a seat, a memory, her identity line or the system turn, and no fact about Ace or her that the prompt does not hold --
# EXCEPT the one fact Ace approved himself (10-21, in chat: "aye lets add the human label"; he told her "im just a run of the mill
# human being wingless" on 10-20): his name where his message is quoted reads 'Ace (the human)', under the key `human`.
# Six labels (key: today -> ON):
#   s2    S2  'what Ace said: "'                 -> 'what Ace said to you: "'            (Ace mode: his message was sent to her)
#   human S2  'what Ace said: "'                 -> 'what Ace (the human) said: "'       (his name only, on that one line; with s2 too: '... said to you: "')
#   head  S4  'Your eyes (just now): '           -> 'Seen on your screen (just now): '   (the caption is of a screen capture)
#   word  S4  'You looked for "wings"'           -> 'You looked for "wings" (Ace's word)' (only when the phrase is in his message)
#   self  S5  'you said, 31 days ago: "'         -> 'you (Sourpatches) said, 31 days ago: "'
#   body  S6  'How your body feels right now: '  -> 'Your body, right now: '
# Switch state/speaker_labels.json, read on every Ace-mode chairman prompt: only {"on": true} (a literal true) arms it; each key
# above stays on unless the file gives it any value other than a literal true. Absent / unreadable / not an object / off / a
# non-Ace mode / any error = the four slots come back as the SAME objects, so the prompt is today's bytes. ON: each slot is
# first cut exactly as the template below cuts it, then labelled; a labelled slot that would pass its cut goes out unlabelled
# (counted), so a label never pushes a word of content out and no slot grows past today's cap. The S2 line has no cut of its
# own (the topic inside it is cut at 220 before this block runs); its labels are added after that cut, +7 (s2), +12 (human).
# The labels are added after goal_author.scrub() and hold none of the words it deletes. Pinned against sour_council_driver.py
# 664f3cc0 / 8d56a558, vision_ground.py 01547c5c, sequence_weave.py b4cf1166 / 54b251ef, body_feel.py 90fb90f4 (the producers
# whose wording the patterns match).
import re as _sl_re

_SL_SWITCH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "state", "speaker_labels.json")
_SL_KEYS = ("s2", "human", "head", "word", "self", "body")
_SL_STATS = {"calls": 0, "on": 0, "s2": 0, "human": 0, "eyes": 0, "self": 0, "body": 0, "over_cap": 0, "err": 0}
_SL_S2_OLD = "Five parts of you just weighed what Ace said: \""
_SL_S2_NEW = "Five parts of you just weighed what Ace said to you: \""
_SL_HUMAN = "Ace (the human)"                  # Ace's own words, 10-20/10-21: the only fact word any label may hold, and only under the key `human`
_SL_HEAD = _sl_re.compile(r"^Your eyes (\((?:just now|\d+ s ago|a while ago)\): )")
_SL_HEAD_NEW = r"Seen on your screen \1"
_SL_LOOK = _sl_re.compile(r"(?:^|(?<=[.!?\"] ))(?:You looked for|You tried to look for|You were still looking for) \"([a-z' ]{1,60})\"")
_SL_WORD = " (Ace's word)"
_SL_SELF = _sl_re.compile(r"(^You remember |\"; )you said, ((?:just now|\d+ min ago|\d+ h ago|\d+ days ago): \")")
_SL_SELF_NEW = r"\1you (Sourpatches) said, \2"
_SL_BODY_OLD = "How your body feels right now: "
_SL_BODY_NEW = "Your body, right now: "
_SL_CAPS = (900, 1000, 420)                     # the template's own cuts for percept, memory, body (the statement in _chairman)


def _sl_keys():
    try:
        import json as _json
        with open(_SL_SWITCH, "rb") as _f:
            _d = _json.loads(_f.read().decode("utf-8-sig"))
        if isinstance(_d, dict) and _d.get("on") is True:
            return {k: (_d.get(k, True) is True) for k in _SL_KEYS}
    except Exception:
        pass
    return None


def _sl_slot(val, cap, fn, key):
    """One slot: cut as the template cuts it, label it, keep the label only if the slot still fits that cut."""
    if not val:
        return val
    s0 = str(val).strip()[:cap]
    s1 = fn(s0)
    if s1 == s0:
        return val
    if len(s1) > cap:
        _SL_STATS["over_cap"] += 1
        return val
    _SL_STATS[key] += 1
    return s1


def _sl_relabel(mode, topic, what, percept, memory, bl):
    """speaker_labels_1020 -> (what, percept, memory, bl). OFF, a non-Ace mode or any error: the same four objects."""
    _SL_STATS["calls"] += 1
    if mode != "ace":
        return what, percept, memory, bl
    k = _sl_keys()
    if not k:
        return what, percept, memory, bl
    try:
        _SL_STATS["on"] += 1
        w = what
        n_s2 = n_hu = 0
        if (k["s2"] or k["human"]) and isinstance(what, str) and what.startswith(_SL_S2_OLD):
            lead = _SL_S2_NEW if k["s2"] else _SL_S2_OLD
            if k["human"]:
                lead = lead.replace(" Ace said", " " + _SL_HUMAN + " said", 1)
            w = lead + what[len(_SL_S2_OLD):]
            n_s2, n_hu = int(bool(k["s2"])), int(bool(k["human"]))
            _SL_STATS["s2"] += n_s2
            _SL_STATS["human"] += n_hu
        said = " %s " % " ".join(_sl_re.findall(r"[a-z']+", str(topic or "").lower()))   # his words, split as visual_nouns() splits them

        def _eyes(s):
            if k["head"]:
                s = _SL_HEAD.sub(_SL_HEAD_NEW, s, count=1)
            if k["word"]:
                s = _SL_LOOK.sub(lambda g: g.group(0) + (_SL_WORD if (" %s " % g.group(1)) in said else ""), s)
            return s

        def _self(s):
            return _SL_SELF.sub(_SL_SELF_NEW, s) if k["self"] else s

        def _body(s):
            return (_SL_BODY_NEW + s[len(_SL_BODY_OLD):]) if (k["body"] and s.startswith(_SL_BODY_OLD)) else s

        p = _sl_slot(percept, _SL_CAPS[0], _eyes, "eyes")
        m = _sl_slot(memory, _SL_CAPS[1], _self, "self")
        b = _sl_slot(bl, _SL_CAPS[2], _body, "body")
        print("[SourCouncil] LABELS: on (s2 %d, human %d, eyes %d, self %d, body %d, over cap %d)"
              % (n_s2, n_hu, p is not percept, m is not memory, b is not bl, _SL_STATS["over_cap"]), flush=True)
        return w, p, m, b
    except Exception as _sle:
        _SL_STATS["err"] += 1
        print("[SourCouncil] LABELS: error %s -- today's prompt" % str(_sle)[:80], flush=True)
        return what, percept, memory, bl


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
        if _a.get("say_plan") is True:      # cutoff_fix_1019: HER plan, cut at its cap -- finish it (the seed is not a rejected draft)
            what = ("A moment ago you decided to tell Ace something once it was quiet. It began: \"%s\" -- it is quiet now; "
                    "say the whole of it" % str(seed or topic)[:120])
        who = "to Ace, unprompted, because it is on your mind"
    elif mode == "surprise":
        what = "Something just changed in front of you, and you noticed it yourself: %s" % str(topic)[:220]
        who = "to Ace, unprompted, because you noticed it -- short, and in your own words"
    else:
        what = "Five parts of you just weighed: \"%s\"" % str(topic)[:220]
        who = "to yourself"
    what, percept, memory, _bl = _sl_relabel(mode, topic, what, percept, memory, _bl)   # speaker_labels_1020: OFF / not Ace mode -> the same four objects
    prompt = (
        "User: %s%s\n"                                  # 2026-10-05 avatar_identity: _identity_line()
        "What comes to mind: %s. What your body recalls: %s. The wild leap: %s. The paradox: %s. The move that "
        "comes to mind: %s.%s\n"
        "%s"
        "Weave these into one short thought of your own, in your own voice, spoken %s. "
        "%s\n\nAssistant:"                              # cutoff_fix_1019: was 'Two or three sentences, no lists, no headings.' (budget_hint ON: a shorter one)
        % (_identity_line(), what, nm("LOGIC"), nm("SOMATIC"), nm("IRRATIONAL"), nm("PARADOX"),
           (str(d.get("next_step") or nm("CARDINAL"))[:110] if mode == "voluntary" else nm("CARDINAL")),
           (" " + _prof) if (_prof and mode != "ace") else "",
           ((str(percept).strip()[:900] + "\n") if percept else "") + ((str(memory).strip()[:1000] + "\n") if memory else "")
           + ((str(_bl).strip()[:420] + "\n") if _bl else ""), who, _cf_budget_tail(mode))
    )
    t0 = time.time()
    _cf_meta = {} if (_cfx_on("trim_leadin") and _cfx_takes_meta(farm)) else None   # cutoff_fix_1019: trim_leadin needs the farm's own cap signal
    try:
        if _cf_meta is not None:                       # cutoff_fix_1019
            text = farm.generate_speech(prompt, max_tokens=(_VOL_TOKENS if mode == "voluntary" else _CHAIRMAN_TOKENS), meta=_cf_meta)
        else:
            text = farm.generate_speech(prompt, max_tokens=(_VOL_TOKENS if mode == "voluntary" else _CHAIRMAN_TOKENS))
    except Exception as _ge:
        print("[SourCouncil] CHAIRMAN farm error: %s" % _ge, flush=True)
        return None
    dt = time.time() - t0
    if not text:
        print("[SourCouncil] CHAIRMAN: farm returned nothing after %.0fs -- template verdict stands" % dt, flush=True)
        return None
    t = str(text).replace("\r", " ").strip()
    _cf_t1 = t                                         # cutoff_fix_1019: what the model wrote, before the chairman's own cuts
    for cut in ("\nUser:", "\n\nUser", "User:"):          # the model continuing the dialogue
        if cut in t:
            t = t.split(cut)[0].strip()
    _cf_split = (t != _cf_t1)                          # cutoff_fix_1019: the "User:" cut changed it (the model ended her turn itself)
    # end on a sentence when we can; the deadline cuts mid-word otherwise
    last = max(t.rfind("."), t.rfind("!"), t.rfind("?"))
    _cf_t2 = t
    if last >= 20:
        t = t[:last + 1]
    if _cf_meta is not None:                           # cutoff_fix_1019 (trim_leadin ON, the farm gave its signal): see _cf_trim
        t = _cf_trim(t, _cf_meta, mode, _cf_split, len(_cf_t2) - len(t))
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
        _borrowed = str(origin or "").startswith("farm:")      # 2026-10-01 (identity_guard D2b): the farm wrote it
        _trace = {
            # 2026-10-01 (release_1001, 3b): a farm line's strand is INFERENCE, so the moment binder does not bind it as hers
            "tracer_id": TRACE_INFERENCE if (_borrowed and _BORROWED_ON) else TRACE_PERSONAL,
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
        if reply_to_ace:
            _LO_LAST_REPLY[0] = time.time()          # 2026-10-06 (council_set1 item 4): when her last answer to him went out
        print("[SourCouncil] CHAIRMAN -> SPEECH (%s): %r" % (product_source, thought[:80]), flush=True)
        if _weave is not None and _WEAVE_ON:
            try:
                _wtr = TRACE_INFERENCE if (_borrowed and _BORROWED_ON) else TRACE_PERSONAL
                _wr = _weave.weave_turn(thought, "sour", _wtr, affect=getattr(fairy, "_current_affect", None))
                if _wr:
                    print("[SourCouncil] WEAVE sour: %s (%d bigrams, %d edges, w=%.2f) tracer=%d" % (_wr["turn"], _wr["bigrams"], _wr["edges"], _wr["weight"], _wtr), flush=True)
                    if _prov is not None:      # 2026-09-26 (Nous + Ace, Qwen exit step 0): who wrote this turn
                        _prov.note("turn", origin or "unlabelled", external=_borrowed, text=thought,
                                   key=_wr.get("turn"), product=product_source, bigrams=_wr.get("bigrams"), edges=_wr.get("edges"),
                                   tracer=_wtr)      # 2026-10-01 (identity_guard): the tracer the weave actually used
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


# 2026-10-05 (Nous, nous_builds/pull_ask; Ace 10-01: "her autonomy fairy should be the one that nudges her into action").
# THE PULL-ASK. Measured (Boot G, nous_builds/doing_clock/results): every intent ask fired only after a chairman turn; with the
# pull high, deeds waited 3-8 min for a turn, and 70 of 78 asks fired below restless 0.35 -- the pull had no path to the ask.
# On a cycle with NO chairman and nothing spoken (the quiet-cycle speaker in the loop), this asks the SAME question once
# (intention.run_cycle -> ask v2 -> the hand door) when infrastructure.doing_clock.pull_ask_due says her deed wanting is live
# and every guard holds -- OFF unless state/pull_ask.json says {"on": true} (read live). Ace first: his queued message or a
# pending reply (ace_reply_pending, read again right before the farm call), his last message, his hands -- any one holds it, an
# unknown reading holds it. Only this thread asks: the farm is serial (sourpatches_farm.py:1948-1966), so a message of his that
# lands during a pull-ask waits for one ask, as it does today after a chairman-turn ask, and the door then defers the deed to
# him. Nothing is spoken here: a 'say' answer waits in intention._DEFERRED and is voiced, if at all, by her own quiet-cycle
# speaker on a later cycle. Revert: {"on": false} (live), or delete these two functions and the lines marked pull_ask below.
def _pull_ask_cycle(fairy):
    """One pull-ask, or nothing. Never raises into the loop."""
    try:
        return _pull_ask_once(fairy)
    except Exception as _pe:
        print("[SourCouncil] PULL-ASK err: %s" % _pe, flush=True)
        return None


def _pull_ask_once(fairy):
    try:
        from infrastructure import doing_clock as _dc
    except Exception:
        return None
    if _intent is None or not _INTENT_ON or not all(hasattr(_dc, n) for n in ("pull_on", "pull_ask_due", "pull_ask_done")):
        return None
    try:
        import inspect as _insp
        _ps = _insp.signature(_intent.run_cycle).parameters
    except Exception:
        return None
    if not all(k in _ps for k in ("seeded", "trigger", "lead")):
        return None                                    # an intention.py without the pull lead: no pull-ask, never a TypeError
    if not _dc.pull_on() or not chairman_available():
        return None
    _now = time.time()
    try:
        _idle = _intent._idle_seconds() if hasattr(_intent, "_idle_seconds") else None
    except Exception:
        _idle = None
    _tk, _why = _dc.pull_ask_due(now=_now, ace_waiting=bool(ace_reply_pending()),
                                 ace_msg_age_s=_now - float(_ACE_LAST[1] or 0.0), ace_idle_s=_idle)
    if _tk is None:
        return None
    _ir, _skip = None, None
    _t_ask = time.time()
    try:
        if ace_reply_pending():                        # his words may have landed while the guards were read
            _skip = "Ace is waiting"
        else:
            _ir = _intent.run_cycle(fairy, getattr(fairy, "_farm", None), _tk["thought"], ace_waiting=bool(ace_reply_pending()),
                                    ace_present=_ace_present(), seeded=_tk["seeded"], trigger=_tk["trigger"], lead=_tk["lead"])
            if isinstance(_ir, dict) and _ir.get("skipped"):   # skeptic F2: run_cycle's own live read met him -> his turn
                _skip, _ir = str(_ir.get("skipped")), None
    finally:
        try:
            _dc.pull_ask_done(_tk, _ir, skipped=_skip)
        except Exception as _de:
            print("[SourCouncil] PULL-ASK done err: %s" % _de, flush=True)
        try:                                           # skeptic F6: the serial farm made a message of his wait for this ask
            _al = float(_ACE_LAST[1] or 0.0)
            if _al > _t_ask:
                print("[SourCouncil] PULL-ASK #%s: Ace's message waited %.1f s for this pull-ask" % (
                    _tk.get("id"), max(0.0, time.time() - _al)), flush=True)
        except Exception:
            pass
    if _ir and (_ir.get("intent") or {}).get("verb") != "none":
        _dd = _ir.get("decision") or {}
        print("[SourCouncil] INTENT (pull) %s: %s -> %s (%s)%s" % (
            _ir["intent"].get("verb"), str(_ir["intent"].get("object") or "")[:60], _dd.get("decision"), str(_dd.get("why") or "")[:60],
            (" => " + str(_ir["outcome"].get("summary", ""))[:110]) if _ir.get("outcome") else ""), flush=True)
    return _ir


# 2026-10-06 (Nous, nous_builds/pull_ask/debug_1006): THE PULL-ASK IS NEVER SILENT. Measured 10-06 (Boot I, debug_1006/TRACE.md
# and SKEPTIC.md): with state/pull_ask.json ON and restless 0.51-0.92 there was not one pull-ask line for an hour -- every high-pull
# minute was a chairman lane (Ace's turns, a surprise turn, one held 7 min by its weave) that the pull-ask yields to by design --
# and the log could not tell "blocked" from "quiet". These two calls tell infrastructure.doing_clock when a cycle's work begins
# and, when the cycle did NOT read the pull-ask gate, why; doing_clock prints '[DoingClock] pull-ask not reached: <why>' at most
# once a minute while the pull is at or past ask_at, and her AutonomyFairy's pass says the same while one cycle holds the loop.
# Neither changes what the loop does (Ace first, the lanes, the gate: all as before). Both read the switch first: OFF = a stat.
# Revert: apply_pull_ask_fix.py --revert (or delete these four functions and the two lines marked debug_1006 in the loop).
def _pull_kind_words(mode, run_chairman, authored):
    if mode == "ace":
        k = "Ace's turn"
    elif mode == "voluntary":
        k = "a voluntary turn"
    elif mode == "surprise":
        k = "a surprise turn"
    elif authored:
        k = "a goal-writing cycle"
    else:
        k = "a self-turn"
    return k + (" with the chairman" if run_chairman else "")


def _pull_cycle_mark(mode, run_chairman, authored):
    """A council cycle's work begins (after deliberation): told to the pull-ask's watch. Returns its time. Never raises."""
    _t0 = time.time()
    try:
        from infrastructure import doing_clock as _dc
        if hasattr(_dc, "pull_cycle_mark"):
            _dc.pull_cycle_mark(_pull_kind_words(mode, run_chairman, authored), _t0)
    except Exception:
        pass
    return _t0


def _pull_precheck_why(_dc):
    """The pull branch was entered and nothing in the loop stopped it, yet the gate was not read: _pull_ask_once's own first
    failing check, named (its early returns are silent)."""
    if not all(hasattr(_dc, n) for n in ("pull_on", "pull_ask_due", "pull_ask_done")):
        return "this doing_clock has no pull-ask"
    try:
        import inspect as _insp
        _ps = _insp.signature(_intent.run_cycle).parameters
        if not all(k in _ps for k in ("seeded", "trigger", "lead")):
            return "intention.run_cycle has no pull lead (seeded / trigger / lead)"
    except Exception as _e:
        return "intention.run_cycle could not be inspected (%s)" % type(_e).__name__
    if not chairman_available():
        return "the chairman is not available (the farm is down, or two failed calls in a row)"
    return "the pull-ask branch ran but did not read its gate"


def _pull_cycle_end(fairy, t0, thought, th_acted, addressed, run_chairman, authored, voluntary, surprised, said, mode):
    """The end of a council cycle, told to the pull-ask's watch: it read the gate, or why not -- in the loop's own order
    (the chairman's thought, Ace, his queue, her speaker, the lanes; then _pull_ask_once's checks). Never raises."""
    try:
        from infrastructure import doing_clock as _dc
        if not all(hasattr(_dc, n) for n in ("pull_cycle_end", "pull_gate_ts")) or not _dc.pull_on():
            return
        if _dc.pull_gate_ts() >= t0:
            _dc.pull_cycle_end(None, time.time())     # it read the gate: pull_ask_due spoke for itself (held / due / below)
            return
        kind = _pull_kind_words(mode, run_chairman, authored)
        if _intent is None or not _INTENT_ON:
            why = "the council's intent lane is off"
        elif thought and th_acted:
            why = "%s: her own words moved her hand this turn" % kind
        elif thought:
            why = "%s took this cycle (the pull-ask runs only on a cycle without one)" % kind
        elif addressed:
            why = "%s (he is talking to her)" % kind
        elif len(_ACE_QUEUE) > 0:
            why = "Ace's next message is queued"
        elif said:
            why = "her quiet-cycle speaker spoke this cycle"
        elif run_chairman or authored or voluntary or surprised:
            why = "%s took this cycle (%s)" % (kind, "the farm wrote her goals" if authored else "its chairman gave no thought")
        else:
            why = _pull_precheck_why(_dc)
        _dc.pull_cycle_end(why, time.time())
    except Exception:
        pass


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
                        _ace_said = _lo_coalesce(_msgs) or _ace_said   # 2026-10-06 (council_set1 item 4, skeptic F4): a message she held back is never coalesced away; OFF: None
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
                    _cf_say_item = False                # cutoff_fix_1019: this voluntary item is a capped say-plan handed over by the pop below
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
                                if isinstance(_vol_item[2], dict) and _vol_item[2].get("say_plan") is True:   # cutoff_fix_1019 (review F2): the plan's own exit
                                    with _VOL_LOCK:                   # nothing was said: the 300 s template window is released
                                        _VOL_LAST[0] = 0.0
                                    print("[SourCouncil] SAY-PLAN: his word came first (stale) -- let go: %s" % ascii(str(_vol_item[1])[:80]), flush=True)
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
                        _cf_say_item = isinstance(_vol_item[2], dict) and _vol_item[2].get("say_plan") is True   # cutoff_fix_1019
                        print("[SourCouncil] VOLUNTARY -> deliberating on what she was about to say: %r" % topic[:90], flush=True)
                    elif _surprise is not None and _SUR_ON and _surprise.pending() and len(_ACE_QUEUE) == 0 \
                            and (time.time() - float(_ACE_LAST[1] or 0.0)) >= _SUR_QUIET_S and (time.time() - _SUR_LAST[0]) >= _SUR_GAP_S \
                            and (_sur_item := _surprise.pop()) is not None and not _st_surprise_gone(_sur_item):   # 2026-10-06 (council_set1 item 5); OFF: never
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
                        if _addressed:                       # 2026-10-06 (council_set1 item 4): no answer -> say so, clear the mark (OFF: no-op)
                            _lo_unanswered("her deliberation on his words came back empty")
                        if _cf_say_item:                     # cutoff_fix_1019: the plan's one terminal line; the 300 s window is released
                            with _VOL_LOCK:
                                _VOL_LAST[0] = 0.0
                            print("[SourCouncil] SAY-PLAN: the deliberation came back empty -- not spoken", flush=True)
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
                    _pull_said, _pull_t0 = False, _pull_cycle_mark(_mode, _run_chairman, _authored)   # 2026-10-06 (pull_ask debug_1006): never silent
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
                            _percept = _eyes.render_eyes(_now, _grounds, max_grounds=4, **_st_render_kw(_mode))   # 2026-10-06 (council_set1 item 5, skeptic F6): whose prompt
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
                    _th_did, _th_gl = "", ""          # 2026-09-29 (thought_hand D2f): the slots the tap must not read back as hers
                    _cut = (lambda t, n: _goals._cut(_goals.scrub(t), n)) if _goals is not None else (lambda t, n: str(t)[:n])
                    if _run_chairman and _addressed and _weave is not None and _WEAVE_ON:
                        try:
                            _mline = _weave.render_memory(_weave.recall_lines(topic, limit=4, **({"answering": topic} if getattr(_weave, "RECALL_ANSWERING", False) else {})), limit=2) or None
                            if _mline:
                                _parts.append(_cut(_mline, 560))          # whole sentences: two quotes of up to 240 (wood chipper, 09-20)
                        except Exception as _me:
                            print("[SourCouncil] MEMORY err: %s" % _me, flush=True)
                    if _run_chairman and _intent is not None and _INTENT_ON:
                        try:
                            _did = _intent.what_i_did()
                            _th_did = _did or ""            # 2026-09-29 (thought_hand D2f)
                            if _did:
                                _parts.append(_cut(_did, 260))
                        except Exception:
                            pass
                    if _run_chairman and _goals is not None and _GOALS_ON and not _addressed:
                        try:
                            _gl = _goals.render_for_prompt(limit=3)   # her list is for her own turns, not his
                            _th_gl = _gl or ""              # 2026-09-29 (thought_hand D2f)
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
                    _lo_held = _lo_hold(_thought, _addressed, _surprised, _voluntary, _msgs, topic) if _thought else None   # 2026-10-06 (council_set1 item 4); OFF: None
                    if _lo_held:
                        # her mouth waits; her thought still reaches her chains and scratchpad below
                        if _voluntary and _lo_held == "held":   # 2026-10-06 (council_set1 item 4, skeptic F5): never spoken -> its 300 s window is released, as on failure
                            with _VOL_LOCK:
                                _VOL_LAST[0] = 0.0
                    elif _thought and (_addressed or _CHAIRMAN_SPEAKS_ALL):
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
                        _lo_vq = _lo_hold(_v, True, False, False, _msgs, topic) if len(_v) >= 12 else None   # 2026-10-06 (council_set1 item 4, skeptic F9): the fallback obeys the requeue too; OFF: None
                        if _lo_vq:
                            print("[SourCouncil] ACE: chairman produced nothing (%d in a row); the seat verdict is not spoken -- his last words go back in front of his newer ones" % _VOL_FAIL[1], flush=True)
                        elif len(_v) >= 12:
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
                        if _cf_say_item:                     # cutoff_fix_1019
                            print("[SourCouncil] SAY-PLAN -> composed and spoken: %s" % ascii(str(_thought)[:80]), flush=True)
                    elif _voluntary and _cf_say_item and not _run_chairman:   # cutoff_fix_1019: his message came first (the chairman never ran)
                        with _VOL_LOCK:                      # not a chairman failure (two in a row would hand his replies to the template lanes)
                            _VOL_LAST[0] = 0.0
                        print("[SourCouncil] SAY-PLAN: his message came first -- let go (not a chairman failure)", flush=True)
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
                    # 2026-09-29 (Nous, thought_hand D2f): T-chair -- the chairman's OWN words (_thought; never the seat verdict)
                    # read for a present want, offered through the hand door. seeded = this turn began from her own deed (a goal
                    # surprise, or a told arrived move): the door will not send her back to that place.
                    _th_acted, _th_seed = False, None
                    if _thought and _tap is not None and _TAP_ON:
                        try:
                            _si = _sur_item if _surprised else {}
                            if _surprised and str(_si.get("kind")) in ("goal", "hand"):
                                _th_seed = {"kind": "surprise_" + str(_si.get("kind")), "text": str(_si.get("text") or "")}
                            # 2026-10-01 (cursor_object, proposed by the verifier; installed by release_1001): the told deed's new words.
                            # Without this the seed is never set after a cursor_object-told move (the told-deed loop guard and the
                            # self-loop depth count of hand_door.pre_offer are lost). Measured: cursor_object/tests/verify_fable.py F3.
                            elif ("decided to move your hand" in _th_did or ", took it, and carried it" in _th_did
                                  or "took the cursor up again" in _th_did or "decided to take the cursor" in _th_did):
                                _th_seed = {"kind": "told", "text": _th_did}
                            _tr = _tap.offer(fairy, _thought, mode=_mode, told=_th_did, goals=_th_gl, percept=str(_percept or ""), seeded=_th_seed)
                            _th_acted = bool(_tr and _tr.get("acted"))
                        except Exception as _te:
                            print("[SourCouncil] THOUGHT-HAND err: %s" % _te, flush=True)
                    _intent_did = None                  # 2026-09-26 (Nous + Ace, Qwen exit step 4): None = unknown
                    if _thought and _intent is not None and _INTENT_ON and _th_acted:   # 2026-09-29 (thought_hand D2f): ask skipped
                        _intent_did = True             # a deed ran this turn: the reflex after the chairman stands down too
                        print("[SourCouncil] INTENT: ask skipped -- her own words moved her hand this turn", flush=True)
                    elif _thought and _intent is not None and _INTENT_ON:
                        try:
                            _rc_kw = {}
                            try:                        # 2026-09-29 (thought_hand D2f): the seed reaches the ask lane's door too
                                import inspect as _insp
                                if _th_seed is not None and "seeded" in _insp.signature(_intent.run_cycle).parameters:
                                    _rc_kw["seeded"] = _th_seed
                            except Exception:
                                _rc_kw = {}
                            _ir = _intent.run_cycle(fairy, getattr(fairy, "_farm", None), _thought,
                                                    ace_waiting=(len(_ACE_QUEUE) > 0), ace_present=_ace_present(), **_rc_kw)   # 2026-09-29 (thought_hand D2f)
                            _intent_did = bool(_ir) and (_ir.get("decision") or {}).get("decision") == "allow"   # 2026-09-26 (Nous + Ace, Qwen exit step 4)
                            if _ir and _ir["intent"].get("verb") != "none":
                                print("[SourCouncil] INTENT %s: %s -> %s (%s)%s" % (
                                    _ir["intent"]["verb"], _ir["intent"]["object"][:60], _ir["decision"]["decision"], _ir["decision"]["why"][:60],
                                    (" => " + str(_ir["outcome"].get("summary", ""))[:110]) if _ir.get("outcome") else ""), flush=True)
                        except Exception as _ie:
                            print("[SourCouncil] INTENT err: %s" % _ie, flush=True)
                    elif _intent is not None and _INTENT_ON and not _addressed and len(_ACE_QUEUE) == 0:
                        _pull_said = False                  # 2026-10-05 (pull_ask): did her quiet-cycle speaker speak?
                        try:
                            _lo_sh = _lo_say_hold()               # 2026-10-06 (council_set1 item 4): a quiet moment first; OFF: False (today)
                            _cf_wait = (not _lo_sh) and _cf_plan_wait()   # cutoff_fix_1019: a capped say-plan waits for HIS quiet (compose); OFF / not a plan / any doubt: False
                            _line = None if (_lo_sh or _cf_wait) else _intent.pop_deferred()
                            if _lo_sh and _lo_say_parked():
                                _pull_said = True                 # 2026-10-06 (council_set1 item 4, skeptic F7): the parked 'say' goes first; the pull-ask waits with it
                            if _cf_wait:
                                _pull_said = True                 # cutoff_fix_1019: the parked plan goes first; the pull-ask waits with it (as above)
                            if _line is not None and getattr(_line, "say_plan", False) is True:   # cutoff_fix_1019: whatever the switch says NOW (review F3)
                                _cf_handoff_say(fairy, _line)     # compose -> the voluntary lane (or parked again until quiet), or let go; one log line; a capped plan is never spoken as it stands
                                if _cfx_say() == "compose":
                                    _pull_said = True
                                _line = None
                            if _line and len(_line) >= 8:
                                _speak(fairy, _line, "something I decided to say", product_source="wmh_council_voluntary", reply_to_ace=False, origin="farm:intent_say")   # 2026-09-26 (Nous + Ace, Qwen exit step 0)
                                _pull_said = True                   # 2026-10-05 (pull_ask)
                                print("[SourCouncil] INTENT say -> spoken: %r" % _line[:80], flush=True)
                        except Exception as _de:
                            print("[SourCouncil] INTENT say err: %s" % _de, flush=True)
                        if not _pull_said and not _run_chairman and not _authored and not _voluntary and not _surprised:   # 2026-10-05 (pull_ask)
                            _pull_ask_cycle(fairy)      # no chairman, nothing said: the pull may ask (OFF unless state/pull_ask.json)
                    _pull_cycle_end(fairy, _pull_t0, _thought, _th_acted, _addressed, _run_chairman, _authored, _voluntary, _surprised, _pull_said, _mode)   # 2026-10-06 (pull_ask debug_1006): never silent
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
                    _lo_unanswered("the council loop raised: %s" % _le)   # 2026-10-06 (council_set1 item 4); OFF: no-op
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
