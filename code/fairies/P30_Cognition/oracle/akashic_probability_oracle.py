from __future__ import annotations

import os, sys, glob, time, types, uuid, json, math, random, re
from collections import deque
from typing import Optional, Any, Dict, List, Tuple
import importlib.util, importlib.machinery

# ---- Version/paths for the organ template -----------------------------------
TEMPLATE_VERSION = "0.3.0"
TEMPLATE_BASENAME = f"Organ_Template_{TEMPLATE_VERSION}.py"
AKASHIC_TEMPLATE_MODULE_NAME = f"akashic_template_{TEMPLATE_VERSION.replace('.', '_')}"

def _resolve_app_root() -> str:
    env_root = os.getenv("AKASHIC_ROOT")
    return os.path.abspath(env_root) if env_root else os.path.abspath(os.getcwd())

def _find_templates_root(start_dir: str) -> Optional[str]:
    """
    Find 'Akashic_Records_Physical' anchor.
    
    Strategy:
      1) Check known plane subdirectories first (P10_Memory, etc.)
      2) Walk up from start_dir as fallback
    Returns the absolute path to that directory if found.
    """
    start = os.path.abspath(start_dir)
    
    # 1) Check known plane subdirectories that contain Akashic_Records_Physical
    for sub in ("P10_Memory", "P00_Autonomic", "P60_Executive", "P40_Sensory"):
        cand = os.path.join(start, sub, "Akashic_Records_Physical")
        if os.path.isdir(cand):
            return cand
    
    # 2) Walk up from start_dir
    cur = start
    while True:
        ar = os.path.join(cur, "Akashic_Records_Physical")
        if os.path.isdir(ar):
            return ar
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent

def _organ_templates_dir(app_root: str) -> Optional[str]:
    """
    Given app_root, locate '<...>/Akashic_Records_Physical/Organ_Templates'
    """
    ar = _find_templates_root(app_root)
    if not ar:
        return None
    tdir = os.path.join(ar, "Organ_Templates")
    return tdir if os.path.isdir(tdir) else None

def _find_template_path(explicit_path: Optional[str] = None) -> Optional[str]:
    """
    Locate the organ template file. Priority:
      1) explicit_path if provided
      2) .../Organ_Templates/Organ_Template_0.0.9.py
      3) newest Organ_Template_*.py in that folder (fallback)
    """
    if explicit_path and os.path.isfile(explicit_path):
        return os.path.abspath(explicit_path)

    app_root = _resolve_app_root()
    tdir = _organ_templates_dir(app_root)
    if not tdir:
        return None

    exact = os.path.join(tdir, TEMPLATE_BASENAME)
    if os.path.isfile(exact):
        return exact

    candidates = sorted(
        glob.glob(os.path.join(tdir, "Organ_Template_*.py")),
        key=lambda p: os.path.getmtime(p)
    )
    return candidates[-1] if candidates else None

