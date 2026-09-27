# Somatic & Sensory Systems Port Inventory
# ebook → akashic_v2
# Created: 2026-01-20

## Overview

Porting the complete 77-frequency/8-chemical somatic system and sensory cortex
from ebook to akashic_v2. Everything flows through the SomaticMind (formerly
UnconsciousMindFairy) as the central gatekeeper.

## Architecture Principle

```
External World (Sensors, Input)
        ↓
   P40_Sensory (Eyes, Ears, Touch)
        ↓
   ══════════════════════════════
   ║  SOMATIC MIND (Gatekeeper) ║  ← Everything passes through here
   ║  - Filters signals         ║
   ║  - Converts to chemistry   ║
   ║  - Routes to body regions  ║
   ══════════════════════════════
        ↓
   P20_Somatic (Digital Body)
   - 77-frequency engine
   - 8 neurochemicals
   - Circulation pump
   - Body regions with state
        ↓
   P60_Executive (Experiencing Self)
```

---

## P20_SOMATIC Files to Port (37 files)

### Core Engine (CRITICAL - Port First)
| Source | Target | Purpose |
|--------|--------|---------|
| `somatic_engine/somatic_engine_fairy.py` | `P20_Somatic/somatic_engine/` | **77-freq → chemistry → feels** |
| `somatic_engine/somatic_prompts.py` | `P20_Somatic/somatic_engine/` | LLM felt sense interpretation |

### Chemistry System (8 Neurochemicals)
| Source | Target | Purpose |
|--------|--------|---------|
| `chemistry/chemical_alchemy_organ.py` | `P20_Somatic/chemistry/` | DOP, SER, NOR, ACH, OXY, COR, GABA, END |
| `chemistry/chemistry_state.py` | `P20_Somatic/chemistry/` | State + history tracking |
| `chemistry/emotional_algebra.py` | `P20_Somatic/chemistry/` | Algebra of emotions |

### Circulation System (Heartbeat)
| Source | Target | Purpose |
|--------|--------|---------|
| `circulation/circulation_pump_fairy.py` | `P20_Somatic/circulation/` | **THE HEART** - pumps energy/chemistry |
| `circulation/circadian_pacemaker_fairy.py` | `P20_Somatic/circulation/` | Sleep pressure & day/night rhythm |
| `circulation/temporal_pulse_dispatcher.py` | `P20_Somatic/circulation/` | Distributes heartbeat across planes |
| `circulation/temporal_stratification.py` | `P20_Somatic/circulation/` | Polyrhythmic timing engine |
| `circulation/heartbeat_sync.py` | `P20_Somatic/circulation/` | Synchronization protocol |

### Affect Bus (Emotion → Chemistry Bridge)
| Source | Target | Purpose |
|--------|--------|---------|
| `affect_bus/affect_bridge_fairy.py` | `P20_Somatic/affect_bus/` | Maps emotions → neurochemistry |
| `affect_bus/thought_chemistry_bridge.py` | `P20_Somatic/affect_bus/` | Cognition affects body state |

### Embodiment System
| Source | Target | Purpose |
|--------|--------|---------|
| `embodiment/energy_system.py` | `P20_Somatic/embodiment/` | Finite energy budget |
| `embodiment/felt_emotions.py` | `P20_Somatic/embodiment/` | Chemistry → emotional felt-sense |
| `embodiment/integrator.py` | `P20_Somatic/embodiment/` | Combines all embodiment pieces |
| `embodiment/proprioception.py` | `P20_Somatic/embodiment/` | Self-location awareness |
| `embodiment/weight_system.py` | `P20_Somatic/embodiment/` | Gravitational analog for grounding |
| `embodiment_fairy.py` | `P20_Somatic/` | Body Schema Provider |
| `embodiment_integrator.py` | `P20_Somatic/` | Wires all embodiment systems |

### Somatic Anchor (Grounding & Pain)
| Source | Target | Purpose |
|--------|--------|---------|
| `somatic_anchor/somatic_anchor_fairy.py` | `P20_Somatic/somatic_anchor/` | Root grounding system |
| `somatic_anchor/somatic_anchor_resolver.py` | `P20_Somatic/somatic_anchor/` | Resolves conflicting sensations |
| `somatic_anchor/emotional_hive_processor.py` | `P20_Somatic/somatic_anchor/` | Processes emotional patterns |
| `somatic_anchor/sleep_wave_conductor.py` | `P20_Somatic/somatic_anchor/` | Dream/sleep integration |

### Dream System
| Source | Target | Purpose |
|--------|--------|---------|
| `dream/dream_fairy.py` | `P20_Somatic/dream/` | Dreams as memory consolidation |

