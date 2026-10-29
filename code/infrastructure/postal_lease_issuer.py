"""postal_lease_issuer -- HER identity system issues every postal identity; the Rust postal core only asks.

2026-10-19 (Nous + Ace; wf postal-lease-build-1019; design: nous_builds/postal_lease_1016/DESIGN_B2.md sections 3-6).
Ace 10-16: "whatever is creating the workers should have a trace id, so the workers should have like a sub version of
that. like how a home router works. but i like the id for life idea."
Ace 10-19: "the organ template being what assigns identity it would make sense the lease and what nots come from her
main pc".

Router mapping (DESIGN_B2 section 0):
    her process            namespace root  ns          minted here, lazily, on the first bus
    the router             a bus           bus_tid     issue_bus()          asked inside PostalCore(worker_mode=..)
    a network              a pool (topic)  pool_tid    minted here on first sight of (bus_tid, topic)
    a device's address     postal/<bus_tid>/<topic>/w<serial>   the Rust thread description, fixed at spawn
    the DHCP lease         a worker        lease_tid   issue_lease()        asked on the worker's FIRST delivery
    who the packet is for  a subscription  target tag  issue_subscription() asked inside subscribe(), her thread

Every id is minted by the Organ Template's own Tracer (Organ_Template_0_3_0.py:389, uuid.uuid4().hex[:12]), taken from
sys.modules (never imported here). If the template module is not loaded (MCP servers, tests) the identical expression
is used and the record says minted="fallback". No template is edited; no FairyProfile is created (a profile with no
instance would be a phantom, the 10-05 BaseFairy shape); nothing goes into TracerRegistry (it prunes its oldest
1,000 above 10,000, Organ_Template_0_3_0.py:463-470, and these are the oldest tracers alive).

CONTRACT (each line has a must-fail test in nous_builds/postal_lease_1016/run_tests.py):
  1. Importing this module has NO side effects: no thread, no print, no registration. register() is explicit.
  2. issue_lease runs ON A POSTAL WORKER. It never imports, logs, prints, publishes, touches the fairy registry, or
     calls threading.current_thread() (on a foreign thread that creates a _DummyThread for the life of the lease;
     verify_safety.md section 5). It calls only threading.get_native_id(), time.time(), the mint, and dict inserts.
  3. _LOCK is never held while another lock is taken: registry reads and frame walks happen outside it.
  4. Ids are never reused: every minted id goes into _ISSUED; a collision re-mints (up to 4 tries).
  5. A failure never raises into a delivery: issue_lease returns None (Rust then runs today's per-message attach for
     that worker), issue_subscription returns the "?<name>" tag. Rust treats any exception the same way.
"""
import inspect
import json
import os
import sys
import threading
import time
import uuid

_TEMPLATE_NAMES = (
    "fairies.P00_Autonomic.organ_template.Organ_Template_0_3_0",   # what every fairy imports (82/85 fairy.py)
    "P00_Autonomic.organ_template.Organ_Template_0_3_0",           # the same file under the fairies/ path entry
)
_LOCK = threading.Lock()
_ISSUED = set()            # every tid this process minted (never reused)
NS = None                  # namespace root record
_BUSES = {}                # bus_tid -> rec
_POOLS = {}                # (bus_tid, topic) -> rec
_LEASES = {}               # lease_tid -> rec
_SUBS = {}                 # (bus_tid, topic, name, intent) -> rec
STATS = {"bus": 0, "sub": 0, "lease": 0, "pool": 0, "fail": 0, "fallback_minted": 0, "template_minted": 0,
         "collisions": 0, "evicted": 0, "census_written": 0, "census_failed": 0}
_CFG = {"creators": ["server"], "census_period_s": 300, "max_records": 20000, "census_path": None}
_CENSUS_THREAD = None
_SKIP_MODULE_PREFIXES = ("postal_core",)   # the package and its tensor_fabric: the bus's plumbing, never its creator


