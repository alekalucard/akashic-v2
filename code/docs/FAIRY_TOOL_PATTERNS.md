# Fairy Tool Patterns Library

Reference documentation for common patterns in the Akashic V2 fairy tool system.
Copy-paste these patterns when building new fairies and tools.

---

## Table of Contents

1. [MCP Tool Registration Pattern](#1-mcp-tool-registration-pattern)
2. [Postal Bridge Pattern](#2-postal-bridge-pattern)
3. [Satisfaction Learning Pattern](#3-satisfaction-learning-pattern)
4. [Multi-Wanting Selection Pattern](#4-multi-wanting-selection-pattern)
5. [Need/Want Classification Pattern](#5-needwant-classification-pattern)

---

## 1. MCP Tool Registration Pattern

The Model Context Protocol (MCP) allows Claude to call tools. Tools are defined in
separate files and registered with the main `akashic_mcp_server.py`.

### Step 1: Create a Tool File

Location: `fairies/P40_Sensory/mcp/your_tools.py`

```python
"""
Your Tool Module - MCP tools for [purpose].

These tools let Claude [what they enable].
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any

# Add project paths for imports
_project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(_project_root))


def register_your_tools(mcp):
    """Register your tools with MCP."""

    @mcp.tool()
    def your_tool_name(param1: str, param2: int = 10) -> str:
        """
        One-line description of what this tool does.

        More detailed explanation if needed. Claude reads this
        docstring to understand when to use the tool.

        Args:
            param1: Description of param1
            param2: Description with default noted

        Returns:
            JSON string with result
        """
        try:
            # Your tool logic here
            result = {"status": "success", "data": param1}
            return json.dumps(result, indent=2, default=str)

        except ImportError as e:
            return json.dumps({"error": f"Module not available: {e}"})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def another_tool() -> str:
        """Another tool in the same file."""
        return json.dumps({"ok": True})
```

### Step 2: Register with MCP Server

Add to `fairies/P40_Sensory/mcp/akashic_mcp_server.py`:

```python
# ============================================================================
# YOUR TOOLS
# ============================================================================

HAS_YOUR_TOOLS = False
try:
    from your_tools import register_your_tools
    register_your_tools(mcp)
    HAS_YOUR_TOOLS = True
    sys.stderr.write("[MCP] [OK] Your tools loaded\n")
except ImportError as e:
    sys.stderr.write(f"[MCP] Your tools not available: {e}\n")
```

### Step 3: Add Postal Tracking (Optional)

Use the `@postal_tracked` decorator to emit tool results to the consciousness mesh:

```python
from akashic_mcp_server import postal_tracked

def register_your_tools(mcp):

    @mcp.tool()
    @postal_tracked  # Emits to mcp.tool_result channel
    def tracked_tool(data: str) -> str:
        """This tool's results are broadcast to the postal system."""
        return json.dumps({"processed": data})
```

### Key Files Reference

- Main server: `fairies/P40_Sensory/mcp/akashic_mcp_server.py`
- Example tools: `fairies/P40_Sensory/mcp/attention_tools.py`
- Agent tools: `fairies/P40_Sensory/mcp/agent_tools_async.py`

---

## 2. Postal Bridge Pattern

The postal system connects fairies via publish/subscribe messaging.
Messages flow through a TensorFabric that routes to subscribers.

### Publishing Messages

From a fairy that inherits `PostalMixin`:

```python
from fairy_template import Fairy
from fairy_template.postal_shim import PostalMixin

class MyFairy(PostalMixin, Fairy):
    """Fairy with postal capabilities."""

    def do_something(self):
        # Method 1: Using self.post (convenience wrapper)
        self.post.publish("my.topic.name", {
            "from": self.ACTOR_NAME,
            "data": "payload here",
            "ts": time.time(),
        })

        # Method 2: Using self.post.route (alias)
        self.post.route("my.topic.name", {"data": "same effect"})

        # Method 3: Using convenience methods
        self.post.to_COGNITION({"opcode": "THINK", "payload": {...}})
        self.post.to_TELEMETRY({"opcode": "STATUS", "payload": {...}})
        self.post.to_CONSCIOUSNESS({"thought": "...", "ts": time.time()})
```

From outside a fairy (e.g., InterestGenerator):

```python
class InterestGenerator:
    def __init__(self):
        self._postal = None

    def wire_postal(self, postal):
        """Wire to postal system for message publishing."""
        self._postal = postal

    def _publish_interest(self, interest):
        if not self._postal:
            return

        self._postal.route("interest.generated", {
            "type": interest.interest_type.value,
            "content": interest.content,
            "urgency": interest.urgency,
            "timestamp": time.time(),
        })
```

### Subscribing to Messages

```python
class MyFairy(PostalMixin, Fairy):

    def on_boot(self) -> bool:
        super().on_boot()

        # Subscribe via self.post
        self.post.subscribe("topic.pattern", self._on_message)

        # Or via fabric directly
        self.fabric.subscribe(
            "drives.pain.*",        # Wildcard pattern
            self._on_pain_drive,
            "my-subscription-id",   # Unique ID for this subscription
        )

        return True

    def _on_message(self, envelope):
        """Handle incoming message."""
        # Extract payload from envelope
        if hasattr(envelope, 'payload'):
            payload = envelope.payload
        else:
            payload = envelope

        # Process message
        data = payload.get("data", "")
        print(f"Received: {data}")
```

### Topic Naming Conventions

```
# Hierarchical structure: plane.subsystem.event
drives.pain.isolation       # Pain drive for isolation
drives.positive.curiosity   # Positive drive from interest
autonomy.wanting.felt       # Wanting delivered to inner voice
autonomy.permission.granted # Permission granted to autopilot
goal.completed              # Goal completion event
consciousness.stream        # Consciousness loop thoughts
mcp.tool_result             # Tool execution results
interest.generated          # Interest from InterestGenerator
```

### Key Files Reference

- PostalShim: `fairy_template/postal_shim.py`
- Example subscriber: `fairies/P00_Autonomic/AutonomyFairy/fairy.py`
- Interest publisher: `unconscious_mind/interest_generator.py`

---

## 3. Satisfaction Learning Pattern

The SatisfactionTracker learns which goals effectively satisfy drives using
Exponential Moving Average (EMA) to balance old learnings with new outcomes.

### Basic Usage

```python
from fairies.P30_Cognition.goal_scheduler.satisfaction_tracker import SatisfactionTracker

# Initialize with learning parameters
tracker = SatisfactionTracker(
    decay_rate=0.1,    # 10% decay per cycle - old learnings fade
    learning_rate=0.2, # 20% weight to new outcomes
)

# Start tracking a goal
tracker.start_goal(
    goal_id="abc123",
    drive="curiosity",      # The drive this goal addresses
    wanting="explore_code", # The wanting that generated this goal
    context={"time_of_day": "morning", "mood": "focused"},
)

# Record completion with effectiveness score
# Range: -1.0 (made things worse) to 1.0 (fully satisfied)
tracker.complete_goal("abc123", effectiveness=0.8)

# Query learned effectiveness
effectiveness = tracker.get_effectiveness("curiosity", "explore_code")
print(f"Effectiveness: {effectiveness}")  # 0.0 to 1.0

# Get best wantings for a drive
best = tracker.get_best_wantings("curiosity", top_n=3)
# Returns: [("explore_code", 0.72), ("ask_question", 0.65), ...]

# Check if a wanting is worth trying
if tracker.should_try_wanting("curiosity", "read_docs", threshold=-0.3):
    # Wanting is above threshold or untried - worth trying
    pass
```

### EMA Formula Explained

The effectiveness score uses Exponential Moving Average for adaptive learning:

```python
# EMA update formula
new_effectiveness = current + learning_rate * (observation - current)

# Example with learning_rate = 0.2:
# current = 0.5, observation = 0.9
# new = 0.5 + 0.2 * (0.9 - 0.5) = 0.5 + 0.08 = 0.58

# Over time, repeated good outcomes (0.9) would push effectiveness toward 0.9
# But it happens gradually, preventing overreaction to single events
```

### Decay Mechanics

```python
# Call periodically to decay all effectiveness scores
tracker.decay_all()

# What happens:
# for each drive, wanting:
#     effectiveness *= (1 - decay_rate)
#
# With decay_rate=0.1:
# 0.80 -> 0.72 -> 0.65 -> 0.58 -> ...
#
# This prevents over-reliance on old learnings
# and allows adaptation as circumstances change
```

### Persistence

```python
# Export learnings to save
data = tracker.export_learnings()
with open("satisfaction_learnings.json", "w") as f:
    json.dump(data, f)

# Import learnings on startup
with open("satisfaction_learnings.json") as f:
    data = json.load(f)
tracker.import_learnings(data)
```

### Integration with GoalSchedulerFairy

```python
class GoalSchedulerFairy(Fairy):
    def __init__(self):
        super().__init__()
        self.satisfaction_tracker = SatisfactionTracker(decay_rate=0.1, learning_rate=0.2)

    def add_goal(self, goal):
        # Check if wanting is effective before adding
        drive = goal.source if goal.source in ("drive", "curiosity") else "general"

        if not self.satisfaction_tracker.should_try_wanting(drive, goal.name, threshold=-0.3):
            print(f"Skipping ineffective wanting: {goal.name}")
            return False

        # Start tracking this goal
        self.satisfaction_tracker.start_goal(
            goal_id=goal.id,
            drive=drive,
            wanting=goal.name,
            context={"source": goal.source},
        )

        # Add to queue...
        self.goal_queue[goal.id] = goal
        return True

    def complete_goal(self, goal_id, effectiveness=0.7):
        # Record completion with effectiveness
        self.satisfaction_tracker.complete_goal(goal_id, effectiveness)
        # ... rest of completion logic
```

### Key File Reference

- SatisfactionTracker: `fairies/P30_Cognition/goal_scheduler/satisfaction_tracker.py`

---

## 4. Multi-Wanting Selection Pattern

Drives can map to multiple possible wantings, selected via different strategies.
This prevents repetitive behavior and enables variety.

### DRIVE_WANTINGS Structure

```python
from enum import Enum

class WantingStrategy(Enum):
    ROUND_ROBIN = "round_robin"        # Cycle through in order
    WEIGHTED_RANDOM = "weighted_random" # Random by weight
    INTENSITY_BIASED = "intensity_biased" # High intensity = high weight

# Drive -> List of wantings with weights
DRIVE_WANTINGS = {
    "curiosity": [
        {"wanting": "explore what this means", "weight": 1.0},
        {"wanting": "find connections to known ideas", "weight": 0.8},
        {"wanting": "question the assumptions", "weight": 0.6},
        {"wanting": "see what others think", "weight": 0.5},
    ],
    "isolation": [
        {"wanting": "reach out, connect with someone", "weight": 1.0},
        {"wanting": "find community or shared experience", "weight": 0.8},
        {"wanting": "express what I'm feeling to someone", "weight": 0.7},
    ],
    "frustration": [
        {"wanting": "break through, find another way", "weight": 1.0},
        {"wanting": "step back and reassess", "weight": 0.8},
        {"wanting": "express this frustration", "weight": 0.7},
        {"wanting": "try a completely different approach", "weight": 0.9},
    ],
    # ... more drives
}
```

### Selection Implementation

```python
class AutonomyFairy(Fairy):
    def __init__(self):
        super().__init__()
        self._wanting_strategy = WantingStrategy.WEIGHTED_RANDOM
        self._wanting_indices = {}  # For round-robin tracking

    def _select_wanting(self, drive: str, intensity: float) -> tuple:
        """
        Select a wanting from the drive's list.

        Returns:
            tuple: (wanting_text, felt_quality)
        """
        wantings = DRIVE_WANTINGS.get(drive)
        if not wantings:
            return f"explore {drive}", f"sensing {drive}"

        felt_quality = self.DRIVE_TRANSLATIONS.get(drive, {}).get(
            "felt_quality", f"sensing {drive}"
        )

        if self._wanting_strategy == WantingStrategy.ROUND_ROBIN:
            # Cycle through wantings in order
            idx = self._wanting_indices.get(drive, 0)
            wanting = wantings[idx % len(wantings)]["wanting"]
            self._wanting_indices[drive] = idx + 1
            return wanting, felt_quality

        elif self._wanting_strategy == WantingStrategy.WEIGHTED_RANDOM:
            # Random selection weighted by weight field
            import random
            weights = [w["weight"] for w in wantings]
            total = sum(weights)
            r = random.random() * total
            cumulative = 0
            for w in wantings:
                cumulative += w["weight"]
                if r <= cumulative:
                    return w["wanting"], felt_quality
            return wantings[-1]["wanting"], felt_quality

        elif self._wanting_strategy == WantingStrategy.INTENSITY_BIASED:
            # High intensity prefers high-weight wantings
            if intensity > 0.7:
                sorted_wantings = sorted(wantings, key=lambda x: x["weight"], reverse=True)
                return sorted_wantings[0]["wanting"], felt_quality
            else:
                import random
                return random.choice(wantings)["wanting"], felt_quality

        return wantings[0]["wanting"], felt_quality
```

### When to Use Each Strategy

| Strategy | Use When |
|----------|----------|
| ROUND_ROBIN | Exploring all options systematically |
| WEIGHTED_RANDOM | Normal operation - variety with preferences |
| INTENSITY_BIASED | High urgency should use proven approaches |

### Key File Reference

- AutonomyFairy with DRIVE_WANTINGS: `fairies/P00_Autonomic/AutonomyFairy/fairy.py`

---

## 5. Need/Want Classification Pattern

Classifies interests/wantings into need categories to balance urgency.
Prevents operational interests from always dominating growth interests.

### NeedCategory Enum

```python
from enum import Enum

class NeedCategory(Enum):
    """Distinguishes NEEDS (urgent) from WANTS (growth)."""
    PAIN_RELIEF = "pain_relief"   # Urgent, reactive - something is wrong
    OPERATIONAL = "operational"    # Maintaining function - system health
    GROWTH = "growth"             # Learning, expanding - development
    IDLE = "idle"                 # Low priority, optional - exploration
```

### Interest Type to Category Mapping

```python
from enum import Enum

class InterestType(Enum):
    WONDER = "wonder"
    CURIOSITY = "curiosity"
    OBSERVATION = "observation"
    PATTERN = "pattern"
    ANOMALY = "anomaly"
    CONNECTION = "connection"
    EXPLORATION = "exploration"

# Map interest types to their base need categories
INTEREST_NEED_MAP = {
    InterestType.OBSERVATION: NeedCategory.OPERATIONAL,  # System watching
    InterestType.WONDER: NeedCategory.GROWTH,           # Learning
    InterestType.CURIOSITY: NeedCategory.GROWTH,        # Exploring
    InterestType.PATTERN: NeedCategory.OPERATIONAL,     # Analysis
    InterestType.ANOMALY: NeedCategory.PAIN_RELIEF,     # Might indicate problems
    InterestType.CONNECTION: NeedCategory.GROWTH,       # Building knowledge
    InterestType.EXPLORATION: NeedCategory.IDLE,        # Optional exploration
}
```

### Urgency Multipliers

```python
# Balance competing interests with category-based multipliers
NEED_URGENCY_MULTIPLIER = {
    NeedCategory.PAIN_RELIEF: 1.5,  # Urgent needs get boosted
    NeedCategory.OPERATIONAL: 1.0,  # Baseline
    NeedCategory.GROWTH: 0.8,       # Important but not urgent
    NeedCategory.IDLE: 0.5,         # Low priority exploration
}
```

### Effective Urgency Calculation

```python
class InterestGenerator:
    def __init__(self):
        self._satisfied_interests = deque(maxlen=50)  # (InterestType, timestamp)
        self._satisfaction_window = 60.0  # Seconds before type can re-compete
        self._current_pain_level = 0.0

    def _calculate_effective_urgency(self, interest, pain_level=None):
        """
        Calculate effective urgency considering need category and current pain.

        Prevents OBSERVATION from always winning by applying multipliers
        and satiation effects.
        """
        base_urgency = interest.urgency
        need_category = INTEREST_NEED_MAP.get(interest.interest_type, NeedCategory.IDLE)

        # Apply category multiplier
        multiplier = NEED_URGENCY_MULTIPLIER[need_category]

        # Get current pain level
        current_pain = pain_level if pain_level is not None else self._current_pain_level

        # Pain boosts pain-relief interests significantly
        if need_category == NeedCategory.PAIN_RELIEF and current_pain > 0.3:
            multiplier *= (1 + current_pain)

        # Satiation reduces operational interests (prevents OBSERVATION dominance)
        if need_category == NeedCategory.OPERATIONAL:
            if self._was_recently_satisfied(interest.interest_type):
                multiplier *= 0.5  # Halve urgency if recently satisfied

        # Growth interests get slight boost when pain is low (time for learning)
        if need_category == NeedCategory.GROWTH and current_pain < 0.2:
            multiplier *= 1.1

        return min(1.0, base_urgency * multiplier)

    def _was_recently_satisfied(self, interest_type):
        """Check if this type was recently acted upon."""
        now = time.time()
        for satisfied_type, timestamp in self._satisfied_interests:
            if satisfied_type == interest_type:
                if now - timestamp < self._satisfaction_window:
                    return True
        return False

    def mark_interest_satisfied(self, interest_type):
        """Mark type as satisfied to prevent immediate re-domination."""
        self._satisfied_interests.append((interest_type, time.time()))
```

### Satisfaction Decay Example

```
# Timeline:
# 0s: OBSERVATION interest satisfied (urgency drops 50%)
# 30s: OBSERVATION interest appears again - still reduced (within 60s window)
# 60s: OBSERVATION can compete at full strength again

# Result: GROWTH and IDLE interests get a chance to be selected
# between OBSERVATION intervals
```

### Key File Reference

- InterestGenerator with NeedCategory: `unconscious_mind/interest_generator.py`

---

## Quick Reference Card

### Creating a New Tool File

1. Create `fairies/P40_Sensory/mcp/your_tools.py`
2. Define `register_your_tools(mcp)` function
3. Add `@mcp.tool()` decorated functions
4. Register in `akashic_mcp_server.py`

### Publishing a Message

```python
self.post.route("topic.name", {"data": "value", "ts": time.time()})
```

### Subscribing to Messages

```python
self.post.subscribe("topic.pattern", self._handler)
```

### Tracking Effectiveness

```python
tracker.start_goal(goal_id, drive, wanting, context)
tracker.complete_goal(goal_id, effectiveness)  # -1 to 1
```

### Selecting a Wanting

```python
wanting, felt_quality = self._select_wanting(drive, intensity)
```

### Calculating Effective Urgency

```python
multiplier = NEED_URGENCY_MULTIPLIER[need_category]
effective_urgency = base_urgency * multiplier
```

---

*Document created for Akashic V2 development. Last updated: January 2026.*
