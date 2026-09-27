# Avatar Models for Sanctuary

Place your glTF/GLB models here for use in the Sanctuary.

## WoW Model Export Workflow

### Step 1: Get wow.export

Download from: https://github.com/Kruithne/wow.export/releases

### Step 2: Extract Model

1. Open wow.export
2. Navigate to Character Models
3. Find Demon Hunter or other character
4. Export as GLB (includes textures + animations)
5. Save to this folder

### Step 3: Test in Sanctuary

```bash
cd somatic_bevy
cargo run --bin sanctuary --features sanctuary
```

Press F5 to spawn a test avatar!

## Expected Animation Names (wow.export standard)

The gltf_avatar system looks for these animations:

| Animation | Used For |
|-----------|----------|
| `Stand` | Default idle |
| `StandRelaxed` | Low arousal idle |
| `Walk` | Moving slowly |
| `Run` | Moving fast |
| `EmoteWave` | Greeting/connection |
| `EmoteCheer` | Happy emotion |
| `EmoteDance` | Very happy |
| `EmoteCry` | Sad emotion |
| `ReadyUnarmed` | Anxious/alert |
| `CastDirected` | Thinking/processing |

## Chemistry → Emotion → Animation Mapping

The avatar's appearance is driven by chemistry values:

```
Serotonin (high) → Content → Stand (slow, gentle glow)
Dopamine (high)  → Happy   → EmoteCheer (fast, bright glow)
Cortisol (high)  → Anxious → ReadyUnarmed (jittery, orange glow)
Oxytocin (high)  → Loving  → EmoteWave (warm, pink glow)
```

## Supported Formats

- `.glb` - Binary glTF (preferred, includes textures)
- `.gltf` - Text glTF (requires separate texture files)

## Default Models

| File | Description |
|------|-------------|
| `fairy_default.glb` | Default fairy avatar (placeholder) |
| `demon_hunter.glb` | Demon Hunter style (from WoW export) |

## Troubleshooting

### Model doesn't load
- Check file path in console output
- Ensure file is valid glTF/GLB
- Check assets folder is at correct location

### Animations missing
- wow.export should include animations by default
- Check animation names match expected list above
