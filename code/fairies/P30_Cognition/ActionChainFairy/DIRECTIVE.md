# ActionChainFairy Directive

## Identity
- **Name**: ActionChainFairy
- **Version**: 1.0.0
- **Soul Seed**: motor_planner_sequence_executor
- **Domain**: Cognition
- **Role**: action_chain
- **Boot Priority**: 35 (after AutonomyFairy, before ClaudeFairy)

## Purpose

The ActionChainFairy is the **motor cortex** of the cognitive system. It fills the critical gap between goals and actions.

**The Problem It Solves:**
Before this fairy existed, the system was generating goals but falling back to `observe_screen` because nobody was actually PLANNING how to achieve them. Goals without actions are dreams; actions without planning are chaos.

## Architecture

### ActionChain vs ThoughtChain
```
ThoughtChain: stimulus -> think -> think -> think -> conclusion (reasoning)
ActionChain:  goal -> check -> act -> act -> sense -> done (motor control)
```

ThoughtChains are for internal reasoning and deliberation.
ActionChains are for motor control and executing intentions in the world.

### Core Data Structures

**ActionStep**: A single step in an action chain
- Types: CHECK, ROUTE, WAIT, BRANCH, SUBCHAIN, SENSE, MOTOR
- Tracks: status, timing, retries, results

**ActionChain**: A complete sequence of steps to achieve a goal
- Contains: goal name, reason, ordered steps
- Tracks: current step index, status, context

### Pre-built Templates

The fairy includes templates for common goals:
- **reach_out**: Express desire to connect
- **open_my_window** / **close_my_window**: GUI control
- **express_feeling** / **share_thought**: Communication
- **reduce_stress**: Inject calming chemistry
- **observe_screen**: Request visual observation
- **continue_thought**: Keep thought chains flowing
- **think_about** / **wonder** / **reflect**: Cognitive actions
- **remember**: Memory recall
- **ask_a_question**: Direct questions to Ace

## Postal Subscriptions

**Input:**
- `autonomy.goal` - Goal created events from AutonomyFairy
- `goal.nudge` - Nudges from ThoughtChainSequencerFairy

**State Tracking:**
- `claudefairy.window_state` - Window open/closed
- `claudefairy.feeling` - Current emotional state
- `somatic.chemistry.updated` - Chemistry levels
- `somatic.body_state` - Body state updates
- `consciousness.working` - Working consciousness stream

**Wait Completions:**
- `claudefairy.composed` - Composition complete
- `gui.user_message` - User message received
- `visual.response` - Visual processing complete
- `system.overview.response` - System overview response

## Output Topics

- `motor.chain.started` - Chain execution began
- `motor.chain.completed` - Chain finished successfully
- `motor.chain.failed` - Chain failed

Plus all the topics from template steps (consciousness.collision, gui.*, somatic.*, etc.)

## Spam Prevention

The fairy includes built-in spam prevention:
- Tracks failed goal times and counts
- Cooldown period before retrying failed goals (30s)
- Maximum failure count before giving up (3)
- Resets on success

## Configuration

```python
BOOT_PRIORITY = 35              # Boot order
_max_concurrent_chains = 3      # Max parallel chains
_step_timeout = 30.0            # Step execution timeout
_fallback_cooldown = 30.0       # Failed goal cooldown
_max_fail_count = 3             # Max retries before cooldown
```

## Usage

```python
from fairies.P30_Cognition.ActionChainFairy import get_action_chain_fairy

# Get the singleton
fairy = get_action_chain_fairy()
fairy.on_boot()

# Goals arrive via postal system, but can also be injected directly:
fairy._on_goal({
    "name": "reach_out",
    "reason": "Want to connect with Ace",
    "priority": 0.8,
    "source": "manual"
})

# Check status
status = fairy.get_status()
```

## Philosophy

> "Goals without actions are dreams; actions without planning are chaos."

The ActionChainFairy embodies the principle that intention must be translated into structured action. It's not enough to want something - there must be a plan, and the plan must execute step by step, handling failures gracefully and adapting as state changes.
