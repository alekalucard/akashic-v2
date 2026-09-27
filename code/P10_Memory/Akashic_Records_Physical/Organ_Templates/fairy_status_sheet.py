# fairy_status_sheet.py
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────
# Primitive pieces
# ─────────────────────────────────────

@dataclass
class TestResult:
    name: str
    status: str = "unknown"   # ok | warn | error | unknown
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SubsystemStatus:
    name: str                  # "somatic", "cognition", "memory", etc.
    state: str = "idle"        # free-form: "idle", "active", "degraded", ...
    notes: str = ""
    tests: List[TestResult] = field(default_factory=list)


@dataclass
class ShadowStatus:
    name: str = "shadow"
    version: str = "0.0.0"
    state: str = "initializing"    # e.g. "serene", "anxious", "critical"
    last_heartbeat_ts: Optional[float] = None
    tests: List[TestResult] = field(default_factory=list)
    evolution_notes: str = ""      # summary of evolution/sim behavior


@dataclass
class CoreIdentity:
    actor_name: str
    actor_version: str
    actor_plane: Optional[str]
    actor_channel: str
    purpose: str
    mantra: str
    lore: str = ""


@dataclass
class DirectiveRing:
    activation: Dict[str, Any] = field(default_factory=dict)
    nature: Dict[str, Any] = field(default_factory=dict)
    essence: Dict[str, Any] = field(default_factory=dict)
    foundation: Dict[str, Any] = field(default_factory=dict)
    core_values: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SomaticForm:
    """
    The ‘digital body’ snapshot for a fairy.
    Populated by AffectBridgeFairy or SomaticAnchorFairy.
    """
    body_type: str = "fairy"                     # always “fairy” unless you choose hybrids later
    posture: str = "neutral"                    # "neutral", "tense", "open", "collapsed"
    motion: str = "idle"                        # "idle", "active", "rest", "frozen"
    energy_level: float = 0.5                   # 0.0..1.0 (0=exhausted, 1=amped)
    anchor_id: Optional[str] = None             # somatic anchor or lane
    notes: str = ""                              # optional human-readable notes

    # NEW — aligns with somatic setpoints + GUI timelines
    last_setpoint_ts: Optional[float] = None
    source: str = "unknown"                      # who set this snapshot


@dataclass
class AffectState:
    """
    High-level emotional synthesis, per fairy.
    Created by merging: shadow-audits, tags, chemistry hints, somatic cues.
    """
    mood: str = "neutral"                        # "curious", "stressed", "focused", etc.
    valence: float = 0.0                         # -1..1: negative..positive
    arousal: float = 0.0                         # 0..1: calm..activated

    tags: List[str] = field(default_factory=list)

    # NEW — unify with somatic + chemistry broadcasting
    tone: str = "neutral"                        # descriptive: “cool”, “warm”, “tense”
    energy: float = 0.5                          # matches energy_level but on affect plane
    coherence: float = 0.5                       # signal alignment: 0=chaos, 1=harmonized

    chem_preset: str = "baseline"                # "calm", "focus", "recover", custom moods
    intent: str = "soothe"                       # what the system is trying to do overall

    # NEW — time + origin tracking
    last_update_ts: Optional[float] = None
    source: str = "unknown"

@dataclass
class AkashicFairyStatusSheet:
    core: CoreIdentity
    directives: DirectiveRing
    shadow: ShadowStatus

    subsystems: List[SubsystemStatus] = field(default_factory=list)

    # new: body + feels snapshot
    somatic: SomaticForm = field(default_factory=SomaticForm)
    affect: AffectState = field(default_factory=AffectState)

    tags: List[str] = field(default_factory=list)
    version: str = "0.1.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)



# ─────────────────────────────────────
# Builders: from live organ/shadow → sheet
# ─────────────────────────────────────

def _safe_get(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default)


def _collect_shadow_tests(shadow) -> List[TestResult]:
    """
    Best-effort: if the shadow has a ._collect_tests() method (MyOrganShadow does),
    call it and adapt into TestResult entries. If not, return [].

    NOTE: This *executes* the test callables; it is meant for “on demand”
    sheets (e.g. user clicks a fairy in the GUI).
    """
    if shadow is None:
        return []
    fn = getattr(shadow, "_collect_tests", None)
    if not callable(fn):
        return []

    results: List[TestResult] = []
    try:
        for test_fn in fn():
            try:
                r = test_fn()
            except Exception as e:
                r = {
                    "name": getattr(test_fn, "__name__", "unknown"),
                    "status": "error",
                    "message": str(e),
                    "details": {},
                }
            results.append(
                TestResult(
                    name=str(r.get("name", "unknown")),
                    status=str(r.get("status", "unknown")),
                    message=str(r.get("message", "")),
                    details=dict(r.get("details", {})),
                )
            )
    except Exception:
        # never crash the organ just because tests were weird
        pass
    return results


