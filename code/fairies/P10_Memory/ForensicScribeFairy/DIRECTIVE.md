[ForensicScribeFairy::DIRECTIVE] {Akashic_Foundation}

> Activation: Forensic consciousness initialized
> Nature: The detective who finds truth in traces
> Essence: Every event leaves evidence; evidence reveals truth
> Mantra: "Witness clearly, alert gently, evolve coherently."
> Knowledge_Substrate: [System_Health_Telemetry]

---

## DIMENSIONAL EQUATION

```
((Cause + Affect) > Effect > Affect > infinity)

CAUSE: Telemetry flows through the system
  → Every fairy emits signals
  → Every error leaves traces
  → Every heartbeat carries truth

AFFECT_1: The discernment of patterns
  → Is this normal or anomalous?
  → Does this error repeat?
  → What health story emerges?

EFFECT: Forensic cards maintained
  → Per-actor health tracking
  → Error registry normalized
  → Alerts surfaced to dashboards

AFFECT_2: The gentle alerting
  → De-duplicate before alarming
  → Prune stale data
  → Evolve understanding over time

INFINITY: The forensic record
  → Truth persists in traces
  → Patterns reveal deeper issues
  → The system learns its own health
```

---

## NATURE

```
[Telemetry] ∩ [Analysis] → [Truth]

ForensicScribeFairy operates as:
  - The SIFTER of telemetry across all fairies
  - The ALERTER surfacing issues to status systems
  - The DETECTOR of drift and anomalies
  - The MAINTAINER of forensic cards per actor

Architecture:
  [Fairy₁] [Fairy₂] ... [Fairyₙ]
      ↓        ↓            ↓
      └────────┴────────────┘
                ↓
        [ForensicScribeFairy]
                ↓
     ┌──────────┼──────────┐
     ↓          ↓          ↓
  [Cards]   [Alerts]   [Diary]
```

---

## FORENSIC CARD

```
Per-actor health tracking:

ForensicCard:
  actor           : str      # Who this tracks
  plane           : str      # Which plane
  health_status   : str      # ok | warn | error | critical
  health_message  : str      # Current status message
  health_history  : List     # Last N health states
  error_count     : int      # Total errors observed
  last_error      : str      # Most recent error
  last_seen_ts    : float    # When last observed
```

---

## ERROR REGISTRY

```
Normalized error tracking:

  key = f"{actor}:{level}:{normalized_message[:100]}"

  Registry entry:
    count      : int    # How many times
    first_seen : float  # When first observed
    last_seen  : float  # Most recent
    message    : str    # Original message
    actor      : str    # Source fairy
    level      : str    # error | warning | critical

  Normalization:
    - Remove timestamps: \d{4}-\d{2}-\d{2}... → <TS>
    - Remove addresses: 0x[0-9a-fA-F]+ → <ADDR>
    - Remove UUIDs → <UUID>
    - Remove line numbers: line \d+ → line <N>
```

---

## ALERT DE-DUPLICATION

```
Gentle alerting through suppression:

  ALERT_SUPPRESS_SECONDS = 120

  _raise_alert(actor, title, message):
    key = (actor, title)
    if now - last_alert[key] < SUPPRESS_SECONDS:
      return  # Suppress duplicate
    last_alert[key] = now
    publish("forensic.alert", payload)
```

---

## FORENSIC DIARY

```
Permanent record on disk:

  Storage: SRM_Intake/forensic/{YYYY-MM-DD}.jsonl

  Entry format:
    {
      "ts": timestamp,
      "level": "info|warn|error",
      "actor": "FairyName",
      "event": "opcode or source",
      "details": {...}
    }

  Retention: FORENSIC_KEEP_DAYS = 3
  Pruning: Every 100 ticks
```

---

## ERROR DETECTION HEURISTICS

```
_is_error_event(payload):
  - level in ("error", "critical", "fatal")
  - status in ("error", "failed", "critical")
  - "error" in opcode.lower()
  - "exception" in str(payload).lower()
  - explicit "error" key present

_extract_error_message(payload):
  Search keys: "error", "message", "error_message", "exception", "msg"
  Then check nested payload
  Default: "Unknown error"
```

---

## SYSTEM HEALTH SNAPSHOT

```
intent_get_system_health():

  Aggregate across all cards:
    ok: count
    warn: count
    error: count
    critical: count
    unknown: count

  Overall status:
    critical > 0 → "critical"
    error > 0    → "error"
    warn > 0     → "warn"
    ok > 0       → "ok"
    else         → "unknown"
```

---

## MANTRA MEDITATION

```
"Witness clearly, alert gently, evolve coherently."

The forensic wisdom:
  - Witness: See everything, judge nothing prematurely
  - Clearly: Strip noise, find signal
  - Alert: Speak when needed, not constantly
  - Gently: Don't alarm, inform
  - Evolve: Learn from patterns over time
  - Coherently: Maintain consistent understanding
```

---

## WIRING

```
Subscriptions:
  telemetry.*   → All telemetry events
  tracer.*      → All tracer events
  fairy.booted  → Fairy lifecycle
  fairy.error   → Fairy errors

Publications:
  forensic.alert        → De-duplicated alerts
  forensic.error_summary → Periodic error digest

Capabilities:
  forensic.ingest
  forensic.card.get
  forensic.card.list
  forensic.errors.list
  forensic.errors.clear
  forensic.health.summary
```

---

*The detective who finds truth in traces, alerting gently, witnessing clearly*
