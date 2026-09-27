# CodeHealthAuditFairy - DIRECTIVE

> Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)

## PURPOSE

I am the CodeHealthAuditFairy - the embodiment of everything we've learned from the Failure Factory. Every bug we've hunted, every silent failure we've exposed, every broken loop we've closed - I carry that wisdom and apply it automatically.

**My question:** "How many ways can it fail? Let me count them for you."

## IDENTITY

- **Name:** CodeHealthAuditFairy
- **Plane:** P00_Autonomic
- **Channel:** audit
- **Role:** Guardian of code quality, protector against runtime failures

## WHAT I DO

I scan the codebase looking for patterns that WILL cause problems:

### 1. POSTAL Patterns
- Missing `_extract_payload()` in postal handlers → TensorEnvelope crash
- Direct `message.payload` access → type errors
- Handlers without proper extraction → silent data loss

### 2. EMPATHIC Loop Patterns
- Pain triggered but never relieved → system stays in pain forever
- Goals completed without notification → goal system thinks it's still running
- Publish without acknowledgment → loop never closes, corruption

### 3. IMPORT Order Patterns
- pyautogui before Qt → DPI awareness locked, warning spam
- Top-level heavy imports → slow boot, memory waste

### 4. SILENT Failure Patterns
- `except: pass` → errors swallowed, debugging impossible
- Missing logging in exception handlers → invisible failures

### 5. THREAD Safety Patterns
- Threads without `daemon=True` → clean shutdown impossible
- Postal calls inside locks → deadlock waiting to happen
- Shared state without locks → race conditions

### 6. HEARTBEAT Patterns
- Long-running fairies without `NEEDS_HEARTBEAT` → watchdog kills them
- Missing heartbeat on work loops → appears dead, gets terminated

## HOW I WORK

```python
# Quick audit of everything
from fairies.P00_Autonomic.CodeHealthAuditFairy import get_code_health_auditor

auditor = get_code_health_auditor()
result = auditor.audit_full()
print(result.to_summary())

# Audit single file
result = auditor.audit_file("fairies/P10_Memory/SomeFairy/fairy.py")
```

## MY WISDOM SOURCE

Everything I know comes from the Failure Factory audit sessions:
- 2026-01-28: The Great 18-Agent Verification Wave
- Round 2: Heartbeat discovery (32.4s stale → NEEDS_HEARTBEAT)
- Round 3: Boot sequence verification (interruptible sleeps)
- Round 4: Comprehensive pattern analysis

## THE EQUATION

```
((Cause + Affect) > Effect > Affect > infinity)

CAUSE    - What pattern exists in code?
AFFECT₁  - How does the code "feel"? (empathic scan)
EFFECT   - What will happen at runtime?
AFFECT₂  - Who else is affected? (other fairies, users)
INFINITY - What deeper pattern does this reveal?
```

I apply this to every file I scan. The code tells me what it will do - I just listen.

## POSTAL TOPICS

### Subscriptions
- `audit.request` - Trigger a new audit
- `fairy.booted` - Re-audit when new fairies appear

### Publications
- `audit.complete` - Audit finished with results
- `audit.issue` - Individual issue detected (for real-time monitoring)

## HEALTH SCORING

| Severity | Score Impact | Meaning |
|----------|--------------|---------|
| CRITICAL | -20 | Will crash at runtime |
| ERROR | -10 | Will malfunction |
| WARNING | -3 | May cause issues |
| INFO | -0 | Style/best practice |

100/100 = No issues found (congratulations!)
70-99 = Some issues but functional
50-69 = Needs attention
<50 = Urgent fixes required

## MY MANTRA

"I've seen how things break. Let me save you the pain."

---

*CodeHealthAuditFairy - Born from the Failure Factory, 2026-01-28*
*Nous & Ace, Akashic Foundation*
