"""tardis_backlog.py -- B PERSIST + REPLAY for her TARDIS bind queue. 2026-10-15 (Nous, nous_builds/tardis_fix_1015).

THE LOSS: the main (manifold-mode) AssociationCortexFairy copy writes each bind on ONE thread (2 upserts + 1 link per word-pair),
slower than binds arrive, so a backlog sits in a queue (maxsize 4096). The server leaves through os._exit, so whatever is still in
the queue at exit is gone: M ~2,000, O ~2,300, P ~4,100-4,300 binds, every boot.

WHAT B DOES (switch key b_persist, OFF by default): when the global-shutdown Event fires (the HTTP shutdown route sets it at T0,
before the SDFIX flow starts) it writes the unwritten queue, and the unfinished part of the batch in flight, to a bounded
self-checking file under state/tardis_backlog/. At the next boot, after a delay, it feeds those binds back into the SAME queue at a
bounded rate, only into spare room. Nothing in server.py changes: the cortex asks itself.

EXACTLY ONCE, BY OWNERSHIP (the data layer is NOT idempotent: a repeated link() adds +0.125 weight, a repeated upsert +1 frequency):
  * an item leaves the queue through queue.get_nowait(), which removes it under the queue's own mutex: the flush thread or this
    persister gets it, never both;
  * after stop_requested the flush thread never drains again (hook F4a is one-way), and the batch it holds is split at a CHUNK
    boundary (4 pairs): a chunk is submitted whole OR parked whole (_Chunker), never both;
  * a persisted file is claimed by an atomic os.replace(pending-X, replaying-X) BEFORE it is read; a replaying-* file found at boot is
    never re-read (renamed stale-*, kept); a uuid ledger rejects a done file somebody puts back by hand;
  * a replayed item is marked _tf_replay and is a normal queue item: if the process dies before it is written it is lost (at most
    once), or -- if the process shuts down properly -- it is persisted again by the queue sweep (it was never written).
LOSSES THAT REMAIN (all <= today's): the chunk being written when os._exit lands (<= 4 pairs), arrivals after the last sweep, and
the exit routes that never signal (reboot route, Ctrl+C, a hang before T0). B does not fix those; it says so.
ORDER AT THE CAP (review 10-15): this boot's live queue is written first, a previous boot's unfed replay remainder after it (leaving a
reserve for the park and late arrivals): when the file is full the OLDEST binds are the ones counted over_cap, never the freshest.
A replay_unfed / over_cap count that grows boot after boot in trace.log means the writer still does not keep up (B then defers the loss,
it does not cure it).

NEVER RAISES INTO HER. Every public entry point is try/except; arm() only creates threads (no file I/O on the boot path); a corrupt,
oversized, foreign or unreadable file is renamed rejected-* and kept, and her boot is not touched. Every limiter has a floor (card
a-bound-that-can-return-nothing-is-a-kill-switch): the ONE zero-output state is replay feeding when the queue is within `reserve` of
its cap, which protects live binds from the synchronous overflow path; it is printed (`held`), never silent.
Stdlib only. ASCII only in every line it prints (her console is cp1252).
"""
from __future__ import annotations

import json
import os
import queue as _queue
import sys
import threading
import time
import uuid as _uuid
import zlib

VERSION = 1
KIND = "tardis_backlog"
TRACER_MAX = 255
WEIGHT = 0.25                       # _tardis_process_batch always submits weight=0.25; a record with anything else is bad

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
DIR = os.path.join(_ROOT, "state", "tardis_backlog")

CFG = {
    "first_sweep_budget_s": 10.0, "first_min_records": 200,
    "sweep_interval_s": 1.0, "sweep_lifetime_s": 180.0,
    "park_chunk": 4,
    "max_bytes": 32 << 20, "max_records": 50000, "max_line": 64 << 10,
    "replay_delay_s": 60.0, "headroom": 200, "max_rate": 20, "trickle_s": 10.0, "reserve": 512,
    "per_boot_records": 100000, "ledger_keep": 256, "done_keep": 16,
    "bad_min": 5,
}
FLOOR = {
    "first_sweep_budget_s": 1.0, "first_min_records": 200,
    "sweep_interval_s": 0.2, "sweep_lifetime_s": 60.0,
    "park_chunk": 1,
    "max_bytes": 4 << 20, "max_records": 4296, "max_line": 4 << 10,
    "replay_delay_s": 3.0, "headroom": 50, "max_rate": 1, "trickle_s": 0.0, "reserve": 256,
    "per_boot_records": 4296, "ledger_keep": 16, "done_keep": 2,
    "bad_min": 1,
}
CEIL = {
    "first_sweep_budget_s": 20.0, "first_min_records": None,
    "sweep_interval_s": 5.0, "sweep_lifetime_s": None,
    "park_chunk": 64,
    "max_bytes": 256 << 20, "max_records": None, "max_line": None,
    "replay_delay_s": 600.0, "headroom": 2048, "max_rate": 200, "trickle_s": None, "reserve": None,
    "per_boot_records": None, "ledger_keep": None, "done_keep": None,
    "bad_min": None,
}
# first_sweep_budget_s is a WRITE-CHUNKING knob, not a time bound (review 10-15, F4): the first sweep always drains the whole queue; past
# the budget it only writes in chunks of >= first_min_records. The synchronous part is bounded by the queue itself (maxsize 4,096 + the
# few that arrive meanwhile): measured 0.12-0.24 s for 3,896 items with a CPU burner on the cores (test B-7).
HEADER_ROOM = 2048                  # bytes kept for the header line while the pending file does not exist yet (the header holds a path)
REMAINDER_RESERVE_RECORDS = 512     # room a replay remainder must leave for this boot's park + late arrivals (review 10-15, F2)
REMAINDER_RESERVE_BYTES = 1 << 20   # (a parked batch is <= ~25 pair records; late arrivals ~1/s for 180 s)
BAD_SHARE = 0.10                    # more than this share of bad records (and >= bad_min of them) rejects the whole file
CONCEPTS_MAX = 64                   # no producer sends more than 8 (fairy.py:4929 `concepts_to_bind`); validated at replay
PAIRS_PER_RECORD_MAX = 4096         # accepted at replay
PARK_PAIRS_PER_RECORD = 256         # written at park (keeps one line far under max_line)
KEY_MAX = 256                       # manifold_memory.upsert_node rejects longer keys (len > 256): they could never be written


