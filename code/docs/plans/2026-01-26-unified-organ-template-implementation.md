# Unified Organ Template Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Create the Unified Organ Template that gives every fairy body, shadow, workers, postal, and learning infrastructure with zero mixins.

**Architecture:** Single unified base class inheriting all capabilities. Existing fairies continue working through compatibility layer.

**Tech Stack:** Python 3.11+, existing postal_core, tracer_pool, spellchain systems

---

## Phase 0: Foundation Components

### Task 1: Create Body State Manager

**Files:**
- Create: `fairy_template/body.py`
- Test: `tests/fairy_template/test_body.py`

**Step 1: Write the failing test**

```python
# tests/fairy_template/test_body.py
import pytest
from fairy_template.body import FairyBody

def test_body_initial_state():
    body = FairyBody("TestFairy")
    assert body.energy == 1.0
    assert body.coherence == 0.5
    assert body.valence == 0.0
    assert body.is_depleted == False
    assert body.can_work == True

def test_body_energy_depletion():
    body = FairyBody("TestFairy")
    body.update_somatic({"energy": 0.1})
    assert body.is_depleted == True
    assert body.can_work == False

def test_body_affect_update():
    body = FairyBody("TestFairy")
    body.update_affect({"valence": 0.8, "arousal": 0.6, "primary": "joy"})
    assert body.valence == 0.8
    assert body.arousal == 0.6
    assert body.primary_affect == "joy"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/fairy_template/test_body.py -v`
Expected: FAIL with "No module named 'fairy_template.body'"

**Step 3: Write minimal implementation**

```python
# fairy_template/body.py
"""
Fairy Body - Somatic and Affect State Management

Every fairy has a body. The body tracks:
- Energy (somatic)
- Coherence (clarity of thinking)
- Affect (emotional state)
- Circadian (time-of-day context)

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import threading


@dataclass
class FairyBody:
    """
    Manages body state for a fairy.

    The body is not optional - every fairy has one.
    State is updated via postal subscriptions.
    """

    fairy_name: str

    # Somatic state
    energy: float = 1.0
    coherence: float = 0.5

    # Affect state
    valence: float = 0.0      # -1.0 to +1.0
    arousal: float = 0.5      # 0.0 to 1.0
    primary_affect: str = "neutral"

    # Circadian state
    circadian_phase: str = "unknown"

    # Sedation (sleep model)
    sedation_level: float = 0.0

    # Thread safety
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def is_depleted(self) -> bool:
        """True if energy is critically low."""
        return self.energy < 0.2

    @property
    def can_work(self) -> bool:
        """True if fairy can do work (has energy and not sedated)."""
        return self.energy > 0.3 and self.sedation_level < 0.7

    @property
    def affect(self) -> Dict[str, Any]:
        """Current affect state as dict."""
        return {
            "valence": self.valence,
            "arousal": self.arousal,
            "primary": self.primary_affect,
        }

    def update_somatic(self, state: Dict[str, Any]) -> None:
        """Update somatic state from postal message."""
        with self._lock:
            if "energy" in state:
                self.energy = max(0.0, min(1.0, float(state["energy"])))
            if "coherence" in state:
                self.coherence = max(0.0, min(1.0, float(state["coherence"])))

    def update_affect(self, state: Dict[str, Any]) -> None:
        """Update affect state from postal message."""
        with self._lock:
            if "valence" in state:
                self.valence = max(-1.0, min(1.0, float(state["valence"])))
            if "arousal" in state:
                self.arousal = max(0.0, min(1.0, float(state["arousal"])))
            if "primary" in state:
                self.primary_affect = str(state["primary"])

    def update_circadian(self, phase: str) -> None:
        """Update circadian phase."""
        with self._lock:
            self.circadian_phase = phase

    def update_sedation(self, level: float) -> None:
        """Update sedation level."""
        with self._lock:
            self.sedation_level = max(0.0, min(1.0, level))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize body state."""
        with self._lock:
            return {
                "fairy": self.fairy_name,
                "energy": self.energy,
                "coherence": self.coherence,
                "valence": self.valence,
                "arousal": self.arousal,
                "primary_affect": self.primary_affect,
                "circadian_phase": self.circadian_phase,
                "sedation_level": self.sedation_level,
                "is_depleted": self.is_depleted,
                "can_work": self.can_work,
            }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/fairy_template/test_body.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add fairy_template/body.py tests/fairy_template/test_body.py
git commit -m "feat(fairy_template): add FairyBody state manager

Body tracks somatic state (energy, coherence), affect state (valence,
arousal, primary affect), and circadian phase. Thread-safe updates.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 2: Create Shadow Self-Monitor

**Files:**
- Create: `fairy_template/shadow.py`
- Test: `tests/fairy_template/test_shadow.py`

**Step 1: Write the failing test**

```python
# tests/fairy_template/test_shadow.py
import pytest
from fairy_template.shadow import FairyShadow