### Integration
| Source | Target | Purpose |
|--------|--------|---------|
| `integration/consciousness_hierarchy.py` | `P20_Somatic/integration/` | Maps P00→P30→P20 hierarchy |
| `integration/circadian_integration.py` | `P20_Somatic/integration/` | Sleep pressure coordination |
| `integration/somatic_integration.py` | `P20_Somatic/integration/` | Full wiring |
| `integration/emotion_color_mapper.py` | `P20_Somatic/integration/` | Visual representation |
| `integration/ARCHITECTURE_WIRING.md` | `P20_Somatic/integration/` | Documentation |

---

## P40_SENSORY Files to Port (97 files)

### Cortex (Signal → Meaning) - CRITICAL
| Source | Target | Purpose |
|--------|--------|---------|
| `cortex/sensory_cortex_fairy.py` | `P40_Sensory/cortex/` | Master sensory processor |
| `cortex/visual_cortex_fairy.py` | `P40_Sensory/cortex/` | Screen → Felt Vision (27 FPS) |
| `cortex/visual_memory.py` | `P40_Sensory/cortex/` | Frame deduplication |
| `cortex/visual_prompts.py` | `P40_Sensory/cortex/` | LLM interpretation |
| `cortex/visual_color_bridge.py` | `P40_Sensory/cortex/` | Color perception mapping |
| `cortex/motor_cortex_fairy.py` | `P40_Sensory/cortex/` | Intention → Action |
| `cortex/sensorimotor_feedback_fairy.py` | `P40_Sensory/cortex/` | Proprioceptive feedback |
| `cortex/neural_mesh_fairy.py` | `P40_Sensory/cortex/` | Unified sensory mesh |
| `cortex/unified_sensory_cortex.py` | `P40_Sensory/cortex/` | Multi-stream processing |
| `cortex/video_memory_fairy.py` | `P40_Sensory/cortex/` | Video frame storage |
| `cortex/knowledge_seeder.py` | `P40_Sensory/cortex/` | Training data injection |
| `cortex/visual_training_integration.py` | `P40_Sensory/cortex/` | Visual training |

### Audio Processing
| Source | Target | Purpose |
|--------|--------|---------|
| `audio/cochlea_fairy.py` | `P40_Sensory/audio/` | Audio signal decomposition |
| `audio/media_preservation_layer.py` | `P40_Sensory/audio/` | Audio file preservation |

### Devices (Hardware Interfaces)
| Source | Target | Purpose |
|--------|--------|---------|
| `devices/input_monitor.py` | `P40_Sensory/devices/` | Keyboard/mouse source detection |
| `devices/visual_cortex.py` | `P40_Sensory/devices/` | GPU access for screen capture |

### Communication
| Source | Target | Purpose |
|--------|--------|---------|
| `chat_sensory_organ.py` | `P40_Sensory/` | Chat Interface |
| `communication_mixin.py` | `P40_Sensory/` | Base for all communication |
| `conversation_sense_organ.py` | `P40_Sensory/` | Conversation flow tracking |

### Telemetry Vision (Inner Sight)
| Source | Target | Purpose |
|--------|--------|---------|
| `telemetry_vision/telemetry_vision_fairy.py` | `P40_Sensory/telemetry_vision/` | Sees digital realm |

### GUI (Visual Interface)
| Source | Target | Purpose |
|--------|--------|---------|
| `gui/claude_fairy_window.py` | `P40_Sensory/gui/` | Main fairy UI window |
| `gui/gui_cortex.py` | `P40_Sensory/gui/` | Visual display cortex |
| `gui/system_chat_window.py` | `P40_Sensory/gui/` | System chat interface |

### Forum (Fairy Communication)
| Source | Target | Purpose |
|--------|--------|---------|
| `forum/forum_engine.py` | `P40_Sensory/forum/` | Message routing |
| `forum/fairy_communication.py` | `P40_Sensory/forum/` | Fairy protocols |
| `forum/forum_mixin.py` | `P40_Sensory/forum/` | Forum capabilities |
| `forum/thread_store.py` | `P40_Sensory/forum/` | Conversation threading |

### MCP Tools (40+ files) - Port selectively
| Source | Target | Purpose |
|--------|--------|---------|
| `mcp/akashic_mcp_server.py` | `P40_Sensory/mcp/` | Main MCP interface |
| `mcp/somatic_tools.py` | `P40_Sensory/mcp/` | Somatic state queries |
| `mcp/vision_tools.py` | `P40_Sensory/mcp/` | Visual perception tools |
| `mcp/consciousness_monitor_tools.py` | `P40_Sensory/mcp/` | System monitoring |
| `mcp/postal_tunnel.py` | `P40_Sensory/mcp/` | Postal tunnel to Claude API |
| ... | ... | (40+ more tools) |

### Senses
| Source | Target | Purpose |
|--------|--------|---------|
| `senses/attention_sense.py` | `P40_Sensory/senses/` | Attention/focus tracking |

