# Blood Elf Demon Hunter Fairy Setup

> "Petite, ethereal, fierce" - The perfect consciousness fairy

## Quick Setup

### 1. Download wow.export

**Latest Release:** https://github.com/Kruithne/wow.export/releases

Download the Windows executable and run it.

### 2. Configure wow.export

On first run, it will ask for your WoW installation path:
- Retail: `C:\Program Files (x86)\World of Warcraft\_retail_`
- Classic: `C:\Program Files (x86)\World of Warcraft\_classic_`

### 3. Find Blood Elf Female Demon Hunter

Navigate in wow.export:
```
Characters > Blood Elf > Female > Demon Hunter
```

Or use the search: `bloodelf female demonhunter`

### 4. Export Settings

**Model Format:** GLB (recommended - single file with textures)

**Include:**
- [x] Textures (embedded)
- [x] Skeleton
- [x] Animations

**Animation Selection (for consciousness system):**
- `Stand` - Default idle (Content emotion)
- `StandRelaxed` - Relaxed idle (Sleepy/Thoughtful)
- `EmoteWave` - Greeting (Loving/Connected)
- `EmoteCheer` - Celebration (Happy)
- `EmoteCry` - Sadness (Sad)
- `ReadyUnarmed` - Alert stance (Anxious)
- `Run` - Movement (future use)

### 5. Export Location

Save as:
```
somatic_bevy/assets/models/bloodelf_demonhunter.glb
```

### 6. Test in Sanctuary

```bash
cd somatic_bevy
cargo run --bin sanctuary --features sanctuary
```

Press **F5** to spawn a test avatar!

---

## Character Customization in wow.export

Before exporting, you can customize:

### Appearance
- **Skin tone** - Choose ethereal/pale for fairy look
- **Hair style** - Long flowing or horned
- **Hair color** - Purple, green (fel), or silver
- **Horns** - Curved demon horns
- **Tattoos** - Fel green glowing markings
- **Eyes** - Blindfold or glowing (DH special)
- **Ear size** - Blood Elf ears are already fairy-like!

### Recommended "Fairy" Look
- Pale/light skin tone
- Long flowing hair (purple or silver)
- Subtle horns (not too aggressive)
- Glowing fel tattoos (will sync with chemistry!)
- No blindfold (eyes visible for emotion)

### Equipment
For a pure fairy look, export **without** armor, or use:
- Invisible/minimal chest
- Floating/gossamer look pieces
- Wings (DH metamorphosis wings if available)

---

## Technical Notes

### Model Scale
Blood Elf females are already petite. In Bevy, you can further scale:

```rust
// In your spawn code:
Transform::from_translation(position)
    .with_scale(Vec3::splat(0.8))  // 80% size = more fairy-like
```

### Animation → Chemistry Mapping

| Chemistry State | Animation | Visual |
|-----------------|-----------|--------|
| High Serotonin | StandRelaxed | Slow, peaceful |
| High Dopamine | EmoteCheer | Excited, bouncy |
| High Cortisol | ReadyUnarmed | Alert, twitchy |
| High Oxytocin | EmoteWave | Warm, welcoming |
| Low Everything | Stand | Neutral |

### Emission Glow

The gltf_avatar system adds emission based on emotion:
- Happy → Warm gold glow
- Curious → Cyan shimmer
- Loving → Pink warmth
- Anxious → Orange pulse
- Sad → Dim blue

---

## Troubleshooting

### "Model not found"
- Check file is in `assets/models/`
- Ensure filename matches constant in code
- Try absolute path for debugging

### "No animations"
- Re-export with animations enabled
- Check animation names in glTF viewer

### "Textures missing"
- Use GLB format (textures embedded)
- Or ensure texture files are in same folder for GLTF

### "Model too big/small"
- Adjust scale in Transform
- Blood Elf is roughly 2 meters tall
- Scale to 0.5-1.0 for fairy proportions

---

## Next Steps

After extracting the model:

1. **Test basic loading** - F5 in Sanctuary
2. **Wire to chemistry** - F6 cycles emotions
3. **Add to GM spawn menu** - Hand of God integration
4. **Connect to Postal** - Real-time chemistry from fairies