# ================================================================================================ configuration
def configure(cfg):
    """Apply the switch file's settings (validated; unknown keys ignored). Returns the effective config."""
    if not isinstance(cfg, dict):
        return dict(_CFG)
    c = cfg.get("creators")
    if isinstance(c, list) and all(isinstance(x, str) for x in c):
        _CFG["creators"] = list(c)
    p = cfg.get("census_period_s")
    if isinstance(p, (int, float)) and not isinstance(p, bool) and p >= 0:
        _CFG["census_period_s"] = float(p)
    m = cfg.get("max_records")
    if isinstance(m, int) and not isinstance(m, bool) and m >= 100:
        _CFG["max_records"] = m
    cp = cfg.get("census_path")
    if isinstance(cp, str) and cp:
        _CFG["census_path"] = cp
    return dict(_CFG)


def allowed_creators():
    return list(_CFG["creators"])


def _core():
    """The loaded postal_core extension module (never imported here)."""
    for n in ("postal_core.postal_core", "postal_core"):
        m = sys.modules.get(n)
        if m is not None and hasattr(m, "set_lease_issuer"):
            return m
    return None


def register(core=None):
    """MAIN thread, called by the switch helper (tensor_fabric._make_postal_core). Hands this module to Rust."""
    core = core or _core()
    if core is None:
        raise RuntimeError("postal_core extension with set_lease_issuer is not loaded")
    core.set_lease_issuer(sys.modules[__name__])
    return True


def unregister(core=None):
    core = core or _core()
    if core is not None:
        core.set_lease_issuer(None)


# ================================================================================================ minting
def _template():
    for n in _TEMPLATE_NAMES:
        m = sys.modules.get(n)
        if m is not None and hasattr(m, "Tracer") and hasattr(m, "TracerType"):
            return m
    return None


def _valid_tid(s):
    return isinstance(s, str) and len(s) == 12 and all(ch in "0123456789abcdef" for ch in s)


def _mint(parent, op, fairy_id="", fairy_name="", payload=None):
    """A candidate record with a fresh template tid. No lock taken here (contract 3)."""
    tm = _template()
    tid, how = None, "fallback"
    if tm is not None:
        try:
            t = tm.Tracer(tracer_type=tm.TracerType.TELEMETRY, fairy_id=fairy_id or "", fairy_name=fairy_name or "",
                          parent_id=parent or "", operation=op, payload=dict(payload or {}))
            tid, how = t.id, "template"
        except Exception:
            tid = None
    if not _valid_tid(tid):
        tid, how = uuid.uuid4().hex[:12], "fallback"          # the identical expression (template :389)
    return {"tid": tid, "parent": parent or "", "op": op, "fairy_id": fairy_id or "", "fairy_name": fairy_name or "",
            "payload": dict(payload or {}), "ts": time.time(), "minted": how}


def _commit(rec, table, key):
    """Under _LOCK: insert unless the tid was ever issued. Returns False on a collision (caller re-mints)."""
    if rec["tid"] in _ISSUED:
        STATS["collisions"] += 1
        return False
    _ISSUED.add(rec["tid"])
    STATS["template_minted" if rec["minted"] == "template" else "fallback_minted"] += 1
    if table is not None:
        table[key] = rec
    return True


def _issue(table, key, parent, op, fairy_id="", fairy_name="", payload=None, existing_ok=False):
    for _ in range(4):
        cand = _mint(parent, op, fairy_id, fairy_name, payload)
        with _LOCK:
            if existing_ok and key in table:
                return table[key]
            if _commit(cand, table, key):
                return cand
    raise RuntimeError("4 id collisions in a row")


def _ns_rec():
    global NS
    if NS is not None:
        return NS
    main = _main_name()
    for _ in range(4):
        cand = _mint("", "postal.namespace", "", main, {"pid": os.getpid()})
        with _LOCK:
            if NS is not None:
                return NS
            if _commit(cand, None, None):
                NS = cand
                return NS
    raise RuntimeError("4 id collisions in a row")


def _pool_rec(bus_tid, topic):
    key = (bus_tid, topic)
    with _LOCK:
        rec = _POOLS.get(key)
    if rec is not None:
        return rec
    rec = _issue(_POOLS, key, bus_tid or "", "postal.pool:%s" % topic, payload={"topic": topic}, existing_ok=True)
    with _LOCK:
        if rec.get("_counted") is None:
            rec["_counted"] = True
            STATS["pool"] += 1
    return rec


