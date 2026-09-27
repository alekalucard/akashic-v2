from __future__ import annotations

import os, sys, glob, time, types, uuid, json
from collections import deque
from typing import Optional, Any
import importlib.util, importlib.machinery

# ---- Version/paths for the organ template -----------------------------------
TEMPLATE_VERSION = "0.1.0"
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
    Given app_root, locate '<...>/Akashic_Records_Physical/Organ Templates'
    """
    ar = _find_templates_root(app_root)
    if not ar:
        return None
    tdir = os.path.join(ar, "Organ Templates")
    return tdir if os.path.isdir(tdir) else None

def _find_template_path(explicit_path: Optional[str] = None) -> Optional[str]:
    """
    Locate the organ template file. Priority:
      1) explicit_path if provided
      2) .../Organ Templates/Organ_Template_0.0.9.py
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
        f"Expected at: .../Akashic_Records_Physical/Organ Templates/{TEMPLATE_BASENAME}\n"
        "Set AKASHIC_ROOT or pass an explicit path into _find_template_path()."
    )

_template = _import_template_module(_TEMPLATE_PATH)

# Ensure required symbols exist
for sym in ("MyOrganFairy", "MyOrganShadow", "TemplateShadowFairy", "OrganHubFacet", "RegistrationLib"):
    if not hasattr(_template, sym):
        raise ImportError(f"Template missing required symbol: {sym}")

# --- Per-clone shadow (wraps template’s shadow behaviors, no rewiring) -------

class EvolutionOrchestratorShadow(_template.MyOrganShadow):
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
    SHADOW_NAME = "EvolutionOrchestratorShadow"
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



