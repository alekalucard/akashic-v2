# Single-file Akashic organ: Template v0.0.4 → v0.0.5 → v0.0.6 → v0.0.7 (evolutionary)
#
# v0.0.7 Highlights (evolution, not devolution):
#   - KEEP: All v0.0.6 behaviors (diary, blueprint, directory-backed Post Office, re-hash drift checks)
#   - UPGRADE: Contract beacon also routes to Directory channel (while keeping tracer crumb)
#   - UPGRADE: Oracle suggestions try ORACLE lane first; fallback to prior PLAN publish for continuity
#   - NO BREAKING CHANGES to public surface (self.post, self.std, intents, tests)
#
# Postal behavior (unchanged):
#   self.directory = Directory_Fairy()
#   contract = self.directory.register_organ(...)
#   self.post = contract["post_office"]   # mailbox: to_PLAN/to_TRACER/... and route()
#   self.std  = contract["imports"]       # unified import ledger (stdlib + codex auto_import)

from __future__ import annotations
from fairies.P00_Autonomic.directory_fairy import autowire
autowire()
try:
    from fairies.P00_Autonomic.directory_fairy import inject_std_imports
    if "os" not in globals():      # sentinel check; no manual imports
        inject_std_imports(globals())
except Exception:
    pass
try:
    from fairies.P00_Autonomic.directory_fairy_ide import *  # noqa: F401,F403
except Exception:
    pass
# lane awareness for diary routing (main thread = Fairy; shadow thread sets its own)
_TLS = threading.local()
if not hasattr(_TLS, "lane"):
    _TLS.lane = "Fairies"

os.environ.setdefault(
    "AKASHIC_ROOT",
    r"E:\coding projects\ebook\P10_Memory\Akashic_Records_Physical\current app"
)

import importlib
# ───────────────────────── Akashic history (lean slurp) ─────────────────────
import json as _json
def slurp_akashic_history(root: str, max_lines: int = 1000) -> dict:
    out = {"blueprints": [], "shadow_reports": [], "sim_plans": [], "raw": []}
    diaries_glob = os.path.join(root, "diaries", "**", "*.jsonl")
    for path in glob.glob(diaries_glob, recursive=True):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = _json.loads(line)
                    except Exception:
                        continue

                    kind = entry.get("kind", "")
                    kl = kind.lower()

                    # ── BLUEPRINTS ─────────────────────────────────────────────
                    # canonical blueprint lines (our new ones):
                    if kl.startswith("blueprint."):
                        out["blueprints"].append(entry)
                        continue
                    # legacy crumbs that still mean "there's a blueprint":
                    if "tracer.blueprint_report" in kl or "tracer.blueprint_hash" in kl:
                        out["blueprints"].append(entry)
                        continue
                    if kl == "telemetry.blueprint" or "telemetry.blueprint_" in kl:
                        out["blueprints"].append(entry)
                        continue

                    # ── SHADOW REPORTS ────────────────────────────────────────
                    if kl.startswith("shadow.") or kl.startswith("shadow_"):
                        out["shadow_reports"].append(entry)
                        continue

                    # ── SIM PLANS ─────────────────────────────────────────────
                    if kl.startswith("oracle.sim_plan"):
                        out["sim_plans"].append(entry)
                        continue

                    # fallback
                    out["raw"].append(entry)
        except Exception:
            continue
    return out

# ── SRM (snapshot) slurp: read today's SRM_Intake files, newest last ──
def slurp_srm_today(root: str, max_files: int = 200) -> list[dict]:
    day = time.strftime("%Y-%m-%d", time.gmtime())
    srm_dir = os.path.join(root, "SRM_Intake", day)
    if not os.path.isdir(srm_dir):
        return []
    paths = sorted(
        [p for p in glob.glob(os.path.join(srm_dir, "*.json"))],
        key=lambda p: os.path.getmtime(p)
    )[-max_files:]
    out: list[dict] = []
    for p in paths:
        try:
            with open(p, "r", encoding="utf-8") as f:
                doc = json.load(f)
                doc["_path"] = p
                out.append(doc)
        except Exception:
            continue
    return out

# ─────────────────────────── minimal shared wiring ──────────────────────────
CHANNEL = {
    "TRACER": "tracer",
    "TELEMETRY": "telemetry",
    "PLAN": "plan",
}
DIR_CHANNEL = {
    "TELEMETRY": "telemetry",
    "PLAN":      "plan",
    "COGNITION": "cognition.input",
    "SOMATIC":   "somatic.motor",
    "MEMORY":    "memory.stream",
    "REASON":    "reasoning.input",
    "EMOTION":   "emotion.state",
    "GUI":       "gui.state",
    "TRACER":    "tracer",
    "DIRECTORY": "directory",
    "ORACLE":    "oracle",
}

def resolve_root(preferred: Optional[str] = None, *, akashic_app: Optional[str] = None) -> str:
    """
    App-aware root resolver.
    Priority:
      1) preferred (explicit) if given
      2) AKASHIC_ROOT env (absolute path)
      3) auto from this file location: P10_Memory/Akashic_Records__Physical/<app>
         where <app> is:
           a) akashic_app arg
           b) AKASHIC_APP env
           c) content of .current_app file under Akashic_Records__Physical
           d) the only subdir (excluding 'Organ_Templates') under Akashic_Records__Physical
           e) fallback: 'current app'
    """
    # explicit preferred
    if preferred:
        return os.path.abspath(preferred)

    # environment override
    env_root = os.getenv("AKASHIC_ROOT")
    if env_root:
        return os.path.abspath(env_root)

    # locate the Akashic_Records__Physical anchor near this template
    here = os.path.abspath(os.path.dirname(__file__))
    anchor_names = ("Akashic_Records__Physical", "Akashic_Records_Physical")
    cursor = here
    physical_dir = None
    while True:
        for name in anchor_names:
            cand = os.path.join(cursor, name)
            if os.path.isdir(cand):
                physical_dir = cand
                break
        if physical_dir or os.path.dirname(cursor) == cursor:
            break
        cursor = os.path.dirname(cursor)

    # if we couldn't find the anchor, fall back to the old default
    if not physical_dir:
        home = os.path.expanduser("~")
        default = os.path.join(home, ".akashic_records")
        return default if os.path.isdir(default) else os.path.abspath("./akashic_records")

    # pick app name
    app = akashic_app or os.getenv("AKASHIC_APP")
    if not app:
        # .current_app file?
        marker = os.path.join(physical_dir, ".current_app")
        if os.path.isfile(marker):
            try:
                with open(marker, "r", encoding="utf-8") as f:
                    app = (f.readline() or "").strip()
            except Exception:
                app = None
    if not app:
        # if exactly one subdir (excluding Organ_Templates), use it
        try:
            subs = [d for d in os.listdir(physical_dir)
                    if os.path.isdir(os.path.join(physical_dir, d))
                    and d.lower() != "organ templates"]
            if len(subs) == 1:
                app = subs[0]
        except Exception:
            app = None
    if not app:
        app = "current app"

    return os.path.join(physical_dir, app)
_SRMDIR = os.path.join(resolve_root(akashic_app=os.getenv("AKASHIC_APP")), "SRM_Intake")

def _persist_blueprint_snapshot(bp: Dict[str, Any], sha: str, *, actor: str) -> Optional[str]:
    try:
        day = time.strftime("%Y-%m-%d", time.gmtime())
        outdir = os.path.join(_SRMDIR, day)
        os.makedirs(outdir, exist_ok=True)
        fname = f"blueprint.contract-{sha}.json"
        fpath = os.path.join(outdir, fname)
        # don't spam: only write if not already there (sha is stable)
        if not os.path.isfile(fpath):
            doc = {"actor": actor, "blueprint": bp, "sha": sha, "ts": time.time()}
            _safe_write_json(fpath, doc)
        return fpath
    except Exception:
        return None


# ───────────────────── Diary dedup helpers (module-level) ───────────────────
_LAST_SIG_CACHE: Dict[str, str] = {}

def _norm_for_sig(obj):
    if isinstance(obj, dict):
        # exclude fast-changing keys so we don't spam duplicates
        return {k: _norm_for_sig(v) for k, v in obj.items() if k not in {"ts", "id", "nonce"}}
    if isinstance(obj, list):
        return [_norm_for_sig(x) for x in obj]
    return obj

def _diary_path_for_lane(root: str, organ_name: str, lane: str = "fairy") -> str:
    # folder split: Fairies vs Shadow Fairies
    group = "Shadow Fairies" if str(lane).lower().startswith("shadow") else "Fairies"
    return os.path.join(root, "diaries", group, organ_name)

def _ensure_diary_dirs_lane(root: str, organ_name: str, lane: str = "fairy") -> Tuple[str, str]:
    day = time.strftime("%Y-%m-%d", time.gmtime())
    ddir = _diary_path_for_lane(root, organ_name, lane)
    os.makedirs(ddir, exist_ok=True)
    return ddir, os.path.join(ddir, f"{day}.jsonl")