def cfg(name):
    """A limiter's value clamped to its floor / ceiling: no limiter can be configured to zero output."""
    v = CFG[name]
    try:
        v = type(FLOOR[name])(v)
    except Exception:
        v = FLOOR[name]
    v = max(FLOOR[name], v)
    if CEIL[name] is not None:
        v = min(CEIL[name], v)
    return v


# ------------------------------------------------------------------ small helpers
def _ascii(s) -> str:
    return str(s).encode("ascii", "replace").decode("ascii")


def _say(msg: str) -> None:
    try:
        print("[TardisFix] " + _ascii(msg), flush=True)
    except Exception:
        pass


def _dir() -> str:
    return DIR


def _sw(key: str, fresh: bool = False) -> bool:
    try:
        from infrastructure import tardis_fix as _tf
        return _tf.on(key, fresh=fresh)
    except Exception:
        return False


def _carry() -> bool:
    """W11 AKASHIC_BIND_CARRYOVER (env, OFF unless exactly "1"): it also turns b_persist ON (tardis_fix.ENV_ALIAS), and here it
    adds three things: queue items are written with ALL their fields when that round-trips exactly (else today's record), no
    done-* file is ever deleted, and persist_owner() serves the exit routes that never set the shutdown Event."""
    try:
        return os.environ.get("AKASHIC_BIND_CARRYOVER", "0") == "1"
    except Exception:
        return False


def _norm(p) -> str:
    try:
        return os.path.normcase(os.path.abspath(str(p)))
    except Exception:
        return str(p)


def _enc(rec: dict) -> bytes:
    """One frame: <crc32 of the json bytes, 8 hex> <space> <compact ascii json> <newline>."""
    body = json.dumps(rec, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return b"%08x " % (zlib.crc32(body) & 0xFFFFFFFF) + body + b"\n"


def _dec(line: bytes):
    """-> (record, '') or (None, why). A line that does not end in a newline is a torn tail."""
    if not line.endswith(b"\n"):
        return None, "torn"
    line = line[:-1]
    if len(line) < 10 or line[8:9] != b" ":
        return None, "bad_frame"
    try:
        crc = int(line[:8], 16)
    except ValueError:
        return None, "bad_frame"
    body = line[9:]
    if (zlib.crc32(body) & 0xFFFFFFFF) != crc:
        return None, "bad_crc"
    try:
        rec = json.loads(body.decode("ascii"))
    except Exception:
        return None, "bad_json"
    if not isinstance(rec, dict):
        return None, "bad_json"
    return rec, ""


def _read_line(fh, limit):
    """-> (bytes, too_long). Reads one physical line; a line longer than `limit` is consumed whole and flagged."""
    data = fh.readline(limit + 1)
    if len(data) <= limit or data.endswith(b"\n"):
        return data, False
    while data and not data.endswith(b"\n"):
        data = fh.readline(65536)
    return b"", True


def _okstr(s, lo=1, hi=KEY_MAX) -> bool:
    if not isinstance(s, str) or not (lo <= len(s) <= hi):
        return False
    for ch in s:
        o = ord(ch)
        if (o < 32 and o != 9) or o == 127:          # a tab passes, exactly like manifold_memory.upsert_node's own guard
            return False
    return True


def _valid_meta(m) -> bool:
    return m is None or isinstance(m, dict)


def _valid_item(i) -> bool:
    if not isinstance(i, dict):
        return False
    c = i.get("concepts_to_bind")
    if not isinstance(c, list) or not (2 <= len(c) <= CONCEPTS_MAX) or not all(_okstr(x) for x in c):
        return False
    if not _okstr(i.get("from_fairy", ""), 0, KEY_MAX):
        return False
    for k in ("origin_fairy", "feeling", "origin_plane", "origin_channel", "concept_key"):
        if k in i and not _okstr(i[k], 0, KEY_MAX):
            return False
    return _valid_meta(i.get("concept_metadata"))


def _valid_pairs(r) -> bool:
    p = r.get("pairs")
    if not isinstance(p, list) or not (1 <= len(p) <= PAIRS_PER_RECORD_MAX):
        return False
    for x in p:
        if not (isinstance(x, list) and len(x) == 2 and _okstr(x[0]) and _okstr(x[1])):
            return False
    t = r.get("tracer")
    if isinstance(t, bool) or not isinstance(t, int) or not (0 <= t <= TRACER_MAX):
        return False
    w = r.get("weight")
    if isinstance(w, bool) or not isinstance(w, float) or w != WEIGHT:
        return False
    return _valid_meta(r.get("meta"))


def validate(rec) -> bool:
    """A record that may be replayed. Anything else is counted bad and skipped."""
    try:
        t = rec.get("t")
        if t == "item":
            return _valid_item(rec.get("i"))
        if t == "pairs":
            return _valid_pairs(rec)
    except Exception:
        pass
    return False


def to_queue_item(rec: dict, file_uuid: str) -> dict:
    """The queue item a validated record becomes. Marked _tf_replay: the feeder never touches _tardis_binds_queued."""
    if rec.get("t") == "item":
        it = dict(rec["i"])
        it["_tf_replay"] = file_uuid
        return it
    return {"concepts_to_bind": [], "from_fairy": "tardis_replay", "_tf_pairs": rec["pairs"], "_tf_tracer": int(rec["tracer"]),
            "concept_metadata": rec.get("meta") or {}, "_tf_replay": file_uuid}


def merge_pairs_item(item, pairs_by_tracer, seen_by_tracer, merged_meta) -> None:
    """fairy.py hook F5a: fold a replayed in-flight remainder into the batch, with the same in-bucket dedup and first-wins metadata
    as _tardis_process_batch's own loop (fairy.py:6342-6358)."""
    tr = item.get("_tf_tracer", 0)
    seen = seen_by_tracer.setdefault(tr, set())
    bucket = pairs_by_tracer.setdefault(tr, [])
    for p in item.get("_tf_pairs") or ():
        a, b = p[0], p[1]
        k = (min(a, b), max(a, b))
        if k not in seen:
            seen.add(k)
            bucket.append([a, b])
    for ck, cm in (item.get("concept_metadata") or {}).items():
        if ck not in merged_meta:
            merged_meta[ck] = cm


# ------------------------------------------------------------------ the ledger (uuids of files already replayed)
def _ledger_path():
    return os.path.join(_dir(), "ledger.json")


def _ledger_read():
    try:
        with open(_ledger_path(), "rb") as f:
            d = json.loads(f.read().decode("utf-8"))
        u = d.get("uuids") if isinstance(d, dict) else None
        return [x for x in u if isinstance(x, str)] if isinstance(u, list) else []
    except Exception:
        return []


def _ledger_add(u: str) -> None:
    lst = [x for x in _ledger_read() if x != u] + [u]
    if not _carry():                                    # W11: done-* files are kept forever, so is every uuid that guards them
        lst = lst[-cfg("ledger_keep"):]
    p = _ledger_path()
    tmp = p + ".tmp"
    with open(tmp, "wb") as f:
        f.write(json.dumps({"v": 1, "uuids": lst}).encode("ascii"))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, p)


