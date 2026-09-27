from __future__ import annotations

import os, sys, glob, time, uuid, json, pathlib, re, hashlib
import datetime as _dt
from collections import deque
from typing import Optional, Dict, List, Any, Iterable
# Optional dependencies (auto-fallbacks)
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _WATCHDOG_OK = True
except Exception:
    _WATCHDOG_OK = False
    class FileSystemEventHandler:  # tiny shim for type references
        pass
    class Observer:  # shim that raises on use
        def __init__(self,*a,**k): raise RuntimeError("watchdog not installed")

try:
    from pypdf import PdfReader    # pdf peek
except Exception:
    PdfReader = None

try:
    import docx as _docx            # docx core props
except Exception:
    _docx = None

try:
    from ebooklib import epub as _epub  # epub metadata
except Exception:
    _epub = None
# ---- V2 Fairy base class -----------------------------------------------------
# Import V2 Fairy base class
# HeartbeatMixin removed - Fifth Ring Principle (postal heartbeat via FairyBase)
try:
    from fairies.P00_Autonomic.organ_template import MyFairy as Fairy
    _HAS_FAIRY = True
except ImportError:
    _HAS_FAIRY = False
    Fairy = object

# ---- Local helpers ----------------------------------------------------------

def _output_has_artifacts(path: str) -> bool:
    """
    Return True if the output folder contains any non-empty file (any depth).
    This lets the scanner mark Processed=NO again if the folder was emptied.
    """
    try:
        if not os.path.isdir(path):
            return False
        for root, _dirs, files in os.walk(path):
            for fn in files:
                fpath = os.path.join(root, fn)
                try:
                    if os.path.getsize(fpath) > 0:
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    return False


# ---- SRM + path helpers -----------------------------------------------------

