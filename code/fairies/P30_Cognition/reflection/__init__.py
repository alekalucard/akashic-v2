# P30_Cognition/reflection - Reflection Infrastructure
# ═══════════════════════════════════════════════════════════════════════════════
# INFRA: Core infrastructure for self-observation, learning, and evolution
#
# This is foundational infrastructure, NOT app-level functionality.
# Any fairy can use these primitives to:
#   - Observe their own behavior patterns
#   - Integrate feedback into learning
#   - Emit learning traces to memory
#   - Evolve based on experience
#
# The reflection system implements a "slow thinking" loop:
#
#   Action → Observation → Reflection → Pondering → Crystallization → Learning Trace
#                                                          ↓
#                                              Memory Card (SRM_Intake)
#                                                          ↓
#                                              Future Actions (via trace lookup)
#
# Biological analogs:
#   - ReflectionPool: Default mode network (idle integration)
#   - PatternObserver: Anterior cingulate cortex (error/conflict monitoring)
#   - FeedbackIntegrator: Dopaminergic reward prediction (learning signals)
#   - LearningTrace: Long-term potentiation (consolidated learning)
# ═══════════════════════════════════════════════════════════════════════════════

from .reflection_pool import (
    ReflectionPool,
    Reflection,
    get_reflection_pool,
    set_reflection_pool,
)

from .learning_trace import (
    LearningTrace,
    TraceEmitter,
    get_trace_emitter,
    set_trace_emitter,
)

from .pattern_observer import (
    PatternObserver,
    Observation,
    get_pattern_observer,
    set_pattern_observer,
)

from .feedback_integrator import (
    FeedbackIntegrator,
    Feedback,
    get_feedback_integrator,
    set_feedback_integrator,
)

from .reflective_mixin import (
    ReflectiveMixin,
    reflective,
)

__all__ = [
    # Core classes
    "ReflectionPool",
    "Reflection",
    "LearningTrace",
    "TraceEmitter",
    "PatternObserver",
    "Observation",
    "FeedbackIntegrator",
    "Feedback",
    
    # Mixin for fairies
    "ReflectiveMixin",
    "reflective",
    
    # Global accessors
    "get_reflection_pool",
    "set_reflection_pool",
    "get_trace_emitter",
    "set_trace_emitter",
    "get_pattern_observer",
    "set_pattern_observer",
    "get_feedback_integrator",
    "set_feedback_integrator",
]


# ═══════════════════════════════════════════════════════════════════════════════
# Quick Usage Guide
# ═══════════════════════════════════════════════════════════════════════════════
#
# 1. Make your fairy reflective:
#    
#    from fairies.P30_Cognition.reflection import ReflectiveMixin
#    
#    class MyFairy(BaseFairy, ReflectiveMixin):
#        FAIRY_NAME = "MyFairy"
#        
#        def __init__(self):
#            super().__init__()
#            self.__init_reflection__()
#
# 2. Observe actions automatically:
#    
#    def process_data(self, data):
#        with self.observe_action("process_data", data) as ctx:
#            result = self._do_processing(data)
#            ctx["success"] = True
#            ctx["actual_outcome"] = str(result)
#            return result
#
# 3. Or use the decorator:
#    
#    from fairies.P30_Cognition.reflection import reflective
#    
#    @reflective("process_data")
#    def process_data(self, data):
#        return self._do_processing(data)
#
# 4. Explicit reflection:
#    
#    self.reflect(
#        "Noticed unusual pattern in input",
#        action="process_data",
#        hypothesis="May need different handling for this input type",
#    )
#
# 5. Run reflection cycles (in shadow/idle processing):
#    
#    # Ponder existing reflections
#    self.ponder(n=10)
#    
#    # Crystallize mature reflections into learning traces
#    new_traces = self.crystallize(max_traces=3)
#
# 6. Close the feedback loop:
#    
#    self.report_feedback(
#        "process_data",
#        success=True,
#        quality=0.8,
#        feedback_text="Output was accurate",
#    )
# ═══════════════════════════════════════════════════════════════════════════════