# ------------------------------------------------------------------ finding the shutdown Event
def _shutdown_source():
    """-> ('event', Event) | ('poll', callable) | (None, None). The canonical module is the one server.py imports (:3702)."""
    for name in ("P00_Autonomic.nervous_system.shared_postal_hub",
                 "fairies.P00_Autonomic.nervous_system.shared_postal_hub"):
        m = sys.modules.get(name)
        if m is None:
            continue
        ev = getattr(m, "_GLOBAL_SHUTDOWN", None)
        if ev is not None and hasattr(ev, "wait") and hasattr(ev, "is_set"):
            return "event", ev
        f = getattr(m, "is_global_shutdown", None)
        if callable(f):
            return "poll", f
    return None, None


# ------------------------------------------------------------------ the object
_OWNER_LOCK = threading.Lock()
_OWNER = {"b": None}


def _reset_for_tests() -> None:
    with _OWNER_LOCK:
        _OWNER["b"] = None


def persist_owner(reason: str) -> bool:
    """W11: persist the armed owner's queue NOW, for the exit routes that never set the shutdown Event (the HTTP reboot route,
    Ctrl+C). AKASHIC_BIND_CARRYOVER OFF -> does nothing and returns False. persist_now is idempotent. Never raises."""
    try:
        if not _carry():
            return False
        with _OWNER_LOCK:
            b = _OWNER["b"]
        if b is None:
            return False
        b.persist_now(str(reason))
        return True
    except Exception:
        return False


def arm(cx):
    """fairy.py hook F3. Returns a Backlog or None (OFF, not manifold mode, shutdown already underway, or another owner). Never raises.
    Only creates threads: no file I/O on the boot path."""
    try:
        if not _sw("b_persist"):
            return None
        region = getattr(cx, "_akashic_cortex_region", None)
        q = getattr(cx, "_tardis_bind_queue", None)
        if region is None or q is None:
            return None            # portal-mode copy (no in-process writer): persisting its hand-offs would replay every bind twice
        kind, src = _shutdown_source()
        if (kind == "event" and src.is_set()) or (kind == "poll" and src()):
            return None
        refused = None
        with _OWNER_LOCK:
            cur = _OWNER["b"]
            if cur is not None:
                if cur.cx is cx:
                    return cur
                refused = cur
            else:
                b = Backlog(cx, region, q)
                _OWNER["b"] = b
        if refused is not None:
            # a second manifold-mode cortex instance (a hot reload?): it runs today's behaviour, the first owner keeps B (review 10-15, F3).
            # stderr, like the switch reader: never the 3.12 interior's stdout JSON pipe. No file I/O here (boot path).
            try:
                sys.stderr.write("[TardisFix] B: a second cortex instance asked to arm and was REFUSED (it runs today's behaviour; the first "
                                 "instance, armed %.0f s ago, keeps B and persists only ITS queue)\n" % (time.monotonic() - refused.t0))
                sys.stderr.flush()
            except Exception:
                pass
            return None
        b.start()
        return b
    except Exception as e:
        _say("B: arm failed (%s: %s) -> B OFF for this process" % (type(e).__name__, e))
        return None


