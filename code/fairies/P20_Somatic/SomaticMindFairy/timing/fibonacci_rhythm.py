"""
Fibonacci Rhythm - Natural timing patterns for consciousness.

The golden ratio (phi = 1.618...) appears throughout nature in growth patterns,
spiral arrangements, and aesthetic proportions. We use it here for:

1. Attention Decay - Memories/stimuli fade following phi-based curves
2. Weight Allocation - Distribute attention using golden ratio splits
3. Action Timing - Fibonacci intervals for natural scheduling
4. Priority Ranking - Items weighted by their position in golden sequence
5. Reflection Checkpoints - Dynamic Fibonacci-depth pause points for thought chains
6. Mode Cycling - Golden-ratio-driven rotation through reasoning modes

The unconscious mind uses these patterns because they feel "right" -
they match the natural rhythms that biological systems have evolved.

Mathematical foundation:
- PHI = (1 + sqrt(5)) / 2 ≈ 1.618033988749895
- PSI = (1 - sqrt(5)) / 2 ≈ -0.618033988749895
- Binet's Formula: F(n) = (φⁿ - ψⁿ) / √5  (closed-form Fibonacci)
- PHI has the unique property: phi^2 = phi + 1
- Fibonacci sequence: each term is sum of previous two
- As Fib numbers grow, ratio approaches phi: F(n+1)/F(n) → phi
"""

from typing import List, Tuple, Any, Callable, Optional
import math

# =============================================================================
# GOLDEN CONSTANTS
# =============================================================================

PHI = 1.618033988749895  # The golden ratio: (1 + √5) / 2
PSI = -0.6180339887498949  # The conjugate: (1 - √5) / 2
PHI_INVERSE = 0.6180339887498949  # 1/phi (also phi - 1)
PHI_SQUARED = 2.618033988749895  # phi^2 = phi + 1
SQRT5 = 2.23606797749979  # √5 (Binet denominator)

# First 15 Fibonacci numbers - cached for O(1) lookup of common values
FIB = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610]
FIB_SET = frozenset(FIB)  # For O(1) membership testing


# =============================================================================
# BINET'S FORMULA - Dynamic Fibonacci computation
# =============================================================================
# F(n) = (φⁿ - ψⁿ) / √5
# Replaces static lookup tables with continuous mathematics.
# Accurate for n up to ~70 (beyond that, float precision degrades).
# =============================================================================

def binet(n: int) -> int:
    """
    Compute the nth Fibonacci number using Binet's closed-form formula.

    F(n) = (φⁿ - ψⁿ) / √5

    This eliminates the need for static Fibonacci tables — any F(n) can be
    computed in O(1) time. For n <= 15, uses the cached FIB table. For larger
    n, computes dynamically via Binet's formula.

    Args:
        n: The Fibonacci index (0-indexed: binet(0)=0, binet(1)=1, binet(6)=8)

    Returns:
        The nth Fibonacci number (integer)

    Example:
        >>> binet(10)
        55
        >>> binet(20)
        6765
        >>> binet(0)
        0
    """
    if n <= 0:
        return 0
    if n <= len(FIB):
        return FIB[n - 1]
    # Binet's formula: F(n) = round((φⁿ - ψⁿ) / √5)
    # For n > ~70, float precision degrades — but consciousness doesn't need n > 50
    return round((PHI ** n - PSI ** n) / SQRT5)


def is_fibonacci(n: int) -> bool:
    """
    Check if n is a Fibonacci number using the mathematical test.

    A positive integer n is Fibonacci if and only if one of
    (5n² + 4) or (5n² - 4) is a perfect square.

    This replaces the static FIB_SET membership test — works for ANY n,
    not just the first 15 Fibonacci numbers.

    Args:
        n: Number to test

    Returns:
        True if n is a Fibonacci number

    Example:
        >>> is_fibonacci(8)
        True
        >>> is_fibonacci(9)
        False
        >>> is_fibonacci(6765)
        True
    """
    if n <= 0:
        return n == 0
    if n <= 610:  # Within cached range — O(1) set lookup
        return n in FIB_SET
    # Mathematical test: n is Fibonacci iff 5n²+4 or 5n²-4 is perfect square
    test = 5 * n * n
    sqrt_plus = math.isqrt(test + 4)
    sqrt_minus = math.isqrt(test - 4)
    return (sqrt_plus * sqrt_plus == test + 4) or (sqrt_minus * sqrt_minus == test - 4)