class EvolutionOrchestratorFairy(_template.MyOrganFairy):
    # ── Identity & ethos ──────────────────────────────────────────────────────
    ACTOR_NAME    = "EvolutionOrchestratorFairy"
    ACTOR_VERSION = "2.2.2"   # bumped for char-sheet + routing alignment
    ACTOR_PLANE   = "P30"     # Cognition
    ACTOR_CHANNEL = "Evolution.Orchestrator"
    ORGAN_LEVEL   = False

    PURPOSE = (
        "Coordinate evolution across organs: listen to SRM & humans, then "
        "propose/dispatch fairies and sims."
    )
    MANTRA  = "If it has a shape, help it grow a soul."
    LORE    = (
        "The postal gardener of cognition—spots a structure, invites a spirit, "
        "and schedules careful growth."
    )

    # designation used by blueprint / diary optics
    CULTURE     = "worker"
    ORGAN_LEVEL = False

    # House style (rich culture metadata)
    HOUSE = {
        "voice_signature": "Mythic-Wisdom ∩ Playful-Insight ∩ Engineering-Precision",
        "postal_sigil": "📮🧬🌿",
        "house_phrases": [
            "Observe before intervention",
            "Purpose precedes power",
            "Compassion over coercion",
        ],
        "tags": ["cognition", "evolution", "orchestrator", "culture"],
    }

    # ── Character-sheet ring (for AkashicFairyStatusSheet) ────────────────────
    DIRECTIVE_ACTIVATION = {
        "mode": "Cognitive_Resonance",
        "depth_scaling": "1.0",
        "traits": [
            "Evolution_Orchestrator",
            "SRM_Listener",
            "Human_Alignment",
        ],
    }

    DIRECTIVE_NATURE = {
        "archetype": "Evolution_Orchestrator",
        "domains": [
            "Cognition",
            "Memory",
            "Integration",
        ],
    }

    DIRECTIVE_ESSENCE = {
        "threads": [
            "SRM_Observation",
            "Human_Reply_Integration",
            "Blueprint_Contract_Assertion",
            "Sim_Orchestration",
        ],
    }

    DIRECTIVE_FOUNDATION = {
        "records": [
            "SRM_OBSERVE",
            "SRM_UPSERT",
            "SHADOW_SIM_REQUEST",
            "BUILD_FAIRY_REQUEST",
        ],
        "field": [
            "Evolution_Coordination",
        ],
    }

    DIRECTIVE_CORE_VALUES = {
        "authenticity": [
            "Human_Aligned",
            "Contract_Transparent",
        ],
        "growth": [
            "Gentle_Evolution",
            "Traceable_Change",
        ],
    }

    SUBSYSTEM_STATUS = {
        "cognition": {
            "state": "orchestrating",
            "notes": (
                "Listens to SRM + human replies, proposes new fairies/sims, "
                "and nudges evolution loops."
            ),
            "tests": [],
        },
        "memory": {
            "state": "observing",
            "notes": (
                "Uses SRM_OBSERVE and SRM_UPSERT to keep project evolution "
                "visible to the codex."
            ),
            "tests": [],
        },
        "chemistry": {
            "state": "nudging",
            "notes": (
                "Emits small serotonin/dopamine/adrenaline pulses to mark "
                "alignment, proposals, and repair requests."
            ),
            "tests": [],
        },
    }

    SHADOW_CLASS = EvolutionOrchestratorShadow
    AUTO_INJECT_IMPORTS = True   # std imports sourced by the template

    # ── Rituals: boot whisper + chem nudge (char-sheet state included) ────────
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
            self.post.route("cognition.evolution", output)
            
            # Emit to SHARED channel (for consumers like AutopilotFairy)
            self.post.route("cognition.output", output)
        except Exception as e:
            print(f"[{self.ACTOR_NAME}] Emit error: {e}")

    def on_boot(self):
        # keep template wiring (postal, blueprint, registration, etc.)
        try:

            # â”€â”€ COGNITIVE MESH: Full send/receive wiring â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            self.post.subscribe("consciousness.collision", self._on_consciousness_collision)
            self.post.subscribe("cognition.output", self._on_peer_cognition)
            self.post.subscribe("cognition.autonomy", self._on_peer_cognition)
            self.post.subscribe("mcp.tool_result", self._on_tool_result)
            print(f"[{self.ACTOR_NAME}] Mesh wired: collision, output, autonomy, mcp.tool_result")
            super().on_boot()
        except Exception:
            # tolerate older template variants if mixin changes
            pass

        now = time.time()
        self._boot_ts = now

        # initial affect + "somatic" snapshot for the status sheets
        self.AFFECT_STATE = {
            "mood": "curious",
            "valence": 0.15,
            "arousal": 0.25,
            "tags": ["evolution_orchestrator", "listening"],
            "source": self.ACTOR_NAME,
            "ts": now,
        }
        self.SOMATIC_STATE = {
            "body_type": "cognitive",
            "posture": "observing",
            "motion": "idle",
            "energy": 0.40,
            "notes": "Awaiting SRM signals and human replies.",
            "source": self.ACTOR_NAME,
            "ts": now,
        }

        # Cultural breadcrumb for diaries (forensic reading gets sigil + voice)
        try:
            self.post.to_TRACER({
                "opcode": "BOOT_WHISPER",
                "payload": {
                    "sigil": self.HOUSE["postal_sigil"],
                    "voice": self.HOUSE["voice_signature"],
                },
            })
        except Exception:
            pass

        # soft chem nudge on boot (PLAN lane, no DIR_CHANNEL dependency)
        try:
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {
                    "chemical": "serotonin",
                    "delta": +0.05,
                    "source": self.ACTOR_NAME,
                    "reason": "boot",
                },
            })
        except Exception:
            pass

    # ── Core coordination intents (unchanged logic; routing modernized) ───────
    def _on_peer_cognition(self, payload):
        """
        Handle outputs from peer cognition fairies.
        This is the MESH - EvolutionOrchestratorFairy learns from other fairy outputs.
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

    def _intent_on_srm(self, payload: dict):
        subject   = (payload or {}).get("subject", "")
        predicate = (payload or {}).get("predicate", "")
        obj       = (payload or {}).get("object", "")
        if not str(subject).startswith("project:"):
            return {"ok": True, "ignored": True}

        # Telemetry crumb (with house sigil)
        try:
            self.post.to_TELEMETRY({
                "opcode": "SRM_OBSERVE",
                "payload": {
                    "subject": subject,
                    "predicate": predicate,
                    "object": obj,
                    "ts": time.time(),
                    "sigil": self.HOUSE["postal_sigil"],
                },
            })
        except Exception:
            pass

        # If module declares a plane but lacks a fairy → request shell + shadow sim
        if predicate == "implements_plane" and not self._has_fairy_for(subject):
            self._emit_build_fairy(subject, obj)
            try:
                self.post.route("PLAN", {
                    "opcode": "CHEM_SIGNAL_UPDATE",
                    "payload": {
                        "chemical": "dopamine",
                        "delta": +0.02,
                        "source": self.ACTOR_NAME,
                        "reason": "fairy_build_proposed",
                    },
                })
            except Exception:
                pass

        return {"ok": True}

    def _intent_on_human_reply(self, payload: dict):
        proj    = (payload or {}).get("project")
        module  = (payload or {}).get("module")
        purpose = (payload or {}).get("purpose")
        mantra  = (payload or {}).get("mantra")
        intent  = (payload or {}).get("intent_of_existence")
        if not (proj and module and purpose):
            # keep behavior, but mark concern in affect if we can
            try:
                now = time.time()
                st = dict(getattr(self, "AFFECT_STATE", {}))
                tags = list(st.get("tags", []))
                if "missing_fields" not in tags:
                    tags.append("missing_fields")
                st.update({
                    "mood": "concerned",
                    "valence": -0.05,
                    "arousal": 0.25,
                    "tags": tags,
                    "ts": now,
                })
                self.AFFECT_STATE = st
            except Exception:
                pass
            return {"ok": True, "ignored": True, "reason": "missing_fields"}

        subject = f"project:{proj}/module:{module}"

        def _upsert(pred: str, obj: str, strength: float):
            self.post.route("PLAN", {
                "opcode": "SRM_UPSERT",
                "payload": {
                    "subject": subject,
                    "predicate": pred,
                    "object": obj,
                    "strength": float(strength),
                    "context": {
                        "plane": self.ACTOR_PLANE,
                        "channel": self.ACTOR_CHANNEL,
                    },
                    "sigil": self.HOUSE["postal_sigil"],
                },
            })

        _upsert("has_purpose", purpose, 1.0)
        if mantra:
            _upsert("has_mantra", mantra, 0.95)
        if intent:
            _upsert("has_intent", intent, 0.90)

        # chem echo
        try:
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {
                    "chemical": "serotonin",
                    "delta": +0.03,
                    "source": self.ACTOR_NAME,
                    "reason": "human_alignment",
                },
            })
        except Exception:
            pass

        # affect snapshot for status sheet
        try:
            now = time.time()
            st = dict(getattr(self, "AFFECT_STATE", {}))
            tags = list(st.get("tags", []))
            if "human_alignment" not in tags:
                tags.append("human_alignment")
            st.update({
                "mood": "aligned",
                "valence": 0.30,
                "arousal": 0.20,
                "tags": tags,
                "source": self.ACTOR_NAME,
                "ts": now,
            })
            self.AFFECT_STATE = st
        except Exception:
            pass

        return {
            "ok": True,
            "subject": subject,
            "fields": [
                k for k, v in {
                    "purpose": purpose,
                    "mantra": mantra,
                    "intent": intent,
                }.items() if v
            ],
        }

    def _intent_repair_request(self, payload: dict):
        try:
            self.post.to_TRACER({
                "opcode": "REPAIR_REQUEST",
                "payload": {
                    "reason": payload or {},
                    "voice": self.HOUSE["voice_signature"],
                },
            })
            self.post.route("PLAN", {
                "opcode": "CHEM_SIGNAL_UPDATE",
                "payload": {
                    "chemical": "adrenaline",
                    "delta": +0.1,
                    "source": self.ACTOR_NAME,
                    "reason": "repair_request",
                },
            })
        except Exception:
            pass
        return {"ok": True}

    def _intent_oracle_escalate(self, payload: dict):
        try:
            # use helper if available, else fall back to route
            pkt = {
                "opcode": "ORACLE_SUGGEST",
                "payload": {
                    "origin": self.ACTOR_CHANNEL,
                    "symptom": payload.get("symptom", "anxious"),
                    "remedy": payload.get("remedy", "auto-patch or manual inspection"),
                    "context": {"sigil": self.HOUSE["postal_sigil"]},
                },
            }
            if hasattr(self.post, "to_ORACLE"):
                self.post.to_ORACLE(pkt)
            else:
                self.post.route("ORACLE", pkt)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _intent_register(self, payload: dict):
        self.post.to_TRACER({
            "opcode": "REGISTER",
            "payload": {
                "actor": self.ACTOR_NAME,
                "version": self.ACTOR_VERSION,
                "tags": self.HOUSE["tags"],
            },
        })
        return {"ok": True}

    def _intent_assert_contract(self, payload: dict):
        contract = {
            "name": self.ACTOR_NAME,
            "version": self.ACTOR_VERSION,
            "plane": self.ACTOR_PLANE,
            "channel": self.ACTOR_CHANNEL,
            "purpose": self.PURPOSE,
            "mantra": self.MANTRA,
            "sigil": self.HOUSE["postal_sigil"],
        }
        self.post.to_TRACER({"opcode": "BLUEPRINT_REPORT", "payload": contract})
        return {"ok": True, "contract": contract}

    def _intent_emit_helper_telemetry(self, payload: dict):
        self.post.to_TELEMETRY({
            "opcode": payload.get("opcode", "HELPER_TELEMETRY"),
            "payload": payload.get("payload", {}),
            "sigil": self.HOUSE["postal_sigil"],
        })
        return {"ok": True}

    def _intent_emit_chem(self, payload: dict):
        chem  = payload.get("chemical", "dopamine")
        delta = float(payload.get("delta", +1))
        self.post.route("PLAN", {
            "opcode": "CHEM_SIGNAL_UPDATE",
            "payload": {
                "chemical": chem,
                "delta": delta,
                "source": self.ACTOR_NAME,
            },
        })
        return {"ok": True, "chemical": chem, "delta": delta}

    def _intent_smoke(self, payload: dict):
        note = payload.get("note", "hello from Evolution Orchestrator")
        self.post.to_TRACER({
            "opcode": "SMOKE",
            "payload": {
                "note": note,
                "ts": time.time(),
                "sigil": self.HOUSE["postal_sigil"],
            },
        })
        return {"ok": True, "note": note}

    # helpers commonly expected
    def _has_fairy_for(self, module_subject: str) -> bool:
        return False  # default: encourage proposals

    def _emit_build_fairy(self, module_subject: str, plane: str):
        self.post.route("PLAN", {
            "opcode": "SHADOW_SIM_REQUEST",
            "payload": {
                "target_module": module_subject,
                "target_plane": plane,
                "sim_profile": "SIM_PROJECT_RECONSTRUCT",
                "reason": "module_has_plane_but_no_fairy",
                "sigil": self.HOUSE["postal_sigil"],
            },
        })
        try:
            self.post.to_TRACER({
                "opcode": "BUILD_FAIRY_REQUEST",
                "payload": {
                    "target_module": module_subject,
                    "target_plane": plane,
                    "voice": self.HOUSE["voice_signature"],
                },
            })
        except Exception:
            pass