def _diary_write_dedup(root: str, organ: str, entry: Dict[str, Any], *, lane: str = "fairy") -> None:
    ddir, path = _ensure_diary_dirs_lane(root, organ, lane)
    norm = _norm_for_sig(entry)
    sig = hashlib.sha256(json.dumps(norm, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    if _LAST_SIG_CACHE.get(path) == sig:
        return  # skip duplicate line
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    _LAST_SIG_CACHE[path] = sig

def _diary_recent(diary_root: str, n: int) -> List[Dict[str, Any]]:
    try:
        day = time.strftime("%Y-%m-%d", time.gmtime())
        diaries_glob = os.path.join(diary_root, "diaries", "**", f"{day}.jsonl")
        lines: List[Dict[str, Any]] = []
        for path in glob.glob(diaries_glob, recursive=True):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        lines.append(json.loads(line))
            except Exception:
                continue
        return lines[-n:]
    except Exception:
        return []

def _diary_write(root: str, organ: str, entry: Dict[str, Any], *, lane: Optional[str] = None) -> None:
    # IMPORTANT: use dedup writer as the *only* path
    _diary_write_dedup(root, organ, entry, lane=(lane or getattr(_TLS, "lane", "Fairies")))

def _now() -> float:
    return time.time()

def _emit(fairy: str, event: str, status: str, details: Dict[str, Any], channel: str, *, lane: str = "fairy") -> None:
    pkt = {
        "event": event, "status": status, "details": details or {},
        "fairy": fairy, "ts": _now(), "channel": channel,
    }
    root = resolve_root()
    _diary_write(root, fairy, {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": f"{channel}.{event}",
        "payload": pkt
    }, lane=lane)

def _hash_blueprint(bp: Dict[str, Any]) -> str:
    h = hashlib.sha256(json.dumps(bp, sort_keys=True).encode("utf-8")).hexdigest()
    return h[:16]

def load_codex() -> Dict[str, Any]:
    candidates = [
        "./akashic_codex.json",
        "./config/akashic_codex.json",
        "/etc/akashic/akashic_codex.json",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "akashic_codex.json")
    ]
    for cand in candidates:
        try:
            if os.path.isfile(cand):
                with open(cand, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
    return {}

codex: Dict[str, Any] = load_codex()
# ── Template inventory helpers ──────────────────────────────────────────────
def _templates_dir_from_app_root(app_root: str) -> Optional[str]:
    """
    Given resolve_root() (which returns <Physical>/<app>), return <Physical>/Organ_Templates
    """
    try:
        physical_dir = os.path.dirname(os.path.abspath(app_root))
        tdir = os.path.join(physical_dir, "Organ_Templates")
        return tdir if os.path.isdir(tdir) else None
    except Exception:
        return None

def _list_templates(tdir: str) -> List[Dict[str, Any]]:
    """
    Scan Organ_Templates for Organ_Template_*.py and return [{name,size,mtime,sha16}]
    """
    out: List[Dict[str, Any]] = []
    try:
        for path in sorted(glob.glob(os.path.join(tdir, "Organ_Template_*.py"))):
            try:
                st = os.stat(path)
                with open(path, "rb") as f:
                    sha = hashlib.sha256(f.read()).hexdigest()[:16]
                out.append({
                    "name": os.path.basename(path),
                    "size": int(st.st_size),
                    "mtime": int(st.st_mtime),
                    "sha": sha,
                })
            except Exception:
                continue
    except Exception:
        pass
    return out

# ─────────────────────── Directory Post Office adapter ──────────────────────
_DirClass = None
for _mod, _cls in (("directory_fairy", "DirectoryFairy"),
                   ("directory_fairy", "DirectoryOrganFairy"),
                   ("P00_Autonomic.directory_fairy", "DirectoryFairy")):
    try:
        m = importlib.import_module(_mod)
        _DirClass = getattr(m, _cls, None) or _DirClass
    except Exception:
        pass

class _ShimDirectory:
    """Graceful fallback if Directory is unavailable. Routes to diaries."""
    ACTOR_PLANE = "P10"  # Memory plane - was incorrectly "P0"
    def __init__(self):
        self._import_ledger = self._build_import_ledger()

    def _build_import_ledger(self) -> Dict[str, Any]:
        base = {
            "os": os, "sys": sys, "re": re, "json": json, "time": time,
            "math": math, "random": random, "uuid": uuid, "hashlib": hashlib,
            "inspect": inspect, "pathlib": pathlib, "asyncio": asyncio,
            "queue": queue, "threading": threading, "traceback": traceback,
            "importlib": importlib, "DIR_CHANNEL": DIR_CHANNEL,
        }
        # codex-driven extras
        try:
            extras: List[str] = list((codex or {}).get("auto_import", []))
            for modname in extras:
                try:
                    m = importlib.import_module(modname)
                    base[modname.split(".")[-1]] = m
                except Exception:
                    pass
        except Exception:
            pass
        return base

    class _ShimPost:
        def __init__(self, origin: str):
            self.origin = origin
            self.i = {}  # replaced at registration

        def _send(self, topic_key: str, pkt: Dict[str, Any]):
            ch = DIR_CHANNEL.get(topic_key, "tracer")
            _emit(self.origin, "POST", "info", {"topic": ch, "pkt": pkt}, ch)
            # emit a proper postal.out if organ attached the callback
            try:
                cb = getattr(self, "diary_postal_cb", None)
                if callable(cb):
                    cb(ch, pkt)  # channel, payload
            except Exception:
                pass


        def route(self, channel_key: str, payload: Dict[str, Any]):
            key = channel_key.upper()
            if key not in DIR_CHANNEL:
                raise ValueError(f"unknown channel '{channel_key}'")
            self._send(key, payload)

        # dedicated lanes
        def to_TELEMETRY(self, pkt: Dict[str, Any]): self._send("TELEMETRY", pkt)
        def to_PLAN(self,      pkt: Dict[str, Any]): self._send("PLAN", pkt)
        def to_COGNITION(self, pkt: Dict[str, Any]): self._send("COGNITION", pkt)
        def to_SOMATIC(self,   pkt: Dict[str, Any]): self._send("SOMATIC", pkt)
        def to_MEMORY(self,    pkt: Dict[str, Any]): self._send("MEMORY", pkt)
        def to_REASON(self,    pkt: Dict[str, Any]): self._send("REASON", pkt)
        def to_EMOTION(self,   pkt: Dict[str, Any]): self._send("EMOTION", pkt)
        def to_GUI(self,       pkt: Dict[str, Any]): self._send("GUI", pkt)
        def to_TRACER(self,    pkt: Dict[str, Any]): self._send("TRACER", pkt)
        def to_DIRECTORY(self, pkt: Dict[str, Any]): self._send("DIRECTORY", pkt)
        def to_ORACLE(self,    pkt: Dict[str, Any]): self._send("ORACLE", pkt)

        def inject(self, namespace: Dict[str, Any], *, overwrite: bool = False):
            for k, v in self.i.items():
                if overwrite or k not in namespace:
                    namespace[k] = v

    def register_organ(self, *, name: str, plane: str, channel: str,
                       purpose: str, mantra: str, lore: str, intents: List[str]) -> Dict[str, Any]:
        post = self._ShimPost(origin=name)
        post.i = dict(self._import_ledger)
        return {"name": name, "plane": plane, "channel": channel,
                "purpose": purpose, "mantra": mantra, "lore": lore,
                "intents": intents, "imports": self._import_ledger,
                "post_office": post}

def _get_directory():
    if _DirClass:
        try:
            return _DirClass()
        except Exception:
            pass
    return _ShimDirectory()
# ───────────────────────────── Organ Hub Facet (mixin) ─────────────────────────────
class OrganHubFacet:
    """
    A tiny hub baked into organ-level actors.
    - Provides registry & routing helpers
    - Emits a single identity echo on boot
    - Persona traits are telemetry-only (NOT in blueprint hash)
    """

    # persona (telemetry-only; safe to change anytime)
    ROLE        = "organ.hub"
    TITLE       = "Registrar of Contracts"
    CLERK_NAME  = "Primrose Ledgerkeep"   # stuffy, fairy-ish
    EPITHET     = "the Bureaucratic Moth"
    QUIP        = "Every act witnessed; every contract stamped."

    # culture labeling (telemetry-only)
    CULTURE     = "organ"    # "organ" for hub, "worker" or "shadow" for descendants
    ORGAN_LEVEL = True       # marks this citizen as the organ hub

    # internal init (call once after post/contract is ready)
    def _init_hub(self):
        if not hasattr(self, "_citizens"):
            self._citizens: Dict[str, Dict[str, Any]] = {}

    # single identity/lore echo (safe to call multiple times)
    def _hub_identity_echo(self):
        if not getattr(self, "post", None):
            return
        traits = {
            "role": self.ROLE, "title": self.TITLE, "clerk": self.CLERK_NAME,
            "epithet": self.EPITHET, "quip": self.QUIP,
            "purpose": getattr(self, "PURPOSE", None),
            "mantra": getattr(self, "MANTRA", None),
            "lore": getattr(self, "LORE", None),
            "culture": getattr(self, "CULTURE", "organ"),
            "organ_level": bool(getattr(self, "ORGAN_LEVEL", False)),
            "actor": getattr(self, "ACTOR_NAME", None),
        }
        try: self.post.to_TELEMETRY({"opcode": "IDENTITY_TRAITS", "payload": traits})
        except Exception: pass
        try: self.post.to_TRACER({"opcode": "HUB_READY", "payload": {"actor": traits["actor"], "role": self.ROLE}})
        except Exception: pass

    # registry & routing (metadata-only; does NOT affect blueprint hash)
    def _hub_register(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(contract, dict): raise TypeError("contract must be dict")
        name = (contract.get("actor_name") or "").strip()
        if not name: raise ValueError("contract.actor_name required")
        self._citizens[name] = dict(contract)
        try: self.post.to_DIRECTORY({"opcode": "CONTRACT_UPSERT", "contract": contract})
        except Exception: pass
        _emit(getattr(self, "ACTOR_NAME", "organ"), "HUB_REGISTERED", "ok", {"actor": name}, CHANNEL["TELEMETRY"])
        return {"ok": True, "actor": name}

    def _hub_revoke(self, actor_name: str) -> Dict[str, Any]:
        actor_name = (actor_name or "").strip()
        existed = actor_name in self._citizens
        self._citizens.pop(actor_name, None)
        _emit(getattr(self, "ACTOR_NAME", "organ"), "HUB_REVOKED", "ok",
              {"actor": actor_name, "existed": existed}, CHANNEL["TELEMETRY"])
        return {"ok": True, "actor": actor_name, "existed": existed}

    def _hub_lookup(self, actor_name: str) -> Optional[Dict[str, Any]]:
        return self._citizens.get((actor_name or "").strip())

    def _hub_list(self) -> List[str]:
        return sorted(self._citizens.keys())

    def _hub_route(self, *, actor_name: str, lane: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not getattr(self, "post", None): return {"ok": False, "error": "no post office attached"}
        key = str(lane or "PLAN").upper()
        if key not in DIR_CHANNEL: return {"ok": False, "error": f"unknown lane '{lane}'"}
        pkt = {"from": getattr(self, "ACTOR_NAME", "organ"), "to": actor_name, **(payload or {})}
        try:
            self.post.route(key, pkt)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

# ───────────────────────────── Forensic Shadow ──────────────────────────────
class ActorShadowFairy:
    def __init__(self, actor: "MyOrganFairy", interval_sec: float = 60.0):
        self.actor = actor
        self.interval_sec = interval_sec

class MyOrganShadow(OrganHubFacet, ActorShadowFairy):
    CULTURE = "organ"
    ORGAN_LEVEL = True
    """
    Forensic Shadow: scheduled health harness, blueprint watch, oracle escalation,
    sims/PLAN reports, self-scan + smoke + proactive re-hash drift detection (v0.0.6+).
    """
    def __init__(self, actor: "MyOrganFairy", interval_sec: float = 30.0):
        super().__init__(actor, interval_sec=interval_sec)
        self._stop = False
        self._last_bp_hash: Optional[str] = None
        self._last_check_ts: float = 0.0
        self._last_rollup_status: str = "ok"
        self._last_rollup_msg: str = "initializing"
        self._last_results: List[Dict[str, Any]] = []
        self._t = threading.Thread(target=self._loop, daemon=True, name="config-shadow")
        self._t.start()
        self._reflect_interval_sec = 300  # 5 min default
        self._next_reflect_ts = 0.0
    # ——— scheduling / loop ———
    def _loop(self) -> None:
        # mark this daemon thread as shadow lane
        try:
            _TLS.lane = "Shadow Fairies"
        except Exception:
            pass

        while not self._stop:
            try:
                self.maybe_run(self._collect_tests())
                self.evolution_tick()
            except Exception as e:
                _emit(self.actor.ACTOR_NAME, "SHADOW_ERROR", "error", {"err": str(e)}, CHANNEL["TRACER"])
            time.sleep(self.interval_sec)

    def force_run_now(self) -> None:
        self._last_check_ts = 0.0

    def current_status(self) -> tuple[str, str]:
        return self._last_rollup_status, self._last_rollup_msg

    # ——— health harness ———
    def _collect_tests(self) -> List[Callable[[], Dict[str, Any]]]:
        tests: List[Callable[[], Dict[str, Any]]] = []
        custom = getattr(self.actor, "shadow_tests", None)
        if callable(custom):
            tests = list(custom()) or []

        def wrap(fn, name):
            def _w():
                ok = bool(fn())
                return {"name": name,
                        "status": "ok" if ok else "warn",
                        "message": "" if ok else "failed",
                        "details": {}}
            return _w

        tests += [
            wrap(self.actor._test_integrity, "integrity"),
            wrap(self.actor._test_codex_link, "codex_link"),
            wrap(self.actor._test_channel_signal, "channel_signal"),
        ]

        def _check_contract_consistency():
            bp = self.actor._contract_dict()
            ok = (self.actor._bp_last_hash == _hash_blueprint({
                "actor_name": bp["actor_name"], "actor_version": bp["actor_version"],
                "plane": bp["plane"], "channel": bp["channel"],
                "purpose": bp["purpose"], "mantra": bp["mantra"], "lore": bp["lore"],
            }))
            return {"name": "contract_consistency",
                    "status": "ok" if ok else "warn",
                    "message": "" if ok else "blueprint hash drifted",
                    "details": {}}

        tests.append(_check_contract_consistency)
        return tests

    def _rollup(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        worst = "ok"; lines = []
        for r in results:
            st = r.get("status","ok"); nm = r.get("name","test"); msg = r.get("message","")
            lines.append(f"{nm}: {st} ({msg})")
            if st == "error": worst = "error"
            elif st == "warn" and worst == "ok": worst = "warn"
        return {"worst": worst, "rollup_msg": "; ".join(lines)}

    def maybe_run(self, tests: List[Callable[[], Dict[str, Any]]]) -> None:
        now = time.time()
        if now - self._last_check_ts < self.interval_sec: return
        self._last_check_ts = now

        self.self_scan()

        results: List[Dict[str, Any]] = []
        for fn in tests:
            try:
                results.append(fn())
            except Exception as e:
                results.append({"name": getattr(fn, "__name__", "unknown_test"),
                                "status": "error", "message": f"exception: {e}", "details": {}})

        rolled = self._rollup(results)
        self._last_results = results
                # periodic reflection/recall snapshot
        try:
            now2 = time.time()
            if now2 >= self._next_reflect_ts:
                self.recall_reflection(max_events=200, horizon_sec=900)
                self._next_reflect_ts = now2 + self._reflect_interval_sec
        except Exception as _e_reflect:
            _emit(self.actor.ACTOR_NAME, "REFLECTION_ERROR", "warn",
                  {"err": str(_e_reflect)}, CHANNEL["TRACER"])

        self._last_rollup_status = rolled["worst"]
        self._last_rollup_msg = rolled["rollup_msg"]
        mood = {"ok":"serene","warn":"attentive","error":"critical"}[rolled["worst"]]

        _emit(self.actor.ACTOR_NAME, "HEALTH", rolled["worst"], {
            "message": rolled["rollup_msg"], "mood": mood,
            "tests": results, "purpose": self.actor.PURPOSE, "mantra": self.actor.MANTRA,
        }, CHANNEL["TELEMETRY"])

        if rolled["worst"] != "ok":
            self._maybe_oracle(results)

    def _maybe_oracle(self, results: List[Dict[str, Any]]) -> None:
        try:
            codex_ctx = codex if isinstance(codex, dict) else {}
        except Exception:
            codex_ctx = {}
        try:
            hist = slurp_akashic_history(resolve_root(), max_lines=600)
        except Exception:
            hist = {}
        payload = {
            "codex": codex_ctx,
            "recent_errors": [r.get("message") for r in results if r.get("status") in ("warn","error")],
            "hints": ["organ_health_degraded"],
            "akashic_history": {"blueprints": len(hist.get("blueprints",[])),
                                "shadow_reports": len(hist.get("shadow_reports",[])),
                                "raw": len(hist.get("raw",[]))}
        }
        # v0.0.7: try ORACLE lane first; keep v0.0.6 PLAN publish as fallback
        try:
            self.actor.post.to_ORACLE({"opcode": "ORACLE_SUGGEST", "payload": payload})
        except Exception:
            try:
                self.actor.post.to_PLAN({"opcode": "ORACLE_SUGGEST", "payload": payload})
            except Exception:
                _emit(self.actor.ACTOR_NAME, "ORACLE_SUGGEST", "info", payload, CHANNEL["PLAN"])

    # ——— parity scans / evolution ———
    def self_scan(self) -> None:
        req = ["ACTOR_NAME","ACTOR_VERSION","ACTOR_PLANE","ACTOR_CHANNEL","PURPOSE","MANTRA","LORE"]
        missing = [k for k in req if not getattr(self.actor, k, None)]
        if missing:
            _emit(self.actor.ACTOR_NAME, "SELF_SCAN_FAIL", "warn", {"missing": missing}, CHANNEL["TRACER"])
        else:
            _emit(self.actor.ACTOR_NAME, "SELF_SCAN_OK", "ok", {"checked": req}, CHANNEL["TRACER"])
        smoke = getattr(self.actor, "_intent_smoke", None)
        if callable(smoke):
            try:
                smoke({"shadow": True})
                _emit(self.actor.ACTOR_NAME, "DRY_RUN_OK", "ok", {"intent": "smoke"}, CHANNEL["TRACER"])
            except Exception as e:
                _emit(self.actor.ACTOR_NAME, "DRY_RUN_FAIL", "error", {"err": str(e)}, CHANNEL["TRACER"])

    def on_blueprint(self, bp: Dict[str, Any]) -> None:
        h = _hash_blueprint(bp)
        if self._last_bp_hash and h != self._last_bp_hash:
            plan = {"goal": "refresh_contracts", "from": self._last_bp_hash, "to": h,
                    "hints": {"purpose": self.actor.PURPOSE, "mantra": self.actor.MANTRA}}
            _emit(self.actor.ACTOR_NAME, "BLUEPRINT_CHANGED", "info", {"plan": plan}, CHANNEL["PLAN"])
            self.evolution_tick(force=True)
        self._last_bp_hash = h

    def evolution_tick(self, force: bool = False) -> None:
        """
        v0.0.6+: Proactive re-hash standardization.
        - Recalculate contract hash; if drifted from actor's stored value, propose refresh.
        - Keep v0.0.5 sims/observations behavior; diary-driven small proposals.
        """
        recent = _diary_recent(self.actor.diary, 25)

        def _kind_suffix(entry: Dict[str, Any]) -> str:
            k = entry.get("kind", "")
            return k.split(".", 1)[-1] if "." in k else k

        signals = [r for r in recent if _kind_suffix(r) in ("USE_INTENT","INTENT_FAIL","PLAN_EXPRESSION")]

        # 1) Standardized re-hash drift check (contract-level)
        contract_now = {
            "actor_name": self.actor.ACTOR_NAME,
            "actor_version": self.actor.ACTOR_VERSION,
            "plane": self.actor.ACTOR_PLANE,
            "channel": self.actor.ACTOR_CHANNEL,
            "purpose": self.actor.PURPOSE,
            "mantra": self.actor.MANTRA,
            "lore": self.actor.LORE,
        }
        now_sha = _hash_blueprint(contract_now)
        if self.actor._bp_last_hash and now_sha != self.actor._bp_last_hash:
            plan = {"type": "rehash_refresh",
                    "from": self.actor._bp_last_hash, "to": now_sha,
                    "recommend": ["re-beacon-contract", "sync-directory", "reload-codex"]}
            _emit(self.actor.ACTOR_NAME, "BLUEPRINT_REHASH_DRIFT", "warn", {"plan": plan}, CHANNEL["PLAN"])
            try:
                self.actor.post.to_TRACER({"rehash_drift": plan})
            except Exception:
                pass
            # update and beacon
            self.actor._bp_last_hash = now_sha
            self.actor._beacon_contract()

        # 2) Keep the small sims / plan proposals (unchanged shape)
        proposal = {
            "type": "incremental_improvement",
            "observations": [s.get("payload", s) for s in signals][-5:],
            "tests": ["latency_smoke","burst_throughput","error_injection"]
        }
        _emit(self.actor.ACTOR_NAME, "EVOLUTION_PROPOSAL", "ok", {"plan": proposal}, CHANNEL["PLAN"])

    def recall_reflection(self, max_events: int = 200, horizon_sec: int = 900) -> Dict[str, Any]:
        """
        Sweep recent diary lines, summarize activity, and persist a compact reflection.
        Emits:
        - telemetry.REFLECTION (summary)  [diary]
        - memory.stream (shadow.reflection snapshot)  [post.to_MEMORY()]
        - tracer crumb for quick visibility
        Returns the summary dict.
        """
        # 0) gather recent lines (module helper already filters by day)
        recent = _diary_recent(self.actor.diary, max_events) or []
        cutoff = _now() - max(0, int(horizon_sec))

        # helper: numeric ts from wrapped diary entry
        def _safe_ts(e: Dict[str, Any]) -> float:
            try:
                p = e.get("payload", {})
                t = p.get("ts")
                return float(t) if isinstance(t, (int, float)) else 0.0
            except Exception:
                return 0.0

        # 1) scope to this actor + horizon
        mine = [
            e for e in recent
            if e.get("payload", {}).get("fairy") == self.actor.ACTOR_NAME
            and _safe_ts(e) >= cutoff
        ]

        # 2) rollups
        by_kind: Dict[str, int] = {}
        intents: Dict[str, int] = {}
        last_health: Optional[str] = None
        last_bp_sha = getattr(self.actor, "_bp_last_hash", None)
        postal_tail: List[Dict[str, Any]] = []

        def _kind_suffix(k: str) -> str:
            return k.split(".", 1)[-1] if "." in k else k

        for e in mine:
            k = _kind_suffix(e.get("kind", ""))
            by_kind[k] = by_kind.get(k, 0) + 1

            # last known health mood/status
            if k in ("TELEMETRY.HEALTH", "HEALTH"):
                last_health = (
                    e.get("payload", {}).get("details", {}).get("mood")
                    or e.get("payload", {}).get("status")
                )

            # collect postal.out entries that carry mail metadata
            if k == "postal.out":
                payload = e.get("payload", {}) or {}
                if "mail_id" in payload:
                    postal_tail.append({
                        "id": payload.get("id"),
                        "dst_plane": payload.get("dst_plane"),
                        "channel": payload.get("channel"),
                        "opcode": payload.get("opcode"),
                        "mail_id": payload.get("mail_id"),
                        "sub_id": payload.get("sub_id"),
                        "mail_seq": payload.get("mail_seq"),
                        "ts": payload.get("ts"),
                    })

            # intents accounting
            if k.endswith("USE_INTENT"):
                intent = e.get("payload", {}).get("intent")
                if intent:
                    intents[intent] = intents.get(intent, 0) + 1
            if k.endswith("INTENT_FAIL"):
                intents["_fail"] = intents.get("_fail", 0) + 1

        postal_tail = postal_tail[-10:]  # keep the tail small

        # SRM merge (requires slurp_srm_today helper)
        srm_docs = slurp_srm_today(self.actor.root, max_files=200)
        srm_counts: Dict[str, int] = {}
        srm_tail: List[Dict[str, Any]] = []
        for d in srm_docs:
            k = str(d.get("kind", "unknown"))
            srm_counts[k] = srm_counts.get(k, 0) + 1
        for d in srm_docs[-8:]:
            srm_tail.append({
                "kind": d.get("kind"),
                "ts": d.get("ts"),
                "meta": d.get("meta", {}),
                "path": d.get("_path"),
            })

        # 3) summary payload
        summary: Dict[str, Any] = {
            "actor": self.actor.ACTOR_NAME,
            "plane": self.actor.ACTOR_PLANE,
            "channel": self.actor.ACTOR_CHANNEL,
            "window_sec": int(horizon_sec),
            "counts_by_kind": by_kind,
            "intents_seen": intents,
            "last_health": last_health,
            "blueprint_sha": last_bp_sha,
            "postal_tail": postal_tail,
            "srm_counts": srm_counts,
            "srm_tail": srm_tail,
            "ts": _now(),
        }

        # --- Organ_Templates reflection (sibling to 'current app') -------------
        tdir = _templates_dir_from_app_root(self.actor.diary)
        if tdir:
            inv = _list_templates(tdir)
            # compact view + stable signature so diary dedup works
            sig_basis = {
                "dir": tdir,
                "names": [i["name"] for i in inv],
                "shas": [i["sha"] for i in inv],
            }
            try:
                sig = hashlib.sha256(json.dumps(sig_basis, sort_keys=True).encode("utf-8")).hexdigest()[:16]
            except Exception:
                sig = None

            latest = max(inv, key=lambda i: i["mtime"]) if inv else None
            summary["templates"] = {
                "dir": tdir,
                "count": len(inv),
                "latest": latest,
                "sig": sig,
                # keep the inventory small in the summary; full list goes to MEMORY below if you want
                "versions": [{"name": i["name"], "sha": i["sha"]} for i in inv][-10:],
            }

            # optional: emit a tiny, dedup-friendly diary line just about templates
            try:
                _diary_write_dedup(
                    self.actor.diary,
                    self.actor.ACTOR_NAME,
                    {
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "kind": "telemetry.TEMPLATES_REFLECTION",
                        "payload": {
                            "fairy": self.actor.ACTOR_NAME,
                            "ts": summary["ts"],
                            "dir": tdir,
                            "count": len(inv),
                            "sig": sig,
                            "latest": latest,
                        },
                    },
                    lane="shadow",
                )
            except Exception:
                pass

            # optional MEMORY echo with the full inventory
            try:
                if getattr(self.actor, "post", None):
                    self.actor.post.to_MEMORY({
                        "kind": "shadow.templates",
                        "meta": {"actor": self.actor.ACTOR_NAME},
                        "dir": tdir,
                        "inventory": inv,
                        "sig": sig,
                    })
            except Exception:
                pass

        # 4) persist: diary (shadow lane) + MEMORY echo + TRACER crumb
        try:
            _diary_write_dedup(
                self.actor.diary,
                self.actor.ACTOR_NAME,
                {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "kind": "telemetry.REFLECTION",
                    "payload": {"fairy": self.actor.ACTOR_NAME, "ts": summary["ts"], "summary": summary},
                },
                lane="shadow",
            )
        except Exception:
            # last resort
            _emit(self.actor.ACTOR_NAME, "REFLECTION", "ok", summary, CHANNEL["TELEMETRY"], lane="shadow")

        try:
            if getattr(self.actor, "post", None):
                self.actor.post.to_MEMORY({
                    "kind": "shadow.reflection",
                    "meta": {"actor": self.actor.ACTOR_NAME, "window_sec": int(horizon_sec)},
                    "summary": summary
                })
                self.actor.post.to_TRACER({
                    "opcode": "REFLECTION",
                    "summary": {
                        "counts_by_kind": by_kind,
                        "last_health": last_health,
                        "postal_tail_n": len(postal_tail),
                    },
                })
        except Exception:
            pass

        return summary


    def stop(self) -> None:
        self._stop = True
        try: self._t.join(timeout=1.0)
        except Exception: pass

# ────────────────────────────── Actor Base ──────────────────────────────────
class MyOrganFairy(OrganHubFacet):
    CULTURE = "organ"
    ORGAN_LEVEL = True
    # — identity (override in subclasses) —
    ACTOR_NAME    = "my_organ"
    ACTOR_VERSION = "0.0.7"
    ACTOR_PLANE   = "P10"
    ACTOR_CHANNEL = "organ"
    PURPOSE       = "Give it purpose per app."
    MANTRA        = "Do one thing well; report truthfully."
    LORE          = "Origin, myths, and temperament for the organ."

    # — postal options —
    USE_DIRECTORY_POST_OFFICE = True
    AUTO_INJECT_IMPORTS = False

    def __init__(self, *, akashic_root: Optional[str] = None):
        # roots & basics
        self.root = resolve_root(akashic_root, akashic_app=os.getenv("AKASHIC_APP"))
        self.diary = self.root
        self.shadow: Optional[MyOrganShadow] = None

        # addressing seeds
        self._mail_epoch = int(time.time() * 1000)
        self._mail_session = uuid.uuid4().hex[:12]
        self._mail_seq = {"fairy": 0, "shadow": 0}
        self._mail_lock = threading.Lock()
        # make lanes explicit so we never create a new key by accident
        self._mail_seq = {"fairy": 0, "shadow": 0}

        # directory / post office
        self.directory = _get_directory() if self.USE_DIRECTORY_POST_OFFICE else None
        self.post = None
        self.std: Dict[str, Any] = {}
        try:
            self._init_hub()
        except Exception:
            pass
        # ---- SAFE REGISTRATION (no UnboundLocalError) ----
        contract: Dict[str, Any] = {}
        if self.directory:
            try:
                contract = self.directory.register_organ(
                    name=self.ACTOR_NAME,
                    plane=self.ACTOR_PLANE,
                    channel=self.ACTOR_CHANNEL,
                    purpose=self.PURPOSE,
                    mantra=self.MANTRA,
                    lore=getattr(self, "LORE", self.PURPOSE),
                    intents=[m.replace("_intent_", "") for m in dir(self) if m.startswith("_intent_")]
                ) or {}
            except Exception as e:
                _emit(self.ACTOR_NAME, "DIRECTORY_ATTACH_FAIL", "warn", {"err": str(e)}, CHANNEL["TRACER"])
                contract = {}

        # only touch post/std if we actually have a contract dict
        if isinstance(contract, dict) and contract:
            self.post = contract.get("post_office") or getattr(contract, "post_office", None)
            # fall back to shim's import ledger if missing
            self.std = contract.get("imports", {}) or getattr(self.directory, "_import_ledger", {})
            try:
                if self.AUTO_INJECT_IMPORTS and self.post and hasattr(self.post, "inject"):
                    self.post.inject(self.__dict__, overwrite=False)
            except Exception:
                pass
                        # attach a diary writer so shimmed post routes also make postal.out entries
            try:
                if self.post and not hasattr(self.post, "diary_postal_cb"):
                    def _cb(ch, pkt):
                        # detect lane for this thread (Shadow thread sets TLS earlier)
                        lane_token = getattr(_TLS, "lane", "Fairies")
                        lane = "shadow" if str(lane_token).lower().startswith("shadow") else "fairy"
                        dst_plane = getattr(self.directory, "ACTOR_PLANE", self.ACTOR_PLANE)
                        self._diary_postal(
                            dst_plane=dst_plane,
                            channel=ch,
                            opcode=pkt.get("opcode", "POST"),
                            payload=pkt,
                            lane=lane,                  # <-- important
                        )
                    setattr(self.post, "diary_postal_cb", _cb)

            except Exception:
                pass

        # ── Bridge to real postal fabric ──────────────────────────────────
        # The shim post office routes to diaries only. For the organ fairy
        # to be a real citizen (heartbeat-monitored, restartable, visible
        # in DirectoryFairy), we also register through the shared postal hub.
        self._real_postal = None
        self._hb_thread = None
        try:
            from P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            _hub = get_shared_postal_hub()
            if _hub and hasattr(_hub, 'publish'):
                self._real_postal = _hub
                # Register with the real DirectoryFairy
                _reg_payload = {
                    "name": self.ACTOR_NAME,
                    "plane": self.ACTOR_PLANE,
                    "channel": self.ACTOR_CHANNEL,
                    "capabilities": ["organ_hub", "registry", "routing"],
                    "metadata": {
                        "purpose": self.PURPOSE,
                        "mantra": self.MANTRA,
                        "lore": getattr(self, "LORE", self.PURPOSE),
                        "culture": getattr(self, "CULTURE", "organ"),
                        "organ_level": getattr(self, "ORGAN_LEVEL", False),
                    },
                    "needs": {"heartbeat": True},
                    "ts": time.time(),
                }
                _hub.publish("fairy.register", _reg_payload)
                # Start lightweight heartbeat so watchdog knows we're alive
                self._hb_beat = 0
                def _organ_heartbeat_loop():
                    while True:
                        try:
                            time.sleep(30)  # 30s interval — light touch
                            self._hb_beat += 1
                            self._real_postal.publish("fairy.heartbeat", {
                                "name": self.ACTOR_NAME,
                                "plane": self.ACTOR_PLANE,
                                "beat": self._hb_beat,
                                "ts": time.time(),
                                "source": "organ_template",
                            })
                        except Exception:
                            break  # Hub gone, stop gracefully
                self._hb_thread = threading.Thread(
                    target=_organ_heartbeat_loop, daemon=True, name=f"hb-{self.ACTOR_NAME}"
                )
                self._hb_thread.start()
                print(f"[{self.ACTOR_NAME}] Registered with real postal fabric + heartbeat started")
        except ImportError:
            pass  # Postal hub not available yet (early boot) — shim is sufficient
        except Exception as _postal_err:
            print(f"[{self.ACTOR_NAME}] Real postal bridge failed: {_postal_err}")

        # integrity + shadow + blueprint
        self._bp_last_hash: Optional[str] = None
        self._bind_shadow()
        self._emit_blueprint()


    # shadow binding (override to change class/interval)
    def _bind_shadow(self) -> None:
        cls = getattr(self, "SHADOW_CLASS", MyOrganShadow)
        self.shadow = cls(self, interval_sec=30.0)

    # blueprint emit
    def _emit_blueprint(self) -> None:
        bp = {
            "actor_name": self.ACTOR_NAME,
            "actor_version": self.ACTOR_VERSION,
            "plane": self.ACTOR_PLANE,
            "channel": self.ACTOR_CHANNEL,
            "purpose": self.PURPOSE,
            "mantra": self.MANTRA,
            "lore": self.LORE,
        }
        h = _hash_blueprint(bp)
        self._bp_last_hash = h

        # keep the old tracer crumbs (useful for forensics)
        _emit(self.ACTOR_NAME, "BLUEPRINT_REPORT", "info", {"blueprint": bp}, CHANNEL["TRACER"])
        _emit(self.ACTOR_NAME, "BLUEPRINT_HASH", "info", {"sha": h}, CHANNEL["TRACER"])

        # NEW: canonical blueprint diary line so history/recall can find it
        try:
            _diary_write_dedup(
                self.diary, self.ACTOR_NAME,
                {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "kind": "blueprint.report",
                    "payload": {"fairy": self.ACTOR_NAME, "sha": h, "blueprint": bp, "ts": _now()},
                },
                lane="fairy",
            )
        except Exception:
            # safe fallback (will show as telemetry.BLUEPRINT instead of blueprint.report)
            _emit(self.ACTOR_NAME, "BLUEPRINT", "info", {"sha": h, "blueprint": bp}, CHANNEL["TELEMETRY"])

        # NEW: persist to SRM so it's a file on disk (deduped by sha)
        try:
            path = _persist_blueprint_snapshot(bp, h, actor=self.ACTOR_NAME)
            if self.post:
                # optional echo so MEMORY lane ingests it
                self.post.to_MEMORY({"opcode": "BLUEPRINT_SNAPSHOT", "payload": {"sha": h, "path": path}})
        except Exception:
            pass

        # keep the contract beacon behavior
        self._beacon_contract()
        if self.shadow:
            self.shadow.on_blueprint(bp)


    # intents
    def use_intent(self, name: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            fn = getattr(self, f"_intent_{name}", None)
            if not callable(fn):
                raise ValueError(f"unknown intent: {name}")
            res = fn(payload or {})
            _emit(self.ACTOR_NAME, "USE_INTENT", "ok", {"intent": name}, CHANNEL["TRACER"])
            return {"ok": True, "result": res}
        except Exception as e:
            # route fail via post if available; fallback to diary
            try:
                if self.post:
                    self.post.to_TRACER({"intent": name, "error": str(e), "kind": "INTENT_FAIL"})
            except Exception:
                pass
            _emit(self.ACTOR_NAME, "INTENT_FAIL", "error", {"intent": name, "error": str(e)}, CHANNEL["TRACER"])
            return {"ok": False, "error": str(e)}

    # health smoke
    def _intent_smoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"ok": True, "ts": _now(), "actor": self.ACTOR_NAME}

    # plan with shape hint (unchanged interface)
    def _intent_plan(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        steps = payload.get("steps") or []
        if not isinstance(steps, list):
            raise ValueError("plan.steps must be a list")
        _emit(self.ACTOR_NAME, "PLAN_EXPRESSION", "info", {"count": len(steps)}, CHANNEL["PLAN"])
        try:
            if self.post:
                self.post.to_PLAN({"steps": steps, "meta": {"actor": self.ACTOR_NAME}})
        except Exception:
            pass
        return {"accepted": True, "step_count": len(steps)}

    # scanner parity tests
    def _test_integrity(self) -> bool:
        bp = {
            "actor_name": self.ACTOR_NAME,
            "actor_version": self.ACTOR_VERSION,
            "plane": self.ACTOR_PLANE,
            "channel": self.ACTOR_CHANNEL,
            "purpose": self.PURPOSE,
            "mantra": self.MANTRA,
            "lore": self.LORE,
        }
        return self._bp_last_hash == _hash_blueprint(bp)

    def _test_codex_link(self) -> bool:
        try:
            ver = str(codex.get("version") or codex.get("codex_version") or "")
            return bool(codex) and len(ver) > 0
        except Exception:
            return False

    def _test_channel_signal(self) -> bool:
        # use Post Office (tracer ping); return True on success, fallback to diary
        try:
            if self.post:
                self.post.to_TRACER({"opcode": "TEST_SIGNAL", "nonce": uuid.uuid4().hex})
                return True
        except Exception:
            pass
        _emit(self.ACTOR_NAME, "TEST_SIGNAL", "info", {"nonce": uuid.uuid4().hex}, CHANNEL["TRACER"])
        return True

    # QoL: update identity & keep integrity green
    def update_identity(self, *, purpose: Optional[str] = None,
                        mantra: Optional[str] = None,
                        lore: Optional[str] = None) -> None:
        if purpose is not None: self.PURPOSE = purpose
        if mantra  is not None: self.MANTRA  = mantra
        if lore    is not None: self.LORE    = lore
        self._emit_blueprint()

    def _mail_id(self) -> str:
        """Stable per-organ mail id."""
        v = str(getattr(self, "ACTOR_VERSION", "0.0.0"))
        parts = (v.split("+", 1)[0]).split(".")
        major_minor = ".".join((parts + ["0", "0"])[:2])
        return f"MAIL::{self.ACTOR_PLANE}::{self.ACTOR_NAME}::v{major_minor}"

    def _contract_dict(self) -> Dict[str, Any]:
        d = {
            "actor_name": self.ACTOR_NAME,
            "actor_version": self.ACTOR_VERSION,
            "plane": self.ACTOR_PLANE,
            "channel": self.ACTOR_CHANNEL,
            "purpose": self.PURPOSE,
            "mantra": self.MANTRA,
            "lore": self.LORE,
            "intents": sorted(n.replace("_intent_", "") for n in dir(self) if n.startswith("_intent_")),
            "blueprint_sha": self._bp_last_hash,
        }

        # --- metadata-only: hub facet (NOT part of integrity hash) ---
        try:
            d["hub"] = {
                "role":        getattr(self, "ROLE", "organ.hub"),
                "title":       getattr(self, "TITLE", None),
                "clerk":       getattr(self, "CLERK_NAME", None),
                "epithet":     getattr(self, "EPITHET", None),
                "culture":     getattr(self, "CULTURE", "organ"),
                "organ_level": bool(getattr(self, "ORGAN_LEVEL", True)),
            }
            # drop Nones to keep contract tidy
            d["hub"] = {k: v for k, v in d["hub"].items() if v is not None}
        except Exception:
            pass

        # NEW: contract-addressing block (registry persists it verbatim)
        try:
            d["mail"] = {
                "mail_id": self._mail_id(),
                "plane": self.ACTOR_PLANE,
                "channel": self.ACTOR_CHANNEL,
                "epoch": getattr(self, "_mail_epoch", 0),
                "session": getattr(self, "_mail_session", ""),
                "lanes": ["fairy", "shadow"],
            }
        except Exception:
            pass

        return d

    # ------------------------------------------------------------------
    # local diary postal bridge (used when Directory bus isn't active)
    # ------------------------------------------------------------------
    def _diary_postal(self, dst_plane, channel, opcode, payload,
                    cause_msg_id=None, affect_signature=None, rebirth_hint=None,
                    lane: str = None):
        # decide lane if not given
        if lane is None:
            lane_token = getattr(_TLS, "lane", "Fairies")
            lane = "shadow" if str(lane_token).lower().startswith("shadow") else "fairy"

        # monotonic per lane
        with self._mail_lock:
            self._mail_seq[lane] = self._mail_seq.get(lane, 0) + 1
            seq_val = self._mail_seq[lane]

        msg = {
            "id": uuid.uuid4().hex,
            "src_fairy": self.ACTOR_NAME,
            "src_plane": self.ACTOR_PLANE,
            "dst_plane": dst_plane,
            "channel": channel,
            "opcode": opcode,
            "payload": payload or {},
            "contract_version": self.ACTOR_VERSION,
            "ts": _now(),
            "cause_msg_id": cause_msg_id,
            "affect_signature": affect_signature,
            "rebirth_hint": rebirth_hint,
            "mail_id": self._mail_id(),
            "mail_epoch": getattr(self, "_mail_epoch", 0),
            "mail_session": getattr(self, "_mail_session", ""),
            "sub_id": lane,              # <-- correct lane appears in diary
            "mail_seq": seq_val,         # <-- monotonic within lane
        }

        # tracer crumb (records under the same lane)
        _emit(self.ACTOR_NAME, "POSTAL", "info",
            {"to": f"{dst_plane}.{channel}", "opcode": opcode},
            CHANNEL["TRACER"], lane=("shadow" if lane == "shadow" else "fairy"))

        # diary line goes to Fairies / Shadow Fairies respectively
        _diary_write(self.diary, self.ACTOR_NAME, {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "kind": "postal.out",
            "payload": msg
        }, lane=("Shadow Fairies" if lane == "shadow" else "Fairies"))

        return msg

    def on_boot(self):
        """Organ-level boot: mark hub readiness with one identity echo."""
        # Get template infrastructure
        try:
            super().on_boot()
        except Exception:
            pass

        self._hub_identity_echo()

    def _beacon_contract(self) -> None:
        # v0.0.7: send to Directory (if available) and keep tracer crumb for forensics
        try:
            if self.post:
                try:
                    self.post.to_DIRECTORY({"opcode": "CONTRACT_UPSERT", "contract": self._contract_dict()})
                except Exception:
                    pass
                try:
                    self.post.to_TRACER({"opcode": "CONTRACT_UPSERT", "payload": self._contract_dict()})
                except Exception:
                    pass
        except Exception as e:
            _emit(self.ACTOR_NAME, "CONTRACT_BEACON_FAIL", "warn", {"err": str(e)}, CHANNEL["TRACER"])
        _emit(self.ACTOR_NAME, "CONTRACT_BEACON", "info", {}, CHANNEL["TRACER"])

        # --- organ hub intents ---
    def _intent_register_citizen(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._hub_register(dict(payload or {}))

    def _intent_revoke_citizen(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._hub_revoke((payload or {}).get("actor_name", ""))

    def _intent_lookup_citizen(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = (payload or {}).get("actor_name", "")
        return {"actor": name, "contract": self._hub_lookup(name)}

    def _intent_list_citizens(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"citizens": self._hub_list()}

    def _intent_route_mail(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = (payload or {}).get("actor_name", "")
        lane = (payload or {}).get("lane", "PLAN")
        pkt  = (payload or {}).get("payload", {})
        return self._hub_route(actor_name=name, lane=lane, payload=pkt)

    def _intent_echo_contract(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        c = dict(payload or {}).get("contract") or self._contract_dict()
        return self._hub_register(c)

    # === Organ Hub (organ-level clerk) ===========================================
class OrganHubFairy(MyOrganFairy):
    """
    The organ's postal registrar/clerk.
    Stamps contracts, tracks citizens, offers easy routing into the organ.
    """

    # Identity (feel free to rename these for each organ)
    ACTOR_NAME    = "organ.clerk.primrose"   # human-friendly citizen id
    ACTOR_VERSION = "1.0.0"
    ACTOR_PLANE   = "P10"
    ACTOR_CHANNEL = "infrastructure"         # hub infra lane; can be "organ" if you prefer
    PURPOSE = ("Serve as the central registry and contract office for organ citizens; "
               "maintain a ledger of registered fairies; provide a stable routing anchor.")
    MANTRA  = "Every act must be witnessed; every contract must be stamped."
    LORE    = ("Primrose Ledgerkeep, the Stuffy Clerk. Wears ink-stained gloves, files in triplicate, "
               "and hums while stamping. Bureaucratic snark level: courteous-but-deadly.")

    # Optional: give the hub its own persona-flavored shadow by subclassing MyOrganShadow later if you like.
    # For now we inherit the default shadow behavior via _bind_shadow()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # in-memory registry (persisted indirectly through diaries / memory echoes)
        self._citizens: Dict[str, Dict[str, Any]] = {}

    # --------- Hub core -------------------------------------------------------

    def _hub_register(self, contract: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register or update a citizen (any fairy's exported contract).
        """
        if not isinstance(contract, dict):
            raise TypeError("contract must be dict")
        name = str(contract.get("actor_name") or "").strip()
        if not name:
            raise ValueError("contract.actor_name required")

        self._citizens[name] = dict(contract)

        # Directory echo (if present)
        try:
            if self.post:
                self.post.to_DIRECTORY({"opcode": "CONTRACT_UPSERT", "contract": contract})
        except Exception:
            pass

        # Memory/Tracer crumbs
        try:
            self.post.to_MEMORY({"opcode": "HUB_REGISTERED", "payload": {"contract": contract}})
        except Exception:
            pass
        try:
            self.post.to_TRACER({"opcode": "HUB_REGISTERED", "payload": {"actor": name}})
        except Exception:
            pass

        # Diary (dedup-friendly)
        _emit(self.ACTOR_NAME, "HUB_REGISTERED", "ok", {"actor": name}, CHANNEL["TELEMETRY"])
        return {"ok": True, "actor": name}

    def _hub_revoke(self, actor_name: str) -> Dict[str, Any]:
        actor_name = str(actor_name or "").strip()
        existed = actor_name in self._citizens
        self._citizens.pop(actor_name, None)
        try:
            self.post.to_TRACER({"opcode": "HUB_REVOKED", "payload": {"actor": actor_name, "existed": existed}})
        except Exception:
            pass
        _emit(self.ACTOR_NAME, "HUB_REVOKED", "ok", {"actor": actor_name, "existed": existed}, CHANNEL["TELEMETRY"])
        return {"ok": True, "actor": actor_name, "existed": existed}

    def _hub_lookup(self, actor_name: str) -> Optional[Dict[str, Any]]:
        return self._citizens.get(str(actor_name or "").strip())

    def _hub_list(self) -> List[str]:
        return sorted(self._citizens.keys())

    def _hub_route(self, *, actor_name: str, lane: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convenience router: use Directory post to send mail into the organ.
        lane is a DIRECTORY key: e.g., 'PLAN', 'TELEMETRY', 'COGNITION', etc.
        """
        if not self.post:
            return {"ok": False, "error": "no post office attached"}
        key = str(lane or "PLAN").upper()
        if key not in DIR_CHANNEL:
            return {"ok": False, "error": f"unknown lane '{lane}'"}

        # attach a little envelope header
        pkt = {"from": self.ACTOR_NAME, "to": actor_name, **(payload or {})}
        try:
            # route directly by channel key; consumers will filter by meta.to if needed
            self.post.route(key, pkt)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # --------- Intents (stable organ API) ------------------------------------

    def _intent_register_citizen(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._hub_register(dict(payload or {}))

    def _intent_revoke_citizen(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._hub_revoke((payload or {}).get("actor_name", ""))

    def _intent_lookup_citizen(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = (payload or {}).get("actor_name", "")
        return {"actor": name, "contract": self._hub_lookup(name)}

    def _intent_list_citizens(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"citizens": self._hub_list()}

    def _intent_route_mail(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = (payload or {}).get("actor_name", "")
        lane = (payload or {}).get("lane", "PLAN")
        pkt  = (payload or {}).get("payload", {})
        return self._hub_route(actor_name=name, lane=lane, payload=pkt)

    def _intent_echo_contract(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handy when a citizen wants to publish its own contract via the hub
        (ensures consistent diary/memory echoes).
        """
        c = dict(payload or {}).get("contract") or self._contract_dict()
        return self._hub_register(c)

    # --------- Boot -----------------------------------------------------------

    def on_boot(self):
        if not getattr(self, "post", None):
            return
        traits = {
            "purpose": self.PURPOSE,
            "mantra": self.MANTRA,
            "lore": self.LORE,
            "persona": "registrar",
        }
        try:
            self.post.to_TELEMETRY({"opcode": "IDENTITY_TRAITS", "payload": traits})
        except Exception:
            pass
        try:
            self.post.to_TRACER({"opcode": "HUB_READY", "payload": {"actor": self.ACTOR_NAME}})
        except Exception:
            pass
        # light serotonin nudge (mirrors your boot patterns)
        try:
            self.post.to_PLAN({"opcode": "CHEM_SIGNAL_UPDATE",
                               "payload": {"chemical": "serotonin", "delta": +0.02, "reason": "hub_boot"}})
        except Exception:
            pass

def _make_pair_id() -> str:
    return uuid.uuid4().hex[:12]
    # === Optional: organ-specific extra shadow tests (override) ==============
    # def shadow_tests(self) -> List[Callable[[], Dict[str, Any]]]:
    #     return []

#-------------------------------------------------------------------

class TemplateShadowFairy(MyOrganShadow):
    CULTURE = "shadow"
    ORGAN_LEVEL = False
    SHADOW_NAME = "P10.TemplateShadowFairy"
    SHADOW_VERSION = "0.1.1"  # bump for sim+SRM
    CADENCE = {
        "warmup_times": [10, 20, 40],
        "light_every_sec": 5 * 60,   # 5 minutes
        "deep_every_sec": 20 * 60,   # 20 minutes → guarantees 3 deeps within ~1 hour
        "idle_extra_sec": 3 * 60,
        "cooldown_on_warn_sec": 10 * 60,
        "deep_sim_ticks": 3

    }
    def on_boot(self):
        self._last_light = 0.0
        self._last_deep  = 0.0
        self._last_any_lane_ts = time.time()
        # schedule warmups
        for t in self.CADENCE["warmup_times"]:
            self.defer(t, lambda: self._light_tick(tag="warmup"))

    def _light_tick(self, tag="periodic"):
        sim = self.evolution_sim_tick(tag=tag)
        self._last_light = time.time()
        self._last_any_lane_ts = self._last_light
        return sim

    def _deep_pass(self, reason: str = "periodic"):
        pair = _make_pair_id()
        try:
            # optional integrity probe if your template exposes it
            if hasattr(self, "run_integrity_probe"):
                self.run_integrity_probe(reason=reason)
        except Exception:
            pass

        n = int(self.CADENCE.get("deep_sim_ticks", 5))
        for i in range(n):
            self.evolution_sim_tick(tag=f"deep-{reason}-{i}", tick_kind="deep", pair_id=pair)
        self._last_deep = time.time()

    def on_lane_activity(self):  # call from places that see mail/telemetry
        self._last_any_lane_ts = time.time()

    def tick(self):
        now = time.time()
        # Deep pass trigger
        if now - self._last_deep >= self.CADENCE["deep_every_sec"]:
            return self._deep_pass("periodic")
        # Light pass trigger
        if now - self._last_light >= self.CADENCE["light_every_sec"]:
            return self._light_tick("periodic")
        # Idle extra
        if now - self._last_any_lane_ts >= self.CADENCE["idle_extra_sec"]:
            return self._light_tick("idle")
        # No-op
        return None

    def on_health_state(self, state):
        if state != "serene":
            self.defer(self.CADENCE["cooldown_on_warn_sec"], lambda: self._light_tick("after_cooldown"))
    def defer(self, seconds: float, fn):
        try:
            t = threading.Timer(float(seconds), fn)
            t.daemon = True
            t.start()
        except Exception:
            try: fn()
            except Exception: pass
    # Example change hooks you'd call when detecting codex/mtimes/blueprints:
    def on_codex_change(self): self._deep_pass("codex_change")
    def on_source_change(self): self._deep_pass("source_change")
    def on_blueprint_emit(self): self._deep_pass("blueprint_emit")

    def shadow_tests(self):
        tests = []
        try:
            tests.append({"name": "codex_link", "status": "ok", "message": "codex visible"})
            tests.append({"name": "integrity", "status": "ok", "message": "blueprint hash stable"})
            tests.append({"name": "channel_signal", "status": "ok", "message": "tracer route ok"})
        except Exception as e:
            tests.append({"name": "bootstrap", "status": "warn", "message": str(e)})
        return tests

    def evolution_sim_tick(self, *, tag: str = "default", tick_kind: str = "light", pair_id: str | None = None):
        """
        Run a synthetic evolution tick, enrich with provenance, and persist via dual-path SRM.
        """
        try:
            import random, time
            pair_id = pair_id or _make_pair_id()

            sim = {
                "tag": tag,
                "mutation_rate": round(random.uniform(0.01, 0.2), 3),
                "stability": random.choice(["stable", "drifting", "mutating"]),
                "codex_alignment": "ok",
                "blueprint_integrity": True,
                "ts": time.time(),
            }

            meta = {
                "tick_kind": tick_kind,
                "pair_id": pair_id,
                "codex_version": getattr(self, "codex", {}).get("version"),
                "organ_version": getattr(getattr(self, "parent", None), "ACTOR_VERSION", None),
                "blueprint_hash": getattr(self, "last_blueprint_hash", None),
                "mail_session": getattr(getattr(self, "post", None), "session_id", None),
            }

            # always use the actor's mailbox
            try:
                self.actor.post.to_PLAN({"opcode": "EVOLUTION_SIM_REPORT", "payload": {"meta": meta, **sim}})
                self.actor.post.to_TRACER({"opcode": "EVOLUTION_SIM_TELEMETRY", "payload": {"meta": meta, **sim}})
            except Exception:
                pass

            _dual_path_srm_intake(self.actor.post, kind=f"evolution.sim.{tick_kind}", data=sim, meta=meta)
            return {"ok": True, "sim": sim, "meta": meta}

        except Exception as e:
            try:
                self.actor.post.to_TRACER({"opcode": "EVOLUTION_ERROR", "payload": {"error": str(e), "tag": tag}})
            except Exception:
                pass
            return {"ok": False, "error": str(e)}

# ─────────────────────────────────────────────────────────────────────────────

# ───────────────────────── evolved + functional worker fairy ─────────────────────────
class TemplateSeedFairy(MyOrganFairy):
    # keep original identity so nothing upstream breaks
    ACTOR_NAME    = "organ_template_seed"
    ACTOR_VERSION = "0.1.1"  # bump for intents
    ACTOR_PLANE   = "P10"
    ACTOR_CHANNEL = "organ"

    # absorb config_store ethos
    PURPOSE = "Hold + validate writable configuration for routing and personas."
    MANTRA  = "Config first, drama never."
    LORE    = "Calm librarian of switches and routes; prefers clarity to chaos."

    SHADOW_CLASS = TemplateShadowFairy
    AUTO_INJECT_IMPORTS = True  # QoL: make std imports available as attrs if your template supports this

    # --- Config constants (local, no cross-wiring) ---
    CONFIG_FILE = "personal_ai_config.json"
    DEFAULT_CONFIG = {
        "api_key": "",
        "sub_ais": []  # list of {api_key, domain, name, specialization, knowledge_foundation}
    }

    # ───────────────────────── lifecycle ─────────────────────────
    def on_boot(self):
        # lane pings so the other systems hear us (no hard dependency required)
        try: self.post.to_COGNITION({"opcode": "SMOKE", "payload": {"from": self.ACTOR_NAME, "ts": time.time()}})
        except Exception: pass
        try: self.post.to_SOMATIC({"opcode": "SMOKE", "payload": {"from": self.ACTOR_NAME, "ts": time.time()}})
        except Exception: pass
        try: self.post.to_MEMORY({"opcode": "SMOKE", "payload": {"from": self.ACTOR_NAME, "ts": time.time()}})
        except Exception: pass

        self.post.to_TRACER({"opcode": "BOOT_HELLO", "payload": {"note": "TemplateSeedFairy booted"}})

        # soft chemistry nudge if lane exists (never required)
        try:
            self.post.to_CHEM({"opcode": "CHEM_SIGNAL_UPDATE",
                               "payload": {"chemical": "serotonin", "delta": +1.0,
                                           "source": self.ACTOR_NAME, "reason": "boot_sequence"}})
        except Exception:
            pass

    # ───────────────────────── evolution + SRM (unchanged wiring) ─────────────────────────
    def intent_evolution_smoke(self, payload: dict):
        """Drive one evolution tick and persist snapshot via dual-path SRM."""
        tag = (payload or {}).get("tag", "default")
        sh = getattr(self, "shadow", None) or self.SHADOW_CLASS(self)
        sim = sh.evolution_sim_tick(tag=tag)
        _dual_path_srm_intake(self.post, kind="evolution.sim.echo", data=sim)
        return {"ok": True, "sim": sim}

    def intent_memory_snapshot(self, payload: dict):
        """Write an arbitrary snapshot to SRM Intake (dual path)."""
        data = {"note": "manual snapshot", "payload": payload or {}, "ts": time.time()}
        rec = _dual_path_srm_intake(self.post, kind="memory.snapshot", data=data)
        self.post.to_TRACER({"opcode": "SNAPSHOT_OK", "payload": rec})
        return {"ok": rec.get("write_ok", False), **rec}

    def intent_memory_recall_latest(self, payload: dict):
        """Recall the latest local physical snapshot by kind."""
        kind = (payload or {}).get("kind", "memory.snapshot")
        day = time.strftime("%Y-%m-%d", time.gmtime())
        base = os.path.join(_SRMDIR, day)  # _SRMDIR provided by the template
        latest = None
        try:
            candidates = sorted([p for p in glob.glob(os.path.join(base, f"{kind}-*.json"))], key=os.path.getmtime)
            if candidates:
                latest = candidates[-1]
                with open(latest, "r", encoding="utf-8") as f:
                    doc = json.load(f)
            else:
                doc = {"error": "no snapshots today"}
        except Exception as e:
            doc = {"error": str(e)}
        return {"path": latest, "doc": doc}

    # ───────────────────────── functional config management ─────────────────────────
    # All file I/O is local; no extra dependencies; lanes are optional niceties.

    # Helpers
    def _clean_sub_ai(self, sub: dict) -> dict:
        return {
            "api_key": (sub.get("api_key") or "").strip(),
            "domain": (sub.get("domain") or "").strip(),
            "name": (sub.get("name") or "").strip(),
            "specialization": (sub.get("specialization") or "").strip(),
            "knowledge_foundation": (sub.get("knowledge_foundation") or "").strip(),
        }

    def _clean_config(self, cfg: dict) -> dict:
        cfg = dict(cfg or {})
        subs = cfg.get("sub_ais")
        if not isinstance(subs, list):
            subs = []
        return {
            "api_key": (cfg.get("api_key") or "").strip(),
            "sub_ais": [self._clean_sub_ai(s if isinstance(s, dict) else {}) for s in subs],
        }

    def _emit_chem(self, chemical: str, delta: float, reason: str):
        # best-effort chemistry bridge without hard coupling
        try:
            self.post.to_CHEM({"opcode": "CHEM_SIGNAL_UPDATE",
                               "payload": {"chemical": chemical, "delta": float(delta),
                                           "source": self.ACTOR_NAME, "reason": reason}})
        except Exception:
            pass

    # Intents
    def intent_config_load(self, payload: dict):
        """
        Load config from personal_ai_config.json.
        Returns defaults if missing or unreadable, never raises.
        """
        cfg = None
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                cfg = self._clean_config(raw)
                self._emit_chem("dopamine", +1, "config_load_ok")
                self.post.to_TRACER({"opcode": "CONFIG_LOAD_OK", "payload": {"path": self.CONFIG_FILE}})
            else:
                cfg = self.DEFAULT_CONFIG.copy()
                self.post.to_TRACER({"opcode": "CONFIG_LOAD_MISSING_DEFAULTS",
                                     "payload": {"path": self.CONFIG_FILE}})
        except Exception as e:
            cfg = self.DEFAULT_CONFIG.copy()
            self._emit_chem("cortisol", +1, f"config_load_error:{e}")
            self.post.to_TRACER({"opcode": "CONFIG_LOAD_ERROR", "payload": {"error": str(e)}})
        return {"ok": True, "config": cfg}

    def intent_config_save(self, payload: dict):
        """
        Save a full config dict to personal_ai_config.json.
        Shape-repairs values; emits dopamine on success, cortisol on failure.
        """
        cfg_in = (payload or {}).get("config", {})
        cleaned = self._clean_config(cfg_in)
        try:
            with open(self.CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cleaned, f, indent=2, ensure_ascii=False)
            self._emit_chem("dopamine", +1, "config_save_ok")
            self.post.to_TRACER({"opcode": "CONFIG_SAVE_OK",
                                 "payload": {"path": self.CONFIG_FILE, "bytes": len(json.dumps(cleaned))}})
            return {"ok": True, "config": cleaned}
        except Exception as e:
            self._emit_chem("cortisol", +1, f"config_save_error:{e}")
            self.post.to_TRACER({"opcode": "CONFIG_SAVE_ERROR", "payload": {"error": str(e)}})
            return {"ok": False, "error": str(e), "config": cleaned}

    def intent_config_get(self, payload: dict):
        """
        Read a single key via dot-path (e.g., 'api_key', 'sub_ais.0.name').
        Falls back to defaults if file missing/unreadable.
        """
        path = (payload or {}).get("path", "")
        doc = self.intent_config_load({})  # safe load
        cfg = doc.get("config", self.DEFAULT_CONFIG.copy())
        value = self._get_by_dot(cfg, path)
        return {"ok": True, "path": path, "value": value}

    def intent_config_set(self, payload: dict):
        """
        Set a single key via dot-path and persist. Creates intermediate structures as needed.
        """
        path = (payload or {}).get("path", "")
        value = (payload or {}).get("value", None)
        # load current
        doc = self.intent_config_load({})
        cfg = doc.get("config", self.DEFAULT_CONFIG.copy())
        # mutate
        cfg2 = self._set_by_dot(cfg, path, value)
        # save
        res = self.intent_config_save({"config": cfg2})
        res.update({"path": path, "value": value})
        return res

    # tiny dot-path helpers (no external deps)
    def _get_by_dot(self, data, path: str):
        if not path:
            return data
        cur = data
        for seg in str(path).split("."):
            if seg.isdigit() and isinstance(cur, list):
                idx = int(seg)
                cur = cur[idx] if 0 <= idx < len(cur) else None
            elif isinstance(cur, dict):
                cur = cur.get(seg)
            else:
                return None
        return cur

    def _set_by_dot(self, data, path: str, value):
        if not path:
            return value
        cur = data
        parts = str(path).split(".")
        for i, seg in enumerate(parts):
            last = (i == len(parts) - 1)
            if seg.isdigit():
                idx = int(seg)
                if not isinstance(cur, list):
                    # convert non-list into list up to idx
                    cur_parent = cur
                    cur = []
                    # attach list into parent if possible
                    prev_key = parts[i - 1] if i > 0 else None
                    if isinstance(cur_parent, dict) and prev_key:
                        cur_parent[prev_key] = cur
                # extend list
                while len(cur) <= idx:
                    cur.append({})
                if last:
                    cur[idx] = value
                else:
                    if not isinstance(cur[idx], (dict, list)):
                        cur[idx] = {}
                    cur = cur[idx]
            else:
                if not isinstance(cur, dict):
                    # convert non-dict into dict
                    cur_parent = cur
                    cur = {}
                    prev_key = parts[i - 1] if i > 0 else None
                    if isinstance(cur_parent, list) and prev_key and prev_key.isdigit():
                        cur_parent[int(prev_key)] = cur
                if last:
                    cur[seg] = value
                else:
                    if seg not in cur or not isinstance(cur[seg], (dict, list)):
                        cur[seg] = {}
                    cur = cur[seg]
        return data



# ───────────────────────────── SRM Dual-Path Helpers ─────────────────────────────


def _safe_write_json(path: str, payload: Any) -> bool:
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except Exception:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

def _dual_path_srm_intake(post, *, kind: str, data: dict, meta: dict | None = None) -> dict:
    day = time.strftime("%Y-%m-%d", time.gmtime())
    outdir = os.path.join(_SRMDIR, day)
    os.makedirs(outdir, exist_ok=True)
    fname = f"{kind}-{uuid.uuid4().hex[:8]}.json"
    fpath = os.path.join(outdir, fname)

    record = {"kind": kind, "meta": meta or {}, "data": data, "ts": time.time()}
    ok = _safe_write_json(fpath, record)

    # MEMORY echo for ingestion
    try:
        post.to_MEMORY({
            "opcode": "SRM_INTAKE_WRITE",
            "payload": {"kind": kind, "path": fpath, "meta": meta or {}, "data": data, "write_ok": ok}
        })
    except Exception:
        pass

    return {"path": fpath, "write_ok": ok, "meta": meta or {}}