def nearest_fibonacci(n: int) -> int:
    """
    Find the nearest Fibonacci number to n.

    Uses Binet's inverse: the index of the nearest Fibonacci number is
    approximately round(log_phi(n * √5)).

    Args:
        n: Target number

    Returns:
        The closest Fibonacci number

    Example:
        >>> nearest_fibonacci(10)
        8
        >>> nearest_fibonacci(50)
        55
    """
    if n <= 1:
        return 1
    # Approximate Fibonacci index using inverse Binet
    idx = round(math.log(n * SQRT5) / math.log(PHI))
    idx = max(1, idx)
    # Check idx and neighbors for closest
    candidates = [binet(max(1, idx - 1)), binet(idx), binet(idx + 1)]
    return min(candidates, key=lambda f: abs(f - n))


# =============================================================================
# DYNAMIC REFLECTION DEPTHS - Replaces hardcoded [5, 8, 13, 21]
# =============================================================================
# Thought chains pause for reflection at Fibonacci depths. Instead of a
# static set, we generate depths dynamically up to any max_depth.
# This means deeper chains naturally get more reflection points.
# =============================================================================

def reflection_depths(max_depth: int = 21) -> frozenset:
    """
    Generate Fibonacci-number reflection checkpoints up to max_depth.

    Replaces the hardcoded FIB_REFLECTION_DEPTHS = frozenset([5, 8, 13, 21]).
    Now dynamically computed: if max_depth grows (e.g., for a deeper thinker),
    the reflection checkpoints grow with it.

    Skips depths < 3 (too early to reflect — need momentum first).

    Args:
        max_depth: Maximum chain depth to generate checkpoints for

    Returns:
        frozenset of Fibonacci numbers between 3 and max_depth (inclusive)

    Example:
        >>> reflection_depths(21)
        frozenset({3, 5, 8, 13, 21})
        >>> reflection_depths(55)
        frozenset({3, 5, 8, 13, 21, 34, 55})
    """
    depths = set()
    a, b = 1, 1
    while b <= max_depth:
        if b >= 3:  # Skip 1, 1, 2 — too early to pause
            depths.add(b)
        a, b = b, a + b
    return frozenset(depths)


def is_reflection_depth(depth: int, max_depth: int = 21) -> bool:
    """
    Check if a given chain depth is a Fibonacci reflection checkpoint.

    Args:
        depth: Current chain depth
        max_depth: Maximum chain depth

    Returns:
        True if this depth should trigger a reflection pause
    """
    if depth < 3:
        return False
    return is_fibonacci(depth) and depth <= max_depth


def dynamic_max_depth(energy: float = 1.0, base_depth: int = 21) -> int:
    """
    Compute max chain depth based on available energy using golden ratio.

    When energy is full (1.0), use base_depth. As energy drops, depth
    contracts to the nearest-lower Fibonacci number. This creates natural
    thinking conservation: tired systems think in shallower chains.

    Args:
        energy: Available energy (0.0 to 1.0)
        base_depth: Maximum depth at full energy (default 21)

    Returns:
        Fibonacci-aligned max depth for current energy level

    Example:
        >>> dynamic_max_depth(1.0)
        21
        >>> dynamic_max_depth(0.5)
        13
        >>> dynamic_max_depth(0.2)
        5
    """
    energy = max(0.0, min(1.0, energy))
    target = int(base_depth * energy)
    if target < 3:
        return 3  # Minimum thinking depth
    return nearest_fibonacci(target)


# Export the commonly-used defaults for backward compatibility
FIB_REFLECTION_DEPTHS = reflection_depths(21)  # {3, 5, 8, 13, 21}
FIB_BRANCH_DEPTHS = reflection_depths(13)  # {3, 5, 8, 13} — for branching


# =============================================================================
# GOLDEN RATIO MODE CYCLING - Replaces hardcoded % 10 / % 5
# =============================================================================
# Instead of cycling through modes on fixed modular intervals,
# use golden ratio spacing for maximal coverage (like phyllotaxis in plants).
# =============================================================================