def test_shadow_initial_health():
    shadow = FairyShadow("TestFairy")
    assert shadow.health == 1.0
    assert shadow.error_count == 0
    assert shadow.success_rate == 1.0

def test_shadow_error_tracking():
    shadow = FairyShadow("TestFairy")
    shadow.record_error(Exception("Test error"))
    assert shadow.error_count == 1
    assert shadow.health < 1.0
    assert shadow.last_error is not None

def test_shadow_success_tracking():
    shadow = FairyShadow("TestFairy")
    for _ in range(10):
        shadow.record_success()
    assert shadow.success_rate == 1.0

def test_shadow_should_rest():
    shadow = FairyShadow("TestFairy")
    # Record many errors
    for _ in range(20):
        shadow.record_error(Exception("Error"))
    assert shadow.should_rest() == True
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/fairy_template/test_shadow.py -v`
Expected: FAIL with "No module named 'fairy_template.shadow'"

**Step 3: Write minimal implementation**

```python
# fairy_template/shadow.py
"""
Fairy Shadow - Self-Monitoring and Evolution

The shadow is the fairy's immune system:
- Tracks errors and successes
- Monitors health
- Enables self-healing
- Supports evolution through learning

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class FairyShadow:
    """
    Self-monitoring shadow for a fairy.

    The shadow watches the fairy's health and enables evolution.
    Think of it as the immune system - always monitoring, ready to heal.
    """

    fairy_name: str

    # Health tracking
    _errors: deque = field(default_factory=lambda: deque(maxlen=100))
    _successes: deque = field(default_factory=lambda: deque(maxlen=100))

    # Evolution tracking
    _observations: int = 0
    _reflections: int = 0
    _crystallizations: int = 0

    # Thread safety
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def health(self) -> float:
        """Overall health score (0.0 to 1.0)."""
        with self._lock:
            if not self._errors and not self._successes:
                return 1.0
            total = len(self._errors) + len(self._successes)
            if total == 0:
                return 1.0
            return len(self._successes) / total

    @property
    def error_count(self) -> int:
        """Number of recent errors."""
        with self._lock:
            return len(self._errors)

    @property
    def success_rate(self) -> float:
        """Success rate of recent operations."""
        return self.health

    @property
    def last_error(self) -> Optional[Dict[str, Any]]:
        """Most recent error, if any."""
        with self._lock:
            if self._errors:
                return self._errors[-1]
            return None

    @property
    def evolution_score(self) -> float:
        """Learning progress score."""
        with self._lock:
            total = self._observations + self._reflections + self._crystallizations
            if total == 0:
                return 0.0
            # Weight crystallizations higher (actual learnings)
            weighted = (
                self._observations * 0.1 +
                self._reflections * 0.3 +
                self._crystallizations * 0.6
            )
            return min(1.0, weighted / 100)

    def record_error(self, error: Exception, context: Dict[str, Any] = None) -> None:
        """Record an error occurrence."""
        with self._lock:
            self._errors.append({
                "ts": time.time(),
                "error": str(error),
                "type": type(error).__name__,
                "context": context or {},
            })

    def record_success(self, context: Dict[str, Any] = None) -> None:
        """Record a successful operation."""
        with self._lock:
            self._successes.append({
                "ts": time.time(),
                "context": context or {},
            })

    def record_observation(self) -> None:
        """Record that an observation was made."""
        with self._lock:
            self._observations += 1

    def record_reflection(self) -> None:
        """Record that a reflection was made."""
        with self._lock:
            self._reflections += 1

    def record_crystallization(self) -> None:
        """Record that a learning was crystallized."""
        with self._lock:
            self._crystallizations += 1

    def should_rest(self) -> bool:
        """True if health is poor and fairy should rest."""
        return self.health < 0.3

    def get_health_report(self) -> Dict[str, Any]:
        """Full health diagnostics."""
        with self._lock:
            recent_errors = list(self._errors)[-5:]
            return {
                "fairy": self.fairy_name,
                "health": self.health,
                "error_count": len(self._errors),
                "success_count": len(self._successes),
                "success_rate": self.success_rate,
                "evolution_score": self.evolution_score,
                "should_rest": self.should_rest(),
                "recent_errors": recent_errors,
                "observations": self._observations,
                "reflections": self._reflections,
                "crystallizations": self._crystallizations,
            }

    def to_dict(self) -> Dict[str, Any]:
        """Serialize shadow state."""
        return self.get_health_report()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/fairy_template/test_shadow.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add fairy_template/shadow.py tests/fairy_template/test_shadow.py
git commit -m "feat(fairy_template): add FairyShadow self-monitoring

Shadow tracks errors, successes, and evolution. Acts as the fairy's
immune system - monitoring health and signaling when to rest.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

### Task 3: Create Worker Pool Wrapper

**Files:**
- Create: `fairy_template/workers.py`
- Test: `tests/fairy_template/test_workers.py`

**Step 1: Write the failing test**

```python
# tests/fairy_template/test_workers.py
import pytest
import time
from fairy_template.workers import FairyWorkerPool

def test_worker_pool_creation():
    pool = FairyWorkerPool("TestFairy", max_workers=2)
    assert pool.fairy_name == "TestFairy"
    assert pool.max_workers == 2

def test_worker_submit_and_result():
    pool = FairyWorkerPool("TestFairy", max_workers=2)

    def add(a, b):
        return a + b

    tracer_id = pool.submit(fn=add, args=(1, 2), intent="test.add")
    assert tracer_id is not None

    # Wait for result
    time.sleep(0.1)
    result = pool.get_result(tracer_id)
    assert result == 3

def test_worker_status_tracking():
    pool = FairyWorkerPool("TestFairy", max_workers=2)

    def slow_fn():
        time.sleep(0.5)
        return "done"

    tracer_id = pool.submit(fn=slow_fn, intent="test.slow")
    status = pool.get_status(tracer_id)
    assert status in ["pending", "running"]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/fairy_template/test_workers.py -v`
Expected: FAIL with "No module named 'fairy_template.workers'"

**Step 3: Write minimal implementation**

```python
# fairy_template/workers.py
"""
Fairy Worker Pool - Tracer-Tracked Parallel Execution