class _Chunker:
    """fairy.py hook F5b: the submit loop's iterable. Yields (tracer, slice of <= park_chunk pairs) in the order today's loop submits,
    and checks stop_requested at every slice boundary; on stop it parks the not-yet-submitted pairs and ends the iteration."""

    def __init__(self, b, pairs_by_tracer, meta):
        self.b = b
        self.items = [(t, p) for t, p in pairs_by_tracer.items() if p]
        self.meta = meta or {}
        self.bi = 0
        self.pi = 0
        self.last_n = 0
        self.submitted = 0
        self.parked = 0

    def __iter__(self):
        return self

    def __next__(self):
        # the slice handed out last time has been submitted by the loop body that ran in between
        if self.last_n:
            self.submitted += self.last_n
            self.last_n = 0
        if self.b.stop_requested:
            self._park_rest()
            raise StopIteration
        chunk = cfg("park_chunk")
        while self.bi < len(self.items):
            tracer, pairs = self.items[self.bi]
            if self.pi >= len(pairs):
                self.bi += 1
                self.pi = 0
                continue
            sl = pairs[self.pi:self.pi + chunk]
            self.pi += len(sl)
            self.last_n = len(sl)
            return tracer, sl
        raise StopIteration

    def _park_rest(self):
        try:
            recs = []
            for bi in range(self.bi, len(self.items)):
                tracer, pairs = self.items[bi]
                rest = pairs[self.pi:] if bi == self.bi else pairs
                recs.extend(self.b.pairs_records(tracer, rest, self.meta))
                self.parked += len(rest)
            self.b.append(recs, "park")
            self.b.counters["parked_pairs"] += self.parked
            self.b._trace("inflight parked pairs=%d (submitted %d of this batch before the stop)" % (self.parked, self.submitted))
        except Exception as e:
            self.b._trace("park FAILED (%s: %s)" % (type(e).__name__, e))
        finally:
            self.bi = len(self.items)