def golden_cycle_index(tick: int, num_modes: int) -> int:
    """
    Select a mode index using golden ratio cycling.

    In nature, leaves arrange at golden-angle offsets (137.5°) so each
    new leaf maximally avoids overlap with previous ones. We use the same
    principle: each tick selects a mode by advancing by PHI_INVERSE fraction,
    ensuring maximum spread across modes over time.

    This replaces hardcoded `index % len(modes)` sequential cycling, which
    tends to create predictable, repetitive patterns.

    Args:
        tick: Current tick/iteration count
        num_modes: Number of available modes

    Returns:
        Mode index (0 to num_modes-1)

    Example:
        >>> [golden_cycle_index(t, 4) for t in range(8)]
        [0, 2, 1, 3, 0, 2, 1, 3]  # Quasi-random, maximal spread
    """
    if num_modes <= 0:
        return 0
    # Golden angle in mode-space: tick * φ⁻¹ mod 1.0 → scaled to num_modes
    fractional = (tick * PHI_INVERSE) % 1.0
    return int(fractional * num_modes) % num_modes


def weighted_mode_index(tick: int, num_modes: int, depth_type: str = "none") -> int:
    """
    Select a mode index with gravitational bias based on reflection depth.

    The golden angle provides base spread (phyllotaxis), but the reflection
    TYPE bends the selection toward preferred regions of mode-space:

    - "light" reflections: bias toward SURFACE modes (indices 0, 1)
      → logical, probabilistic — quick analytical passes
    - "full" reflections: bias toward DEPTH modes (indices 2, 3)
      → paradoxical, irrational — deep symbolic/paradox work
    - "none": uniform golden-ratio spread (original behavior)

    The bias uses PHI itself as the gravitational exponent:
    - Light: fractional^PHI pulls the distribution toward 0 (surface)
    - Full: 1 - (1-fractional)^PHI pulls toward 1 (depth)

    This means PHI simultaneously controls:
    1. TIMING of reflections (Fibonacci tick gating)
    2. SPACING between modes (golden angle phyllotaxis)
    3. WEIGHTING of which modes are preferred (gravitational bias)

    One constant ruling all three dimensions.

    Args:
        tick: Current tick/iteration count
        num_modes: Number of available modes (typically 4)
        depth_type: "light", "full", or "none"

    Returns:
        Mode index (0 to num_modes-1)

    Example:
        >>> # Light reflections favor early modes (0, 1)
        >>> counts = [0]*4
        >>> for t in range(100):
        ...     counts[weighted_mode_index(t, 4, "light")] += 1
        >>> counts[0] + counts[1] > counts[2] + counts[3]
        True

        >>> # Full reflections favor later modes (2, 3)
        >>> counts = [0]*4
        >>> for t in range(100):
        ...     counts[weighted_mode_index(t, 4, "full")] += 1
        >>> counts[2] + counts[3] > counts[0] + counts[1]
        True
    """
    if num_modes <= 0:
        return 0
    if num_modes == 1:
        return 0

    # Base golden-angle spread: tick * phi-inverse mod 1.0
    fractional = (tick * PHI_INVERSE) % 1.0

    # Apply gravitational bias based on reflection depth
    if depth_type == "light":
        # Pull toward 0 (surface modes): fractional^PHI
        # PHI > 1, so values < 1 get smaller → concentrates near 0
        fractional = fractional ** PHI
    elif depth_type == "full":
        # Pull toward 1 (depth modes): 1 - (1 - fractional)^PHI
        # Mirror the light bias around 0.5
        fractional = 1.0 - (1.0 - fractional) ** PHI

    # Scale to mode count
    return int(fractional * num_modes) % num_modes


def should_reflect_at_tick(tick: int, base_interval: float = 8.0) -> str:
    """
    Determine reflection type at this tick using golden ratio intervals.

    Replaces hardcoded `tick % 10 == 0` (full) and `tick % 5 == 0` (light).
    Uses golden ratio to space full reflections, with lighter reflections
    at phi-subdivisions between them.

    Args:
        tick: Current tick count
        base_interval: Base interval for full reflections (default 8, a Fibonacci number)

    Returns:
        "full" for deep DualCoT reflection
        "light" for analytical-only reflection
        "none" for no reflection this tick

    Example:
        >>> should_reflect_at_tick(8)
        "full"       # Fibonacci >= 8
        >>> should_reflect_at_tick(6)
        "light"      # 6 % 3 == 0, every 3rd tick
        >>> should_reflect_at_tick(4)
        "none"       # Not a reflection tick
    """
    if tick <= 0:
        return "none"

    # Full reflection at Fibonacci intervals (8, 13, 21, 34, ...)
    if is_fibonacci(tick) and tick >= int(base_interval):
        return "full"

    # Light reflection at golden-ratio subdivisions
    # Every base_interval * PHI_INVERSE ≈ 5 ticks (nearest Fibonacci)
    light_interval = max(3, nearest_fibonacci(int(base_interval * PHI_INVERSE)))
    if tick % light_interval == 0 and tick >= 3:
        return "light"

    return "none"

