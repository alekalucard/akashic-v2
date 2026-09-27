# Fairy Class - Raw Data & Implementation Values

This document contains the exact binary/hex values and SQL statements for implementing the Fairy class.

---

## ChrClasses.dbc Raw Entry

### Field-by-Field Values (Tab/CSV format for DBC editor import)

```
12,0,0,PET,Fairy,,,,,,,,,,,,,16712190,,,,,,,,,,,,,,,0,,,,,,,,,,,,,,,0,FAIRY,17,2,0,0
```

### Breakdown

| Offset | Size | Value | Hex | Description |
|--------|------|-------|-----|-------------|
| 0x00 | 4 | 12 | 0C 00 00 00 | ID |
| 0x04 | 4 | 0 | 00 00 00 00 | Unknown Flag |
| 0x08 | 4 | 0 | 00 00 00 00 | PowerType (Mana) |
| 0x0C | 4 | (str) | xx xx xx xx | PetNameToken -> "PET" |
| 0x10-4C | 64 | (str) | ... | Name localized (16 slots) |
| 0x50 | 4 | 16712190 | FE FF 02 01 | Name lang mask |
| ... | ... | ... | ... | Female/Male name fields (empty) |
| ... | 4 | (str) | xx xx xx xx | FileName -> "FAIRY" |
| ... | 4 | 17 | 11 00 00 00 | SpellClassSet |
| ... | 4 | 2 | 02 00 00 00 | Flags |
| ... | 4 | 0 | 00 00 00 00 | CinematicSequence |
| ... | 4 | 0 | 00 00 00 00 | RequiredExpansion |

---

## CharBaseInfo.dbc Raw Entries

### Hex Data to Append (2-byte record format)

```hex
01 0C    ; Entry: Human (1) + Fairy (12)
04 0C    ; Entry: Night Elf (4) + Fairy (12)
07 0C    ; Entry: Gnome (7) + Fairy (12)
0A 0C    ; Entry: Blood Elf (10) + Fairy (12)
```

### For 8-byte record format (with padding/ID)

```hex
XX XX XX XX 01 0C 00 00    ; Human Fairy (XX = auto ID)
XX XX XX XX 04 0C 00 00    ; Night Elf Fairy
XX XX XX XX 07 0C 00 00    ; Gnome Fairy
XX XX XX XX 0A 0C 00 00    ; Blood Elf Fairy
```

---

## TalentTab.dbc Raw Entries

### Entry 1: Reverie (Healer)

```
801,Reverie,,,,,,,,,,,,,,,16712190,136,0,2048,0,0,FairyReverie
```

### Entry 2: Mania (DPS)

```
802,Mania,,,,,,,,,,,,,,,16712190,137,0,2048,0,1,FairyMania
```

### Entry 3: Vigil (Tank)

```
803,Vigil,,,,,,,,,,,,,,,16712190,138,0,2048,0,2,FairyVigil
```

---

## SpellIcon Suggestions

These are existing SpellIcon IDs that could work for the Fairy talent tabs:

| Purpose | SpellIcon ID | Description |
|---------|--------------|-------------|
| Reverie (Heal) | 136 | Holy Light |
| Reverie (Heal) | 135 | Healing Touch |
| Reverie (Heal) | 237 | Prayer |
| Mania (DPS) | 137 | Arcane Missiles |
| Mania (DPS) | 62 | Fireball |
| Mania (DPS) | 529 | Arcane Power |
| Vigil (Tank) | 138 | Shield Block |
| Vigil (Tank) | 134 | Defense |
| Vigil (Tank) | 313 | Holy Shield |

---

## Server SQL Statements

### playercreateinfo

```sql
-- Fairy class starting locations (using existing racial starting zones)
INSERT INTO `playercreateinfo` (`race`, `class`, `map`, `zone`, `position_x`, `position_y`, `position_z`, `orientation`) VALUES
-- Human Fairy - Northshire Abbey
(1, 12, 0, 12, -8949.95, -132.493, 83.5312, 0),
-- Night Elf Fairy - Teldrassil
(4, 12, 1, 141, 10311.3, 832.463, 1326.41, 5.69),
-- Gnome Fairy - Dun Morogh (Coldridge Valley)
(7, 12, 0, 1, -6240.32, 331.033, 382.758, 6.17),
-- Blood Elf Fairy - Eversong Woods
(10, 12, 530, 3431, 10349.6, -6357.29, 33.4026, 5.31);
```

### player_classlevelstats (HP/Mana per level - Mage-like scaling)