Every fairy has workers (like blood cells) that do the actual work.
All work is tracked via tracer IDs for perfect recall.

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
"""

import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, Tuple


@dataclass
class WorkerTask:
    """A single tracked work item."""
    tracer_id: str
    intent: str
    fn: Callable
    args: Tuple
    kwargs: Dict[str, Any]
    status: str = "pending"
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class FairyWorkerPool:
    """
    Tracer-tracked worker pool for a fairy.

    Wraps ThreadPoolExecutor with tracer ID tracking.
    Every operation gets a unique ID for perfect recall.
    """

    def __init__(
        self,
        fairy_name: str,
        max_workers: int = 4,
        timeout: float = 30.0,
    ):
        self.fairy_name = fairy_name
        self.max_workers = max_workers
        self.timeout = timeout

        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: Dict[str, WorkerTask] = {}
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()

    def submit(
        self,
        fn: Callable,
        args: Tuple = (),
        kwargs: Dict[str, Any] = None,
        intent: str = "unknown",
    ) -> str:
        """
        Submit work to the pool.

        Returns tracer_id for tracking.
        """
        tracer_id = f"{self.fairy_name}_{intent}_{uuid.uuid4().hex[:8]}"
        kwargs = kwargs or {}

        task = WorkerTask(
            tracer_id=tracer_id,
            intent=intent,
            fn=fn,
            args=args,
            kwargs=kwargs,
        )

        with self._lock:
            self._tasks[tracer_id] = task

        # Submit to executor
        future = self._executor.submit(self._run_task, tracer_id)
        with self._lock:
            self._futures[tracer_id] = future

        return tracer_id

    def _run_task(self, tracer_id: str) -> Any:
        """Execute a task and update its status."""
        with self._lock:
            task = self._tasks.get(tracer_id)
            if not task:
                return None
            task.status = "running"
            task.started_at = time.time()

        try:
            result = task.fn(*task.args, **task.kwargs)
            with self._lock:
                task.result = result
                task.status = "completed"
                task.completed_at = time.time()
            return result
        except Exception as e:
            with self._lock:
                task.error = str(e)
                task.status = "failed"
                task.completed_at = time.time()
            raise

    def get_result(self, tracer_id: str, timeout: float = None) -> Any:
        """Get the result of a task (blocks if not complete)."""
        timeout = timeout or self.timeout
        with self._lock:
            future = self._futures.get(tracer_id)
            task = self._tasks.get(tracer_id)

        if not future or not task:
            return None

        try:
            return future.result(timeout=timeout)
        except Exception:
            return task.result if task else None

    def get_status(self, tracer_id: str) -> str:
        """Get the status of a task."""
        with self._lock:
            task = self._tasks.get(tracer_id)
            return task.status if task else "unknown"

    def get_task_info(self, tracer_id: str) -> Optional[Dict[str, Any]]:
        """Get full task information."""
        with self._lock:
            task = self._tasks.get(tracer_id)
            if not task:
                return None
            return {
                "tracer_id": task.tracer_id,
                "intent": task.intent,
                "status": task.status,
                "error": task.error,
                "started_at": task.started_at,
                "completed_at": task.completed_at,
                "duration_ms": (
                    (task.completed_at - task.started_at) * 1000
                    if task.started_at and task.completed_at
                    else None
                ),
            }

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the worker pool."""
        self._executor.shutdown(wait=wait)

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            statuses = {}
            for task in self._tasks.values():
                statuses[task.status] = statuses.get(task.status, 0) + 1
            return {
                "fairy": self.fairy_name,
                "max_workers": self.max_workers,
                "total_tasks": len(self._tasks),
                "by_status": statuses,
            }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/fairy_template/test_workers.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add fairy_template/workers.py tests/fairy_template/test_workers.py