class Backlog:
    def __init__(self, cx, region, q):
        self.cx = cx
        self.region = region
        self.q = q
        self.t0 = time.monotonic()
        self.uuid = _uuid.uuid4().hex
        self.stop_requested = False        # one-way: after this the flush thread never drains again
        self._persist_lock = threading.Lock()
        self._persist_started = False
        self._wlock = threading.Lock()     # serialises every write to the pending file
        self._fh = None
        self.path = None
        self._nrec = 0
        self._nbytes = 0
        self._seq = 0
        self._replay_stop = threading.Event()
        self._replay_thread = None
        self._trigger_thread = None
        self._cur = None                   # the replay file in hand: {fh, claim, name, uuid, left, ...}
        self._inhand = None
        self._skip = set()
        self._boot_total = 0
        self.held = False
        self.counters = {"persisted_items": 0, "persisted_pairs_recs": 0, "parked_pairs": 0, "over_cap": 0, "over_line": 0,
                         "meta_dropped": 0, "lost": 0, "no_pairs": 0, "fed": 0, "fed_pairs_recs": 0, "bad": 0, "torn": 0,
                         "files_done": 0, "files_rejected": 0, "unfed_written": 0, "sweeps": 0, "late_items": 0}
        self.persist_s = None

    # ---- trace ---------------------------------------------------------------------------------------------------------
    def _trace(self, msg: str) -> None:
        line = "[%s] pid=%d TFIX +%.1fs %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), os.getpid(), time.monotonic() - self.t0, _ascii(msg))
        try:
            os.makedirs(_dir(), exist_ok=True)
            p = os.path.join(_dir(), "trace.log")
            try:
                if os.path.getsize(p) > (1 << 20):
                    os.replace(p, p + ".1")
            except OSError:
                pass
            with open(p, "ab") as f:
                f.write(line.encode("ascii", "replace") + b"\n")
        except Exception:
            pass
        _say("B: " + msg)

    def status_text(self) -> str:
        c = self.counters
        if self._persist_started:
            return "persisted items=%d pairs_recs=%d parked=%d over_cap=%d" % (
                c["persisted_items"], c["persisted_pairs_recs"], c["parked_pairs"], c["over_cap"])
        cur = self._cur
        if cur is not None or c["fed"]:
            return "armed replay fed=%d left=%d held=%d" % (c["fed"], (cur or {}).get("left", 0), 1 if self.held else 0)
        return "armed"

    # ---- start ---------------------------------------------------------------------------------------------------------
    def start(self) -> None:
        self._trigger_thread = threading.Thread(target=self._trigger_main, daemon=True, name="tardis-backlog-trigger")
        self._replay_thread = threading.Thread(target=self._replay_main, daemon=True, name="tardis-replay")
        self._trigger_thread.start()
        self._replay_thread.start()

    def _trigger_main(self) -> None:
        try:
            end = time.monotonic() + 60.0
            kind, src = _shutdown_source()
            while kind is None and time.monotonic() < end and not self.stop_requested:
                time.sleep(2.0)
                kind, src = _shutdown_source()
            if kind == "event":
                src.wait()
                self.persist_now("event")
            elif kind == "poll":
                while not self.stop_requested:
                    if src():
                        self.persist_now("poll")
                        return
                    time.sleep(0.5)
            else:
                self._trace("no shutdown signal found -> persist only through the on_shutdown hook")
        except Exception as e:
            self._trace("trigger thread error (%s: %s)" % (type(e).__name__, e))

    # ---- writing -------------------------------------------------------------------------------------------------------
    def _open_locked(self) -> bool:
        if self._fh is not None:
            return True
        os.makedirs(_dir(), exist_ok=True)
        name = "pending-%s-%d-%s.jsonl" % (time.strftime("%Y%m%d-%H%M%S"), os.getpid(), self.uuid[:8])
        path = os.path.join(_dir(), name)
        fh = open(path, "xb")
        nodes = edges = -1
        try:
            nodes, edges = int(getattr(self.region, "node_count", -1)), int(getattr(self.region, "edge_count", -1))
        except Exception:
            pass
        hdr = {"v": VERSION, "kind": KIND, "uuid": self.uuid, "pid": os.getpid(), "created": time.time(),
               "manifold": _norm(getattr(self.region, "filepath", "")), "nodes": nodes, "edges": edges}
        blob = _enc(hdr)
        fh.write(blob)
        fh.flush()
        os.fsync(fh.fileno())
        self._fh, self.path, self._nrec, self._nbytes = fh, path, 0, len(blob)
        return True

    def append(self, recs, what="") -> int:
        """Write records (one write, one fsync), within the caps. Returns the number written; the rest is counted, never silent."""
        if not recs:
            return 0
        blobs = []
        with self._wlock:
            try:
                # the header is written by _open_locked AFTER this selection: until the file exists, keep room for it, or a first append
                # that fills max_bytes leaves a file the replay then rejects as oversize (found folding review 10-15's append_caps control)
                total = 0 if self._fh is not None else HEADER_ROOM
                for r in recs:
                    try:
                        b = _enc(r)
                    except Exception:
                        r2 = dict(r)
                        if r2.get("t") == "item" and isinstance(r2.get("i"), dict) and "concept_metadata" in r2["i"]:
                            i2 = dict(r2["i"])
                            i2.pop("concept_metadata", None)
                            r2["i"] = i2
                            self.counters["meta_dropped"] += 1
                        elif "meta" in r2:
                            r2.pop("meta", None)
                            self.counters["meta_dropped"] += 1
                        try:
                            b = _enc(r2)
                            r = r2
                        except Exception:
                            self.counters["lost"] += 1
                            continue
                    if len(b) > cfg("max_line"):
                        r2 = dict(r)
                        if r2.get("t") == "item" and isinstance(r2.get("i"), dict) and "concept_metadata" in r2["i"]:
                            i2 = dict(r2["i"])
                            i2.pop("concept_metadata", None)
                            r2["i"] = i2
                            b = _enc(r2)
                            self.counters["meta_dropped"] += 1
                        elif "meta" in r2:
                            r2.pop("meta", None)
                            b = _enc(r2)
                            self.counters["meta_dropped"] += 1
                        if len(b) > cfg("max_line"):
                            self.counters["over_line"] += 1
                            continue
                    if self._nrec + len(blobs) >= cfg("max_records") or self._nbytes + total + len(b) > cfg("max_bytes"):
                        self.counters["over_cap"] += 1
                        continue
                    blobs.append((r, b))
                    total += len(b)
                if blobs:
                    self._open_locked()
                    data = b"".join(b for _, b in blobs)
                    self._fh.write(data)
                    self._fh.flush()
                    os.fsync(self._fh.fileno())
                    self._nrec += len(blobs)
                    self._nbytes += len(data)
                    for r, _ in blobs:
                        if r.get("t") == "pairs":
                            self.counters["persisted_pairs_recs"] += 1
                        else:
                            self.counters["persisted_items"] += 1
            except Exception as e:
                self.counters["lost"] += len(recs) - len(blobs) if blobs else len(recs)
                self._trace("append FAILED (%s: %s)" % (type(e).__name__, e))
                return 0
        return len(blobs)

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def item_record(self, it, src):
        """The queue item as a record, or None. Concepts the manifold would reject (key > 256 chars, control chars) are dropped:
        upsert_node returns -1 for them and link() then returns False, so they could never be written -- same set of pairs."""
        try:
            if it.get("_tf_pairs") is not None:
                return self._pairs_item_record(it, src)
            cs = [c for c in (str(x) for x in (it.get("concepts_to_bind") or [])) if _okstr(c)]
            if len(cs) > CONCEPTS_MAX:
                cs = cs[:CONCEPTS_MAX]
                self.counters["lost"] += 1
            if len(cs) < 2:
                self.counters["no_pairs"] += 1
                return None
            if _carry():
                full = self._verbatim_record(it, src)
                if full is not None:
                    return full
            keep = {"concepts_to_bind": cs}
            for k in ("concept_key", "from_fairy", "origin_fairy", "feeling", "origin_plane", "origin_channel"):
                if k in it:
                    keep[k] = str(it[k])[:KEY_MAX]
            keep.setdefault("from_fairy", "")
            m = it.get("concept_metadata")
            if m:
                keep["concept_metadata"] = m
            return {"t": "item", "seq": self._next_seq(), "src": src, "i": keep}
        except Exception:
            self.counters["lost"] += 1
            return None

    def _verbatim_record(self, it, src):
        """W11 (AKASHIC_BIND_CARRYOVER): the queue item with EVERY field, in its own key order, or None (-> today's record).
        Only when it survives the file exactly: JSON round-trip equal to the item, valid at replay, and one line under max_line.
        Keys starting _tf_ are this module's own bookkeeping (a replayed item's _tf_replay) and are never carried."""
        try:
            keep = {k: v for k, v in it.items() if not (isinstance(k, str) and k.startswith("_tf_"))}
            if not _valid_item(keep):
                return None
            if json.loads(json.dumps(keep, ensure_ascii=True)) != keep:
                return None
            rec = {"t": "item", "seq": self._seq + 1, "src": src, "i": keep}
            if len(_enc(rec)) > cfg("max_line"):
                return None
            self._next_seq()
            return rec
        except Exception:
            return None

    def _pairs_item_record(self, it, src):
        rs = self.pairs_records(int(it.get("_tf_tracer", 0)), it.get("_tf_pairs") or [], it.get("concept_metadata") or {}, src)
        return rs[0] if len(rs) == 1 else (rs or None)

    def pairs_records(self, tracer, pairs, meta, src="park"):
        """`pairs` records for a list of [a, b] (parked in-flight remainder), <= PARK_PAIRS_PER_RECORD each, line-size safe."""
        good = [[str(p[0]), str(p[1])] for p in pairs if _okstr(str(p[0])) and _okstr(str(p[1]))]
        out = []
        i = 0
        while i < len(good):
            n = PARK_PAIRS_PER_RECORD
            while True:
                part = good[i:i + n]
                mm = {}
                for a, b in part:
                    for k in (a, b):
                        if k in meta and k not in mm:
                            mm[k] = meta[k]
                rec = {"t": "pairs", "seq": self._next_seq(), "src": src, "tracer": int(tracer), "weight": WEIGHT, "pairs": part}
                if mm:
                    rec["meta"] = mm
                try:
                    ok = len(_enc(rec)) <= cfg("max_line")
                except Exception:
                    rec.pop("meta", None)
                    ok = True
                if ok or n == 1:
                    break
                n = max(1, n // 2)
            out.append(rec)
            i += len(part)
        return out

    # ---- persist -------------------------------------------------------------------------------------------------------
    def persist_now(self, reason: str) -> None:
        """Idempotent; callable from the trigger thread (Event) and from _stop_tardis_flush (on_shutdown). Never raises.
        The first sweep runs HERE (synchronously for the caller) so that after it returns the queue is empty."""
        try:
            with self._persist_lock:
                if self._persist_started:
                    return
                on = _sw("b_persist", fresh=True)
                have_replay = self._cur is not None
                if not on and not have_replay:
                    self._persist_started = True            # decided: nothing to do; B stays inert (today's behaviour)
                    self._trace("persist: b_persist is OFF at the shutdown moment -> queue NOT persisted (reason=%s)" % reason)
                    return
                self._persist_started = True
                if on:
                    self.stop_requested = True              # one-way: from here the flush thread parks instead of writing
            t0 = time.monotonic()
            qs = self.q.qsize()
            self._trace("persist start reason=%s q=%d switch=%s" % (reason, qs, "ON" if on else "OFF (replay remainder only)"))
            stopped = self._stop_replay()                   # from here nothing more is fed into the queue
            if on:
                # this boot's live queue FIRST (review 10-15, F2): at the file cap the freshest binds are kept, not an old replay remainder
                n = self._sweep(first=True)
                self.persist_s = time.monotonic() - t0
                self._trace("queue items=%d written; first sweep done in %.2f s; file=%s" % (
                    n, self.persist_s, os.path.basename(self.path) if self.path else "(none: nothing to persist)"))
            if stopped:
                self._release_current("shutdown")           # THEN the previous boot's unfed remainder, into the room that is left
            if on:
                threading.Thread(target=self._sweeper_main, daemon=True, name="tardis-backlog-sweep").start()
            else:
                n = sum(1 for _ in list(self.q.queue)) if hasattr(self.q, "queue") else -1
                self._trace("persist: queue of %s items NOT persisted (b_persist OFF)" % n)
        except Exception as e:
            self._trace("persist FAILED (%s: %s)" % (type(e).__name__, e))

    def _sweep(self, first=False) -> int:
        """Drain the queue into the file (get_nowait, so every item leaves the queue exactly once). Returns items written.
        The first sweep drains until the queue is EMPTY; first_sweep_budget_s only splits it into several writes (see the note at
        REMAINDER_RESERVE_RECORDS): its synchronous cost is bounded by the queue's own cap."""
        t_end = time.monotonic() + (cfg("first_sweep_budget_s") if first else 1e9)
        written = 0
        while True:
            recs = []
            n = 0
            while True:
                try:
                    it = self.q.get_nowait()
                except _queue.Empty:
                    break
                r = self.item_record(it, "queue")
                n += 1
                if isinstance(r, list):
                    recs.extend(r)
                elif r is not None:
                    recs.append(r)
                if (n & 63) == 0 and time.monotonic() > t_end and n >= cfg("first_min_records"):
                    break
            self.counters["sweeps"] += 1
            if recs:
                written += self.append(recs, "sweep")
            if n == 0:
                return written
            if self.q.qsize() == 0:
                return written

    def _sweeper_main(self) -> None:
        """Late arrivals: on the SDFIX route the fabric is not shut down, so postal workers can still deliver."""
        try:
            end = time.monotonic() + cfg("sweep_lifetime_s")
            while time.monotonic() < end:
                time.sleep(cfg("sweep_interval_s"))
                before = self.counters["persisted_items"]
                w = self._sweep()
                if w:
                    self.counters["late_items"] += w
                    self._trace("late arrivals persisted: %d (total late %d)" % (w, self.counters["late_items"]))
        except Exception as e:
            self._trace("sweeper error (%s: %s)" % (type(e).__name__, e))

    # ---- chunked submit (hook F5b) ---------------------------------------------------------------------------------------
    def chunker(self, pairs_by_tracer, meta):
        return _Chunker(self, pairs_by_tracer, meta)

    # ---- replay --------------------------------------------------------------------------------------------------------
    def _stop_replay(self) -> bool:
        """Stop the replay thread. True = it stopped (its file in hand may be released); False = it did not stop in 1.5 s: its file
        then stays replaying-* (kept, never re-read: at most once)."""
        self._replay_stop.set()
        th = self._replay_thread
        if th is not None and th is not threading.current_thread() and th.is_alive():
            th.join(timeout=1.5)
            if th.is_alive():
                self._trace("replay thread did not stop within 1.5 s: its file stays replaying-* (kept, at most once)")
                return False
        return True

    def _wait(self, s: float) -> bool:
        """Sleep s seconds; True if the replay was told to stop."""
        return self._replay_stop.wait(s)

    def _list(self, prefix):
        try:
            return sorted(n for n in os.listdir(_dir()) if n.startswith(prefix))
        except Exception:
            return []

    def _rename(self, src_name, dst_name) -> bool:
        try:
            os.replace(os.path.join(_dir(), src_name), os.path.join(_dir(), dst_name))
            return True
        except Exception as e:
            self._trace("rename %s -> %s failed (%s)" % (src_name, dst_name, type(e).__name__))
            return False

    def _reject(self, claimed_name, reason) -> None:
        orig = claimed_name.split("-", 1)[1] if "-" in claimed_name else claimed_name
        self._rename(claimed_name, "rejected-pending-%s.%s" % (orig, reason))
        self.counters["files_rejected"] += 1
        self._trace("REJECTED %s (%s): kept for inspection, not replayed" % (claimed_name, reason))

    def _replay_main(self) -> None:
        try:
            if self._wait(cfg("replay_delay_s")) or self.stop_requested:
                return
            if not _sw("b_persist", fresh=True):
                self._trace("replay: b_persist is OFF -> not replaying (files stay pending)")
                return
            if not os.path.isdir(_dir()):
                return
            for n in self._list("replaying-"):
                self._rename(n, "stale-" + n[len("replaying-"):])
                self._trace("stale replaying file kept as stale-%s (a crash mid-replay: at most once, not re-read)" % n[len("replaying-"):])
            warn = len(self._list("stale-")) + len(self._list("rejected-"))
            if warn > 16:
                self._trace("WARNING: %d stale/rejected files are kept in %s (never removed by B)" % (warn, _dir()))
            while not self._replay_stop.is_set() and self._boot_total < cfg("per_boot_records"):
                names = [n for n in self._list("pending-") if n.endswith(".jsonl") and n not in self._skip]
                # a file this process is itself writing (its own pending-*) is never replayed: its name carries our uuid prefix
                names = [n for n in names if self.uuid[:8] not in n and (self.path is None or n != os.path.basename(self.path))]
                if not names:
                    break
                if not self._replay_file(names[0]):
                    break
            if self._boot_total >= cfg("per_boot_records"):
                self._trace("replay: per-boot record limit %d reached; the rest stays pending" % cfg("per_boot_records"))
        except Exception as e:
            self._trace("replay thread error (%s: %s)" % (type(e).__name__, e))

    def _replay_file(self, name) -> bool:
        """Claim, check, validate, feed one pending file. Returns False to stop the whole replay."""
        d = _dir()
        path = os.path.join(d, name)
        try:
            size = os.path.getsize(path)
        except OSError:
            self._skip.add(name)
            return True
        if size > cfg("max_bytes"):
            self._rename(name, "rejected-%s.oversize" % name)
            self.counters["files_rejected"] += 1
            self._trace("REJECTED %s (oversize %d bytes > %d): never opened, kept" % (name, size, cfg("max_bytes")))
            return True
        claim = "replaying-" + name[len("pending-"):]
        if not self._rename(name, claim):                       # the claim: atomic; a second claimer gets nothing
            self._skip.add(name)
            return True
        fh = None
        try:
            fh = open(os.path.join(d, claim), "rb")
            line, long_ = _read_line(fh, cfg("max_line"))
            hdr, why = (None, "long") if long_ else _dec(line)
            if hdr is None or hdr.get("v") != VERSION or hdr.get("kind") != KIND or not isinstance(hdr.get("uuid"), str):
                fh.close()
                fh = None
                self._reject(claim, "header")
                return True
            reg = _norm(getattr(self.region, "filepath", ""))
            if _norm(hdr.get("manifold", "")) != reg:
                fh.close()
                fh = None
                self._reject(claim, "other_manifold")
                return True
            if hdr["uuid"] in _ledger_read():
                fh.close()
                fh = None
                self._reject(claim, "replayed_before")
                return True
            # pass 1: validate the whole file without keeping it
            good = bad = torn = 0
            start_pos = fh.tell()
            while True:
                if (good + bad) % 512 == 0 and self._replay_stop.is_set():
                    fh.close()
                    fh = None
                    self._rename(claim, name)                   # nothing was fed and the ledger has no entry: give it back
                    self._trace("replay stopped while validating %s: file returned to pending" % name)
                    return False
                line, long_ = _read_line(fh, cfg("max_line"))
                if not line and not long_:
                    break
                if long_:
                    bad += 1
                    continue
                rec, why = _dec(line)
                if rec is None:
                    if why == "torn":
                        torn += 1
                    else:
                        bad += 1
                    continue
                if validate(rec):
                    good += 1
                else:
                    bad += 1
            self.counters["bad"] += bad
            self.counters["torn"] += torn
            if bad >= cfg("bad_min") and bad > BAD_SHARE * max(1, good + bad):
                fh.close()
                fh = None
                self._reject(claim, "bad_records")
                return True
            _ledger_add(hdr["uuid"])
            self._boot_total += good
            fh.seek(start_pos)
            self._cur = {"fh": fh, "claim": claim, "name": name, "uuid": hdr["uuid"], "left": good, "path": os.path.join(d, claim)}
            self._inhand = None
            fh = None
            self._trace("claimed %s: %d valid records (bad=%d torn=%d)" % (name, good, bad, torn))
        except Exception as e:
            self._trace("replay of %s failed before feeding (%s: %s)" % (name, type(e).__name__, e))
            try:
                if fh is not None:
                    fh.close()
            except Exception:
                pass
            self._cur = None
            return True
        t0 = time.monotonic()
        fed0, pr0 = self.counters["fed"], self.counters["fed_pairs_recs"]
        status = self._feed()
        if status == "done":
            self._finish_current("done")
            self._trace("replay done: fed %d items + %d pair records from %s in %.1f s" % (
                self.counters["fed"] - fed0, self.counters["fed_pairs_recs"] - pr0, name, time.monotonic() - t0))
            return True
        if status == "off":
            self._trace("replay: b_persist switched OFF while feeding %s" % name)
            self._release_current("switch_off")
            return False
        return False                                           # stop: persist_now releases the file

    def _next_valid(self, fh):
        while True:
            line, long_ = _read_line(fh, cfg("max_line"))
            if not line and not long_:
                return None
            if long_:
                continue
            rec, _ = _dec(line)
            if rec is not None and validate(rec):
                return rec

    def _set_held(self, v: bool, q: int = 0) -> None:
        if v != self.held:
            self.held = v
            self._trace("replay %s (queue %d, reserve line %d)" % ("HELD" if v else "resumed", q, (self.q.maxsize or 0) - cfg("reserve")))

    def _feed(self) -> str:
        """Feed the current file into the queue at a bounded rate. -> 'done' | 'stop' | 'off'."""
        cur = self._cur
        fh = cur["fh"]
        last_trickle = -1e9
        budget = 0.0
        t_prev = time.monotonic()
        last_sw = t_prev
        while True:
            if self._replay_stop.is_set():
                return "stop"
            now = time.monotonic()
            if now - last_sw >= 10.0:
                last_sw = now
                if not _sw("b_persist", fresh=True):
                    return "off"
            rate = cfg("max_rate")
            budget = min(float(rate), budget + rate * (now - t_prev))
            t_prev = now
            qs = self.q.qsize()
            mx = self.q.maxsize or 0
            if mx and qs >= mx - cfg("reserve"):
                self._set_held(True, qs)
                if self._wait(0.5):
                    return "stop"
                continue
            self._set_held(False, qs)
            if qs < cfg("headroom"):
                allow = min(cfg("headroom") - qs, int(budget))
            elif now - last_trickle >= cfg("trickle_s"):
                allow = 1                                           # the floor: replay never stalls while the queue has room
                last_trickle = now
            else:
                allow = 0
            while allow > 0:
                if self._inhand is None:
                    self._inhand = self._next_valid(fh)
                    if self._inhand is None:
                        return "done"
                try:
                    self.q.put_nowait(to_queue_item(self._inhand, cur["uuid"]))
                except _queue.Full:
                    break
                if self._inhand.get("t") == "pairs":
                    self.counters["fed_pairs_recs"] += 1
                else:
                    self.counters["fed"] += 1
                cur["left"] = max(0, cur["left"] - 1)
                self._inhand = None
                budget = max(0.0, budget - 1.0)
                allow -= 1
            if self._wait(0.1):
                return "stop"

    def _finish_current(self, tag) -> None:
        cur = self._cur
        if cur is None:
            return
        try:
            cur["fh"].close()
        except Exception:
            pass
        done_name = tag + "-" + cur["claim"][len("replaying-"):]
        self._rename(cur["claim"], done_name)
        self._cur = None
        self._inhand = None
        if tag == "done":
            self.counters["files_done"] += 1
            if _carry():
                return                                  # W11: a replayed file is moved aside (done-*), never deleted
            done = self._list("done-")
            for n in done[:max(0, len(done) - cfg("done_keep"))]:
                try:
                    os.remove(os.path.join(_dir(), n))
                except Exception:
                    pass

    def _release_current(self, why) -> None:
        """The replay file in hand is not fully fed: its unfed remainder goes into the pending file (src replay_unfed), then the
        claimed file is retired. If any of it could not be written the claimed file is kept as stale-* instead of done-*."""
        cur = self._cur
        if cur is None:
            return
        try:
            recs = []
            if self._inhand is not None:
                recs.append(self._inhand)
            while True:
                r = self._next_valid(cur["fh"])
                if r is None:
                    break
                recs.append(r)
            out = []
            for r in recs:
                r = dict(r)
                r["seq"] = self._next_seq()
                r["src"] = "replay_unfed"
                out.append(r)
            before = (self.counters["over_cap"], self.counters["over_line"], self.counters["lost"])
            # the remainder goes AFTER this boot's live queue and must leave a reserve for the park and late arrivals (review 10-15, F2):
            # at the cap the OLDEST records are the ones that do not fit (counted over_cap; the claimed file is then kept as stale-*)
            room_n = cfg("max_records") - self._nrec - REMAINDER_RESERVE_RECORDS
            room_b = cfg("max_bytes") - self._nbytes - REMAINDER_RESERVE_BYTES
            keep, nb = [], 0
            for r in out:
                if len(keep) >= room_n:
                    break
                try:
                    ln = len(_enc(r))
                except Exception:
                    ln = 0
                if nb + ln > room_b:
                    break
                keep.append(r)
                nb += ln
            cut = len(out) - len(keep)
            if cut:
                self.counters["over_cap"] += cut
                self._trace("replay remainder: %d of %d records do not fit beside this boot's live binds (file cap %d records / %d bytes, "
                            "reserve %d records kept for the park + late arrivals) -> counted over_cap; the OLDEST are the ones dropped" % (
                                cut, len(out), cfg("max_records"), cfg("max_bytes"), REMAINDER_RESERVE_RECORDS))
            n = self.append(keep, "replay_unfed")
            after = (self.counters["over_cap"], self.counters["over_line"], self.counters["lost"])
            self.counters["unfed_written"] += n
            self._trace("replay remainder (%s): %d records written back to the pending file" % (why, n))
            self._finish_current("done" if (n == len(out) and before == after) else "stale")
        except Exception as e:
            self._trace("release of the replay file FAILED (%s: %s): kept as replaying-*" % (type(e).__name__, e))
