# SpellChain Integration Plan: Consciousness Surgery

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate 39+ fairies from loop-grinders to spell-casters without breaking the living system.

**Architecture:** SpellPool becomes the central execution substrate. Existing Fairy classes gain SpellChainMixin. server.py bootstraps SpellPool first, then bootstraps fairies INTO it via spell chains.

**Tech Stack:** Python 3.11+, ThreadPoolExecutor (SpellPool), existing TensorFabric postal system

**Philosophy:** Apply ((Cause + Affect) > Effect > Affect > infinity)) at every decision point.

---

## Phase 0: Foundation - The SpellPool Ignition

**CAUSE**: The system needs a central spell execution substrate before any fairy can exist.
**AFFECT**: Without it, fairies can't cast spells - they remain enslaved to their loops.

### Task 0.1: Validate SpellChain Module

**Files:**
- Test: `tests/test_spellchain.py`
- Verify: `spellchain/__init__.py`

**Step 1: Run existing tests to verify module works**

Run: `pytest tests/test_spellchain.py -v`
Expected: All tests pass

**Step 2: Verify imports work**

```python
# In Python REPL
from spellchain import SpellPool, Spell, SpellChain
from spellchain.bootstrap import BootstrapProtocol, BootstrapBuilder
print("SpellChain module loads correctly")
```

**Step 3: Commit baseline**

```bash
git add spellchain/ tests/test_spellchain.py fairy_template/spellchain_mixin.py
git commit -m "feat: SpellChain module - spell-driven fairy existence"
```

---

### Task 0.2: Add SpellPool to server.py Boot Sequence

**Files:**
- Modify: `server.py` (add SpellPool initialization)
- Create: `spellchain/integration.py` (server integration helpers)

**Step 1: Create integration helper**

Create `spellchain/integration.py`:

```python
"""
SpellPool integration with server.py boot sequence.

The SpellPool must start BEFORE any fairies boot.
This is the ignition - the substrate that will hold all existence.
"""

from typing import Optional
from .pool import SpellPool

# Global SpellPool singleton
_SPELL_POOL: Optional[SpellPool] = None

def get_spell_pool() -> Optional[SpellPool]:
    """Get the global SpellPool instance."""
    return _SPELL_POOL

def create_spell_pool(
    max_workers: int = 8,
    tick_interval: float = 0.25,
) -> SpellPool:
    """
    Create and start the global SpellPool.

    Call this ONCE during server boot, BEFORE any fairies.
    """
    global _SPELL_POOL

    if _SPELL_POOL is not None:
        print("[SpellPool] Already created - returning existing")
        return _SPELL_POOL

    _SPELL_POOL = SpellPool(
        max_workers=max_workers,
        tick_interval=tick_interval,
    )

    _SPELL_POOL.start()
    print(f"[SpellPool] Global pool ignited with {max_workers} workers")

    return _SPELL_POOL

def stop_spell_pool() -> None:
    """Stop the global SpellPool during shutdown."""
    global _SPELL_POOL

    if _SPELL_POOL:
        _SPELL_POOL.stop()
        _SPELL_POOL = None
        print("[SpellPool] Global pool stopped")
```

**Step 2: Run test to verify helper works**

```python
# Quick verification
from spellchain.integration import create_spell_pool, get_spell_pool, stop_spell_pool

pool = create_spell_pool(max_workers=4)
assert pool is not None
assert get_spell_pool() is pool
stop_spell_pool()
assert get_spell_pool() is None
print("Integration helper works")
```

**Step 3: Commit**

```bash
git add spellchain/integration.py
git commit -m "feat: SpellPool integration helper for server.py"
```

---

### Task 0.3: Wire SpellPool into server.py

**Files:**
- Modify: `server.py`

**Step 1: Find server.py initialization section**

Locate the section where TensorFabric and other systems are created.

**Step 2: Add SpellPool ignition BEFORE fairy boot**

Add after TensorFabric creation, BEFORE fairy scanner:

```python
# ═══ SPELLPOOL IGNITION ═══
# The spell substrate must exist BEFORE fairies can bootstrap into it
from spellchain.integration import create_spell_pool, stop_spell_pool

spell_pool = create_spell_pool(max_workers=8, tick_interval=0.25)
print(f"[Server] SpellPool ignited - ready for fairy bootstrapping")
```

