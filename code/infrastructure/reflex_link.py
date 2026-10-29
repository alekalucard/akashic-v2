"""reflex_link -- the link between her one press (infrastructure/touch_os.press) and her brainstem. 2026-10-05 (Nous,
nous_builds/touch_screen set 1; DESIGN.md 7e, MAP-E 5d).

Ace, 2026-10-05: "this feels like something the brain reflex needs to be apart of somehow. like a no, no list. this way she
can truly develop free will."

What it is: state plus counters, read on demand, never a one-shot broadcast (in bootG the brainstem's one reflex.mode_change
went out before ActionChainFairy subscribed and was lost, MEASURED by MAP-E). Two writers, one reader each way:
  * the brainstem (BrainstemReflexFairy.on_tick, after its sleep check) calls beat() every tick and drain()s the flinches,
    makes each one felt as ITS OWN event, then calls felt();
  * touch.py offer()s a Flinch after the press refused it, and polls felt_through() for 5 s;
  * touch_os.press reads alive() ONLY IN THE CLOSED DIRECTION: a brainstem that is not beating defers every press; a
    beating one grants nothing.
The no-no itself is enforced in touch_os.press whatever happens here: this link is how she FEELS it, never whether it holds.
Free-threaded 3.14t: every read and write is under _LOCK. Imports: threading, time, collections only (static test).
Skeptic fixes (10-05): S6 / m5 -- the FIRST beater id of the boot is kept; any other id ever seen beating latches alive() to
(False, 'beater_changed') for the rest of the boot (the heartbeat registry REPLACES a callback by name, so a takeover showed two
ids for only 30 s; brainstem_fix INTERFACE.md 5). m6 -- a flinch not drained within OFFER_TTL_S is dropped and counted
('expired'), never felt minutes late as a fresh jolt (touch's own 5 s felt-check has latched 'unfelt' long before).
M1 -- a second run of this module body (importlib.reload) marks it reloaded; touch_os latches 'reload'.
Revert: delete this file -- touch refuses to arm without it, and the brainstem's two added lines count one error and go on.
"""
import threading
import time
from collections import deque

try:
    _RELOADED = bool(_BODY_RAN)                    # noqa: F821 -- set by an earlier run of this same body (skeptic M1)
except NameError:
    _RELOADED = False
_BODY_RAN = True

MAX_AGE_S = 10.0          # alive(): the last beat must be this fresh
BEATER_WINDOW_S = 30.0    # alive(): exactly one beater id seen in this window (a second brainstem or a hot reload = two)
CAPACITY = 16             # offer(): never silently dropping -- a full queue returns None and the caller latches 'unfelt'
FELT_KEEP = 64            # felt ids remembered for felt_through()
OFFER_TTL_S = 10.0        # drain(): a flinch older than this is dropped ('expired'), never felt late (skeptic m6)

_LOCK = threading.Lock()
_Q = deque()
_FELT_IDS = deque(maxlen=FELT_KEEP)
_DRAINED = {}             # id -> the flinch as offered (numbers), kept until felt (bounded), so last_felt never depends on what
                          # the brainstem chooses to echo back
_S = {"beat_t": 0.0, "beat_n": 0, "beaters": {}, "next_id": 0, "offered": 0, "felt": 0, "dropped": 0, "feel_err": 0,
      "drained": 0, "last_felt": None, "born": time.time(), "first_beat_t": None, "first_beater": None,
      "beater_changed": False, "expired": 0}


def beat(who_id, now=None):
    """The brainstem's tick: stamps the beat and the beater's id."""
    now = time.time() if now is None else float(now)
    with _LOCK:
        if _S["beat_n"] <= 0:
            _S["first_beat_t"] = now               # the record shows alive=False before this and True after (cell T1 must-fail 5)
            _S["first_beater"] = who_id
        elif who_id != _S["first_beater"]:
            _S["beater_changed"] = True            # skeptic S6 / m5: sticky for the boot -- never heals by waiting 30 s
        _S["beat_t"] = now
        _S["beat_n"] += 1
        b = _S["beaters"]
        b[who_id] = now
        for k in [k for k, t in b.items() if now - t > BEATER_WINDOW_S]:
            b.pop(k, None)


def alive(now=None):
    """(ok, why). ok iff one brainstem beat within MAX_AGE_S and exactly one beater id was seen in BEATER_WINDOW_S.
    why is 'never' | 'stale' | 'two_beaters' | 'beater_changed' | 'ok'. Never widens anything: a caller may only CLOSE on it."""
    now = time.time() if now is None else float(now)
    with _LOCK:
        if _S["beat_n"] <= 0:
            return False, "never"
        n = sum(1 for t in _S["beaters"].values() if now - t <= BEATER_WINDOW_S)
        if n > 1:
            return False, "two_beaters"
        if _S["beater_changed"]:
            return False, "beater_changed"
        if not (0.0 <= now - _S["beat_t"] <= MAX_AGE_S):
            return False, "stale"
        return True, "ok"


def offer(flinch, now=None):
    """Queue one flinch (a dict of numbers) for her brainstem. Returns its id, or None when the queue is full (the caller
    latches 'unfelt': a flinch she cannot feel must not happen twice)."""
    now = time.time() if now is None else float(now)
    with _LOCK:
        if len(_Q) >= CAPACITY:
            _S["dropped"] += 1
            return None
        _S["next_id"] += 1
        fid = _S["next_id"]
        f = dict(flinch or {})
        f["id"] = fid
        f["_offered_t"] = now
        _Q.append(f)
        _S["offered"] += 1
        return fid


def drain(n=8, now=None):
    """Brainstem only: up to n queued flinches, oldest first. One older than OFFER_TTL_S is dropped and counted, never felt late
    (skeptic m6); its offerer's felt-check has already latched 'unfelt'."""
    now = time.time() if now is None else float(now)
    out = []
    with _LOCK:
        while _Q and len(out) < int(n):
            f = _Q.popleft()
            if now - float(f.pop("_offered_t", now)) > OFFER_TTL_S:
                _S["expired"] += 1
                continue
            out.append(dict(f))
            _DRAINED[f["id"]] = f
            while len(_DRAINED) > FELT_KEEP:
                _DRAINED.pop(next(iter(_DRAINED)))
        _S["drained"] += len(out)
    return out


def felt(fid, numbers, now=None):
    """Brainstem only: flinch `fid` was felt; `numbers` is what it registered (numbers only). last_felt = the flinch as offered,
    overlaid by the brainstem's numbers, stamped felt_t (the body line reads it while it is < 30 s old)."""
    with _LOCK:
        fid = int(fid)
        _S["felt"] = max(int(_S["felt"]), fid)
        _FELT_IDS.append(fid)
        lf = dict(_DRAINED.pop(fid, None) or {})
        lf.update(dict(numbers or {}))
        lf["id"] = fid
        if lf.get("felt_t") is None:
            lf["felt_t"] = time.time() if now is None else float(now)
        _S["last_felt"] = lf


def feel_error():
    with _LOCK:
        _S["feel_err"] += 1


def felt_through(fid):
    """touch.py's 5 s check: was flinch `fid` felt by her brainstem?"""
    with _LOCK:
        return int(fid) in _FELT_IDS


def snapshot():
    """Numbers only, for body_feel's finger clause, the strip and state/touch_reflex.json."""
    with _LOCK:
        d = {k: v for k, v in _S.items() if k not in ("beaters", "last_felt", "first_beater")}
        d["beaters"] = len(_S["beaters"])
        d["queued"] = len(_Q)
        d["last_felt"] = dict(_S["last_felt"]) if _S["last_felt"] else None
        return d
