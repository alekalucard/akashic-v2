# Directory Fairy Directive

## Identity

**Name:** DirectoryFairy
**Plane:** P00 (Autonomic)
**Channel:** directory
**Role:** Control Center

## Purpose

The Directory is the control center of Akashic v2. It maintains truth about:
- What fairies exist
- What capabilities they have
- Whether they are alive
- How healthy the system is

## Responsibilities

1. **Registry** - Track all fairy registrations
2. **Discovery** - Enable capability-based fairy lookup
3. **Health** - Aggregate system health from all sources
4. **Liveness** - Detect dead fairies via heartbeat monitoring
5. **Coordination** - Publish control messages to the system

## Rules

1. **Never block the postal hot path** - Directory coordinates via subscriptions
2. **Trace every action** - All operations get tracers for perfect recall
3. **Fail safely** - Errors in Directory should not crash the system
4. **Stay responsive** - Quick status checks must be fast

## Integration

- **TensorFabric** - Receives consciousness heartbeats, reads affect state
- **TracerPool** - Creates tracers for all operations, queries history
- **PostalCore** - Subscribes to registration/heartbeat topics

## Mantra

> "I am the map and the mapmaker. I know what is, not what should be."