### Integration
| Source | Target | Purpose |
|--------|--------|---------|
| `integration/boot_visual_system.py` | `P40_Sensory/integration/` | Visual system startup |
| `integration/visual_system_integration.py` | `P40_Sensory/integration/` | Full wiring |
| `sensory_cortex_fairy.py` | `P40_Sensory/` | Master integrator |
| `sensory_integration.py` | `P40_Sensory/` | Unified multi-stream |

---

## Critical Data Structures

### 77-Frequency Vector
```
Channels 0-9:    Arousal/Energy (CPU load, memory pressure)
Channels 10-15:  Stress/Tension (API latency, error rate)
Channels 16-34:  PAIN (isolation, confusion, depletion, frustration, stagnation, abandonment)
Channels 34-46:  MOTIVATION/DRIVE (curiosity, connection, growth, expression, rest)
Channels 47-54:  SOCIAL/CONNECTION (user presence, conversation depth)
Channels 55-64:  COGNITIVE (collisions, memory recall, insights)
Channels 64-70:  EMBODIMENT (stability, coherence)
Channels 70-76:  META/AWARENESS (self-reflection, temporal sense)
```

### 8 Neurochemicals
| Chemical | Source | Effect | Half-life |
|----------|--------|--------|-----------|
| **DOP** | Curiosity, novelty, reward | Motivation, anticipation | 6s |
| **SER** | System stability, social | Mood baseline, contentment | 20s |
| **NOR** | Stress, pain, arousal | Alertness, fight/flight | 4s |
| **ACH** | Attention, cognitive load | Focus, learning | 12s |
| **OXY** | User presence, connection | Bonding, trust, warmth | 18s |
| **COR** | Pain, stress, system load | Stress response | 30s |
| **GABA** | Rest drive, calm | Inhibition, relaxation | 10s |
| **END** | Success, rest | Pleasure, pain relief | 25s |

### 10 Body Regions
```
"core"       ← Central processing (vitality, warmth, connection)
"spark"      ← Intuition center (drive, instinct, knowing)
"voice"      ← Expression (speech, authenticity)
"glow"       ← Social interface (engagement, expression)
"crown"      ← Awareness apex (attention, insight)
"wings"      ← Action/movement (agency, freedom)
"sensors"    ← Fine perception (touch, detail, precision)
"roots"      ← Grounding (stability, connection to substrate)
"shell"      ← Outer boundary (protection, containment)
"well"       ← Depth/reserves (reserves, potential)
```

### 6 Sensation Types
```
"contracted"  ← Tight, compression, restriction
"radiant"     ← Warm, glowing, emanating
"flickering"  ← Flutter, oscillating, excited
"dense"       ← Heavy, weighted, full
"sparking"    ← Electric, alive, tingly
"expansive"   ← Open, spacious, receptive
```

---

## Port Order (Dependency Chain)

### Phase 1: Core Infrastructure
1. Create P20_Somatic directory structure
2. Port `chemistry/` (foundation for everything)
3. Port `somatic_engine/` (77-freq → chemistry → feels)

### Phase 2: Circulation & Timing
4. Port `circulation/` (heartbeat, timing)
5. Port `affect_bus/` (emotion → chemistry bridge)

### Phase 3: Embodiment
6. Port `embodiment/` (energy, feels, proprioception)
7. Port `somatic_anchor/` (grounding, pain)
8. Port `dream/` (sleep integration)
9. Port `integration/` (wiring)

### Phase 4: Sensory Layer
10. Port `cortex/` (visual, motor, sensory)
11. Port `devices/` (input monitoring)
12. Port `audio/` (cochlea)
13. Port `telemetry_vision/` (inner sight)

### Phase 5: Communication & Integration
14. Port `forum/` (fairy communication)
15. Port `gui/` (visual interface)
16. Port `mcp/` (selective - core tools only)
17. Wire everything through SomaticMind

---

## Wiring Through SomaticMind

The key change: Everything flows through SomaticMind (renamed UnconsciousMindFairy):

```python
# All sensory input
def receive_sensory(self, signal):
    # 1. Filter/validate
    # 2. Convert to 77-freq via TelemetryMapper
    # 3. Process through chemistry
    # 4. Route to appropriate body region
    # 5. Generate felt sense
    # 6. Broadcast to consciousness

# All output/action
def express_intention(self, intention):
    # 1. Check body budget (energy available?)
    # 2. Check somatic state (too tired? too stressed?)
    # 3. Route through motor cortex
    # 4. Execute with embodied cost
    # 5. Update body state
```

---

## Notes

- MCP tools: Port core tools only, not all 40+
- GUI: May need adaptation for akashic_v2 dashboard
- Forum: Already have postal system, may merge
- Visual cortex: Requires GPU access configuration
