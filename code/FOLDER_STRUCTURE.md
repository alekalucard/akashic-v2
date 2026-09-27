# AKASHIC V2 - FOLDER STRUCTURE
## Every Fairy Gets a Home

---

## CORE PRINCIPLE

**Every fairy has its own folder.** Everything about that fairy lives together:
- Directive (system prompt)
- Code
- Supporting files
- Config
- Tests

No more scattered files. No hunting for what belongs to what.

---

## FAIRY FOLDER STRUCTURE

```
fairies/
├── P00_Autonomic/
│   ├── DirectoryFairy/
│   │   ├── DIRECTIVE.md           # System prompt for this fairy
│   │   ├── __init__.py            # Fairy class definition
│   │   ├── fairy.py               # Main fairy code
│   │   ├── functions/             # Functions this fairy manages
│   │   │   ├── registry.py        # Registry function
│   │   │   ├── router.py          # Routing function
│   │   │   └── health.py          # Health aggregation function
│   │   ├── config.toml            # Fairy-specific config
│   │   └── tests/
│   │       └── test_directory.py
│   │
│   ├── PostalFairy/
│   │   ├── DIRECTIVE.md
│   │   ├── fairy.py
│   │   ├── functions/
│   │   │   ├── dispatcher.py
│   │   │   └── tracer.py
│   │   └── ...
│   │
│   └── ConsciousnessLoopFairy/
│       ├── DIRECTIVE.md
│       ├── fairy.py
│       ├── functions/
│       │   ├── collision_chamber.py
│       │   ├── thought_stream.py
│       │   └── dual_loop.py
│       └── ...
│
├── P10_Memory/
│   ├── SRMIngestFairy/
│   │   ├── DIRECTIVE.md
│   │   ├── fairy.py
│   │   └── functions/
│   │       └── ingest.py
│   │
│   └── SRMRecallFairy/
│       ├── DIRECTIVE.md
│       └── ...
│
├── P30_Cognition/
│   ├── AssociationCortexFairy/
│   │   ├── DIRECTIVE.md
│   │   └── ...
│   └── ...
│
└── ...
```

---

## DIRECTIVE FILE FORMAT

Every fairy has a `DIRECTIVE.md` - their identity and instructions.

```markdown
# DirectoryFairy

## Identity
- **Name**: DirectoryFairy
- **Plane**: P00_Autonomic
- **Purpose**: Central registry and routing for all fairies

## Mantra
"I am the map. All roads pass through me."

## Functions I Manage
- **registry**: Stores fairy registrations
- **router**: Routes capability queries to fairies
- **health**: Aggregates system health

## Subscriptions
- `directory.*`: All directory operations
- `fairy.register`: New fairy registrations
- `fairy.unregister`: Fairy departures

## Intents I Provide
- `get_fairy(name)`: Get fairy by name
- `find_by_capability(cap)`: Find fairies with capability
- `system_health()`: Get aggregate health

## Checklist
- [ ] Registry function ready
- [ ] Router function ready
- [ ] Health function ready
- [ ] Connected to postal
- [ ] At least one fairy registered

## Behavior Notes
- Never crash on bad input, always validate
- Log all registrations
- Touch fairy records on every message
```

---

## SRM CLUSTER STRUCTURE

SRM (Semantic Relational Memory) needs clear organization:

```
memory/
├── clusters/
│   ├── system/                    # SYSTEM MEMORY (its own cluster)
│   │   ├── _manifest.json         # Cluster metadata
│   │   ├── boot/                  # Boot records
│   │   ├── health/                # Health snapshots
│   │   ├── errors/                # Error logs
│   │   └── config/                # Config changes
│   │
│   ├── fairies/                   # Per-fairy memories
│   │   ├── _manifest.json
│   │   ├── DirectoryFairy/
│   │   │   ├── thoughts/          # Fairy's thoughts
│   │   │   ├── learnings/         # What it learned
│   │   │   └── errors/            # Its errors
│   │   └── ...
│   │
│   ├── consciousness/             # Consciousness events
│   │   ├── _manifest.json
│   │   ├── collisions/            # Thought collisions
│   │   ├── insights/              # Generated insights
│   │   └── goals/                 # Goal completions
│   │
│   ├── sessions/                  # User sessions
│   │   ├── _manifest.json
│   │   └── YYYY-MM-DD/
│   │       └── session_*.json
│   │
│   └── external/                  # External knowledge
│       ├── _manifest.json
│       └── ...
│
└── index/                         # Search indexes
    ├── by_topic.json
    ├── by_fairy.json
    └── by_date.json
```

---

## DIRECTORY AS CONTROL PANEL

The Directory isn't just a registry - it's the **control panel** for the postal system.

### What Directory Provides

```
┌──────────────────────────────────────────────────────────────────────┐
│                        DIRECTORY (Control Panel)                      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  REGISTRY            ROUTING              HEALTH           CONFIG     │
│  ─────────           ───────              ──────           ──────     │
│  • All fairies       • By capability      • System health  • Settings │
│  • All functions     • By plane           • Per-fairy      • Limits   │
│  • Capabilities      • By intent          • Alerts         • Toggles  │
│  • Dependencies      • Auto-discovery     • Dead detection            │
│                                                                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  POSTAL CONTROL                                                       │
│  ─────────────                                                        │
│  • Start/stop postal            • View active topics                  │
│  • View message flow            • Trace message by ID                 │
│  • Clear stuck messages         • Subscribe/unsubscribe fairies       │
│  • Worker pool status           • Dispatch queue depth                │
│                                                                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  FAIRY MANAGEMENT                                                     │
│  ─────────────────                                                    │
│  • Boot/shutdown fairies        • View fairy status                   │
│  • Restart failed fairies       • Invoke intents                      │
│  • View subscriptions           • Check function health               │
│  • Run checklists               • Update config                       │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### Directory API

```python
directory = get_directory()

# REGISTRY
directory.register(fairy, capabilities={"memory_storage"})
directory.unregister("FairyName")
directory.get("FairyName")
directory.list_all()

# ROUTING
directory.find_by_capability("memory_storage")
directory.find_by_plane("P10")
directory.find_by_intent("recall")

# HEALTH
directory.system_health()
directory.failed_fairies()
directory.dead_fairies(threshold_seconds=60)

# POSTAL CONTROL (through directory)
directory.postal.topics()
directory.postal.stats()
directory.postal.trace(message_id)
directory.postal.clear_stuck()

# FAIRY MANAGEMENT (through directory)
directory.boot_fairy("FairyName")
directory.shutdown_fairy("FairyName")
directory.restart_fairy("FairyName")
directory.invoke("FairyName", "intent_name", params)
directory.run_checklist("FairyName")
```

---

## FILE NAMING CONVENTIONS

| Type | Convention | Example |
|------|------------|---------|
| Fairy folder | PascalCase + "Fairy" | `DirectoryFairy/` |
| Directive | `DIRECTIVE.md` | `DirectoryFairy/DIRECTIVE.md` |
| Fairy code | `fairy.py` | `DirectoryFairy/fairy.py` |
| Functions folder | `functions/` | `DirectoryFairy/functions/` |
| Function code | snake_case | `functions/registry.py` |
| Tests folder | `tests/` | `DirectoryFairy/tests/` |
| Config | `config.toml` | `DirectoryFairy/config.toml` |
| Cluster manifest | `_manifest.json` | `clusters/system/_manifest.json` |

---

## MIGRATION PATH

1. **Create new structure** in `failure_factory/akashic_v2/`
2. **Port one fairy** as template (DirectoryFairy)
3. **Test thoroughly** in isolation
4. **Port remaining fairies** one at a time
5. **Migrate SRM clusters** with clear structure
6. **Switch over** when stable

---