def _minted():
    with _LOCK:
        t, f = STATS["template_minted"], STATS["fallback_minted"]
    return "template" if f == 0 else ("fallback" if t == 0 else "mixed")


# ================================================================================================ who is asking
def _main_name():
    m = sys.modules.get("__main__")
    f = getattr(m, "__file__", None) or ""
    b = os.path.basename(f)
    return b[:-3] if b.endswith(".py") else (b or "__main__")


def _self_of(frame):
    try:
        return frame.f_locals.get("self")
    except Exception:
        return None


def _static(obj, name):
    """Attribute lookup that runs NO code of the object (no __getattr__, no property, no descriptor): the frame walk
    looks at arbitrary objects on her stack and must never trigger their behaviour."""
    try:
        v = inspect.getattr_static(obj, name, None)
    except Exception:
        return None
    if v is None or isinstance(v, (property, staticmethod, classmethod)) or "__get__" in dir(type(v)):
        return None                                      # a descriptor (method, property, slot): never invoked here
    return v


def _fairy_of(obj):
    """(ACTOR_NAME, fairy_id) if obj looks like an Organ Template fairy (self._profile.fairy_id), else None."""
    if obj is None:
        return None
    try:
        prof = _static(obj, "_profile")
        fid = _static(prof, "fairy_id") if prof is not None else None
        if not _valid_tid(fid):
            return None
        name = _static(obj, "ACTOR_NAME") or _static(prof, "name")
        return (str(name), fid) if isinstance(name, str) and name else None
    except Exception:
        return None


def _walk(skip):
    try:
        f = sys._getframe(skip + 1)
    except ValueError:
        return
    n = 0
    while f is not None and n < 24:
        mod = f.f_globals.get("__name__", "") or ""
        if mod != __name__ and not mod.startswith(_SKIP_MODULE_PREFIXES):
            yield f, mod
        f = f.f_back
        n += 1


def creator(skip=1):
    """Who is building this bus: ('fairy', ACTOR_NAME, fairy_id) for the nearest fairy frame, else ('main', <__main__
    basename>, '') for the nearest __main__ frame, else ('unknown', '', ''). Never on a postal worker."""
    for f, mod in _walk(skip):
        fr = _fairy_of(_self_of(f))
        if fr:
            return ("fairy", fr[0], fr[1])
        if mod == "__main__":
            return ("main", _main_name(), "")
    return ("unknown", "", "")


def _registries():
    """Every loaded template registry (deduplicated). Read OUTSIDE _LOCK (contract 3)."""
    out, seen = [], set()
    for n in _TEMPLATE_NAMES:
        m = sys.modules.get(n)
        g = getattr(m, "get_fairy_registry", None) if m is not None else None
        if g is None:
            continue
        try:
            r = g()
        except Exception:
            continue
        if id(r) not in seen:
            seen.add(id(r))
            out.append(r)
    return out


def _lookup(name):
    for r in _registries():
        try:
            p = r.get(name)
        except Exception:
            p = None
        fid = getattr(p, "fairy_id", None) if p is not None else None
        if _valid_tid(fid):
            return fid
    return None


def _by_name(name):
    """The longest registered profile name P with name == P or name.startswith(P + '-') (the bridge's default naming,
    Organ_Template_0_3_0.py:812-813). Returns (P, fairy_id) or None."""
    if not isinstance(name, str) or not name:
        return None
    fid = _lookup(name)
    if fid:
        return (name, fid)
    i = len(name)
    while True:
        i = name.rfind("-", 0, i)
        if i <= 0:
            return None
        p = name[:i]
        fid = _lookup(p)
        if fid:
            return (p, fid)


def _sanitize_tag(name):
    s = "?" + "".join(ch if (0x21 <= ord(ch) <= 0x7E and ch != "/") else "_" for ch in str(name or ""))
    s = s[:64]
    return s if len(s) > 1 else "?_"


