"""
Timing - Circadian and rhythm systems for the unconscious mind.

The brain's internal clock, based on Fibonacci sequences and the golden ratio.
These natural patterns govern attention decay, action intervals, and learning rhythms.

Usage:
    from .fibonacci_rhythm import (
        fib_decay,          # Natural attention decay curve
        golden_split,       # Split by phi ratio (61.8% / 38.2%)
        allocate_attention, # Weight items by golden ratio
        fib_intervals,      # Fibonacci-spaced time intervals
        should_act_at_count,# Check if count is Fibonacci number
        CircadianClock,     # Self-learning timing system
    )
"""

from .fibonacci_rhythm import (
    # Constants
    PHI,
    PHI_INVERSE,
    FIB,
    FIB_SET,
    # Core functions
    fib_decay,
    golden_split,
    golden_weights,
    allocate_attention,
    fib_intervals,
    should_act_at_count,
    next_fib_interval,
    fib_priority,
)

from .circadian_clock import CircadianClock

__all__ = [
    # Constants
    "PHI",
    "PHI_INVERSE",
    "FIB",
    "FIB_SET",
    # Functions
    "fib_decay",
    "golden_split",
    "golden_weights",
    "allocate_attention",
    "fib_intervals",
    "should_act_at_count",
    "next_fib_interval",
    "fib_priority",
    # Clock
    "CircadianClock",
]