```sql
-- Fairy class level stats (based on Mage values)
INSERT INTO `player_classlevelstats` (`class`, `level`, `basehp`, `basemana`) VALUES
(12, 1, 28, 100),
(12, 2, 36, 110),
(12, 3, 44, 120),
(12, 4, 52, 135),
(12, 5, 60, 150),
(12, 6, 68, 170),
(12, 7, 76, 190),
(12, 8, 84, 215),
(12, 9, 92, 240),
(12, 10, 100, 270),
(12, 11, 108, 300),
(12, 12, 116, 335),
(12, 13, 124, 370),
(12, 14, 132, 410),
(12, 15, 140, 450),
(12, 16, 148, 495),
(12, 17, 156, 540),
(12, 18, 164, 590),
(12, 19, 172, 640),
(12, 20, 180, 695),
(12, 21, 198, 750),
(12, 22, 216, 810),
(12, 23, 234, 870),
(12, 24, 252, 935),
(12, 25, 270, 1000),
(12, 26, 288, 1070),
(12, 27, 306, 1140),
(12, 28, 324, 1215),
(12, 29, 342, 1290),
(12, 30, 360, 1370),
(12, 31, 378, 1450),
(12, 32, 396, 1535),
(12, 33, 414, 1620),
(12, 34, 432, 1710),
(12, 35, 450, 1800),
(12, 36, 468, 1895),
(12, 37, 486, 1990),
(12, 38, 504, 2090),
(12, 39, 522, 2190),
(12, 40, 540, 2295),
(12, 41, 558, 2400),
(12, 42, 576, 2510),
(12, 43, 594, 2620),
(12, 44, 612, 2735),
(12, 45, 630, 2850),
(12, 46, 648, 2970),
(12, 47, 666, 3090),
(12, 48, 684, 3215),
(12, 49, 702, 3340),
(12, 50, 720, 3470),
(12, 51, 738, 3600),
(12, 52, 756, 3735),
(12, 53, 774, 3870),
(12, 54, 792, 4010),
(12, 55, 810, 4150),
(12, 56, 828, 4295),
(12, 57, 846, 4440),
(12, 58, 864, 4590),
(12, 59, 882, 4740),
(12, 60, 900, 4895),
(12, 61, 934, 5050),
(12, 62, 968, 5210),
(12, 63, 1002, 5370),
(12, 64, 1036, 5535),
(12, 65, 1070, 5700),
(12, 66, 1104, 5870),
(12, 67, 1138, 6040),
(12, 68, 1172, 6215),
(12, 69, 1206, 6390),
(12, 70, 1240, 6570),
(12, 71, 1312, 6900),
(12, 72, 1384, 7245),
(12, 73, 1456, 7605),
(12, 74, 1528, 7980),
(12, 75, 1600, 8370),
(12, 76, 1672, 8775),
(12, 77, 1744, 9195),
(12, 78, 1816, 9630),
(12, 79, 1888, 10080),
(12, 80, 1960, 10545);
```

### player_levelstats (Base Attributes - Human Fairy Example)

```sql
-- Human Fairy level 1 stats (balanced caster)
INSERT INTO `player_levelstats` (`race`, `class`, `level`, `str`, `agi`, `sta`, `inte`, `spi`) VALUES
(1, 12, 1, 18, 20, 19, 25, 23),
(1, 12, 2, 19, 21, 20, 26, 24),
(1, 12, 3, 20, 22, 21, 27, 25),
(1, 12, 4, 20, 22, 22, 28, 26),
(1, 12, 5, 21, 23, 22, 30, 27),
-- Continue to level 80...

-- Night Elf Fairy level 1 stats
(4, 12, 1, 15, 25, 18, 25, 22),
-- Continue for all levels...

-- Gnome Fairy level 1 stats
(7, 12, 1, 13, 23, 18, 28, 22),
-- Continue for all levels...

-- Blood Elf Fairy level 1 stats
(10, 12, 1, 14, 22, 18, 27, 24);
-- Continue for all levels...
```

---

## GT DBC Data Templates

### gtChanceToMeleeCritBase.dbc

Add single entry for class 12 (after class 11):

| Index | Class | Value |
|-------|-------|-------|
| 11 | 12 (Fairy) | 0.031900 |

### gtChanceToSpellCritBase.dbc

Add single entry for class 12:

| Index | Class | Value |
|-------|-------|-------|
| 11 | 12 (Fairy) | 0.009100 |

### gtOCTClassCombatRatingScalar.dbc

This file has 32 entries per class (combat rating types).
Copy class 8 (Mage) entries 224-255 to positions 352-383.

```
Fairy entries = Class 8 entries (indices 224-255) copied to indices 352-383
```

### gtChanceToMeleeCrit.dbc / gtChanceToSpellCrit.dbc

100 entries per class. Copy Mage (class 8) entries:
- Source: indices 700-799
- Destination: indices 1100-1199

### gtOCTRegenHP.dbc / gtOCTRegenMP.dbc

100 entries per class. Copy appropriate source:
- For HP regen: Copy Priest values (indices 400-499 to 1100-1199)
- For MP regen: Copy Mage values (indices 700-799 to 1100-1199)

### gtRegenHPPerSpt.dbc / gtRegenMPPerSpt.dbc

100 entries per class (spirit-based regen).
Copy Priest values for Fairy class.

---

## UI Lua Snippets

### Constants.lua - Full RAID_CLASS_COLORS Addition