def _resolve_target(name, skip=2):
    """Which fairy a subscription delivers to (DESIGN_B2 5.2). Candidates: frame, bridge, name. The tag follows
    `name` when it disagrees with the chosen candidate; both are recorded, never hidden."""
    cand_frame = cand_bridge = None
    for f, _mod in _walk(skip):
        s = _self_of(f)
        if cand_frame is None:
            fr = _fairy_of(s)
            if fr:
                cand_frame = fr
        if cand_bridge is None and s is not None:
            bn = _static(s, "_fairy_name")
            if isinstance(bn, str) and bn:
                fid = _lookup(bn)
                cand_bridge = (bn, fid) if fid else None
        if cand_frame and cand_bridge:
            break
    cand_name = _by_name(name)
    chosen, via = None, "none"
    for c, v in ((cand_frame, "frame"), (cand_bridge, "bridge"), (cand_name, "name")):
        if c:
            chosen, via = c, v
            break
    disagree = bool(cand_name and chosen and chosen[1] != cand_name[1])
    if disagree:
        chosen, via = cand_name, "name"
    tag = chosen[1] if chosen else _sanitize_tag(name)
    return {"tag": tag, "fairy_name": chosen[0] if chosen else "", "fairy_id": chosen[1] if chosen else "",
            "via": via, "disagree": disagree,
            "cand_frame": list(cand_frame) if cand_frame else None,
            "cand_bridge": list(cand_bridge) if cand_bridge else None,
            "cand_name": list(cand_name) if cand_name else None}


# ================================================================================================ the three asks
def issue_bus(serial, mode, pid):
    """Ask 1, the router. Runs on the thread constructing PostalCore(worker_mode=..)."""
    kind, name, fid = creator(skip=1)                         # outside _LOCK
    ns = _ns_rec()
    rec = _issue(None, None, ns["tid"], "postal.bus", fid, name,
                 {"serial": serial, "mode": mode, "pid": pid, "creator_kind": kind})
    with _LOCK:
        _BUSES[rec["tid"]] = rec
        STATS["bus"] += 1
    _maybe_start_census_thread()
    try:
        sys.stderr.write(("[postal_lease] bus %s issued under ns %s (creator=%s, ids=%s)\n"
                          % (rec["tid"], ns["tid"], name or kind, _minted())).encode("ascii", "replace").decode("ascii"))
        sys.stderr.flush()
    except Exception:
        pass
    return rec["tid"]


def issue_subscription(bus_tid, topic, name, intent):
    """Ask 2, the target tag. Runs on HER subscribing thread inside subscribe(). Returns a fairy_id or '?<name>'."""
    try:
        target = _resolve_target(name, skip=1)                # outside _LOCK
        pool = _pool_rec(bus_tid, topic)
        with _LOCK:
            _SUBS[(bus_tid, topic, name, intent)] = dict(target, pool_tid=pool["tid"], bus_tid=bus_tid, topic=topic,
                                                         name=name, intent=intent, ts=time.time())
            STATS["sub"] += 1
        return target["tag"]
    except Exception:
        with _LOCK:
            STATS["fail"] += 1
        return _sanitize_tag(name)


def issue_lease(bus_tid, topic, w_serial, tstate_id, leased):
    """Ask 3, the DHCP lease. Runs ON THE POSTAL WORKER at its first delivery (contract 2). None = decline."""
    try:
        native = threading.get_native_id()
        pool = _pool_rec(bus_tid, topic)
        address = "postal/%s/%s/w%d" % (bus_tid, topic, w_serial)
        for _ in range(4):
            cand = _mint(pool["tid"], "postal.lease", "", "",
                         {"w": w_serial, "native_tid": native, "tstate_id": tstate_id, "leased": bool(leased)})
            cand["address"] = address
            cand["pool_tid"] = pool["tid"]
            cand["bus_tid"] = bus_tid
            cand["topic"] = topic
            with _LOCK:
                if _commit(cand, _LEASES, cand["tid"]):
                    STATS["lease"] += 1
                    return cand["tid"]
        with _LOCK:
            STATS["fail"] += 1
        return None
    except Exception:
        try:
            with _LOCK:
                STATS["fail"] += 1
        except Exception:
            pass
        return None