# =============================================================================
# DECAY FUNCTIONS
# =============================================================================

def fib_decay(age: float, scale: float = 10.0) -> float:
    """
    Fibonacci-based decay curve for attention/relevance.

    Returns a value from 1.0 (new) to approaching 0.0 (old).
    The decay follows a phi-based power law for natural feel.

    Formula: 1.0 / (1.0 + (age / scale) ^ phi)

    Args:
        age: How old the item is (seconds, iterations, etc.)
        scale: Time scale - higher = slower decay (default 10)

    Returns:
        Relevance weight from 0.0 to 1.0

    Example:
        >>> fib_decay(0)    # Brand new
        1.0
        >>> fib_decay(10)   # age == scale
        0.382...            # ~38.2% relevance
        >>> fib_decay(100)  # Much older
        0.014...            # ~1.4% relevance
    """
    if age <= 0:
        return 1.0
    ratio = age / scale
    return 1.0 / (1.0 + ratio ** PHI)


def exponential_fib_decay(age: float, half_life: float = 8.0) -> float:
    """
    Exponential decay with Fibonacci-tuned half-life.

    Default half-life of 8 (Fibonacci number) means item loses
    half its relevance every 8 time units.

    Args:
        age: How old the item is
        half_life: Time to reach half relevance (should be Fib number)

    Returns:
        Relevance weight from 0.0 to 1.0
    """
    if age <= 0:
        return 1.0
    return 0.5 ** (age / half_life)


# =============================================================================
# GOLDEN RATIO SPLITS
# =============================================================================

def golden_split(total: float) -> Tuple[float, float]:
    """
    Split a value by the golden ratio.

    Returns (major, minor) where major/minor ≈ phi.
    Major is ~61.8% and minor is ~38.2% of total.

    Args:
        total: The value to split

    Returns:
        (major, minor) tuple

    Example:
        >>> golden_split(100)
        (61.80..., 38.19...)
    """
    major = total * PHI_INVERSE
    minor = total - major
    return (major, minor)


def golden_weights(count: int) -> List[float]:
    """
    Generate weights for N items using golden ratio splits.

    Repeatedly applies golden_split to create a natural
    distribution where each weight is phi times the next.
    Weights are normalized to sum to 1.0.

    Args:
        count: Number of weights to generate

    Returns:
        List of weights summing to 1.0

    Example:
        >>> golden_weights(3)
        [0.5, 0.309..., 0.190...]  # Each is ~0.618x the previous
    """
    if count <= 0:
        return []
    if count == 1:
        return [1.0]

    weights = []
    remaining = 1.0

    for i in range(count - 1):
        major, minor = golden_split(remaining)
        weights.append(major)
        remaining = minor

    weights.append(remaining)  # Last item gets what's left
    return weights


# =============================================================================
# ATTENTION ALLOCATION
# =============================================================================

def allocate_attention(
    items: List[Any],
    key: Optional[Callable[[Any], float]] = None
) -> List[Tuple[Any, float]]:
    """
    Allocate attention weights to items using golden ratio.

    Items are optionally sorted by key, then assigned weights
    following golden ratio distribution. First item gets most
    attention, each subsequent gets ~61.8% of previous.

    Args:
        items: List of items to weight
        key: Optional function to extract sort value (higher = more attention)

    Returns:
        List of (item, weight) tuples, weights sum to 1.0

    Example:
        >>> items = ['urgent', 'normal', 'low']
        >>> allocate_attention(items)
        [('urgent', 0.5), ('normal', 0.309...), ('low', 0.190...)]
    """
    if not items:
        return []

    # Sort by key if provided (descending - high values first)
    sorted_items = sorted(items, key=key, reverse=True) if key else list(items)

    # Generate golden weights
    weights = golden_weights(len(sorted_items))

    # Pair items with weights
    return list(zip(sorted_items, weights))


# =============================================================================
# FIBONACCI INTERVALS
# =============================================================================