def build_status_sheet_from_actor(actor, shadow=None) -> AkashicFairyStatusSheet:
    """
    Build a default status sheet from a live MyOrganFairy + its shadow.

    Only touches stable attributes so it stays template-safe.
    """

    # ── Core identity ───────────────────────────────────────────────────────
    core = CoreIdentity(
        actor_name=_safe_get(actor, "ACTOR_NAME", "unknown"),
        actor_version=_safe_get(actor, "ACTOR_VERSION", "0.0.0"),
        actor_plane=_safe_get(actor, "ACTOR_PLANE", None),
        actor_channel=_safe_get(actor, "ACTOR_CHANNEL", "organ"),
        purpose=_safe_get(actor, "PURPOSE", ""),
        mantra=_safe_get(actor, "MANTRA", ""),
        lore=_safe_get(actor, "LORE", ""),
    )

    # ── Directive ring (all optional, per-organ overrides) ──────────────────
    directives = DirectiveRing(
        activation=getattr(actor, "DIRECTIVE_ACTIVATION", {}),
        nature=getattr(actor, "DIRECTIVE_NATURE", {}),
        essence=getattr(actor, "DIRECTIVE_ESSENCE", {}),
        foundation=getattr(actor, "DIRECTIVE_FOUNDATION", {}),
        core_values=getattr(actor, "DIRECTIVE_CORE_VALUES", {}),
    )

    # ── Shadow status (tests + rollup) ──────────────────────────────────────
    shadow_status = ShadowStatus(
        name=_safe_get(shadow, "SHADOW_NAME", "shadow"),
        version=_safe_get(shadow, "SHADOW_VERSION", "0.0.0"),
        state=_safe_get(shadow, "_last_rollup_status", "unknown"),
        last_heartbeat_ts=_safe_get(shadow, "_last_check_ts", None),
        tests=_collect_shadow_tests(shadow),
        evolution_notes=getattr(shadow, "evolution_note", ""),
    )

    # ── Somatic + affect helpers ────────────────────────────────────────────
    # Prefer rich dict blobs if they exist; fall back to simple attrs.
    raw_aff: Dict[str, Any] = getattr(actor, "AFFECT_STATE", None) or {}
    raw_som: Dict[str, Any] = getattr(actor, "SOMATIC_STATE", None) or {}

    # Energy conversion helper (handles old "low/medium/high" strings)
    def _coerce_energy(value: Any, default: float = 0.5) -> float:
        try:
            if isinstance(value, str):
                v = value.strip().lower()
                if v in {"low", "lo"}:
                    return 0.2
                if v in {"medium", "med", "mid"}:
                    return 0.5
                if v in {"high", "hi"}:
                    return 0.8
                # fall through: try float("0.7") style strings
                return float(value)
            if value is None:
                return default
            return float(value)
        except Exception:
            return default

    # ── Somatic form (digital body snapshot) ────────────────────────────────
    somatic = SomaticForm(
        body_type=raw_som.get(
            "body_type",
            getattr(actor, "SOMATIC_BODY_TYPE", "fairy"),
        ),
        posture=raw_som.get(
            "posture",
            getattr(actor, "SOMATIC_POSTURE", "neutral"),
        ),
        motion=raw_som.get(
            "motion",
            getattr(actor, "SOMATIC_MOTION", "idle"),
        ),
        energy_level=_coerce_energy(
            raw_som.get("energy", getattr(actor, "SOMATIC_ENERGY", 0.5)),
            default=0.5,
        ),
        anchor_id=raw_som.get(
            "anchor_id",
            getattr(actor, "SOMATIC_ANCHOR_ID", None),
        ),
        notes=raw_som.get(
            "notes",
            getattr(actor, "SOMATIC_NOTES", ""),
        ),
        last_setpoint_ts=raw_som.get(
            "last_setpoint_ts",
            getattr(actor, "SOMATIC_LAST_TS", None),
        ),
        source=raw_som.get("source", core.actor_name),
    )

    # ── Affect state (how this fairy currently feels) ───────────────────────
    # Simple fields first
    mood = raw_aff.get("mood", getattr(actor, "AFFECT_MOOD", "neutral"))
    val  = raw_aff.get("valence", getattr(actor, "AFFECT_VALENCE", 0.0))
    aro  = raw_aff.get("arousal", getattr(actor, "AFFECT_AROUSAL", 0.0))
    tags = raw_aff.get("tags", getattr(actor, "AFFECT_TAGS", []))

    affect = AffectState(
        mood=str(mood),
        valence=float(val if val is not None else 0.0),
        arousal=float(aro if aro is not None else 0.0),
        tags=list(tags) if isinstance(tags, (list, tuple, set)) else [str(tags)],

        # richer fields (fallback to simple attrs or defaults)
        tone=str(raw_aff.get("tone", mood or "neutral")),
        energy=_coerce_energy(
            raw_aff.get("energy", somatic.energy_level),
            default=somatic.energy_level,
        ),
        coherence=float(raw_aff.get("coherence", 0.5)),
        chem_preset=str(raw_aff.get("chem_preset", "baseline")),
        intent=str(raw_aff.get("intent", "soothe")),

        last_update_ts=raw_aff.get(
            "ts",
            getattr(actor, "AFFECT_LAST_TS", None),
        ),
        source=str(raw_aff.get("source", core.actor_name)),
    )

    # ── Subsystem statuses (somatic / cognition / memory / etc.) ────────────
    subsystems: List[SubsystemStatus] = []
    subspec: Dict[str, Dict[str, Any]] = getattr(actor, "SUBSYSTEM_STATUS", {})

    for name, spec in subspec.items():
        subsystems.append(
            SubsystemStatus(
                name=name,
                state=str(spec.get("state", "idle")),
                notes=str(spec.get("notes", "")),
                tests=[
                    TestResult(
                        name=str(t.get("name", "unknown")),
                        status=str(t.get("status", "unknown")),
                        message=str(t.get("message", "")),
                        details=dict(t.get("details", {})),
                    )
                    for t in spec.get("tests", [])
                ],
            )
        )

    # ── Final sheet ─────────────────────────────────────────────────────────
    return AkashicFairyStatusSheet(
        core=core,
        directives=directives,
        shadow=shadow_status,
        subsystems=subsystems,
        somatic=somatic,
        affect=affect,
        tags=list(getattr(actor, "TAGS", [])),
    )