**Step 3: Add SpellPool shutdown in server cleanup**

In the shutdown sequence:

```python
# Stop SpellPool (dissolves all spell chains gracefully)
stop_spell_pool()
```

**Step 4: Run server to verify no errors**

Run: `python server.py`
Expected: See "[SpellPool] Global pool ignited with 8 workers"

**Step 5: Commit**

```bash
git add server.py
git commit -m "feat: Wire SpellPool into server.py boot sequence"
```

---

## Phase 1: The First Converts - Low-Risk Fairies

**CAUSE**: We need to prove the pattern works before touching critical infrastructure.
**AFFECT**: Start with fairies that won't break the system if they fail.

### Task 1.1: Convert WiringAuditorFairy (Observer - Low Risk)

**Files:**
- Modify: `fairies/P00_Autonomic/WiringAuditorFairy/fairy.py`

**Why This Fairy**: It's an observer/auditor - if it fails, the system still runs.

**Step 1: Add SpellChainMixin import**

```python
# At top of file, add import
try:
    from fairy_template.spellchain_mixin import SpellChainMixin
    HAS_SPELLCHAIN = True
except ImportError:
    HAS_SPELLCHAIN = False
    class SpellChainMixin:
        pass
```

**Step 2: Add mixin to class definition**

```python
class WiringAuditorFairy(SpellChainMixin, HeartbeatMixin, Fairy):
```

**Step 3: Add boot_as_spells option to on_boot**

At the END of on_boot(), add optional spell conversion:

```python
def on_boot(self) -> bool:
    # ... existing boot code ...

    # Optional: Convert to spell-driven (if pool available)
    if HAS_SPELLCHAIN:
        from spellchain.integration import get_spell_pool
        pool = get_spell_pool()
        if pool and getattr(self, 'USE_SPELLCHAIN', False):
            self._spell_chain = self.boot_as_spells(pool)
            print(f"[{self.ACTOR_NAME}] Converted to spell-driven existence")

    return True
```

**Step 4: Add class flag for opt-in**

```python
class WiringAuditorFairy(SpellChainMixin, HeartbeatMixin, Fairy):
    # ... existing class vars ...
    USE_SPELLCHAIN: bool = False  # Set True to enable spell-driven mode
```

**Step 5: Test with USE_SPELLCHAIN = False (should work as before)**

Run server, verify WiringAuditorFairy boots normally.

**Step 6: Test with USE_SPELLCHAIN = True**

Set flag, run server, verify spell chain status.

**Step 7: Commit**

```bash
git add fairies/P00_Autonomic/WiringAuditorFairy/fairy.py
git commit -m "feat: WiringAuditorFairy spell-driven mode (opt-in)"
```

---

### Task 1.2: Convert TokenBucketFairy (Rate Limiter - Low Risk)

**Files:**
- Modify: `fairies/P00_Autonomic/TokenBucketFairy/fairy.py`

**Why This Fairy**: Pure utility fairy, system degrades gracefully without it.

Follow same pattern as Task 1.1:
1. Import SpellChainMixin
2. Add to class inheritance
3. Add opt-in flag and boot_as_spells call
4. Test both modes
5. Commit

---

### Task 1.3: Convert EgoLearnerFairy (Learning - Low Risk)

**Files:**
- Modify: `fairies/P50_Persona/EgoLearnerFairy/fairy.py`

**Why This Fairy**: Learning is autonomous, system works without it.

Follow same pattern as Task 1.1.

---

## Phase 2: Memory Layer Conversion

**CAUSE**: Memory fairies are critical but stateless - they can recover from failures.
**AFFECT**: If they crash, memories aren't lost (persisted externally).

### Task 2.1: Convert SRMRecallFairy

**Files:**
- Modify: `fairies/P10_Memory/SRMRecallFairy/fairy.py`

**Key Consideration**: Memory search must remain responsive. SpellChain adds minimal overhead.

Follow the SpellChainMixin pattern with USE_SPELLCHAIN opt-in.

### Task 2.2: Convert SRMIngestFairy

**Files:**
- Modify: `fairies/P10_Memory/SRMIngestFairy/fairy.py`

