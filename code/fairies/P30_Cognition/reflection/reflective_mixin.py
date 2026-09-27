# reflective_mixin.py — Mixin for Fairies to Use Reflection Infrastructure
# ═══════════════════════════════════════════════════════════════════════════════
# INFRA: This is foundational infrastructure, not app-level functionality.
#
# This mixin provides the interface that any fairy can use to:
#   - Observe their own actions
#   - Generate reflections
#   - Apply learning traces
#   - Report feedback
#
# Usage:
#   class MyFairy(SomeBaseFairy, ReflectiveMixin):
#       def some_action(self, input_data):
#           with self.observe_action("some_action", input_data):
#               result = do_the_thing()
#               return result
#
# The context manager handles:
#   - Recording timing
#   - Capturing affect before/after
#   - Detecting success/failure
#   - Generating appropriate reflections
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import time
import hashlib
import functools
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Callable, Generator, TypeVar, cast

from .reflection_pool import ReflectionPool, Reflection, get_reflection_pool
from .learning_trace import LearningTrace, TraceEmitter, get_trace_emitter
from .pattern_observer import PatternObserver, Observation, get_pattern_observer
from .feedback_integrator import FeedbackIntegrator, get_feedback_integrator


T = TypeVar("T")


class ReflectiveMixin:
    """
    Mixin that gives fairies reflection capabilities.
    
    Any fairy that inherits from this mixin gains:
    - self.reflect() - Submit a reflection
    - self.observe_action() - Context manager for action observation
    - self.apply_trace() - Record that a learning trace was applied
    - self.report_feedback() - Report feedback on an action
    - self.ponder() - Trigger a pondering cycle
    - self.crystallize() - Process crystallized reflections into traces
    """
    
    # Override these in your fairy class
    FAIRY_NAME: str = "UnnamedFairy"
    
    def __init_reflection__(
        self,
        reflection_pool: Optional[ReflectionPool] = None,
        pattern_observer: Optional[PatternObserver] = None,
        trace_emitter: Optional[TraceEmitter] = None,
        feedback_integrator: Optional[FeedbackIntegrator] = None,
    ):
        """
        Initialize reflection components. Call this in your fairy's __init__.
        
        Example:
            def __init__(self):
                super().__init__()
                self.__init_reflection__()
        """
        self._reflection_pool = reflection_pool or get_reflection_pool()
        self._pattern_observer = pattern_observer or get_pattern_observer()
        self._trace_emitter = trace_emitter or get_trace_emitter()
        self._feedback_integrator = feedback_integrator or get_feedback_integrator()
        
        # Track applied traces for feedback correlation
        self._applied_traces: List[str] = []
        
        # Current affect state (fairies should update this)
        self._current_affect: Dict[str, Any] = {
            "valence": 0.0,
            "arousal": 0.0,
            "resonance": [],
        }
    
    @property
    def _fairy_name(self) -> str:
        """Get the fairy's name for reflection attribution."""
        # Try various common attribute names
        for attr in ["FAIRY_NAME", "ACTOR_NAME", "name", "__class__"]:
            val = getattr(self, attr, None)
            if val:
                if attr == "__class__":
                    return val.__name__
                return str(val)
        return "UnknownFairy"
    
    def reflect(
        self,
        observation: str,
        *,
        action: str = "",
        expected: Optional[str] = None,
        actual: Optional[str] = None,
        hypothesis: Optional[str] = None,
        tags: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Reflection:
        """
        Submit a reflection to the pool.
        
        Use this when you want to explicitly reflect on something,
        outside of the automatic observation system.
        """
        pool = getattr(self, "_reflection_pool", None) or get_reflection_pool()
        
        return pool.reflect(
            source_fairy=self._fairy_name,
            observation=observation,
            source_action=action,
            source_context=context or {},
            expected=expected,
            actual=actual,
            hypothesis=hypothesis,
            affect=getattr(self, "_current_affect", {}).copy(),
            tags=tags or [],
        )
    
    @contextmanager
    def observe_action(
        self,
        action: str,
        input_data: Any = None,
        *,
        expected_outcome: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Context manager for observing an action.
        
        Usage:
            with self.observe_action("process_data", input_data) as ctx:
                result = self.do_processing(input_data)
                ctx["actual_outcome"] = str(result)
                ctx["success"] = True
        
        The context dict can be modified to provide:
        - actual_outcome: What actually happened
        - success: Whether it succeeded (default: True unless exception)
        - output_summary: Summary of output for reflection
        """
        observer = getattr(self, "_pattern_observer", None) or get_pattern_observer()
        
        # Capture before state
        affect_before = getattr(self, "_current_affect", {}).copy()
        start_time = time.time()
        
        # Context dict that the caller can modify
        ctx = {
            "actual_outcome": None,
            "success": True,
            "output_summary": "",
            "exception": None,
        }
        
        try:
            yield ctx
        except Exception as e:
            ctx["success"] = False
            ctx["exception"] = e
            ctx["actual_outcome"] = f"Exception: {type(e).__name__}: {str(e)[:100]}"
            raise
        finally:
            # Capture after state
            affect_after = getattr(self, "_current_affect", {}).copy()
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            
            # Generate input summary
            if input_data is not None:
                if isinstance(input_data, str):
                    input_summary = input_data[:200]
                elif isinstance(input_data, dict):
                    input_summary = str({k: str(v)[:50] for k, v in list(input_data.items())[:5]})
                else:
                    input_summary = str(input_data)[:200]
            else:
                input_summary = ""
            
            # Record observation
            observer.observe(
                fairy_name=self._fairy_name,
                action=action,
                input_summary=input_summary,
                output_summary=ctx.get("output_summary", ""),
                expected_outcome=expected_outcome,
                actual_outcome=ctx.get("actual_outcome"),
                success=ctx.get("success", True),
                duration_ms=duration_ms,
                affect_before=affect_before,
                affect_after=affect_after,
                context={
                    "tags": tags or [],
                    "applied_traces": list(getattr(self, "_applied_traces", [])),
                },
            )
            
            # Clear applied traces for next action
            if hasattr(self, "_applied_traces"):
                self._applied_traces.clear()
    
    def apply_trace(self, trace: LearningTrace) -> bool:
        """
        Record that a learning trace is being applied to the current action.
        
        Call this before/during an action when you're using a learning trace
        to guide behavior. This enables feedback correlation.
        """
        if not hasattr(self, "_applied_traces"):
            self._applied_traces = []
        
        self._applied_traces.append(trace.id)
        trace.mark_applied()  # Increment application counter
        
        return True
    
    def report_feedback(
        self,
        action: str,
        *,
        success: bool = True,
        quality: float = 0.5,
        feedback_text: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Report feedback on an action.
        
        This closes the learning loop by updating trace effectiveness
        and potentially triggering new reflections.
        """
        integrator = getattr(self, "_feedback_integrator", None) or get_feedback_integrator()
        
        return integrator.integrate(
            fairy_name=self._fairy_name,
            action=action,
            success=success,
            quality=quality,
            feedback_text=feedback_text,
            trace_ids_applied=list(getattr(self, "_applied_traces", [])),
            context=context or {},
        )
    
    def ponder(self, n: int = 5) -> List[Reflection]:
        """
        Trigger a pondering cycle.
        
        This ages reflections in the pool and may crystallize some.
        Call this periodically (e.g., in shadow/idle processing).
        """
        pool = getattr(self, "_reflection_pool", None) or get_reflection_pool()
        return pool.ponder_cycle(n=n)
    
    def crystallize(self, max_traces: int = 5) -> List[LearningTrace]:
        """
        Process crystallized reflections into learning traces.
        
        Returns the new traces that were created and emitted.
        """
        pool = getattr(self, "_reflection_pool", None) or get_reflection_pool()
        emitter = getattr(self, "_trace_emitter", None) or get_trace_emitter()
        
        traces = []
        for _ in range(max_traces):
            reflection = pool.pop_crystallized()
            if reflection is None:
                break
            
            # Create trace from reflection
            trace = LearningTrace.from_reflection(
                reflection,
                insight=reflection.hypothesis or f"Pattern observed in {reflection.source_action}",
                recommendation=f"Consider applying this pattern: {reflection.observation[:100]}",
                confidence=min(0.8, 0.3 + reflection.pondered_count * 0.1),
            )
            
            # Emit to memory system
            emitter.emit(trace)
            traces.append(trace)
        
        return traces
    
    def update_affect(
        self,
        valence: Optional[float] = None,
        arousal: Optional[float] = None,
        resonance: Optional[List[str]] = None,
    ):
        """
        Update the fairy's current affect state.
        
        Call this when emotional state changes. It will be captured
        in observations for affect shift detection.
        """
        if not hasattr(self, "_current_affect"):
            self._current_affect = {"valence": 0.0, "arousal": 0.0, "resonance": []}
        
        if valence is not None:
            self._current_affect["valence"] = max(-1.0, min(1.0, valence))
        if arousal is not None:
            self._current_affect["arousal"] = max(0.0, min(1.0, arousal))
        if resonance is not None:
            self._current_affect["resonance"] = resonance
    
    def get_reflection_stats(self) -> Dict[str, Any]:
        """Get reflection statistics for this fairy."""
        pool = getattr(self, "_reflection_pool", None) or get_reflection_pool()
        observer = getattr(self, "_pattern_observer", None) or get_pattern_observer()
        integrator = getattr(self, "_feedback_integrator", None) or get_feedback_integrator()
        
        return {
            "pool_stats": pool.stats(),
            "observation_stats": observer.get_fairy_stats(self._fairy_name),
            "feedback_stats": integrator.get_fairy_stats(self._fairy_name),
        }


def reflective(action_name: Optional[str] = None):
    """
    Decorator for methods that should be automatically observed.
    
    Usage:
        @reflective("process_data")
        def process_data(self, input_data):
            return do_processing(input_data)
    
    Or without explicit name (uses method name):
        @reflective()
        def process_data(self, input_data):
            return do_processing(input_data)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        name = action_name or func.__name__
        
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs) -> T:
            # Check if self has observe_action (is a ReflectiveMixin)
            if not hasattr(self, "observe_action"):
                return func(self, *args, **kwargs)
            
            with self.observe_action(name, args[0] if args else kwargs):
                result = func(self, *args, **kwargs)
                return result
        
        return wrapper
    
    return decorator