# ================================================================================================ her census
def census():
    """The namespace tree with Rust's per-worker counts joined on lease_tid. Any NON-worker thread."""
    core = _core()
    rust, rstats = [], {}
    if core is not None:
        try:
            rust = list(core.lease_census())
            rstats = dict(core.lease_stats())
        except Exception:
            rust, rstats = [], {}
    with _LOCK:
        ns = dict(NS) if NS else None
        buses = [dict(v) for v in _BUSES.values()]
        pools = [dict(v) for v in _POOLS.values()]
        leases = {k: dict(v) for k, v in _LEASES.items()}
        subs = [dict(v) for v in _SUBS.values()]
        stats = dict(STATS)
    _evict(rust)
    pool_by_key = {(p["payload"].get("topic") and p["parent"], p["payload"].get("topic")): p["tid"] for p in pools}
    by_tag = {}
    for s in subs:
        by_tag.setdefault(s["tag"], s)
    now_cache = {}
    workers = []
    for r in rust:
        lt = r.get("lease_tid")
        lrec = leases.get(lt) if lt else None
        tgts = []
        for tag, n in sorted((r.get("targets") or {}).items(), key=lambda kv: -kv[1]):
            s = by_tag.get(tag)
            fname = s["fairy_name"] if s else ""
            if fname and fname not in now_cache:
                now_cache[fname] = _lookup(fname) or ""
            now = now_cache.get(fname, "")
            tgts.append({"tag": tag, "deliveries": n, "fairy_name": fname, "fairy_id_at_subscribe": tag,
                         "fairy_id_now": now, "changed": bool(now and _valid_tid(tag) and now != tag),
                         "via": s["via"] if s else None})
        pool_tid = lrec["pool_tid"] if lrec else pool_by_key.get((r.get("bus_tid"), r.get("topic")))
        workers.append(dict(r, targets=tgts, pool_tid=pool_tid,
                            native_tid_issuer=(lrec or {}).get("payload", {}).get("native_tid"),
                            lineage="/".join(x or "-" for x in ((ns or {}).get("tid"), r.get("bus_tid"), pool_tid, lt))))
    return {"schema": "postal_lease_census/1", "t": time.time(), "pid": os.getpid(), "minted": _minted(),
            "ns": ns, "buses": buses, "pools": [{k: v for k, v in p.items() if k != "_counted"} for p in pools],
            "workers": workers, "subs": subs, "issuer_stats": stats, "rust_stats": rstats,
            "leases_recorded": len(leases)}


def _evict(rust):
    """Bound: evict the oldest NON-live leases past max_records (live ones never)."""
    with _LOCK:
        over = len(_LEASES) - _CFG["max_records"]
        if over <= 0:
            return 0
        live = {r.get("lease_tid") for r in rust if r.get("state") == "live"}
        victims = sorted((v["ts"], k) for k, v in _LEASES.items() if k not in live)[:over]
        for _ts, k in victims:
            del _LEASES[k]
        STATS["evicted"] += len(victims)
        return len(victims)


def census_path():
    p = _CFG.get("census_path")
    if p:
        return p
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # <akashic_v2>/infrastructure/..
    return os.path.join(root, "state", "postal_lease_census.json")


def write_census(path=None):
    """Atomic: ASCII JSON built BEFORE open, temp file, os.replace (the provenance.py:43-47 pattern)."""
    path = path or census_path()
    data = json.dumps(census(), ensure_ascii=True, default=str, separators=(",", ":"))
    tmp = "%s.tmp.%d.%d" % (path, os.getpid(), threading.get_ident())
    with open(tmp, "w", encoding="ascii") as f:
        f.write(data)
    os.replace(tmp, path)
    with _LOCK:
        STATS["census_written"] += 1
    return path


def _census_loop():
    while True:
        period = _CFG.get("census_period_s") or 0
        if period <= 0:
            return
        time.sleep(period)
        try:
            write_census()
        except Exception:
            with _LOCK:
                STATS["census_failed"] += 1


def _maybe_start_census_thread():
    global _CENSUS_THREAD
    if (_CFG.get("census_period_s") or 0) <= 0:
        return
    with _LOCK:
        if _CENSUS_THREAD is not None:
            return
        _CENSUS_THREAD = threading.Thread(target=_census_loop, name="postal-lease-census", daemon=True)
    _CENSUS_THREAD.start()