def resolve_root(preferred: Optional[str] = None, *, akashic_app: Optional[str] = None) -> str:
    """
    Resolve the Akashic root directory.
    """
    if preferred:
        return os.path.abspath(preferred)
    env_root = os.getenv("AKASHIC_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    return os.path.abspath(os.getcwd())

# SRM base directory
_SRMDIR: str = os.path.join(
    resolve_root(akashic_app=os.getenv("AKASHIC_APP")),
    "SRM_Intake",
)

def _dual_path_srm_intake(
    post,
    *,
    kind: str,
    data: dict,
    meta: dict | None = None,
) -> dict:
    """
    SRM intake helper - routes to postal if available.
    """
    result = {"kind": kind, "data": data, "meta": meta, "write_ok": False}
    try:
        if post:
            post.route("memory.srm_intake", {"kind": kind, "data": data, "meta": meta})
            result["write_ok"] = True
    except Exception:
        pass
    return result


# --- Per-clone shadow --------------------------------------------------------

class ScannerShadowFairy:
    """
    Shadow fairy for ScannerFairy health monitoring.
    """
    ORGAN_LEVEL = False
    SHADOW_NAME = "ScannerShadowFairy"
    SHADOW_VERSION = "0.1.1"

    # cadence knobs for extras (seconds)
    CADENCE = {
        "silence_warn_after": 300,   # 5 min without lane activity -> warn
        "snapshot_every":     900,   # 15 min suggest blueprint snapshot
        "sim_light_every":    300,   # 5 min evolution sim (light)
        "sim_deep_every":     1800,  # 30 min deep sim
    }

    REG = {
        "enabled":   True,
        "domain":    "Sensory",
        "role":      "worker",
        "name":      "lexi",
        "every_sec": 20.0,
    }

    def __init__(self, actor, interval_sec: float = 30.0):
        self.actor = actor
        self.interval_sec = interval_sec
        self._lane_seen_ts = time.time()
        self._last_snapshot_ts = 0.0
        self._last_sim_light_ts = 0.0
        self._last_sim_deep_ts  = 0.0
        self._lane_tail = deque(maxlen=10)
        self._last_reg_ts: float | None = 0.0
        self._last_reg_sig: str | None = None

    def on_lane_activity(self):
        self._lane_seen_ts = time.time()
        self._lane_tail.append(self._lane_seen_ts)

    def _collect_tests(self):
        tests = []

        def _dir_link_ok():
            ok = bool(getattr(self.actor, "directory", None))
            return {"name":"directory_link","status":"ok" if ok else "warn",
                    "message":"" if ok else "no directory attached","details":{}}

        def _post_present():
            ok = bool(getattr(self.actor, "post", None))
            return {"name":"post_office","status":"ok" if ok else "warn",
                    "message":"" if ok else "no post office","details":{}}

        def _lane_silence():
            idle = time.time() - self._lane_seen_ts
            warn_after = float(self.CADENCE.get("silence_warn_after", 300))
            ok = idle < warn_after
            return {"name":"lane_activity","status":"ok" if ok else "warn",
                    "message":"" if ok else f"idle {int(idle)}s","details":{"idle_sec": int(idle)}}

        tests.extend([_dir_link_ok, _post_present, _lane_silence])
        return tests

    def current_status(self):
        """Return current health status."""
        tests = [t() for t in self._collect_tests()]
        worst = "ok"
        for t in tests:
            if t.get("status") == "error":
                worst = "error"
                break
            elif t.get("status") == "warn" and worst == "ok":
                worst = "warn"
        return (worst, tests)

    def maybe_run(self, tests=None):
        now = time.time()

        # 1) periodic blueprint snapshot nudge
        try:
            snap_every = float(self.CADENCE.get("snapshot_every", 900))
            if now - self._last_snapshot_ts >= snap_every:
                if hasattr(self.actor, "_emit_blueprint"):
                    self.actor._emit_blueprint()
                self._last_snapshot_ts = now
        except Exception:
            pass

        # 2) evolution sim ticks
        try:
            light_every = float(self.CADENCE.get("sim_light_every", 300))
            deep_every  = float(self.CADENCE.get("sim_deep_every", 1800))
            if now - self._last_deep_ts() >= deep_every:
                self._evolution_sim_tick(kind="deep", n=3)
                self._touch_deep(now)
            elif now - self._last_sim_light_ts >= light_every:
                self._evolution_sim_tick(kind="light", n=1)
                self._last_sim_light_ts = now
        except Exception:
            pass

        # 3) optional shadow.* echoes
        try:
            if getattr(self.actor, "post", None):
                self.actor.post.route("shadow.health", {
                    "actor": self.actor.ACTOR_NAME,
                    "status": self.current_status()[0],
                    "ts": now
                })
        except Exception:
            pass

    def _last_deep_ts(self):
        return getattr(self, "__deep_ts", 0.0)

    def _touch_deep(self, t: float):
        setattr(self, "__deep_ts", t)

    def _evolution_sim_tick(self, kind: str = "light", n: int = 1):
        """Send synthetic evolution observations."""
        try:
            import random
            for i in range(max(1, int(n))):
                sim = {
                    "kind": f"evolution.sim.{kind}",
                    "tag": f"{kind}-{i}",
                    "mutation_rate": round(random.uniform(0.01, 0.2), 3),
                    "stability": random.choice(["stable","drifting","mutating"]),
                    "actor": self.actor.ACTOR_NAME,
                    "ts": time.time(),
                    "pair_id": uuid.uuid4().hex[:12],
                }
                meta = {
                    "shadow": self.SHADOW_NAME,
                    "version": self.SHADOW_VERSION,
                    "blueprint_sha": getattr(self.actor, "_bp_last_hash", None),
                }
                _dual_path_srm_intake(
                    getattr(self.actor, "post", None),
                    kind=sim["kind"],
                    data=sim,
                    meta=meta,
                )
                try:
                    if getattr(self.actor, "post", None):
                        self.actor.post.route("tracer", {
                            "opcode":"EVOLUTION_SIM",
                            "payload": {"kind": kind, "meta": meta}
                        })
                except Exception:
                    pass
        except Exception:
            pass


class ScannerFairy(Fairy):
    # Identity aligned to scanner
    ACTOR_NAME    = "ScannerFairy"
    ACTOR_VERSION = "2.2.0"  # parity bump: template-0.0.7 + legacy duties infused
    ACTOR_PLANE   = "P40"
    ACTOR_CHANNEL = "scanner"
    ORGAN_LEVEL   = False

    PURPOSE       = "Watch source folder, detect new artifacts, and enqueue them for processing."
    MANTRA        = "See all. Judge nothing. Name what arrives, then vanish."
    LORE          = "Eyes open; wings steady. We witness, route, and archive."

    CULTURE       = "worker"

    SHADOW_CLASS        = ScannerShadowFairy
    AUTO_INJECT_IMPORTS = True

    # ── Character-sheet directive ring ────────────────────────────────────────
    DIRECTIVE_ACTIVATION = {
        "mode": "Scanner_Watch",
        "depth_scaling": "0.8",
        "traits": [
            "Folder_Watcher",
            "Ingestion_Scout",
            "Queue_Emitter",
        ],
    }

    DIRECTIVE_NATURE = {
        "archetype": "Scanner",
        "domains": [
            "Sensory",
            "Ingestion",
            "Filesystem",
        ],
    }

    DIRECTIVE_ESSENCE = {
        "threads": [
            "Watch_Input_Dir",
            "Emit_Enqueue_Events",
            "Write_Scan_Index",
            "Emit_Health_and_Blueprint",
        ],
    }

    DIRECTIVE_FOUNDATION = {
        "records": [
            "scanner.file_enqueued",
            "scanner.scan_summary",
            "scanner.index_saved",
            "scanner.watch_state",
            "shadow.health_report",
            "blueprint.report",
        ],
        "field": [
            "Ingestion_State",
            "Scanner_Health",
        ],
    }

    DIRECTIVE_CORE_VALUES = {
        "authenticity": [
            "Accurate_File_Detection",
            "Non_Judgmental_Scanning",
        ],
        "growth": [
            "Safer_Watches",
            "Better_Metadata",
        ],
    }

    SUBSYSTEM_STATUS = {
        "sensory": {
            "state": "watching",
            "notes": "Monitors input folders and emits enqueue events for new artifacts.",
            "tests": [],
        },
        "memory": {
            "state": "snapshotting",
            "notes": "Writes SRM snapshots for scans, indices, and health reports.",
            "tests": [],
        },
        "telemetry": {
            "state": "echoing",
            "notes": "Emits TRACER events for scans, paths, health, and blueprint reports.",
            "tests": [],
        },
        "chemistry": {
            "state": "signalling",
            "notes": "Marks health state (serene/anxious/critical) via chem pulses.",
            "tests": [],
        },
    }

    # Legacy scanner constants (kept)
    SUPPORTED_EXTS = (".epub", ".pdf", ".doc", ".docx")

    # Things that are not classic “books” but should be scanned and sent
    # through the pipeline anyway.
    EXTRA_MODALITY_EXTS = {
        ".cbz": "comic",
        ".cbr": "comic",

        ".fasta": "genome",
        ".fa": "genome",
        ".fastq": "genome",
        ".vcf": "genome",

        # Code / notebooks – we’ll turn these into readable PDFs via SplittingForge
        ".py": "code",
        ".js": "code",
        ".ts": "code",
        ".ipynb": "code",

        # Text-y sources we still want in the pipeline
        ".md": "text",
        ".markdown": "text",
    }

    TEMPFILE_SUFFIXES  = (".crdownload", ".part", ".tmp", ".swp", ".swx", ".download")
    TEMPFILE_PREFIXES  = ("~$", ".~lock")
    EVENT_DEBOUNCE_SEC = 1.25
    SIZE_STABILITY_CHECKS = 3
    SIZE_STABILITY_SLEEP  = 0.4

    CONTRACT_VERSION = "1.0"
    SCANNER_PARITY_UPGRADE_ID = "SCANNER_PARITY_V1"

    def __init__(self, fabric=None):
        if _HAS_FAIRY:
            super().__init__(fabric)
        else:
            self.post = fabric

    # ── Boot & lanes ──────────────────────────────────────────────────────────
    def on_boot(self):
        print(f"[{self.ACTOR_NAME}] on_boot: START", flush=True)
        # Call parent on_boot if available
        try:
            if _HAS_FAIRY:
                super().on_boot()
            print(f"[{self.ACTOR_NAME}] on_boot: super() DONE", flush=True)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] super().on_boot() error: {e}")
        
        # lane pings so other systems hear us (seed behavior)
        now = time.time()
        for lane in ("to_COGNITION", "to_SOMATIC", "to_MEMORY"):
            try:
                getattr(self.post, lane)(
                    {"opcode": "SMOKE", "payload": {"from": self.ACTOR_NAME, "ts": now}}
                )
            except Exception:
                pass
        try:
            self.post.to_TRACER({
                "opcode": "BOOT_HELLO",
                "payload": {"note": "Scanner fairy online"},
            })
        except Exception:
            pass
        print(f"[{self.ACTOR_NAME}] on_boot: lane pings DONE", flush=True)

        # local state
        cfg = getattr(self, "CONFIG", {}) or {}
        self._input_dir  = os.path.abspath(cfg.get("input_dir",  "./input"))
        self._output_dir = os.path.abspath(cfg.get("output_dir", "./output"))
        self._recursive  = bool(cfg.get("recursive_watch", False))
        self._watching   = False
        self._observer: Optional[Observer] = None
        self._handler: Optional["ScannerFairy._WatchdogHandler"] = None
        self._debounce: Dict[str, float] = {}
        self._last_seen_mtime: Dict[str, float] = {}
        self._last_error: Optional[str] = None
        self._use_watchdog = _WATCHDOG_OK
        print(f"[{self.ACTOR_NAME}] on_boot: local state DONE", flush=True)

        # calm chemistry nudge on boot (non-fatal if bridge absent)
        try:
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {
                    "chemical": "serotonin",
                    "delta": +0.5,
                    "source": self.ACTOR_NAME,
                    "reason": "boot",
                },
            })
        except Exception:
            pass
        print(f"[{self.ACTOR_NAME}] on_boot: CHEM done", flush=True)

        # ── initial character-sheet state ─────────────────────────────────────
        self.AFFECT_STATE = {
            "mood": "attentive",
            "valence": 0.05,
            "arousal": 0.30,
            "tags": ["scanner", "watching"],
            "tone": "neutral",
            "energy": 0.4,
            "coherence": 0.8,
            "intent": "watch_input_dir",
            "source": self.ACTOR_NAME,
            "ts": now,
        }
        self.SOMATIC_STATE = {
            "body_type": "sensory",
            "posture": "upright",
            "motion": "low",
            "energy": 0.4,
            "anchor_id": "P40.scanner",
            "notes": "Ready to watch input_dir and enqueue new artifacts.",
            "last_setpoint_ts": None,
            "source": self.ACTOR_NAME,
        }
        return True

    # ── Seed Intents (verbatim from template seed) ─────────────────────────────
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
        base = os.path.join(_SRMDIR, day)
        latest = None
        try:
            candidates = sorted(
                [p for p in glob.glob(os.path.join(base, f"{kind}-*.json"))],
                key=os.path.getmtime,
            )
            if candidates:
                latest = candidates[-1]
                with open(latest, "r", encoding="utf-8") as f:
                    doc = json.load(f)
            else:
                doc = {"error": "no snapshots today"}
        except Exception as e:
            doc = {"error": str(e)}
        return {"path": latest, "doc": doc}

    # ── Scanner Intents (legacy duties, template-safe) ─────────────────────────
    def intent_start_watch(self, payload: dict | None):
        """Begin watching input_dir (watchdog if available, else polling on tick)."""
        self._watching = True
        mode = "polling"
        if self._use_watchdog and os.path.isdir(self._input_dir) and self._observer is None:
            try:
                self._handler = self._WatchdogHandler(self)
                self._observer = Observer()
                self._observer.schedule(
                    self._handler, self._input_dir, recursive=self._recursive
                )
                self._observer.start()
                mode = "watchdog"
            except Exception as e:
                self._observer = None
                self._handler = None
                self._last_error = f"watchdog fallback: {e}"
                self.post.to_TRACER({
                    "opcode": "WATCH_FALLBACK",
                    "payload": {"error": self._last_error},
                })
        self.post.to_TRACER({
            "opcode": "WATCH_START",
            "payload": {
                "mode": mode,
                "input_dir": self._input_dir,
                "recursive": self._recursive,
            },
        })
        _dual_path_srm_intake(
            self.post,
            kind="scanner.watch_state",
            data={"watching": True, "mode": mode, "ts": time.time()},
        )
        return {"ok": True, "watching": self._watching, "mode": mode}

    def intent_stop_watch(self, payload: dict | None):
        """Stop watching input_dir."""
        if self._observer:
            try:
                self._observer.stop()
                self._observer.join(timeout=5.0)
            except Exception:
                pass
            self._observer = None
            self._handler = None
        self._watching = False
        self.post.to_TRACER({"opcode": "WATCH_STOP", "payload": {}})
        _dual_path_srm_intake(
            self.post,
            kind="scanner.watch_state",
            data={"watching": False, "ts": time.time()},
        )
        return {"ok": True, "watching": self._watching}

    def intent_resync_paths(self, payload: dict | None):
        """Change input/output dirs; preserves active watch mode seamlessly."""
        p = payload or {}
        want_input  = os.path.abspath(p.get("input_dir",  self._input_dir))
        want_output = os.path.abspath(p.get("output_dir", self._output_dir))
        was = self._watching
        if was:
            self.intent_stop_watch(None)
        self._input_dir, self._output_dir = want_input, want_output
        if was:
            self.intent_start_watch(None)
        self.post.to_TRACER({
            "opcode": "PATHS_RESYNC",
            "payload": {
                "input_dir": self._input_dir,
                "output_dir": self._output_dir,
            },
        })
        _dual_path_srm_intake(
            self.post,
            kind="scanner.paths_resync",
            data={
                "input_dir": self._input_dir,
                "output_dir": self._output_dir,
                "ts": time.time(),
            },
        )
        return {"ok": True, "input_dir": self._input_dir, "output_dir": self._output_dir}

    def intent_scan_now(self, payload: dict | None):
        """Scan input_dir immediately and return rows (legacy bulk scan)."""
        rows = self._scan_source_folder()
        return {"ok": True, "rows": rows}

    def intent_save_index_now(self, payload: dict | None):
        """Scan and write/merge scan_index.json in output_dir."""
        rows = self._scan_source_folder()
        path = self._save_scan_index_json(rows)
        return {"ok": bool(path), "path": path, "rows": len(rows or [])}

    def intent_selfcheck_now(self, payload: dict | None):
        """Emit a consolidated health report, escalate if needed."""
        return self._emit_health_report_now()

    def intent_emit_blueprint(self, payload: dict | None):
        """Emit BLUEPRINT_REPORT and BLUEPRINT_HASH (parity)."""
        return self._emit_blueprint_now()

    # ── Tick loop (polling mode) ───────────────────────────────────────────────
    def tick(self):
        """When in polling mode, detect changed/new files and enqueue."""
        if not self._watching or self._observer is not None:
            return  # watchdog handles events; or not watching
        try:
            for path in self._iter_candidate_files(
                self._input_dir, recursive=self._recursive
            ):
                base = os.path.basename(path).lower()
                if any(base.startswith(p) for p in self.TEMPFILE_PREFIXES) or any(
                    base.endswith(s) for s in self.TEMPFILE_SUFFIXES
                ):
                    continue
                try:
                    mt = os.path.getmtime(path)
                except Exception:
                    continue
                last = self._last_seen_mtime.get(path)
                if (last is None) or (mt > last):
                    self._last_seen_mtime[path] = mt
                    self._record_enqueue(path)
        except Exception as e:
            self._last_error = str(e)
            self.post.to_TRACER({
                "opcode": "SCAN_TICK_ERROR",
                "payload": {"error": self._last_error},
            })

    # ── Watchdog handler (debounce + size stability) ───────────────────────────
    class _WatchdogHandler(FileSystemEventHandler):
        def __init__(self, actor: "ScannerFairy"):
            super().__init__()
            self.actor = actor

        def _is_tmp_or_lock(self, path: str) -> bool:
            low = os.path.basename(path).lower()
            return any(low.startswith(p) for p in self.actor.TEMPFILE_PREFIXES) or any(
                low.endswith(s) for s in self.actor.TEMPFILE_SUFFIXES
            )

        def _wait_size_stable(self, path: str) -> bool:
            last = -1
            steady = 0
            for _ in range(self.actor.SIZE_STABILITY_CHECKS):
                try:
                    sz = os.path.getsize(path)
                except Exception:
                    return False
                if sz > 0 and sz == last:
                    steady += 1
                else:
                    steady = 0
                last = sz
                if steady >= (self.actor.SIZE_STABILITY_CHECKS - 1):
                    return True
                time.sleep(self.actor.SIZE_STABILITY_SLEEP)
            return False

        def _maybe_enqueue(self, new_path: str):
            low = new_path.lower()
            ext = os.path.splitext(low)[1]
            if self._is_tmp_or_lock(new_path):
                return
            if not (
                low.endswith(self.actor.SUPPORTED_EXTS)
                or ext in self.actor.EXTRA_MODALITY_EXTS
            ):
                return
            t = time.time()
            last = self.actor._debounce.get(new_path, 0.0)
            if (t - last) < self.actor.EVENT_DEBOUNCE_SEC:
                return
            self.actor._debounce[new_path] = t
            if not self._wait_size_stable(new_path):
                return
            self.actor._record_enqueue(new_path)

        def on_created(self, e):
            if not getattr(e, "is_directory", False):
                self._maybe_enqueue(e.src_path)

        def on_modified(self, e):
            if not getattr(e, "is_directory", False):
                self._maybe_enqueue(e.src_path)

    # ── Health/Blueprint parity helpers ─────────────────────────────────────────
    def _emit_blueprint_now(self) -> dict:
        bp = {
            "id": uuid.uuid4().hex,
            "name": self.ACTOR_NAME,
            "version": self.ACTOR_VERSION,
            "plane": self.ACTOR_PLANE,
            "channel": self.ACTOR_CHANNEL,
            "archetype": "digital_organ",
            "purpose": self.PURPOSE,
            "mantra": self.MANTRA,
            "input_dir": self._input_dir,
            "output_dir": self._output_dir,
            "watching": self._watching,
            "recursive": self._recursive,
            "ts": time.time(),
        }
        try:
            self.post.to_TRACER({"opcode": "BLUEPRINT_REPORT", "payload": bp})
            _dual_path_srm_intake(self.post, kind="blueprint.report", data=bp)
        except Exception:
            pass

        # source hash (best-effort)
        try:
            src_path = str(pathlib.Path(__file__).resolve())
            h = hashlib.sha256()
            with open(src_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            sha = h.hexdigest()
            self.post.to_TRACER({
                "opcode": "BLUEPRINT_HASH",
                "payload": {"path": src_path, "sha256": sha},
            })
            _dual_path_srm_intake(
                self.post,
                kind="blueprint.hash",
                data={"path": src_path, "sha256": sha},
            )
        except Exception as e:
            self.post.to_TRACER({
                "opcode": "BLUEPRINT_HASH_ERROR",
                "payload": {"error": repr(e)},
            })
        # upgrade ack
        try:
            self.post.to_TRACER({
                "opcode": "UPGRADE_ACK",
                "payload": {
                    "upgrade_id": self.SCANNER_PARITY_UPGRADE_ID,
                    "actor": self.ACTOR_NAME,
                },
            })
        except Exception:
            pass
        return {"ok": True, "blueprint": bp}

    def _emit_health_report_now(self) -> dict:
        tests = []

        # input dir
        try:
            if not os.path.isdir(self._input_dir):
                raise RuntimeError("input_dir missing")
            os.listdir(self._input_dir)
            tests.append({
                "name": "input_dir",
                "status": "ok",
                "message": self._input_dir,
            })
        except Exception as e:
            tests.append({
                "name": "input_dir",
                "status": "error",
                "message": str(e),
            })

        # output dir
        try:
            os.makedirs(self._output_dir, exist_ok=True)
            probep = os.path.join(self._output_dir, ".scan_probe.tmp")
            with open(probep, "w", encoding="utf-8") as f:
                f.write("ok")
            try:
                os.remove(probep)
            except Exception:
                pass
            tests.append({
                "name": "output_dir",
                "status": "ok",
                "message": self._output_dir,
            })
        except Exception as e:
            tests.append({
                "name": "output_dir",
                "status": "error",
                "message": str(e),
            })

        # lanes
        try:
            self.post.to_TRACER({
                "opcode": "SMOKE",
                "payload": {"from": self.ACTOR_NAME},
            })
            tests.append({"name": "lane_tracer", "status": "ok", "message": "ok"})
        except Exception as e:
            tests.append({
                "name": "lane_tracer",
                "status": "warn",
                "message": str(e),
            })

        try:
            self.post.route("PLAN", {
                "opcode": "LOOPBACK",
                "payload": {"from": self.ACTOR_NAME},
            })
            tests.append({"name": "lane_plan", "status": "ok", "message": "ok"})
        except Exception as e:
            tests.append({
                "name": "lane_plan",
                "status": "warn",
                "message": str(e),
            })

        worst = (
            "ok"
            if all(t["status"] == "ok" for t in tests)
            else ("warn" if any(t["status"] == "warn" for t in tests) else "error")
        )
        state = {"ok": "serene", "warn": "anxious", "error": "critical"}[worst]
        report = {"state": state, "tests": tests, "ts": time.time()}
        try:
            self.post.to_TRACER({"opcode": "HEALTH_REPORT", "payload": report})
            _dual_path_srm_intake(
                self.post, kind="shadow.health_report", data=report
            )
        except Exception:
            pass

        # chemistry + oracle
        try:
            chem = (
                "dopamine"
                if state == "serene"
                else ("cortisol" if state == "anxious" else "adrenaline")
            )
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {
                    "chemical": chem,
                    "delta": +1.0,
                    "source": self.ACTOR_NAME,
                    "reason": "scanner_health",
                },
            })
        except Exception:
            pass
        if state != "serene":
            try:
                self.post.to_ORACLE({
                    "opcode": "ORACLE_SUGGEST",
                    "payload": {
                        "origin": self.ACTOR_CHANNEL,
                        "symptom": state,
                        "remedy": "check dirs/perm; throttle watch; resync paths",
                        "tests": tests,
                    },
                })
            except Exception:
                pass
        return {"ok": True, **report}

    # ── Scan / Index (legacy behavior, dependency-safe) ────────────────────────
    def _iter_candidate_files(self, root: str, *, recursive: bool) -> Iterable[str]:
        if not os.path.isdir(root):
            return []
        pats = [
            "*.epub",
            "*.pdf",
            "*.doc",
            "*.docx",
            "*.cbz",
            "*.cbr",
            "*.py",
            "*.js",
            "*.ts",
            "*.ipynb",
            "*.fasta",
            "*.fa",
            "*.fastq",
            "*.vcf",
        ]
        if recursive:
            for pat in pats:
                for p in glob.glob(os.path.join(root, "**", pat), recursive=True):
                    if os.path.isfile(p):
                        yield p
        else:
            for fn in os.listdir(root):
                p = os.path.join(root, fn)
                if os.path.isfile(p) and any(
                    fn.lower().endswith(ext)
                    for ext in (self.SUPPORTED_EXTS + tuple(self.EXTRA_MODALITY_EXTS.keys()))
                ):
                    yield p

    def _scan_source_folder(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if not os.path.isdir(self._input_dir):
            self._last_error = "input_dir missing"
            _dual_path_srm_intake(
                self.post,
                kind="scanner.error",
                data={"message": self._last_error},
            )
            return rows
        for path in self._iter_candidate_files(
            self._input_dir, recursive=self._recursive
        ):
            base = os.path.basename(path).lower()
            if any(base.startswith(p) for p in self.TEMPFILE_PREFIXES) or any(
                base.endswith(s) for s in self.TEMPFILE_SUFFIXES
            ):
                continue
            meta = self._guess_meta(path)
            safe = self._safe_folder_name(meta["title"])
            out_dir = os.path.join(self._output_dir, safe)
            already = _output_has_artifacts(out_dir)
            row = {
                "source_path": path,
                "safe_title": safe,
                "output_dir": out_dir,
                "title": meta["title"],
                "creators": ", ".join(meta.get("creators", ["Unknown"]))[:50],
                "language": meta["language"],
                "identifier": meta["identifier"],
                "publisher": meta.get("publisher", ""),
                "publication_date": meta.get("publication_date", ""),
                "series_info": meta.get("series_info", ""),
                "subject_categories": "; ".join(meta.get("subject_categories") or []),
                "fiction_nonfiction": meta.get("fiction_nonfiction", "Unknown"),
                "content_rating": meta.get("content_rating") or "",
                "word_count": meta.get("word_count", 0),
                "file_type": meta.get("file_type"),
                "last_modified": meta.get("last_modified"),
                # store as bool so UIs don't misread truthy strings like "NO"
                "processed": bool(already),
                "needs_ocr": meta.get("needs_ocr_deep_scan", False),
                "chosen_isbn": meta.get("chosen_isbn", ""),
                "publisher_hint": meta.get("publisher_hint", ""),
                "catalog_code_hint": meta.get("catalog_code_hint", ""),
                "publisher_lookup_pending": meta.get("publisher_lookup_pending", False),
                "ocr_priority": meta.get("ocr_priority", "normal"),
                "type_display": f"{meta.get('file_type','?')} / "
                f"{('Needs OCR' if meta.get('needs_ocr_deep_scan') else (meta.get('subject_categories') or ['Unknown'])[0])}",
            }
            row["doc_id"] = self._make_doc_id(
                row["source_path"], row["last_modified"]
            )
            rows.append(row)

        _dual_path_srm_intake(
            self.post,
            kind="scanner.scan_summary",
            data={
                "files_found": len(rows),
                "watching": self._watching,
                "input_dir": self._input_dir,
                "ts": time.time(),
            },
        )
        self.post.to_TRACER({
            "opcode": "SCAN_SUMMARY",
            "payload": {"files_found": len(rows), "watching": self._watching},
        })
        self._last_error = None
        return rows

    def _save_scan_index_json(self, rows: List[Dict[str, Any]]) -> Optional[str]:
        if not os.path.isdir(self._output_dir):
            try:
                os.makedirs(self._output_dir, exist_ok=True)
            except Exception as e:
                self._last_error = f"cannot create output_dir: {e}"
                _dual_path_srm_intake(
                    self.post,
                    kind="scanner.error",
                    data={"message": self._last_error},
                )
                return None
        index_path = os.path.join(self._output_dir, "scan_index.json")
        current: Dict[str, Any] = {}
        if os.path.isfile(index_path):
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    current = json.load(f) or {}
            except Exception:
                current = {}
        for row in rows:
            did = row.get("doc_id")
            if did:
                current[did] = row
        # prune stale
        for did in list(current.keys()):
            rec = current.get(did, {})
            sp = rec.get("source_path", "")
            od = rec.get("output_dir", "")
            if not os.path.isfile(sp) and not os.path.isdir(od):
                current.pop(did, None)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        _dual_path_srm_intake(
            self.post,
            kind="scanner.index_saved",
            data={"path": index_path, "rows": len(rows), "ts": time.time()},
        )
        self.post.to_TRACER({
            "opcode": "SCAN_EXPORT_OK",
            "payload": {"json_path": index_path, "rows": len(rows)},
        })
        return index_path

    # ── Metadata helpers (legacy, dependency-aware) ────────────────────────────
    def _safe_folder_name(self, name: str) -> str:
        if not name:
            name = "book"
        for bad in '<>:"/\\|?*':
            name = name.replace(bad, "_")
        name = name.strip() or "book"
        return name

    def _make_doc_id(self, source_path: str, last_modified: str) -> str:
        h = hashlib.sha256()
        h.update(source_path.encode())
        h.update(last_modified.encode())
        return h.hexdigest()[:16]

    # ISBN utils
    def _isbn10_ok(self, s: str) -> bool:
        if len(s) != 10:
            return False
        tot = 0
        for i, c in enumerate(s):
            v = 10 if (c in "Xx" and i == 9) else (int(c) if c.isdigit() else -1000)
            tot += (i + 1) * v
        return tot % 11 == 0

    def _isbn13_ok(self, s: str) -> bool:
        if len(s) != 13 or not s.isdigit():
            return False
        ssum = sum(
            (int(d) if i % 2 == 0 else 3 * int(d)) for i, d in enumerate(s[:12])
        )
        return (10 - (ssum % 10)) % 10 == int(s[12])

    def _isbn_candidates(self, *blobs: str) -> List[str]:
        pat = re.compile(
            r"(?:ISBN[:\s]*)?(?P<num>(?:97[89][\-\s]?\d{1,5}[\-\s]?\d{1,7}[\-\s]?\d{1,7}[\-\s]?\d)|"
            r"(?:\d{1,5}[\-\s]?\d{1,7}[\-\s]?\d{1,7}[\-\s]?[\dXx]))"
        )
        seen, out = set(), []
        for b in blobs:
            if not b:
                continue
            for m in pat.finditer(b):
                raw = re.sub(r"[\s\-]", "", m.group("num")).upper()
                if len(raw) == 13 and self._isbn13_ok(raw) and raw not in seen:
                    seen.add(raw)
                    out.append(raw)
                if len(raw) == 10 and self._isbn10_ok(raw) and raw not in seen:
                    seen.add(raw)
                    out.append(raw)
        return out

    def _peek_pdf(self, pdf_path: str) -> Dict[str, Any]:
        if PdfReader is None:
            return {
                "word_count_est": 0,
                "head": "",
                "tail": "",
                "scanned": True,
                "tail_present": False,
            }
        try:
            r = PdfReader(pdf_path)
        except Exception:
            return {
                "word_count_est": 0,
                "head": "",
                "tail": "",
                "scanned": True,
                "tail_present": False,
            }
        total = len(r.pages) or 0

        def _txt(p):
            try:
                return r.pages[p].extract_text() or ""
            except Exception:
                return ""

        head = " ".join(_txt(p) for p in range(min(5, total)))
        tail = " ".join(_txt(p) for p in range(max(0, total - 5), total))
        combined = re.sub(r"\s+", " ", (head + " " + tail)).strip()
        wc = len(combined.split())
        scanned = (len(head.strip()) < 20 and len(tail.strip()) < 20)
        return {
            "word_count_est": wc,
            "head": head[:2000],
            "tail": tail[:2000],
            "scanned": scanned,
            "tail_present": total > 0,
        }

    def _pdf_docinfo(self, pdf_path: str) -> Dict[str, Any]:
        """
        Try to harvest PDF document info (title/author/subject/keywords/dates).
        Keeps it light and tolerant so scanner doesn't fail on bad files.
        """
        out: Dict[str, Any] = {}
        if PdfReader is None:
            return out
        try:
            r = PdfReader(pdf_path)
            meta = getattr(r, "metadata", None) or {}
        except Exception:
            return out

        def _clean(val):
            if not val:
                return None
            try:
                s = str(val).strip()
                return s.strip("\x00") or None
            except Exception:
                return None

        out["title"] = _clean(meta.get("/Title") or getattr(meta, "title", None))
        out["author"] = _clean(meta.get("/Author") or getattr(meta, "author", None))
        out["subject"] = _clean(meta.get("/Subject") or getattr(meta, "subject", None))
        kw_raw = meta.get("/Keywords") or getattr(meta, "keywords", None)
        if kw_raw:
            kws = [
                k.strip() for k in re.split(r"[;,]", str(kw_raw)) if k and k.strip()
            ]
            if kws:
                out["keywords"] = kws
        # PDF CreationDate format: D:YYYYMMDDHHmmSS...
        def _parse_pdf_date(s: Optional[str]) -> Optional[str]:
            if not s:
                return None
            s = str(s)
            if s.startswith("D:"):
                s = s[2:]
            try:
                dt = _dt.datetime.strptime(s[:14], "%Y%m%d%H%M%S")
                return dt.isoformat()
            except Exception:
                try:
                    dt = _dt.datetime.strptime(s[:8], "%Y%m%d")
                    return dt.date().isoformat()
                except Exception:
                    return None
        out["creation_date"] = _parse_pdf_date(
            meta.get("/CreationDate") or getattr(meta, "creation_date", None)
        )
        out["mod_date"] = _parse_pdf_date(
            meta.get("/ModDate") or getattr(meta, "modification_date", None)
        )
        return out

    def _docx_wc(self, path: str) -> int:
        if _docx is None:
            return 0
        try:
            d = _docx.Document(path)
            text = " ".join(p.text for p in d.paragraphs if p.text)
            text = re.sub(r"\s+", " ", text).strip()[:5000]
            return len(text.split())
        except Exception:
            return 0

    def _epub_meta(self, path: str) -> Dict[str, Any]:
        meta = {
            "title": None,
            "creators": [],
            "language": None,
            "identifier": None,
            "subject_categories": [],
            "description": None,
            "publication_date": None,
            "publisher": None,
        }
        if _epub is None:
            return meta
        try:
            book = _epub.read_epub(path)

            def first(tag):
                v = book.get_metadata("DC", tag)
                return v[0][0] if v else None

            def many(tag):
                v = book.get_metadata("DC", tag)
                return [x[0] for x in v] if v else []

            meta.update(
                {
                    "title": first("title"),
                    "creators": many("creator"),
                    "language": first("language"),
                    "identifier": first("identifier"),
                    "subject_categories": many("subject"),
                    "description": first("description"),
                    "publication_date": first("date"),
                    "publisher": first("publisher"),
                }
            )
        except Exception:
            pass
        return meta

    def _guess_meta(self, file_path: str) -> Dict[str, Any]:
        base = os.path.basename(file_path)
        stem, ext = os.path.splitext(base)
        ext = ext.lower()
        last_modified = _dt.datetime.fromtimestamp(
            os.path.getmtime(file_path)
        ).isoformat(timespec="seconds")

        def _parse_filename_author_title(name: str) -> tuple[str | None, str | None]:
            # common pattern: "Author - Title.ext"
            if " - " in name:
                left, right = name.split(" - ", 1)
                return left.strip() or None, right.strip() or None
            if "-" in name:
                left, right = name.split("-", 1)
                return left.strip() or None, right.strip() or None
            return None, None

        meta: Dict[str, Any] = {
            "title": stem,
            "creators": ["Unknown"],
            "language": "en",
            "identifier": "",
            "subject_categories": [],
            "description": "",
            "publication_date": "",
            "publisher": "Unknown",
            "series_info": "",
            "content_rating": None,
            "fiction_nonfiction": "Unknown",
            "word_count": 0,
            "file_type": ext.lstrip("."),
            "last_modified": last_modified,
            "needs_ocr_deep_scan": False,
            "chosen_isbn": "",
            "isbn_candidates": [],
            "publisher_hint": "",
            "catalog_code_hint": "",
            "publisher_lookup_pending": False,
            "ocr_priority": "normal",
        }

        file_author, file_title = _parse_filename_author_title(stem)
        if file_title and (not meta["title"] or meta["title"] == stem):
            meta["title"] = file_title
        if file_author and meta["creators"] == ["Unknown"]:
            meta["creators"] = [file_author]

        if ext == ".epub":
            e = self._epub_meta(file_path)
            for k in (
                "title",
                "language",
                "identifier",
                "description",
                "publication_date",
                "publisher",
            ):
                if e.get(k):
                    meta[k] = e[k]
            if e.get("creators"):
                meta["creators"] = e["creators"]
            if e.get("subject_categories"):
                meta["subject_categories"] = e["subject_categories"]
            isbns = self._isbn_candidates(
                stem,
                e.get("identifier", "") or "",
                e.get("description", "") or "",
                e.get("title", "") or "",
            )
            meta["isbn_candidates"] = isbns
            meta["chosen_isbn"] = isbns[0] if isbns else ""

        elif ext == ".pdf":
            peek = self._peek_pdf(file_path)
            meta["word_count"] = peek["word_count_est"]
            meta["needs_ocr_deep_scan"] = peek["scanned"]
            pdf_info = self._pdf_docinfo(file_path)
            if pdf_info.get("title") and (not meta["title"] or meta["title"] == stem):
                meta["title"] = pdf_info["title"]
            if pdf_info.get("author") and meta["creators"] == ["Unknown"]:
                meta["creators"] = [pdf_info["author"]]
            if pdf_info.get("creation_date"):
                meta["publication_date"] = meta["publication_date"] or pdf_info["creation_date"]
            if pdf_info.get("subject"):
                meta["subject_categories"] = (meta.get("subject_categories") or []) + [pdf_info["subject"]]
            if pdf_info.get("keywords"):
                meta["subject_categories"] = list(
                    set((meta.get("subject_categories") or []) + pdf_info["keywords"])
                )
            if pdf_info.get("mod_date"):
                meta["last_modified"] = pdf_info["mod_date"]
            isbns = self._isbn_candidates(
                stem, peek.get("head", ""), peek.get("tail", "")
            )
            meta["isbn_candidates"] = isbns
            meta["chosen_isbn"] = isbns[0] if isbns else ""
            if not meta["title"] or meta["title"] == stem:
                for line in (peek.get("head", "") or "").splitlines():
                    l = line.strip()
                    if l and len(l) <= 120 and "copyright" not in l.lower():
                        meta["title"] = l
                        break
            if (
                meta["needs_ocr_deep_scan"]
                and peek.get("tail_present")
                and not meta["chosen_isbn"]
            ):
                meta["ocr_priority"] = "publisher_id_tail"

        elif ext in (".doc", ".docx"):
            meta["word_count"] = self._docx_wc(file_path)
            if _docx is not None:
                try:
                    d = _docx.Document(file_path)
                    core = getattr(d, "core_properties", None)
                    if core:
                        if getattr(core, "title", None):
                            t = (core.title or "").strip()
                            if t:
                                meta["title"] = t
                        if getattr(core, "author", None):
                            a = (core.author or "").strip()
                            if a:
                                meta["creators"] = [a]
                        if getattr(core, "language", None):
                            lg = (core.language or "").strip()
                            if lg:
                                meta["language"] = lg
                        if getattr(core, "created", None):
                            meta["publication_date"] = str(core.created)
                except Exception:
                    pass
            isbns = self._isbn_candidates(stem)
            meta["isbn_candidates"] = isbns
            meta["chosen_isbn"] = isbns[0] if isbns else ""

        # fiction vs non-fiction + simple subject hints from filename
        hay = stem.lower()
        if any(
            t in hay
            for t in [
                "novel",
                "fantasy",
                "sci-fi",
                "thriller",
                "romance",
                "chapter",
                "prologue",
            ]
        ):
            meta["fiction_nonfiction"] = "Fiction"
        elif any(
            t in hay
            for t in [
                "introduction",
                "preface",
                "foreword",
                "references",
                "bibliography",
                "index",
                "guide",
                "manual",
                "research",
                "method",
            ]
        ):
            meta["fiction_nonfiction"] = "Non-fiction"
        cats = set(meta.get("subject_categories") or [])
        if any(t in hay for t in ["biology", "physics", "chem", "quantum", "genetic"]):
            cats.add("Science")
        if any(t in hay for t in ["history", "empire", "civilization", "biography"]):
            cats.add("History")
        if any(t in hay for t in ["business", "leadership", "marketing", "sales"]):
            cats.add("Business")
        meta["subject_categories"] = list(cats)
        return meta

    # ── Enqueue emit (NS/PLAN + TRACER + SRM) ─────────────────────────────────
    def _record_enqueue(self, path: str) -> None:
        pkt = {"path": path, "submitted_by": self.ACTOR_NAME, "submitted_at": time.time()}
        try:
            self.post.route("PLAN", {"opcode": "SCAN_FILE_ENQUEUED", "payload": pkt})
        except Exception:
            pass
        try:
            self.post.to_TRACER({"opcode": "SCAN_FILE_ENQUEUED", "payload": pkt})
        except Exception:
            pass
        _dual_path_srm_intake(self.post, kind="scanner.file_enqueued", data=pkt)
