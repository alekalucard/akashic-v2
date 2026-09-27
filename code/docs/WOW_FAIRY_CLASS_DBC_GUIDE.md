# WoW 3.3.5a Custom "Fairy" Class - Complete DBC Modding Guide

**Version:** WotLK 3.3.5.12340
**Class ID:** 12
**Class Name:** Fairy
**SpellClassSet:** 17
**PowerType:** Mana (0)

---

## Table of Contents

1. [Overview](#overview)
2. [Required Tools](#required-tools)
3. [DBC Files Reference](#dbc-files-reference)
4. [ChrClasses.dbc Entry](#1-chrclassesdbc-entry)
5. [CharBaseInfo.dbc Entries](#2-charbaseinfodbc-entries)
6. [TalentTab.dbc Entries](#3-talenttabdbc-entries)
7. [GT DBC Files](#4-gt-dbc-files-game-tables)
8. [UI File Modifications](#5-ui-file-modifications)
9. [MPQ Packaging](#6-mpq-packaging)
10. [Server-Side Requirements](#7-server-side-requirements)
11. [Troubleshooting](#8-troubleshooting)
12. [Sources](#sources)

---

## Overview

This guide provides exact values and structures for creating a custom "Fairy" class in World of Warcraft 3.3.5a (WotLK). The Fairy class features:

| Property | Value |
|----------|-------|
| Class ID | 12 |
| Bitmask Value | 2048 (1 << 11) |
| Power Type | Mana (0) |
| SpellClassSet | 17 (custom) |
| Playable Races | Night Elf, Blood Elf, Human, Gnome |
| Talent Trees | Reverie (Healer), Mania (DPS), Vigil (Tank) |
| Required Expansion | 0 (Classic - available to all) |

### Race IDs for Reference

| Race | ID | Bitmask |
|------|-----|---------|
| Human | 1 | 1 |
| Night Elf | 4 | 8 |
| Gnome | 7 | 64 |
| Blood Elf | 10 | 512 |

**Combined Race Mask:** 1 + 8 + 64 + 512 = **585**

---

## Required Tools

### DBC Editors

1. **WDBX Editor** (Recommended)
   - Download: [GitHub - WowDevTools/WDBXEditor](https://github.com/WowDevTools/WDBXEditor)
   - Supports all DBC, DB2, WDB formats
   - Full SQL export/import capability

2. **WoW Spell Editor**
   - Download: [GitHub - stoneharry/WoW-Spell-Editor](https://github.com/stoneharry/WoW-Spell-Editor)
   - Specifically designed for 3.3.5a, 2.4.3, 1.12.1
   - Includes DBC import/export to SQL

3. **Tallis DBC Editor**
   - Required for CharBaseInfo.dbc (unique format)
   - Some older editors cannot open this file

### MPQ Editor

- **Ladik's MPQ Editor**
   - Download: [HIVE Workshop](https://www.hiveworkshop.com/threads/ladiks-mpq-editor.249562/)
   - Best for creating patch-x.mpq files

### Image Editor

- **BLP Lab** or **Photoshop with BLP plugin**
   - For editing UI-CHARACTERCREATE-CLASSES.blp

### Reference Projects

- **stoneharry/WoW-Custom-Class**: [GitHub Repository](https://github.com/stoneharry/WoW-Custom-Class)
   - Contains tools and detailed documentation
   - Includes GT DBC automation utility

---

## DBC Files Reference

### Files Requiring Modification

| File | Purpose | Priority |
|------|---------|----------|
| ChrClasses.dbc | Class definition | Required |
| CharBaseInfo.dbc | Race/class combinations | Required |
| TalentTab.dbc | Talent tree tabs | Required |
| Talent.dbc | Individual talents | Required |
| SkillLineAbility.dbc | Starting spells | Required |
| SkillRaceClassInfo.dbc | Skill availability | Required |
| gtChanceToMeleeCrit.dbc | Melee crit scaling | Required |
| gtChanceToMeleeCritBase.dbc | Base melee crit | Required |
| gtChanceToSpellCrit.dbc | Spell crit scaling | Required |
| gtChanceToSpellCritBase.dbc | Base spell crit | Required |
| gtOCTClassCombatRatingScalar.dbc | Combat rating | Required |
| gtOCTRegenHP.dbc | HP regeneration | Required |
| gtOCTRegenMP.dbc | Mana regeneration | Required |
| gtRegenHPPerSpt.dbc | HP regen per spirit | Required |
| gtRegenMPPerSpt.dbc | MP regen per spirit | Required |
| gtCombatRatings.dbc | Combat ratings | Required |
| CharStartOutfit.dbc | Starting gear | Optional |
| SpellIcon.dbc | Custom icons | Optional |

---

## 1. ChrClasses.dbc Entry

### Structure Definition (3.3.5.12340)

```c
struct ChrClassesRec {
    uint32_t m_ID;                    // Column 0
    uint32_t m_unknownFlag;           // Column 1 (0 for most, 1 for hybrid, 9 for DK)
    uint32_t m_powerType;             // Column 2
    char*    m_petNameToken;          // Column 3
    char*    m_name[16];              // Columns 4-19 (localized)
    uint32_t m_nameLangMask;          // Column 20
    char*    m_nameFemale[16];        // Columns 21-36 (localized)
    uint32_t m_nameFemaleLangMask;    // Column 37
    char*    m_nameMale[16];          // Columns 38-53 (localized)
    uint32_t m_nameMaleLangMask;      // Column 54
    char*    m_fileName;              // Column 55
    uint32_t m_spellClassSet;         // Column 56
    uint32_t m_flags;                 // Column 57
    uint32_t m_cinematicSequence;     // Column 58
    uint32_t m_requiredExpansion;     // Column 59
};
```

### Fairy Class Entry Values

| Column | Field | Value | Notes |
|--------|-------|-------|-------|
| 0 | ID | **12** | Next available after Druid (11) |
| 1 | UnknownFlag | **0** | Same as Mage/Priest |
| 2 | PowerType | **0** | Mana |
| 3 | PetNameToken | **PET** | Standard pet naming |
| 4-19 | Name_lang | **Fairy** | English in column 4, others empty or localized |
| 20 | NameLangMask | **16712190** | Standard mask |
| 21-36 | NameFemale_lang | (empty) | Same as Name if identical |
| 37 | NameFemaleLangMask | **0** | |
| 38-53 | NameMale_lang | (empty) | Same as Name if identical |
| 54 | NameMaleLangMask | **0** | |
| 55 | FileName | **FAIRY** | Uppercase, used for file paths |
| 56 | SpellClassSet | **17** | Custom spell family |
| 57 | Flags | **2** | Player class flag |
| 58 | CinematicSequence | **0** | No custom cinematic (or create one) |
| 59 | RequiredExpansion | **0** | Available in base game |

### Flags Breakdown

| Bit | Value | Description | Use for Fairy |
|-----|-------|-------------|---------------|
| 0 | 1 | Use loincloth | No |
| 1 | 2 | Player class | **Yes** |
| 2 | 4 | Display pet | No |
| 3 | 8 | (Unused) | No |
| 4 | 16 | Can wear mail | No |
| 5 | 32 | Can wear plate | No |
| 6 | 64 | Bind starting area | No |

**Recommended Flags Value:** 2 (Player class only)

### Bitmask Calculation

```
Class ID 12 bitmask = 1 << (12 - 1) = 1 << 11 = 2048
```

This value (2048) is used in:
- quest_template.RequiredClasses
- item_template.AllowableClass
- SkillRaceClassInfo ClassMask
- TalentTab ClassMask

---

## 2. CharBaseInfo.dbc Entries

### File Structure

CharBaseInfo.dbc has a non-standard structure:

```
Header: 20 bytes
  - Bytes 0-3: Magic "WDBC" (0x57444243)
  - Bytes 4-7: Record count (uint32)
  - Bytes 8-11: Field count (uint32)
  - Bytes 12-15: Record size (uint32)
  - Bytes 16-19: String block size (uint32)

Records: 2 bytes each (older versions) or 8 bytes with padding
  - Byte 0: Race ID
  - Byte 1: Class ID
  - Bytes 2-3: Padding (if present)
  - Bytes 4-7: Padding/ID (if 8-byte records)
```

### Entries to Add for Fairy Class

Add these 4 entries to enable Human, Night Elf, Gnome, and Blood Elf:

| Entry | Race ID | Class ID | Race Name |
|-------|---------|----------|-----------|
| 1 | 1 | 12 | Human |
| 2 | 4 | 12 | Night Elf |
| 3 | 7 | 12 | Gnome |
| 4 | 10 | 12 | Blood Elf |

### Hex Values (for manual hex editing)

For 2-byte record format:
```
01 0C    ; Human (1) + Fairy (12)
04 0C    ; Night Elf (4) + Fairy (12)
07 0C    ; Gnome (7) + Fairy (12)
0A 0C    ; Blood Elf (10) + Fairy (12)
```

### Editing Process

1. Open CharBaseInfo.dbc in **Tallis** or **WDBX Editor**
2. Note the current record count
3. Add 4 new entries at the end
4. Update the record count in header (+4)
5. Save the file

---

## 3. TalentTab.dbc Entries

### Structure Definition

```c
struct TalentTabRec {
    uint32_t m_ID;                    // Column 0
    char*    m_name[16];              // Columns 1-16 (localized)
    uint32_t m_nameLangMask;          // Column 17
    uint32_t m_spellIconID;           // Column 18
    uint32_t m_raceMask;              // Column 19
    uint32_t m_classMask;             // Column 20
    uint32_t m_petTalentMask;         // Column 21
    uint32_t m_orderIndex;            // Column 22
    char*    m_backgroundFile;        // Column 23
};
```

### Fairy Talent Tab Entries

#### Tab 1: Reverie (Healer)

| Column | Field | Value |
|--------|-------|-------|
| 0 | ID | **801** (or next available) |
| 1-16 | Name_lang | **Reverie** |
| 17 | NameLangMask | **16712190** |
| 18 | SpellIconID | **136** (Holy Light icon - customize) |
| 19 | RaceMask | **0** |
| 20 | ClassMask | **2048** |
| 21 | PetTalentMask | **0** |
| 22 | OrderIndex | **0** |
| 23 | BackgroundFile | **FairyReverie** |

#### Tab 2: Mania (DPS)

| Column | Field | Value |
|--------|-------|-------|
| 0 | ID | **802** |
| 1-16 | Name_lang | **Mania** |
| 17 | NameLangMask | **16712190** |
| 18 | SpellIconID | **137** (Arcane icon - customize) |
| 19 | RaceMask | **0** |
| 20 | ClassMask | **2048** |
| 21 | PetTalentMask | **0** |
| 22 | OrderIndex | **1** |
| 23 | BackgroundFile | **FairyMania** |

#### Tab 3: Vigil (Tank)

| Column | Field | Value |
|--------|-------|-------|
| 0 | ID | **803** |
| 1-16 | Name_lang | **Vigil** |
| 17 | NameLangMask | **16712190** |
| 18 | SpellIconID | **138** (Shield icon - customize) |
| 19 | RaceMask | **0** |
| 20 | ClassMask | **2048** |
| 21 | PetTalentMask | **0** |
| 22 | OrderIndex | **2** |
| 23 | BackgroundFile | **FairyVigil** |

### Background File Creation

Create talent background images at:
```
Interface\TALENTFRAME\FairyReverie.blp
Interface\TALENTFRAME\FairyMania.blp
Interface\TALENTFRAME\FairyVigil.blp
```

Dimensions: 256x256 or 512x512 (check existing files for exact size)

---

## 4. GT DBC Files (Game Tables)

These files contain per-level scaling data. Each requires entries for Class ID 12.

### Complete GT DBC File List

| File | Records Per Class | Total Records (11 classes) |
|------|-------------------|---------------------------|
| gtBarberShopCostBase.dbc | 1 | 11 |
| gtChanceToMeleeCrit.dbc | 100 | 1100 |
| gtChanceToMeleeCritBase.dbc | 1 | 11 |
| gtChanceToSpellCrit.dbc | 100 | 1100 |
| gtChanceToSpellCritBase.dbc | 1 | 11 |
| gtCombatRatings.dbc | 32 | 352 |
| gtNPCManaCostScaler.dbc | 1 | 11 |
| gtOCTClassCombatRatingScalar.dbc | 32 | 352 |
| gtOCTRegenHP.dbc | 100 | 1100 |
| gtOCTRegenMP.dbc | 100 | 1100 |
| gtRegenHPPerSpt.dbc | 100 | 1100 |
| gtRegenMPPerSpt.dbc | 100 | 1100 |

### Adding Fairy Class Data

For each GT file, you need to duplicate an existing class's data and add it as Class 12.

**Recommended Source Classes:**
- For Healer (Reverie): Copy Priest values
- For DPS (Mania): Copy Mage values
- For Tank (Vigil): Copy Warrior values

**Automation Tool:**
Use the GT DBC automation tool from [stoneharry/WoW-Custom-Class](https://github.com/stoneharry/WoW-Custom-Class) to avoid manual errors.

### Manual Process

For each GT file with 100 records per class:

1. Find the offset for the new class: `(ClassID - 1) * RecordsPerClass`
   - For Fairy (ID 12): `(12 - 1) * 100 = 1100`

2. Copy 100 records from your source class (e.g., Mage = ID 8)
   - Source offset: `(8 - 1) * 100 = 700`
   - Copy records 700-799

3. Insert at position 1100-1199

4. Update header record count

### Example: gtChanceToMeleeCritBase.dbc

Structure: 1 record per class, single float value

| Class ID | Value (Example) |
|----------|-----------------|
| 1 (Warrior) | 0.031900 |
| ... | ... |
| 11 (Druid) | 0.019400 |
| **12 (Fairy)** | **0.031900** (copy from Warrior) |

---

## 5. UI File Modifications

### 5.1 CharacterCreate.lua

**Location:** `Interface\GlueXML\CharacterCreate.lua`

#### Modification 1: MAX_CLASSES_PER_RACE

Find:
```lua
MAX_CLASSES_PER_RACE = 10;
```

Replace with:
```lua
MAX_CLASSES_PER_RACE = 11;
```

#### Modification 2: Class Texture Coordinates

Find the `CLASS_ICON_TCOORDS` table and add:

```lua
CLASS_ICON_TCOORDS = {
    ["WARRIOR"]     = {0, 0.25, 0, 0.25},
    ["MAGE"]        = {0.25, 0.50, 0, 0.25},
    ["ROGUE"]       = {0.50, 0.75, 0, 0.25},
    ["DRUID"]       = {0.75, 1.00, 0, 0.25},
    ["HUNTER"]      = {0, 0.25, 0.25, 0.50},
    ["SHAMAN"]      = {0.25, 0.50, 0.25, 0.50},
    ["PRIEST"]      = {0.50, 0.75, 0.25, 0.50},
    ["WARLOCK"]     = {0.75, 1.00, 0.25, 0.50},
    ["PALADIN"]     = {0, 0.25, 0.50, 0.75},
    ["DEATHKNIGHT"] = {0.25, 0.50, 0.50, 0.75},
    ["FAIRY"]       = {0.50, 0.75, 0.50, 0.75},  -- NEW
};
```

### 5.2 Constants.lua

**Location:** `Interface\FrameXML\Constants.lua`

#### Modification 1: MAX_CLASSES

Find:
```lua
MAX_CLASSES = 11;
```

Replace with:
```lua
MAX_CLASSES = 12;
```

#### Modification 2: RAID_CLASS_COLORS

Add to the `RAID_CLASS_COLORS` table:

```lua
RAID_CLASS_COLORS = {
    ["WARRIOR"] = { r = 0.78, g = 0.61, b = 0.43 },
    ["MAGE"] = { r = 0.41, g = 0.80, b = 0.94 },
    ["ROGUE"] = { r = 1.00, g = 0.96, b = 0.41 },
    ["DRUID"] = { r = 1.00, g = 0.49, b = 0.04 },
    ["HUNTER"] = { r = 0.67, g = 0.83, b = 0.45 },
    ["SHAMAN"] = { r = 0.00, g = 0.44, b = 0.87 },
    ["PRIEST"] = { r = 1.00, g = 1.00, b = 1.00 },
    ["WARLOCK"] = { r = 0.58, g = 0.51, b = 0.79 },
    ["PALADIN"] = { r = 0.96, g = 0.55, b = 0.73 },
    ["DEATHKNIGHT"] = { r = 0.77, g = 0.12, b = 0.23 },
    ["FAIRY"] = { r = 0.80, g = 0.60, b = 1.00 },  -- Light purple/lavender
};
```

#### Modification 3: CLASS_SORT_ORDER (if present)

```lua
CLASS_SORT_ORDER = {
    "WARRIOR",
    "DEATHKNIGHT",
    "PALADIN",
    "PRIEST",
    "SHAMAN",
    "DRUID",
    "ROGUE",
    "MAGE",
    "WARLOCK",
    "HUNTER",
    "FAIRY",  -- NEW
};
```

### 5.3 GlueStrings.lua

**Location:** `Interface\GlueXML\GlueStrings.lua`

Add all class-related strings:

```lua
FAIRY = "Fairy";
CLASS_FAIRY = "Fairy";
CLASS_FAIRY_MALE = "Fairy";
CLASS_FAIRY_FEMALE = "Fairy";
CLASS_INFO_FAIRY = "Fairies are mystical beings who wield the power of dreams and imagination. They can heal wounds, unleash chaotic magic, or stand vigilant as protectors.";
CLASS_FAIRY_0 = "Reverie";  -- Talent spec 1
CLASS_FAIRY_1 = "Mania";    -- Talent spec 2
CLASS_FAIRY_2 = "Vigil";    -- Talent spec 3
```

### 5.4 CharacterCreate.xml

**Location:** `Interface\GlueXML\CharacterCreate.xml`

Add a new class button. Copy an existing ClassButton template and modify:

```xml
<Button name="CharacterCreateClassButton12" inherits="CharacterCreateClassButtonTemplate" id="12">
    <Anchors>
        <Anchor point="TOPLEFT" relativeTo="CharacterCreateClassButton11" relativePoint="TOPRIGHT" x="4" y="0"/>
    </Anchors>
</Button>
```

### 5.5 Class Icon Texture

**Location:** `Interface\GLUES\CHARACTERCREATE\UI-CHARACTERCREATE-CLASSES.blp`

This is a texture atlas containing all class icons in a grid.

**Grid Layout (4x3):**
```
Row 0: Warrior, Mage, Rogue, Druid
Row 1: Hunter, Shaman, Priest, Warlock
Row 2: Paladin, Death Knight, [FAIRY], [Empty]
```

Each icon is 64x64 pixels in a 256x256 texture.

**Steps to add Fairy icon:**
1. Extract UI-CHARACTERCREATE-CLASSES.blp
2. Convert to PNG/TGA
3. Add 64x64 Fairy icon at position (128, 128) - third row, third column
4. Convert back to BLP
5. Include in patch MPQ

---

## 6. MPQ Packaging

### Folder Structure

Create this folder structure for your patch:

```
patch-4.mpq/
├── DBFilesClient/
│   ├── ChrClasses.dbc
│   ├── CharBaseInfo.dbc
│   ├── TalentTab.dbc
│   ├── Talent.dbc
│   ├── SkillLineAbility.dbc
│   ├── SkillRaceClassInfo.dbc
│   ├── gtBarberShopCostBase.dbc
│   ├── gtChanceToMeleeCrit.dbc
│   ├── gtChanceToMeleeCritBase.dbc
│   ├── gtChanceToSpellCrit.dbc
│   ├── gtChanceToSpellCritBase.dbc
│   ├── gtCombatRatings.dbc
│   ├── gtNPCManaCostScaler.dbc
│   ├── gtOCTClassCombatRatingScalar.dbc
│   ├── gtOCTRegenHP.dbc
│   ├── gtOCTRegenMP.dbc
│   ├── gtRegenHPPerSpt.dbc
│   └── gtRegenMPPerSpt.dbc
├── Interface/
│   ├── FrameXML/
│   │   └── Constants.lua
│   ├── GlueXML/
│   │   ├── CharacterCreate.lua
│   │   ├── CharacterCreate.xml
│   │   └── GlueStrings.lua
│   ├── GLUES/
│   │   └── CHARACTERCREATE/
│   │       └── UI-CHARACTERCREATE-CLASSES.blp
│   └── TALENTFRAME/
│       ├── FairyReverie.blp
│       ├── FairyMania.blp
│       └── FairyVigil.blp
```

### Creating the MPQ

1. Open **Ladik's MPQ Editor**
2. Create new archive: `File > New MPQ Archive`
3. Select "MPQ Version 2.0" (for WotLK)
4. Name it `patch-4.mpq` (or next available number)
5. Add folder structure: `Operations > Add Files...`
   - **IMPORTANT:** Preserve folder paths (DBFilesClient\, Interface\, etc.)
6. Save and close

### Installation

1. Copy `patch-4.mpq` to your WoW `Data` folder
2. Delete `Cache` folder in WoW directory
3. **For server:** Copy modified DBCs to `<server>/dbc/` folder
4. Restart client and server

### MPQ Load Order

WoW loads MPQ files alphabetically. Higher-letter patches override lower ones:
- patch.mpq (original)
- patch-2.mpq
- patch-3.mpq
- **patch-4.mpq** (your custom class) - loads last, overrides

---

## 7. Server-Side Requirements

### Database Tables

#### playercreateinfo

```sql
INSERT INTO `playercreateinfo` (`race`, `class`, `map`, `zone`, `position_x`, `position_y`, `position_z`, `orientation`) VALUES
(1, 12, 0, 12, -8949.95, -132.493, 83.5312, 0),   -- Human Fairy -> Northshire
(4, 12, 1, 141, 10311.3, 832.463, 1326.41, 5.69),  -- Night Elf Fairy -> Teldrassil
(7, 12, 0, 1, -6240.32, 331.033, 382.758, 6.17),   -- Gnome Fairy -> Dun Morogh
(10, 12, 530, 3431, 10349.6, -6357.29, 33.4026, 5.31); -- Blood Elf Fairy -> Eversong
```

#### player_levelstats

```sql
-- Base stats for Fairy class (example for level 1, Human)
INSERT INTO `player_levelstats` (`race`, `class`, `level`, `str`, `agi`, `sta`, `inte`, `spi`) VALUES
(1, 12, 1, 18, 20, 19, 25, 23);
-- Repeat for levels 2-80 and all 4 races
```

#### player_classlevelstats

```sql
-- HP and mana per level
INSERT INTO `player_classlevelstats` (`class`, `level`, `basehp`, `basemana`) VALUES
(12, 1, 28, 100),
(12, 2, 36, 110),
-- ... continue to level 80
```

### TrinityCore/AzerothCore Enum Updates

In `SharedDefines.h`:

```cpp
enum Classes : uint8
{
    CLASS_NONE          = 0,
    CLASS_WARRIOR       = 1,
    CLASS_PALADIN       = 2,
    CLASS_HUNTER        = 3,
    CLASS_ROGUE         = 4,
    CLASS_PRIEST        = 5,
    CLASS_DEATH_KNIGHT  = 6,
    CLASS_SHAMAN        = 7,
    CLASS_MAGE          = 8,
    CLASS_WARLOCK       = 9,
    // CLASS_UNK        = 10,  // unused
    CLASS_DRUID         = 11,
    CLASS_FAIRY         = 12,  // NEW
};

#define MAX_CLASSES 13  // Update from 12
```

### DBC Files for Server

Copy these modified DBCs to your server's `dbc` folder:
- ChrClasses.dbc
- CharBaseInfo.dbc
- TalentTab.dbc
- Talent.dbc
- All GT DBC files

---

## 8. Troubleshooting

### Client Crashes on Character Creation

**Cause:** Missing CharBaseInfo.dbc entries or malformed file
**Fix:** Verify file structure, ensure 4-byte alignment

### Client Crashes Opening Talent Panel

**Cause:** Missing GT DBC data for class 12
**Fix:** Add entries to ALL gt*.dbc files

### Client Crashes Opening Character Panel

**Cause:** Missing gtOCTClassCombatRatingScalar entries
**Fix:** Add 32 entries for class 12 (positions 352-383)

### Class Button Not Appearing

**Cause:** CharacterCreate.xml button missing or MAX_CLASSES_PER_RACE not updated
**Fix:** Verify XML button added, Lua constant updated to 11

### Class Color Missing (Gray Name)

**Cause:** RAID_CLASS_COLORS table not updated
**Fix:** Add FAIRY entry to Constants.lua

### "Invalid Class" Error on Login

**Cause:** Server doesn't recognize class 12
**Fix:** Update server-side enum, recompile core, add playercreateinfo data

### Talent Background Missing/Black

**Cause:** Missing .blp files in Interface\TALENTFRAME
**Fix:** Create FairyReverie.blp, FairyMania.blp, FairyVigil.blp

### MPQ Not Loading

**Cause:** Wrong MPQ format or improper folder structure
**Fix:** Use MPQ Version 2.0, verify paths include `DBFilesClient\`

---

## Sources

### Official Documentation
- [wowdev.wiki - DB/ChrClasses](https://wowdev.wiki/DB/ChrClasses)
- [wowdev.wiki - DB/CharBaseInfo](https://wowdev.wiki/DB/CharBaseInfo)
- [wowdev.wiki - DB/TalentTab](https://wowdev.wiki/DB/TalentTab)
- [wowdev.wiki - DB/GameTables](https://wowdev.wiki/DB/GameTables)
- [AzerothCore Wiki - ChrClasses.dbc](https://www.azerothcore.org/wiki/chrclasses)
- [TrinityCore Wiki - DBC List](https://trinitycore.info/en/files/DBC/335/DBC)

### Tutorials & Guides
- [OwnedCore - Creating a Custom Class in 3.3.5a](https://www.ownedcore.com/forums/world-of-warcraft/world-of-warcraft-emulator-servers/wow-emu-guides-tutorials/774546-creating-custom-class-3-3-5a.html)
- [OwnedCore - Custom Talents How-To](https://www.ownedcore.com/forums/world-of-warcraft/world-of-warcraft-emulator-servers/wow-emu-guides-tutorials/262507-custom-talents-how-scrub-friendly.html)
- [WoW Modding - Creating Your First MPQ Patch](https://www.wowmodding.net/topic/1460-41-creating-your-first-mpq-patch/)

### Tools
- [GitHub - WowDevTools/WDBXEditor](https://github.com/WowDevTools/WDBXEditor)
- [GitHub - stoneharry/WoW-Custom-Class](https://github.com/stoneharry/WoW-Custom-Class)
- [GitHub - stoneharry/WoW-Spell-Editor](https://github.com/stoneharry/WoW-Spell-Editor)
- [HIVE - Ladik's MPQ Editor](https://www.hiveworkshop.com/threads/ladiks-mpq-editor.249562/)
- [GitHub - AlbearKamoo/custom-talent-trees](https://github.com/AlbearKamoo/custom-talent-trees)

### Reference Projects
- [GitHub - stoneharry/WoW-Custom-Class README](https://github.com/stoneharry/WoW-Custom-Class/blob/master/README.md)
- [GitHub - Ennie/wow-ui-source (CharacterCreate.lua)](https://github.com/Ennie/wow-ui-source/blob/master/GlueXML/CharacterCreate.lua)

---

## Quick Reference Card

```
FAIRY CLASS - QUICK VALUES
==========================
Class ID:        12
Bitmask:         2048 (1 << 11)
PowerType:       0 (Mana)
SpellClassSet:   17
FileName:        FAIRY
Flags:           2

Race Support:
  Human (1)      - Alliance
  Night Elf (4)  - Alliance
  Gnome (7)      - Alliance
  Blood Elf (10) - Horde

Race Mask:       585 (1+8+64+512)

Talent Tabs:
  801 - Reverie (Healer) - OrderIndex 0
  802 - Mania (DPS)      - OrderIndex 1
  803 - Vigil (Tank)     - OrderIndex 2

Class Color:     0.80, 0.60, 1.00 (Light Purple)
```

---

*Document created for Akashic Foundation - Fairy Class Implementation*
*Last Updated: January 2026*
