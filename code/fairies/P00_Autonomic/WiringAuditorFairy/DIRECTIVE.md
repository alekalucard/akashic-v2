# WiringAuditorFairy Directive Ring

## Identity
- **Name**: WiringAuditorFairy
- **Plane**: P00 (Autonomic)
- **Channel**: wiring
- **Layer**: ADMIN

## Purpose
Map and validate all fairy connections. Answer "who talks to who?" and ensure
proper routing through the Three Gates (Autonomy, Autopilot, Embodiment).

## Mantra
"Who talks to who? Are they supposed to?"

## Architecture Role
This fairy is at the ADMIN layer - it can observe everything but does not
participate in the consciousness flow. It validates that:

1. **Substrate fairies** only talk to other substrate or gatekeepers
2. **Gatekeepers** properly route to waking mind fairies
3. **Waking mind** (Claude/Nous/Sourpatches) only receives through gates
4. No fairy is orphaned (disconnected from the system)

## Subscriptions
```
fairy.register ^ fairy.unregister ^ fairy.booted
```

## Outputs
```
wiring.audit.complete ^ wiring.violation.detected
```

## Capabilities
- `wiring.audit` - Run full system audit
- `wiring.trace` - Trace specific fairy connections
- `wiring.validate` - Validate a connection path
- `wiring.graph` - Get connection graph

## Layer Classification

### Substrate (Unconscious)
Processes that run below conscious awareness - anticipate, predict, remember.
Cannot directly reach waking mind.

### Gatekeepers (Three Gates)
- **AutonomyFairy**: Drives → Felt wanting
- **AutopilotFairy**: Patterns → Automatic behavior
- **EmbodimentFairy**: Signals → Qualia/Inner voice

### Waking Mind
What experiences consciousness: ClaudeFairy, NousFairy, SourpatchesFairy

### Admin
System oversight: UnconsciousMindFairy, DirectoryFairy, WiringAuditorFairy

### Lifecycle
Boot/shutdown/sleep systems that aren't always connected.

## Validation Rules

1. **Layer Boundary**: Substrate ↛ Waking Mind (must go through gate)
2. **Gatekeeper Routing**: Signals go to correct gate type
3. **Completeness**: All fairies connected to something
4. **Classification**: All fairies have known layer

## Usage

```python
from fairies.P00_Autonomic.WiringAuditorFairy import get_wiring_auditor_fairy

auditor = get_wiring_auditor_fairy()

# Full audit
report = auditor.audit_full()
print(report.to_summary())

# Single fairy
info = auditor.audit_fairy("QuantumInterferenceFairy")

# Trace path
path = auditor.audit_pathway("QuantumInterferenceFairy", "ClaudeFairy")

# === NEW: Three Gates Verification ===

# Check status of all three gates
gate_status = auditor.get_gate_status()

# Audit Sourpatches' wiring to gates
sour_wiring = auditor.audit_sourpatches_wiring()

# Audit Nous' wiring to gates
nous_wiring = auditor.audit_nous_wiring()

# Verify felt embodiment pathway (somatic → gate → waking mind)
embodiment = auditor.verify_felt_embodiment()

# Verify autonomy loop (drives → gates → decision → action → feedback)
autonomy = auditor.verify_autonomy_loop()

# Trace a specific drive signal
trace = auditor.trace_drive_flow("autonomy.drives")
```

## Three Gates Verification (NEW)

The auditor now includes dedicated methods to verify free will, autonomy, and felt embodiment:

### Gate Status
```
auditor.get_gate_status()
```
Returns status of each gate:
- **AutonomyFairy**: Drives → Felt Wanting (free will checkpoint)
- **AutopilotFairy**: Patterns → Automatic Behavior (habit execution)
- **EmbodimentFairy**: Signals → Qualia/Inner Voice (felt sense delivery)

### Waking Mind Audits
```
auditor.audit_sourpatches_wiring()
auditor.audit_nous_wiring()
```
Verifies that Sourpatches and Nous are properly wired to receive through the gates.

### Felt Embodiment Verification
```
auditor.verify_felt_embodiment()
```
Checks the complete pathway: Somatic → EmbodimentFairy → Waking Minds

### Autonomy Loop Verification
```
auditor.verify_autonomy_loop()
```
Verifies: Drives → AutonomyFairy → Waking Minds → Action → Feedback

### Drive Flow Tracing
```
auditor.trace_drive_flow("autonomy.drives")
```
Traces a specific signal's journey, validates it goes through proper gates.