git commit -m "feat(fairy_template): add FairyWorkerPool with tracer tracking

Worker pool wraps ThreadPoolExecutor with tracer IDs for every task.
Enables perfect recall of all parallel work.

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

---

## Phase 1: Unified Base Class

### Task 4: Create UnifiedFairy Base

**Files:**
- Create: `fairy_template/unified.py`
- Modify: `fairy_template/__init__.py`
- Test: `tests/fairy_template/test_unified.py`

**Step 1: Write the failing test**

```python
# tests/fairy_template/test_unified.py
import pytest
from fairy_template.unified import UnifiedFairy

class TestFairy(UnifiedFairy):
    ACTOR_NAME = "TestFairy"
    PLANE = "P30"
    CHANNEL = "test"
    PURPOSE = "Testing"
    CAPABILITIES = ["test.capability"]
    SUBSCRIPTIONS = ["test.input"]

def test_unified_fairy_has_body():
    fairy = TestFairy()
    assert hasattr(fairy, 'body')
    assert fairy.body.energy == 1.0

def test_unified_fairy_has_shadow():
    fairy = TestFairy()
    assert hasattr(fairy, 'shadow')
    assert fairy.shadow.health == 1.0

def test_unified_fairy_has_workers():
    fairy = TestFairy()
    assert hasattr(fairy, 'workers')
    assert fairy.workers.fairy_name == "TestFairy"

def test_unified_fairy_identity():
    fairy = TestFairy()
    assert fairy.ACTOR_NAME == "TestFairy"
    assert fairy.PLANE == "P30"
    assert fairy.PURPOSE == "Testing"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/fairy_template/test_unified.py -v`
Expected: FAIL

**Step 3: Write implementation**

Create `fairy_template/unified.py` - the full unified base class integrating body, shadow, workers, postal, learning.

**Step 4: Run test to verify passes**

**Step 5: Commit**

---

### Task 5: Wire Postal Subscriptions

**Files:**
- Modify: `fairy_template/unified.py`
- Test: `tests/fairy_template/test_postal_wiring.py`

Wire automatic postal subscriptions from SUBSCRIPTIONS class variable.

---

### Task 6: Integrate Learning Infrastructure

**Files:**
- Modify: `fairy_template/unified.py`
- Test: `tests/fairy_template/test_learning.py`

Integrate observe(), reflect(), crystallize() methods.

---

## Phase 2: Compatibility Layer

### Task 7: Make Existing Fairy Inherit UnifiedFairy

**Files:**
- Modify: `fairy_template/base.py`

Make the existing `Fairy` class inherit from `UnifiedFairy` so existing fairies continue working.

---

### Task 8: Deprecation Warnings for Mixins

**Files:**
- Modify: `fairy_template/mixins/__init__.py`

Add deprecation warnings when mixins are imported.

---

## Phase 3: Migration (Per-Fairy)

### Task 9-N: Migrate Individual Fairies

For each fairy, remove mixin inheritance and convert to SUBSCRIPTIONS config.

---

## Verification

After implementation, verify:

1. **New fairy can boot with minimal code:**
   ```python
   class MinimalFairy(Fairy):
       ACTOR_NAME = "MinimalFairy"
       PLANE = "P40"
   ```

2. **Existing fairies still work** (compatibility layer)

3. **Body/Shadow/Workers accessible:**
   ```python
   fairy.body.energy
   fairy.shadow.health
   fairy.workers.submit(...)
   ```

4. **Learning methods work:**
   ```python
   fairy.observe(action="test")
   fairy.reflect(topic="test", thought="test")
   fairy.crystallize(learning_type="pattern", content="test")
   ```

---

## Risk Mitigation

- **Compatibility First**: Never break existing fairies
- **Incremental Migration**: One fairy at a time
- **Feature Flags**: Can disable unified components
- **Extensive Testing**: Test before each phase