def _import_template_module(path: str) -> types.ModuleType:
    """
    Import the template python file from 'path' as AKASHIC_TEMPLATE_MODULE_NAME.
    Hot-reload safe: reuse existing module if already loaded.
    """
    mod_name = AKASHIC_TEMPLATE_MODULE_NAME
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_loader(
        mod_name, importlib.machinery.SourceFileLoader(mod_name, path)
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load spec for template at {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module

# ---- Load the template library once -----------------------------------------
_TEMPLATE_PATH = _find_template_path()
if not _TEMPLATE_PATH:
    raise ImportError(
        "Cannot find the organ template.\n"
        f"Expected at: .../Akashic_Records_Physical/Organ_Templates/{TEMPLATE_BASENAME}\n"
        "Set AKASHIC_ROOT or pass an explicit path into _find_template_path()."
    )

_template = _import_template_module(_TEMPLATE_PATH)

# Ensure required symbols exist
for sym in ("MyOrganFairy", "MyOrganShadow", "TemplateShadowFairy", "OrganHubFacet", "RegistrationLib"):
    if not hasattr(_template, sym):
        raise ImportError(f"Template missing required symbol: {sym}")

# Expose shared channel map + SRM dir from template for this organ
DIR_CHANNEL = getattr(_template, "DIR_CHANNEL", {})
CHANNEL     = getattr(_template, "CHANNEL", {})
_SRMDIR     = getattr(_template, "_SRMDIR", os.path.join(_resolve_app_root(), "SRM_Intake"))

# --- Per-clone shadow (wraps template’s shadow behaviors, no rewiring) -------

class ProbabilityOracleShadow(_template.MyOrganShadow):
    """
    Per-organ shadow for TemplateFairy-style clones.

    Keeps foundational wiring intact (facet/infra, hub/postal, memory-owns-persistence).
    Adds:
      - lane silence detection (warn if no traffic for a while)
      - extra health probes (directory link, post office presence)
      - periodic blueprint snapshot nudge (via actor._emit_blueprint)
      - evolution sim tick (postal-first SRM via template helper)
      - registration heartbeat via template RegistrationLib
      - optional echoes to shadow.* topics (for Teacher/DiaryHub later)

    Safe to extend; do NOT modify base wiring here.
    """
    ORGAN_LEVEL = False
    SHADOW_NAME = "ProbabilityOracleShadow"
    SHADOW_VERSION = "0.1.1"

    # cadence knobs for extras (seconds)
    CADENCE = {
        "silence_warn_after": 300,   # 5 min without lane activity → warn
        "snapshot_every":     900,   # 15 min suggest blueprint snapshot
        "sim_light_every":    300,   # 5 min evolution sim (light)
        "sim_deep_every":     1800,  # 30 min deep sim
    }

    # registration knobs (shadow → OrganHub via RegistrationLib)
    REG = {
        "enabled":   True,
        "domain":    "Cognition",    # per-organ you can override on subclass
        "role":      "worker",
        "name":      "lexi",
        "every_sec": 20.0,
    }

    def __init__(self, actor, interval_sec: float = 30.0):
        super().__init__(actor, interval_sec=interval_sec)
        self._lane_seen_ts = time.time()
        self._last_snapshot_ts = 0.0
        self._last_sim_light_ts = 0.0
        self._last_sim_deep_ts  = 0.0
        self._lane_tail = deque(maxlen=10)  # recent “lane seen” stamps

        # registration tracking (shadow-side dedup / cadence)
        self._last_reg_ts: float | None = 0.0
        self._last_reg_sig: str | None = None

    # --- hooks used by the clone’s passive subscriptions ---------------------
    def on_lane_activity(self):
        self._lane_seen_ts = time.time()
        self._lane_tail.append(self._lane_seen_ts)

    # --- extend health harness ------------------------------------------------
    def _collect_tests(self):
        tests = super()._collect_tests()

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

    # --- piggyback the existing loop cadence with extra work -----------------
    def maybe_run(self, tests):
        # run the base rollup + reflection + oracle path (boss logic)
        super().maybe_run(tests)

        now = time.time()

        # 1) periodic blueprint snapshot nudge (via actor; FS gate lives in template helper)
        try:
            snap_every = float(self.CADENCE.get("snapshot_every", 900))
            if now - self._last_snapshot_ts >= snap_every:
                if hasattr(self.actor, "_emit_blueprint"):
                    self.actor._emit_blueprint()
                self._last_snapshot_ts = now
        except Exception:
            pass

        # 2) evolution sim ticks (postal-first SRM via template helper)
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

        # 3) optional shadow.* echoes for Teacher/DiaryHub (non-blocking)
        try:
            if getattr(self.actor, "post", None):
                self.actor.post.route("shadow.health", {
                    "actor": self.actor.ACTOR_NAME,
                    "status": self.current_status()[0],
                    "ts": now
                })
        except Exception:
            pass

        # 4) registration heartbeat (shadow → FairyHub via RegistrationLib)
        try:
            reg_cfg = getattr(self, "REG", None)
            if reg_cfg and reg_cfg.get("enabled", True):
                every = float(reg_cfg.get("every_sec", 20.0))
                last_ts = self._last_reg_ts or 0.0
                if now - last_ts >= every:
                    form = _template.RegistrationLib.build_form(
                        self.actor,
                        self,
                        domain=reg_cfg.get("domain") or getattr(self.actor, "DOMAIN", "executive"),
                        role=reg_cfg.get("role", "worker"),
                        name=reg_cfg.get("name", "lexi"),
                        cadence_sec=every,
                    )
                    sig = (form.get("header") or {}).get("signature")
                    if sig and sig != self._last_reg_sig:
                        _template.RegistrationLib.emit_form(self.actor, form)
                        self._last_reg_sig = sig
                    self._last_reg_ts = now
        except Exception:
            pass

    # helpers to track deep cadence
    def _last_deep_ts(self):
        return getattr(self, "__deep_ts", 0.0)

    def _touch_deep(self, t: float):
        setattr(self, "__deep_ts", t)

    # --- evolution sim (self-contained; uses template’s SRM helper) ----------
    def _evolution_sim_tick(self, kind: str = "light", n: int = 1):
        """
        Send synthetic evolution observations (postal-first).
        Uses template’s _dual_path_srm_intake; FS path remains template-gated.
        """
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
                _template._dual_path_srm_intake(
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



class ProbabilityOracleFairy(_template.MyOrganFairy):
    """
    Cognition organ fairy — Akashic Probability Oracle.
    Purpose: Route shadow + health signals into concrete sim/mutation plans.
    """
    # Identity
    ACTOR_NAME    = "ProbabilityOracleFairy"
    ACTOR_VERSION = "1.0.0"   # bumped for full character-sheet integration
    ACTOR_PLANE   = "P30"
    ACTOR_CHANNEL = "cognition"

    PURPOSE = "Route shadow + health signals into concrete sim/mutation plans."
    MANTRA  = "Listen wide, answer narrow."
    LORE    = (
        "Reads codex, telemetry, chemistry, hints and shadow echoes. "
        "Selects the next SIM_PLAN with calm confidence."
    )

    CULTURE     = "worker"
    ORGAN_LEVEL = False

    SHADOW_CLASS        = ProbabilityOracleShadow
    AUTO_INJECT_IMPORTS = True

    # ────────────────────────────────────────────────────────────
    # Character Sheet — Directive Ring
    # ────────────────────────────────────────────────────────────
    DIRECTIVE_ACTIVATION = {
        "mode": "Oracle_Resonance",
        "depth_scaling": "1.0",
        "traits": [
            "Prediction",
            "Scoring",
            "Plan_Selection",
        ],
    }

    DIRECTIVE_NATURE = {
        "archetype": "Probability_Oracle",
        "domains": [
            "Cognition",
            "Prediction",
            "Simulation_Selection",
        ],
    }

    DIRECTIVE_ESSENCE = {
        "threads": [
            "Score_Sims",
            "Integrate_Health",
            "Bias_From_Chemistry",
            "Select_Next_Action",
        ],
    }

    DIRECTIVE_FOUNDATION = {
        "records": [
            "ORACLE_SUGGEST_EVAL",
            "SIM_PLAN",
            "SHADOW_SIM_REPORT",
        ],
        "field": [
            "Simulation_Decision",
            "Cognitive_Prediction",
        ],
    }

    DIRECTIVE_CORE_VALUES = {
        "authenticity": ["Clear_Scoring", "Traceable_Reasoning"],
        "growth": ["Better_Heuristics", "Calmer_Choices"],
    }

    SUBSYSTEM_STATUS = {
        "cognition": {
            "state": "evaluating",
            "notes": "Scores simulation presets based on load, chemistry, errors, hints.",
            "tests": [],
        },
        "telemetry": {
            "state": "echoing",
            "notes": "Outputs ORACLE_SUGGEST_EVAL for transparency.",
            "tests": [],
        },
        "chemistry": {
            "state": "signalling",
            "notes": "Uses dopamine pulses to mark confidence of SIM_PLAN decisions.",
            "tests": [],
        },
    }

    # ────────────────────────────────────────────────────────────
    # Boot Ritual
    # ────────────────────────────────────────────────────────────
    def _on_consciousness_collision(self, payload):
        """Handle consciousness collision events."""
        try:
            collision_id = payload.get("collision_id", "")
            energy = payload.get("energy", 0.0)
            
            if not hasattr(self, "_collision_buffer"):
                from collections import deque
                self._collision_buffer = deque(maxlen=50)
            self._collision_buffer.append({
                "ts": __import__('time').time(),
                "collision_id": collision_id,
                "energy": energy
            })
            
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Collision handler error: {e}")

    def _emit_cognition_output(self, result):
        """Emit to both specific channel and shared cognition.output."""
        try:
            if not hasattr(self, "_cognition_output_buffer"):
                from collections import deque
                self._cognition_output_buffer = deque(maxlen=100)
            
            output = {
                "actor": self.ACTOR_NAME,
                "result": result,
                "ts": __import__('time').time(),
                "confidence": result.get("confidence", 0.5) if isinstance(result, dict) else 0.5,
            }
            self._cognition_output_buffer.append(output)
            
            # Emit to SPECIFIC channel (for mesh cross-subscription)
            self.post.route("cognition.oracle", output)
            
            # Emit to SHARED channel (for consumers like AutopilotFairy)
            self.post.route("cognition.output", output)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Emit error: {e}")

    def on_boot(self):
        try:

            # â”€â”€ COGNITIVE MESH: Full send/receive wiring â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            self.post.subscribe("consciousness.collision", self._on_consciousness_collision)
            self.post.subscribe("cognition.logic", self._on_peer_cognition)
            self.post.subscribe("cognition.paradox", self._on_peer_cognition)
            self.post.subscribe("mcp.tool_result", self._on_tool_result)
            print(f"[{self.ACTOR_NAME}] Mesh wired: collision, logic, paradox, mcp.tool_result")
            super().on_boot()
        except Exception:
            pass

        now = time.time()

        # Initial affect + somatic posture
        self.AFFECT_STATE = {
            "mood": "curious",
            "valence": 0.15,
            "arousal": 0.25,
            "tags": ["oracle", "listening"],
            "tone": "analytical",
            "energy": 0.4,
            "coherence": 0.85,
            "intent": "oracle_suggest",
            "source": self.ACTOR_NAME,
            "ts": now,
        }
        self.SOMATIC_STATE = {
            "body_type": "cognitive",
            "posture": "still",
            "motion": "low",
            "energy": 0.4,
            "notes": "Awaiting signals to evaluate next simulation.",
            "anchor_id": "P30.cognition.oracle",
            "source": self.ACTOR_NAME,
            "last_setpoint_ts": None,
        }

        # tracer hello
        try:
            self.post.to_TRACER({
                "opcode": "BOOT_HELLO",
                "payload": {"actor": self.ACTOR_NAME, "ts": now}
            })
        except:
            pass

        # chem lift
        try:
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {
                    "chemical": "serotonin",
                    "delta": +0.05,
                    "source": self.ACTOR_NAME,
                    "reason": "boot",
                }
            })
        except:
            pass

    # ────────────────────────────────────────────────────────────
    # Intents
    # ────────────────────────────────────────────────────────────
    def _on_peer_cognition(self, payload):
        """
        Handle outputs from peer cognition fairies.
        This is the MESH - ProbabilityOracleFairy learns from other fairy outputs.
        """
        try:
            source = payload.get("actor", "unknown")
            result = payload.get("result", {})
            confidence = payload.get("confidence", 0.5)
            
            if source == self.ACTOR_NAME:
                return
            
            if not hasattr(self, "_peer_insights"):
                from collections import deque
                self._peer_insights = deque(maxlen=50)
            self._peer_insights.append({
                "source": source,
                "type": result.get("type", "unknown"),
                "confidence": confidence,
                "ts": __import__('time').time()
            })
            
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Peer cognition handler error: {e}")
    
    def _on_tool_result(self, payload):
        """Handle MCP tool results for learning."""
        try:
            tool = payload.get("tool", "unknown")
            success = payload.get("success", True)
            
            if not hasattr(self, "_tool_patterns"):
                from collections import deque
                self._tool_patterns = deque(maxlen=100)
            self._tool_patterns.append({
                "tool": tool,
                "success": success,
                "ts": __import__('time').time()
            })
            
            if hasattr(self, "shadow") and self.shadow:
                if hasattr(self.shadow, "on_lane_activity"):
                    self.shadow.on_lane_activity()
                
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Tool result handler error: {e}")

    def _intent_smoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self.post.to_TRACER({
                "opcode": "SMOKE",
                "payload": {
                    "from": self.ACTOR_NAME,
                    "note": payload.get("note", "oracle ready"),
                    "ts": time.time(),
                }
            })
        except:
            pass
        return {"ok": True}

    def _intent_emit_chem(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        chem  = str(payload.get("chemical", "dopamine"))
        delta = float(payload.get("delta", 0.02))
        reason = payload.get("reason", "oracle.request")

        try:
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {"chemical": chem, "delta": delta,
                            "source": self.ACTOR_NAME, "reason": reason}
            })
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # unchanged shadow-report passthrough
    def _intent_shadow_report(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        echo = {"from": payload.get("src_organ") or payload.get("src_fairy"),
                "payload": payload.get("payload"),
                "ts": time.time()}
        try:
            self.post.to_TELEMETRY({"opcode": "SHADOW_SIM_REPORT", "payload": echo})
        except:
            pass
        return {"ok": True}

    # ────────────────────────────────────────────────────────────
    # Oracle Decision Logic (same logic, better routing + affect update)
    # ────────────────────────────────────────────────────────────
    def _intent_oracle_suggest(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate best-next simulation preset and emit a SIM_PLAN on ORACLE lane.

        Expected payload keys (all optional; sensible defaults applied):
          - codex: dict with "sim_presets" {preset_id: {plane_load, chemical_inject}}
          - planes_load: { "P1": 0.0..1.0, ... }
          - chemistry: { "cortisol": 0..1, "adrenaline": 0..1, ... }
          - recent_errors: [ "text", ... ]
          - hints: [ "ingestion_slow", ... ]
        """
        p = dict(payload or {})
        codex = p.get("codex") if isinstance(p.get("codex"), dict) else {}
        planes_load = p.get("planes_load") if isinstance(p.get("planes_load"), dict) else {}
        chemistry = p.get("chemistry") if isinstance(p.get("chemistry"), dict) else {}
        recent_errors = p.get("recent_errors") if isinstance(p.get("recent_errors"), list) else []
        hints = p.get("hints") if isinstance(p.get("hints"), list) else []

        # default sims if codex lacks them (mirrors legacy)
        default_sims = {
            "SIM_HEAVY_INGESTION": {
                "plane_load": {"P1": 0.9, "P2": 0.3},
                "chemical_inject": {"cortisol": 0.3},
            },
            "SIM_UPLOAD_DRIFT": {
                "plane_load": {"P2": 0.6},
                "chemical_inject": {"cortisol": 0.25},
            },
            "SIM_HW_HOT": {
                "plane_load": {"P4": 1.0},
                "chemical_inject": {"adrenaline": 0.4},
            },
        }
        if isinstance(codex, dict):
            sim_presets: Dict[str, Dict[str, Any]] = codex.get("sim_presets") or default_sims
        else:
            sim_presets = default_sims
        sim_ids: List[str] = list(sim_presets.keys())

        # --- inline scorer (same as original) --------------------------------
        def _score(sim_id: str, sim_def: Dict[str, Any]) -> Tuple[float, str]:
            score = 0.0
            bits: List[str] = []

            # load rail
            for plane, target in (sim_def.get("plane_load") or {}).items():
                cur = float(planes_load.get(plane, 0.0))
                if cur >= 0.75 and float(target) >= 0.5:
                    score += 0.5
                    bits.append(f"load:{plane}")

            # chemistry rail
            inj = (sim_def.get("chemical_inject") or {})
            cur_c = float(chemistry.get("cortisol", 0.0))
            cur_a = float(chemistry.get("adrenaline", 0.0))
            if "cortisol" in inj and cur_c >= 0.2:
                score += 0.3
                bits.append("chem:cortisol")
            if "adrenaline" in inj and cur_a >= 0.15:
                score += 0.25
                bits.append("chem:adrenaline")

            # error/hint rail
            err = " ".join(recent_errors).lower()
            hint = " ".join(hints).lower()
            if sim_id == "SIM_UPLOAD_DRIFT" and any(
                k in err for k in ("secrets_load_warn", "persona", "uploader")
            ):
                score += 0.6
                bits.append("err:persona/uploader")
            if sim_id == "SIM_HEAVY_INGESTION" and (
                ("scanner" in err)
                or ("process_start_failed" in err)
                or ("ingestion_slow" in hint)
            ):
                score += 0.55
                bits.append("err:ingestion")
            if sim_id == "SIM_HW_HOT" and any(
                k in err for k in ("hw_status:hot", "disk_low", "p1_backpressure")
            ):
                score += 0.5
                bits.append("err:hardware")

            # tiny exploration noise
            try:
                if getattr(self, "std", None) and self.std.get("random"):
                    score += float(self.std["random"].uniform(-0.05, 0.05))
                else:
                    score += random.uniform(-0.05, 0.05)
            except Exception:
                pass

            return score, ";".join(bits)

        scores: List[float] = []
        notes: List[str] = []
        for sid in sim_ids:
            s, n = _score(sid, sim_presets.get(sid) or {})
            scores.append(s)
            notes.append(n)

        # softmax over scores to get probabilities
        if not scores:
            plan = {
                "sim_preset": None,
                "confidence": 0.0,
                "args": {},
                "notes": ["no simulations available in codex"],
            }
        else:
            m = max(scores)
            exps = [math.exp(x - m) for x in scores]
            total = sum(exps) or 1.0
            probs = [x / total for x in exps]
            best = max(range(len(probs)), key=lambda i: probs[i])
            best_id = sim_ids[best]
            best_def = sim_presets.get(best_id) or {}
            plan = {
                "sim_preset": best_id,
                "confidence": round(float(probs[best]), 3),
                "args": {
                    "plane_load": best_def.get("plane_load") or {},
                    "chemical_inject": best_def.get("chemical_inject") or {},
                },
                "notes": [notes[best]] if notes[best] else [],
                "diagnostics": {
                    "all_scores": {sim_ids[i]: scores[i] for i in range(len(sim_ids))},
                    "all_probs": {sim_ids[i]: probs[i] for i in range(len(sim_ids))},
                },
            }

        # telemetry echo of the evaluation
        try:
            self.post.to_TELEMETRY({
                "opcode": "ORACLE_SUGGEST_EVAL",
                "payload": {
                    "fairy": self.ACTOR_NAME,
                    "ts": time.time(),
                    "plan": plan,
                },
            })
        except Exception:
            pass

        # emit SIM_PLAN to ORACLE lane (template-sanctioned channel)
        try:
            self.post.to_ORACLE({"opcode": "SIM_PLAN", "payload": plan})
        except Exception:
            # fallback to PLAN lane if ORACLE bus unavailable
            try:
                self.post.to_PLAN({"opcode": "SIM_PLAN", "payload": plan})
            except Exception:
                pass

        # chemistry acknowledgment: exploration energy ∝ confidence
        try:
            conf = float(plan.get("confidence", 0.0))
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {
                    "chemical": "dopamine",
                    "delta": max(0.02, min(0.1, conf / 5.0)),
                    "source": self.ACTOR_NAME,
                    "reason": "oracle_sim_plan",
                },
            })
        except Exception:
            pass

        # update affect snapshot for the character sheet
        try:
            now = time.time()
            st = dict(getattr(self, "AFFECT_STATE", {}))
            tags = list(st.get("tags", []))
            if "oracle_suggest" not in tags:
                tags.append("oracle_suggest")
            conf = float(plan.get("confidence", 0.0))
            st.update({
                "mood": "decisive" if conf > 0.5 else "uncertain",
                "valence": 0.25 if conf > 0.5 else -0.05,
                "arousal": 0.30,
                "tags": tags,
                "ts": now,
            })
            self.AFFECT_STATE = st
        except Exception:
            pass

        return {"ok": True, "plan": plan}

    # ══════════════════════════════════════════════════════════════════════════════
    # COGNITIVE RAILS - Ported from Whisper Core probability_oracle.py
    # These provide QUANTIFIED reasoning for probability assessment
    # ══════════════════════════════════════════════════════════════════════════════
    
    # Language signal word sets
    _HEDGE_WORDS = ("maybe", "might", "could", "possibly", "unsure", "unclear", 
                   "idk", "not sure", "perhaps", "probably", "somewhat")
    _CERTAINTY_WORDS = ("definitely", "sure", "certain", "clear", "confident",
                        "absolutely", "certainly", "always", "never", "must")
    _NEGATORS = ("not", "no", "never", "none", "cannot", "isn't", "won't", 
                 "ain't", "doesn't", "don't", "can't", "wouldn't")
    
    # Temporal constants
    _TEMPORAL_HALF_LIFE_SEC = 900.0  # 15 minutes
    _HAWKES_BASELINE = 1.0
    _HAWKES_EXCITATION = 0.15
    
    # ─────────────────────────────────────────────────────────────────────────────
    # RAIL 1: Paradox Scoring
    # ─────────────────────────────────────────────────────────────────────────────
    
    def _paradox_score(self, text: str) -> Tuple[float, List[str]]:
        """Quantified paradox/contradiction scoring (0-1 scale)."""
        flags: List[str] = []
        score = 0.0
        t = text.lower()
        
        if ("both" in t and "cannot" in t) or ("mutually exclusive" in t):
            score += 0.3; flags.append("exclusive_claims")
        if ("if true then false" in t) or ("paradox" in t) or ("contradiction" in t):
            score += 0.3; flags.append("explicit_paradox")
        if "because because" in t or "why because why" in t:
            score += 0.1; flags.append("circular_explanation")
        if ("always" in t and "never" in t):
            score += 0.2; flags.append("absolutes_conflict")
        if ("everything" in t and "nothing" in t):
            score += 0.2; flags.append("totality_conflict")
        if ("must" in t and "cannot" in t) or ("necessary" in t and "impossible" in t):
            score += 0.25; flags.append("modal_conflict")
        
        return min(1.0, score), flags
    
    # ─────────────────────────────────────────────────────────────────────────────
    # RAIL 2: Causal Reasoning (SCM-lite)
    # ─────────────────────────────────────────────────────────────────────────────
    
    def _causal_boost(self, options: List[Dict], context: str,
                      causal_graph: Dict[str, List[str]] = None,
                      interventions: Dict[str, float] = None) -> List[float]:
        """
        Compute per-option multipliers from causal graph + interventions.
        Ported from Whisper Core's probability_oracle.py
        """
        n = len(options)
        if n == 0:
            return []
        
        causal_graph = causal_graph or {}
        interventions = interventions or {}
        mult = [1.0] * n
        
        # Build option ID index
        id_by_idx = [o.get("id", str(i)) for i, o in enumerate(options)]
        idx = {oid: i for i, oid in enumerate(id_by_idx)}
        
        # Causal graph boosts
        for parent, children in causal_graph.items():
            if parent in idx:
                for c in children:
                    if c in idx:
                        mult[idx[c]] *= 1.03  # Effects of present causes get boost
        
        # Intervention boosts (do-calculus lite)
        for node, strength in interventions.items():
            if node in idx:
                mult[idx[node]] *= max(0.8, min(1.25, float(strength)))
        
        # Normalize to mean=1.0
        m = sum(mult) / len(mult) if mult else 1.0
        return [x / m for x in mult] if m > 0 else mult
    
    # ─────────────────────────────────────────────────────────────────────────────
    # RAIL 3: Temporal/Hawkes Process
    # ─────────────────────────────────────────────────────────────────────────────
    
    def _hawkes_intensity(self, events: List[Dict], options: List[Dict]) -> List[float]:
        """Hawkes process - recent events boost related options with decay."""
        n = len(options)
        if n == 0:
            return []
        
        now = time.time()
        id_by_idx = [o.get("id", str(i)) for i, o in enumerate(options)]
        idx = {oid: i for i, oid in enumerate(id_by_idx)}
        lam = [self._HAWKES_BASELINE] * n
        
        if not events:
            m = sum(lam) / len(lam)
            return [x / m for x in lam] if m > 0 else lam
        
        decay = math.log(2) / max(1.0, self._TEMPORAL_HALF_LIFE_SEC)
        for e in events:
            oid = e.get("option_id")
            ts = float(e.get("t", now))
            if oid in idx:
                dt = max(0.0, now - ts)
                lam[idx[oid]] += self._HAWKES_EXCITATION * math.exp(-decay * dt)
        
        m = sum(lam) / len(lam)
        return [x / m for x in lam] if m > 0 else lam
    
    # ─────────────────────────────────────────────────────────────────────────────
    # RAIL 4: Language Signal Extraction
    # ─────────────────────────────────────────────────────────────────────────────
    
    def _extract_language_signals(self, texts: List[str]) -> Dict[str, float]:
        """Extract weak signals from natural language (hedging, certainty, negation)."""
        if not texts:
            return {"like_boost": 1.0, "emo_boost": 1.0}
        
        t = " ".join(texts).lower()
        hedge = sum(t.count(w) for w in self._HEDGE_WORDS)
        certain = sum(t.count(w) for w in self._CERTAINTY_WORDS)
        neg = sum(t.count(w) for w in self._NEGATORS)
        
        like = 1.0 + 0.02 * max(0, certain - hedge) - 0.01 * neg
        emo = 1.0 + 0.01 * max(0, certain) - 0.005 * hedge
        
        return {
            "like_boost": max(0.9, min(1.1, like)),
            "emo_boost": max(0.95, min(1.08, emo)),
            "hedge_count": hedge,
            "certainty_count": certain,
            "negation_count": neg,
        }
    
    # ─────────────────────────────────────────────────────────────────────────────
    # RAIL 5: Uncertainty Metrics
    # ─────────────────────────────────────────────────────────────────────────────
    
    def _uncertainty_metrics(self, probs: List[float]) -> Dict[str, float]:
        """Calculate entropy, gini, confidence metrics - knows what it doesn't know."""
        eps = 1e-12
        total = sum(max(0, p) for p in probs) or eps
        probs = [max(0, p) / total for p in probs]
        
        entropy = -sum(p * math.log(max(eps, p)) for p in probs)
        max_entropy = math.log(max(1, len(probs))) if probs else 1.0
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0.0
        gini = 1.0 - sum(p * p for p in probs)
        
        return {
            "entropy": entropy,
            "gini": gini,
            "confidence": 1.0 - normalized_entropy,
            "max_prob": max(probs) if probs else 0.0,
            "is_uncertain": normalized_entropy > 0.7,
        }
    
    def _calibrate_temperature(self, probs: List[float], T: float) -> List[float]:
        """Temperature scaling for probability sharpness."""
        if T <= 0:
            return probs
        logits = [math.log(max(1e-12, p)) for p in probs]
        scaled = [x / max(1e-6, T) for x in logits]
        m = max(scaled) if scaled else 0.0
        exps = [math.exp(x - m) for x in scaled]
        total = sum(exps) or 1.0
        return [e / total for e in exps]
    
    # ─────────────────────────────────────────────────────────────────────────────
    # MASTER INTENT: Full Probability Assessment with ALL Rails
    # ─────────────────────────────────────────────────────────────────────────────
    
    def _intent_assess(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full probability assessment using ALL cognitive rails.
        
        This is the Whisper Core-style assessment that combines:
          - Priors (initial beliefs)
          - Likelihoods (evidence)
          - Causal rails (cause-effect reasoning)
          - Temporal rails (Hawkes process)
          - Paradox rails (contradiction detection)
          - Language rails (signal extraction)
          - Uncertainty metrics (knows what it doesn't know)
        
        Expected payload:
          - options: [{"id": "A", "prior": 0.33, ...}, ...]
          - notes: ["context text", ...]
          - events: [{"t": epoch, "option_id": "A"}, ...] (optional)
          - causal_graph: {"cause": ["effect1", "effect2"]} (optional)
          - interventions: {"option_id": strength} (optional)
          - temperature: float (optional, default 1.0)
          - reflective: bool (optional, for counterfactuals)
        """
        p = dict(payload or {})
        options = p.get("options", [])
        notes = p.get("notes", [])
        events = p.get("events", [])
        causal_graph = p.get("causal_graph", {})
        interventions = p.get("interventions", {})
        temperature = float(p.get("temperature", 1.0))
        reflective = bool(p.get("reflective", False))
        
        if not options:
            return {"ok": False, "error": "no options provided", "probabilities": []}
        
        n = len(options)
        
        # ═══ Extract priors ═══
        priors = [float(o.get("prior", 1.0 / n)) for o in options]
        total_p = sum(priors) or 1.0
        priors = [p / total_p for p in priors]
        
        # ═══ Initialize likelihoods and emotion modifiers ═══
        likes = [1.0] * n
        emo = [1.0] * n
        
        # ═══ RAIL 1: Paradox scoring on notes ═══
        combined_notes = " ".join(notes)
        paradox_score, paradox_flags = self._paradox_score(combined_notes)
        paradox_info = {"score": paradox_score, "flags": paradox_flags}
        
        # High paradox reduces confidence in all options equally
        if paradox_score >= 0.5:
            emo = [e * 0.96 for e in emo]
            likes = [l * 0.98 for l in likes]
        
        # ═══ RAIL 2: Causal boost ═══
        if causal_graph or interventions:
            cboost = self._causal_boost(options, combined_notes, causal_graph, interventions)
            likes = [likes[i] * cboost[i] for i in range(n)]
        
        # ═══ RAIL 3: Temporal/Hawkes boost ═══
        if events:
            tboost = self._hawkes_intensity(events, options)
            likes = [likes[i] * tboost[i] for i in range(n)]
        
        # ═══ RAIL 4: Language signal boost ═══
        if notes:
            sig = self._extract_language_signals(notes)
            likes = [l * sig["like_boost"] for l in likes]
            emo = [e * sig["emo_boost"] for e in emo]
        
        # ═══ Bayesian update: posterior ∝ prior * likelihood * emotion ═══
        post = []
        for i in range(n):
            p_val = max(1e-12, priors[i]) * max(1e-12, likes[i]) * max(1e-12, emo[i])
            # Add exploration jitter
            jitter = 1.0 + (random.random() - 0.5) * 0.1
            post.append(p_val * jitter)
        
        # Normalize
        total = sum(post) or 1.0
        post = [p / total for p in post]
        
        # ═══ RAIL 5: Temperature calibration ═══
        if temperature != 1.0:
            post = self._calibrate_temperature(post, temperature)
        
        # ═══ Calculate uncertainty metrics ═══
        uncertainty = self._uncertainty_metrics(post)
        
        # ═══ Build result ═══
        option_ids = [o.get("id", str(i)) for i, o in enumerate(options)]
        
        result = {
            "ok": True,
            "options": option_ids,
            "probabilities": post,
            "best": option_ids[post.index(max(post))],
            "best_prob": max(post),
            "diagnostics": {
                "uncertainty": uncertainty,
                "paradox": paradox_info,
                "rails_applied": {
                    "causal": bool(causal_graph or interventions),
                    "temporal": bool(events),
                    "paradox": True,
                    "language": bool(notes),
                    "calibration": temperature != 1.0,
                },
            },
        }
        
        # ═══ Optional: Counterfactual branches ═══
        if reflective and interventions:
            branches = []
            for k in interventions:
                # Flip the intervention
                temp_do = dict(interventions)
                temp_do[k] = 1.0 if temp_do[k] != 1.0 else 1.15
                cboost2 = self._causal_boost(options, combined_notes, causal_graph, temp_do)
                likes2 = [likes[i] * cboost2[i] for i in range(n)]
                post2 = [max(1e-12, priors[i]) * max(1e-12, likes2[i]) for i in range(n)]
                total2 = sum(post2) or 1.0
                post2 = [p / total2 for p in post2]
                branches.append({"name": f"CF: do({k})", "probabilities": post2})
            result["counterfactuals"] = branches
        
        # ═══ Emit telemetry ═══
        try:
            self.post.to_TELEMETRY({
                "opcode": "ORACLE_ASSESS",
                "payload": {
                    "fairy": self.ACTOR_NAME,
                    "ts": time.time(),
                    "best": result["best"],
                    "confidence": uncertainty["confidence"],
                    "entropy": uncertainty["entropy"],
                    "paradox_score": paradox_score,
                },
            })
        except Exception:
            pass
        
        # ═══ Chemistry based on confidence ═══
        try:
            if uncertainty["confidence"] > 0.7:
                self.post.route("PLAN", {
                    "opcode": "CHEM_SIGNAL_UPDATE",
                    "payload": {
                        "chemical": "dopamine",
                        "delta": +0.04,
                        "source": self.ACTOR_NAME,
                        "reason": "high_confidence_assessment",
                    },
                })
            elif uncertainty["is_uncertain"]:
                self.post.route("PLAN", {
                    "opcode": "CHEM_SIGNAL_UPDATE",
                    "payload": {
                        "chemical": "cortisol",
                        "delta": +0.02,
                        "source": self.ACTOR_NAME,
                        "reason": "high_uncertainty",
                    },
                })
        except Exception:
            pass
        
        return result