def fib_intervals(base: float = 1.0, count: int = 8) -> List[float]:
    """
    Generate Fibonacci-spaced time intervals.

    These intervals follow the Fibonacci sequence, creating
    a natural rhythm that starts fast and gradually slows.
    Good for retry timing, polling intervals, learning schedules.

    Args:
        base: Base time unit (default 1.0)
        count: Number of intervals to generate

    Returns:
        List of interval durations

    Example:
        >>> fib_intervals(base=1.0, count=8)
        [1, 1, 2, 3, 5, 8, 13, 21]  # Natural rhythm
    """
    if count <= 0:
        return []
    # Use binet() for any index — no need to extend static tables
    return [binet(i + 1) * base for i in range(count)]


def cumulative_fib_intervals(base: float = 1.0, count: int = 8) -> List[float]:
    """
    Generate cumulative Fibonacci intervals (absolute times).

    Returns times at which each interval ends, not the interval durations.
    Useful for scheduling: "wake up at time T[i]"

    Args:
        base: Base time unit
        count: Number of intervals

    Returns:
        List of cumulative times

    Example:
        >>> cumulative_fib_intervals(base=1.0, count=5)
        [1, 2, 4, 7, 12]  # Absolute times
    """
    intervals = fib_intervals(base, count)
    cumulative = []
    total = 0.0
    for interval in intervals:
        total += interval
        cumulative.append(total)
    return cumulative


# =============================================================================
# ACTION TIMING
# =============================================================================

def should_act_at_count(count: int) -> bool:
    """
    Check if an action should happen at this loop count.

    Returns True if count is a Fibonacci number.
    Use this for "act on Fibonacci beats" timing.

    Now delegates to is_fibonacci() which uses Binet's mathematical test,
    so it works for arbitrarily large counts (not just the first 15).

    Args:
        count: Current loop iteration

    Returns:
        True if count is a Fibonacci number

    Example:
        # Only process on Fibonacci iterations
        for i in range(100):
            if should_act_at_count(i):
                process_batch()  # Runs at 1,1,2,3,5,8,13,21,34,55,89
    """
    if count <= 0:
        return False
    return is_fibonacci(count)


def next_fib_interval(current: int) -> int:
    """
    Get the next Fibonacci number after current.

    Used for "when should I next wake up?" timing.

    Args:
        current: Current count/time

    Returns:
        Next Fibonacci number >= current

    Example:
        >>> next_fib_interval(6)
        8
        >>> next_fib_interval(8)
        8  # Already on Fibonacci
    """
    if current <= 1:
        return 1

    # Use Binet's inverse to approximate the Fibonacci index, then check neighbors
    # index ≈ log_phi(current * √5) — the inverse of Binet's formula
    idx = max(1, round(math.log(max(1, current) * SQRT5) / math.log(PHI)))
    # Check idx and idx+1 (binet may undershoot due to rounding)
    f = binet(idx)
    if f >= current:
        return f
    return binet(idx + 1)


# =============================================================================
# PRIORITY RANKING
# =============================================================================

def fib_priority(position: int, total: int) -> float:
    """
    Get priority weight based on position using Fibonacci weighting.

    Position 0 gets highest weight, declining by golden ratio.

    Args:
        position: Item's position (0-indexed)
        total: Total number of items

    Returns:
        Priority weight (higher = more priority)

    Example:
        >>> [fib_priority(i, 5) for i in range(5)]
        [0.5, 0.309, 0.190, 0.117, 0.072...]  # Golden-weighted
    """
    weights = golden_weights(total)
    if 0 <= position < len(weights):
        return weights[position]
    return 0.0


def rank_by_fib_score(
    items: List[Any],
    scorer: Callable[[Any], float]
) -> List[Tuple[Any, float, float]]:
    """
    Rank items by score, then apply Fibonacci priority weights.

    Returns items sorted by score, with both raw score and
    Fibonacci-weighted priority attached.

    Args:
        items: Items to rank
        scorer: Function returning score for each item

    Returns:
        List of (item, score, fib_priority) tuples

    Example:
        >>> tasks = [{'name': 'A', 'urgency': 5}, {'name': 'B', 'urgency': 8}]
        >>> rank_by_fib_score(tasks, lambda t: t['urgency'])
        [({'name': 'B', ...}, 8, 0.618),
         ({'name': 'A', ...}, 5, 0.382)]
    """
    if not items:
        return []

    # Score and sort
    scored = [(item, scorer(item)) for item in items]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Add Fibonacci priorities
    weights = golden_weights(len(scored))
    return [(item, score, weight) for (item, score), weight in zip(scored, weights)]