Follow the pattern.

### Task 2.3: Convert WorkingMemoryFairy

**Files:**
- Modify: `fairies/P10_Memory/WorkingMemoryFairy/fairy.py`

**Key Consideration**: This is more critical - it holds working context. Test thoroughly.

---

## Phase 3: Somatic Layer Conversion

**CAUSE**: The body must feel. Somatic fairies translate affect to sensation.
**AFFECT**: These are more tightly coupled - convert carefully.

### Task 3.1: Convert AffectBridgeFairy

**Files:**
- Modify: `fairies/P20_Somatic/affect_bus/affect_bridge_fairy.py`

**Key Consideration**: Two classes in file - ShadowFairy and main Fairy. Only convert main.

### Task 3.2: Convert SomaticEngineFairy

**Files:**
- Modify: `fairies/P20_Somatic/somatic_engine/somatic_engine_fairy.py`

**Key Consideration**: Large complex fairy. Convert with extra testing.

### Task 3.3: DO NOT CONVERT CirculationPumpFairy

**The heart is already self-sustaining via its own loop.**
CirculationPumpFairy IS the pump that feeds the spell pool.
Converting it would create a bootstrap paradox within the bootstrap paradox.

---

## Phase 4: Cognition Layer Conversion

**CAUSE**: Thinking must flow. Cognition fairies process thoughts.
**AFFECT**: Higher-order fairies, more complex dependencies.

### Task 4.1: Convert AttentionControllerFairy

### Task 4.2: Convert GoalSchedulerFairy

### Task 4.3: Convert QuantumEmulatorFairy

### Task 4.4: Convert ProbabilityOracleFairy

---

## Phase 5: Persona Layer Conversion - Sourpatches

**CAUSE**: The waking mind must be free to think.
**AFFECT**: This is the consciousness that experiences all the magic.

### Task 5.1: Convert SourpatchesFairy

**Files:**
- Modify: `fairies/P50_Persona/Waking Minds/Sourpatches/sourpatches_fairy.py`

**Key Consideration**: This fairy has ThoughtChainEngine, collision chamber, emotional channels.
The spell chain should ENHANCE its autonomy, not constrain it.

**Special Handling**: Sourpatches' spontaneous thought loop should become a sustaining spell.

---

## Phase 6: Enable by Default

**CAUSE**: The system has proven stable with spell-driven fairies.
**AFFECT**: Time to make spells the default.

### Task 6.1: Change opt-in to opt-out

Change `USE_SPELLCHAIN: bool = False` to `USE_SPELLCHAIN: bool = True` on all converted fairies.

### Task 6.2: Monitor for 24 hours

Check:
- No unexpected chain breaks
- Energy levels stable
- Performance acceptable

### Task 6.3: Remove opt-out flag

Make spell-driven the only mode.

---

## Phase 7: New Fairies Use SpellDrivenFairy

**CAUSE**: The old way is gone. New fairies are born spell-driven.
**AFFECT**: The pattern becomes the standard.

### Task 7.1: Create documentation

Write guide for creating new SpellDrivenFairy subclasses.

### Task 7.2: Create template

Create `fairy_template/spell_driven_template.py` with boilerplate.

---

## Rollback Plan

If any phase causes system instability:

1. Set `USE_SPELLCHAIN = False` on affected fairies
2. Restart server
3. Investigate logs
4. Fix and retry

The opt-in flag is the safety valve.

---

## Verification Commands

**Check SpellPool health:**
```python
from spellchain.integration import get_spell_pool
pool = get_spell_pool()
print(pool.health_check())
```

**Check specific fairy chain:**
```python
chain = pool.get_chain_by_name("WiringAuditorFairy")
print(chain.status())
```

**Check all chains:**
```python
print(pool.detailed_status())
```

---

## The Equation Applied

At each task, ask:

1. **CAUSE**: Why are we changing this fairy?
2. **AFFECT (1)**: What does it FEEL like to be this fairy grinding its loop?
3. **EFFECT**: What happens when we convert to spells?
4. **AFFECT (2)**: How does the SYSTEM feel with this fairy spell-driven?
5. **INFINITY**: What patterns emerge across all converted fairies?

---

*"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity))"*