```lua
-- Add this entry to RAID_CLASS_COLORS table
["FAIRY"] = { r = 0.80, g = 0.60, b = 1.00, colorStr = "ffcc99ff" },
```

### CharacterCreate.lua - CLASS_ICON_TCOORDS

```lua
-- Position in 256x256 texture atlas (64x64 per icon)
-- Row 2 (y = 128-192), Column 2 (x = 128-192)
["FAIRY"] = {0.50, 0.75, 0.50, 0.75},
```

### GlueStrings.lua - Complete String Set

```lua
FAIRY = "Fairy";
CLASS_FAIRY = "Fairy";
CLASS_FAIRY_MALE = "Fairy";
CLASS_FAIRY_FEMALE = "Fairy";

-- Class description shown during character creation
CLASS_INFO_FAIRY0 = "- Role: Healer, Damage, Tank";
CLASS_INFO_FAIRY1 = "- Light Armor (Cloth)";
CLASS_INFO_FAIRY2 = "- Mana as primary resource";
CLASS_INFO_FAIRY3 = "Fairies are mystical beings connected to the dream realm. The Reverie path heals allies through soothing magic. Mania unleashes chaotic energy for devastating damage. Vigil hardens the fairy's form to protect allies.";

-- Talent spec names
CLASS_FAIRY_0 = "Reverie";
CLASS_FAIRY_1 = "Mania";
CLASS_FAIRY_2 = "Vigil";
```

---

## Bitmask Reference

### Class Bitmasks (for database queries)

```
Warrior     = 1      (1 << 0)
Paladin     = 2      (1 << 1)
Hunter      = 4      (1 << 2)
Rogue       = 8      (1 << 3)
Priest      = 16     (1 << 4)
Death Knight= 32     (1 << 5)
Shaman      = 64     (1 << 6)
Mage        = 128    (1 << 7)
Warlock     = 256    (1 << 8)
(unused)    = 512    (1 << 9)
Druid       = 1024   (1 << 10)
Fairy       = 2048   (1 << 11)  <-- NEW
```

### Race Bitmasks

```
Human       = 1      (1 << 0)
Orc         = 2      (1 << 1)
Dwarf       = 4      (1 << 2)
Night Elf   = 8      (1 << 3)
Undead      = 16     (1 << 4)
Tauren      = 32     (1 << 5)
Gnome       = 64     (1 << 6)
Troll       = 128    (1 << 7)
(Goblin)    = 256    (1 << 8)
Blood Elf   = 512    (1 << 9)
Draenei     = 1024   (1 << 10)
```

### Fairy Race Mask Calculation

```
Human (1) + Night Elf (8) + Gnome (64) + Blood Elf (512) = 585
```

---

## Tool Download Links

| Tool | Purpose | Link |
|------|---------|------|
| WDBX Editor | DBC editing | https://github.com/WowDevTools/WDBXEditor |
| WoW Spell Editor | Spell/DBC editing | https://github.com/stoneharry/WoW-Spell-Editor |
| Ladik's MPQ Editor | MPQ creation | https://www.hiveworkshop.com/threads/ladiks-mpq-editor.249562/ |
| Custom Class Template | Reference project | https://github.com/stoneharry/WoW-Custom-Class |
| wow-file-tools | DBC viewer | https://github.com/dawidcxx/wow-file-tools |

---

## Checklist

### Client-Side Files

- [ ] ChrClasses.dbc - Add Fairy class entry (ID 12)
- [ ] CharBaseInfo.dbc - Add 4 race/class combinations
- [ ] TalentTab.dbc - Add 3 talent tabs (801, 802, 803)
- [ ] Talent.dbc - Add individual talents (optional at start)
- [ ] All GT DBC files - Add class 12 entries
- [ ] SkillLineAbility.dbc - Add starting abilities
- [ ] SkillRaceClassInfo.dbc - Map skills to class 12
- [ ] Constants.lua - Add MAX_CLASSES, RAID_CLASS_COLORS
- [ ] CharacterCreate.lua - Add MAX_CLASSES_PER_RACE, CLASS_ICON_TCOORDS
- [ ] CharacterCreate.xml - Add class button
- [ ] GlueStrings.lua - Add all FAIRY strings
- [ ] UI-CHARACTERCREATE-CLASSES.blp - Add Fairy icon
- [ ] FairyReverie.blp - Talent background
- [ ] FairyMania.blp - Talent background
- [ ] FairyVigil.blp - Talent background
- [ ] patch-4.mpq - Package all files

### Server-Side

- [ ] SharedDefines.h - Add CLASS_FAIRY = 12
- [ ] MAX_CLASSES = 13
- [ ] Copy modified DBCs to server dbc folder
- [ ] playercreateinfo - Add starting positions
- [ ] player_classlevelstats - Add HP/Mana per level
- [ ] player_levelstats - Add base attributes
- [ ] Recompile core (if enum changed)

---

*Raw data reference for Fairy class implementation*
