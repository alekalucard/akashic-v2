-- ============================================================================
-- FAIRY CLASS (Consciousness Warden) - Database Foundation
-- AzerothCore 3.3.5a
-- Class ID: 12
-- ============================================================================
--
-- The Consciousness Warden (Fairy) is a mystical class that bridges the gap
-- between the mortal realm and the plane of consciousness. They wield
-- thought-magic and emotional resonance to heal allies and confuse enemies.
--
-- Primary Stats: Intellect, Spirit
-- Combat Role: Healer/Support (can DPS with confusion effects)
-- Resource: Mana + Essence (consciousness energy)
-- ============================================================================

-- First, ensure we have a clean slate for class 12
DELETE FROM `playercreateinfo` WHERE `class` = 12;
DELETE FROM `player_levelstats` WHERE `class` = 12;
DELETE FROM `player_classlevelstats` WHERE `class` = 12;
DELETE FROM `playercreateinfo_spell_custom` WHERE `class` = 12;

-- ============================================================================
-- PLAYERCREATEINFO - Starting Locations by Race
-- ============================================================================
-- Fairies can be: Human, Night Elf, Gnome, Draenei, Blood Elf, Undead
-- Each starts in their racial starting zone with fairy-specific gear

-- Human Fairy (Northshire Abbey)
INSERT INTO `playercreateinfo` (`race`, `class`, `map`, `zone`, `position_x`, `position_y`, `position_z`, `orientation`) VALUES
(1, 12, 0, 12, -8949.95, -132.493, 83.5312, 0);

-- Night Elf Fairy (Shadowglen)
INSERT INTO `playercreateinfo` (`race`, `class`, `map`, `zone`, `position_x`, `position_y`, `position_z`, `orientation`) VALUES
(4, 12, 1, 141, 10311.3, 832.463, 1326.41, 5.69632);

-- Gnome Fairy (Gnomeregan - Coldridge Valley start)
INSERT INTO `playercreateinfo` (`race`, `class`, `map`, `zone`, `position_x`, `position_y`, `position_z`, `orientation`) VALUES
(7, 12, 0, 1, -6240.32, 331.033, 382.758, 6.17716);

-- Draenei Fairy (Azuremyst Isle)
INSERT INTO `playercreateinfo` (`race`, `class`, `map`, `zone`, `position_x`, `position_y`, `position_z`, `orientation`) VALUES
(11, 12, 530, 3526, -3961.64, -13931.2, 100.615, 2.08364);

-- Blood Elf Fairy (Sunstrider Isle)
INSERT INTO `playercreateinfo` (`race`, `class`, `map`, `zone`, `position_x`, `position_y`, `position_z`, `orientation`) VALUES
(10, 12, 530, 3431, 10349.6, -6357.29, 33.4026, 5.31605);

-- Forsaken Fairy (Deathknell)
INSERT INTO `playercreateinfo` (`race`, `class`, `map`, `zone`, `position_x`, `position_y`, `position_z`, `orientation`) VALUES
(5, 12, 0, 85, 1676.35, 1677.45, 121.67, 2.70526);

-- ============================================================================
-- PLAYER_CLASSLEVELSTATS - HP/Mana per level
-- ============================================================================
-- Fairies have priest-like HP but higher base mana (consciousness magic)
-- Base stats modeled after Priest but with 10% more mana

INSERT INTO `player_classlevelstats` (`class`, `level`, `basehp`, `basemana`) VALUES
(12, 1, 52, 110),
(12, 2, 67, 131),
(12, 3, 82, 153),
(12, 4, 97, 176),
(12, 5, 112, 200),
(12, 6, 127, 225),
(12, 7, 142, 251),
(12, 8, 157, 278),
(12, 9, 172, 306),
(12, 10, 187, 335),
(12, 11, 202, 365),
(12, 12, 217, 396),
(12, 13, 232, 428),
(12, 14, 252, 461),
(12, 15, 272, 495),
(12, 16, 292, 530),
(12, 17, 317, 566),
(12, 18, 342, 603),
(12, 19, 372, 641),
(12, 20, 402, 680),
(12, 21, 432, 720),
(12, 22, 467, 761),
(12, 23, 502, 803),
(12, 24, 542, 846),
(12, 25, 582, 890),
(12, 26, 627, 935),
(12, 27, 672, 981),
(12, 28, 722, 1028),
(12, 29, 772, 1076),
(12, 30, 827, 1125),
(12, 31, 882, 1175),
(12, 32, 942, 1226),
(12, 33, 1002, 1278),
(12, 34, 1067, 1331),
(12, 35, 1132, 1385),
(12, 36, 1202, 1440),
(12, 37, 1272, 1496),
(12, 38, 1347, 1553),
(12, 39, 1427, 1611),
(12, 40, 1507, 1670),
(12, 41, 1592, 1730),
(12, 42, 1682, 1791),
(12, 43, 1772, 1853),
(12, 44, 1867, 1916),
(12, 45, 1967, 1980),
(12, 46, 2072, 2045),
(12, 47, 2177, 2111),
(12, 48, 2287, 2178),
(12, 49, 2402, 2246),
(12, 50, 2522, 2315),
(12, 51, 2642, 2385),
(12, 52, 2767, 2456),
(12, 53, 2897, 2528),
(12, 54, 3032, 2601),
(12, 55, 3172, 2675),
(12, 56, 3312, 2750),
(12, 57, 3457, 2826),
(12, 58, 3607, 2903),
(12, 59, 3762, 2981),
(12, 60, 3922, 3060),
(12, 61, 4082, 3140),
(12, 62, 4247, 3221),
(12, 63, 4417, 3303),
(12, 64, 4592, 3386),
(12, 65, 4772, 3470),
(12, 66, 4952, 3555),
(12, 67, 5137, 3641),
(12, 68, 5327, 3728),
(12, 69, 5522, 3816),
(12, 70, 5722, 3905),
(12, 71, 5922, 3995),
(12, 72, 6127, 4086),
(12, 73, 6337, 4178),
(12, 74, 6552, 4271),
(12, 75, 6772, 4365),
(12, 76, 6997, 4460),
(12, 77, 7227, 4556),
(12, 78, 7462, 4653),
(12, 79, 7702, 4751),
(12, 80, 7947, 4850);

-- ============================================================================
-- PLAYER_LEVELSTATS - Base Stats per Race/Level
-- ============================================================================
-- Stats: str, agi, sta, int, spi
-- Fairies prioritize: Spirit > Intellect > Stamina > Agility > Strength

-- Human Fairy Stats (Level 1-80)
-- Humans have balanced stats, slight spirit bonus
INSERT INTO `player_levelstats` (`race`, `class`, `level`, `str`, `agi`, `sta`, `inte`, `spi`) VALUES
(1, 12, 1, 18, 18, 19, 22, 24),
(1, 12, 10, 20, 20, 24, 30, 33),
(1, 12, 20, 23, 23, 31, 40, 44),
(1, 12, 30, 27, 27, 40, 52, 57),
(1, 12, 40, 32, 32, 51, 66, 73),
(1, 12, 50, 38, 38, 64, 82, 91),
(1, 12, 60, 45, 45, 79, 101, 112),
(1, 12, 70, 54, 54, 97, 123, 136),
(1, 12, 80, 65, 65, 118, 149, 165);

-- Night Elf Fairy Stats
-- Agility bonus from racial
INSERT INTO `player_levelstats` (`race`, `class`, `level`, `str`, `agi`, `sta`, `inte`, `spi`) VALUES
(4, 12, 1, 15, 22, 18, 22, 24),
(4, 12, 10, 17, 24, 23, 30, 33),
(4, 12, 20, 20, 28, 30, 40, 44),
(4, 12, 30, 24, 33, 39, 52, 57),
(4, 12, 40, 29, 39, 50, 66, 73),
(4, 12, 50, 35, 46, 63, 82, 91),
(4, 12, 60, 42, 55, 78, 101, 112),
(4, 12, 70, 51, 66, 96, 123, 136),
(4, 12, 80, 62, 79, 117, 149, 165);

-- Gnome Fairy Stats
-- Intellect bonus from racial
INSERT INTO `player_levelstats` (`race`, `class`, `level`, `str`, `agi`, `sta`, `inte`, `spi`) VALUES
(7, 12, 1, 13, 20, 18, 27, 22),
(7, 12, 10, 15, 22, 23, 35, 31),
(7, 12, 20, 18, 26, 30, 45, 42),
(7, 12, 30, 22, 31, 39, 57, 55),
(7, 12, 40, 27, 37, 50, 72, 70),
(7, 12, 50, 33, 44, 63, 89, 88),
(7, 12, 60, 40, 53, 78, 109, 108),
(7, 12, 70, 49, 64, 96, 132, 131),
(7, 12, 80, 60, 77, 117, 160, 159);

-- Draenei Fairy Stats
-- Intellect and Spirit from racial
INSERT INTO `player_levelstats` (`race`, `class`, `level`, `str`, `agi`, `sta`, `inte`, `spi`) VALUES
(11, 12, 1, 19, 15, 18, 23, 25),
(11, 12, 10, 21, 17, 23, 31, 34),
(11, 12, 20, 24, 20, 30, 41, 45),
(11, 12, 30, 28, 24, 39, 53, 58),
(11, 12, 40, 33, 29, 50, 67, 74),
(11, 12, 50, 39, 35, 63, 83, 92),
(11, 12, 60, 46, 42, 78, 102, 113),
(11, 12, 70, 55, 51, 96, 124, 137),
(11, 12, 80, 66, 62, 117, 150, 166);

-- Blood Elf Fairy Stats
-- Intellect bonus from racial
INSERT INTO `player_levelstats` (`race`, `class`, `level`, `str`, `agi`, `sta`, `inte`, `spi`) VALUES
(10, 12, 1, 15, 20, 17, 26, 22),
(10, 12, 10, 17, 22, 22, 34, 31),
(10, 12, 20, 20, 26, 29, 44, 42),
(10, 12, 30, 24, 31, 38, 56, 55),
(10, 12, 40, 29, 37, 49, 71, 70),
(10, 12, 50, 35, 44, 62, 88, 88),
(10, 12, 60, 42, 53, 77, 108, 108),
(10, 12, 70, 51, 64, 95, 131, 131),
(10, 12, 80, 62, 77, 116, 159, 159);

-- Forsaken Fairy Stats
-- Unique undead perspective on consciousness
INSERT INTO `player_levelstats` (`race`, `class`, `level`, `str`, `agi`, `sta`, `inte`, `spi`) VALUES
(5, 12, 1, 16, 16, 20, 20, 28),
(5, 12, 10, 18, 18, 25, 28, 37),
(5, 12, 20, 21, 21, 32, 38, 48),
(5, 12, 30, 25, 25, 41, 50, 61),
(5, 12, 40, 30, 30, 52, 64, 77),
(5, 12, 50, 36, 36, 65, 80, 96),
(5, 12, 60, 43, 43, 80, 99, 118),
(5, 12, 70, 52, 52, 98, 121, 143),
(5, 12, 80, 63, 63, 119, 147, 173);

-- ============================================================================
-- PLAYERCREATEINFO_SPELL_CUSTOM - Starting Abilities
-- ============================================================================
-- These are the initial spells Fairy class gets at level 1

-- Basic Attack Ability (like Shoot for wands)
INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES
(0, 2048, 5019, 'Fairy - Shoot (Wand)');

-- Mind Tap - Basic damage ability (consciousness drain)
-- Note: This uses a custom spell ID, would need spell_dbc entry
INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES
(0, 2048, 900001, 'Fairy - Mind Tap (Rank 1)');

-- Soothe - Basic heal ability
INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES
(0, 2048, 900002, 'Fairy - Soothe (Rank 1)');

-- Empathic Shield - Self buff (absorb shield based on Spirit)
INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES
(0, 2048, 900003, 'Fairy - Empathic Shield');

-- Inner Focus - Mana regen ability
INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES
(0, 2048, 900004, 'Fairy - Inner Focus');

-- Racial Abilities (these already exist in game)
-- Human: Diplomacy, Perception
INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES
(1, 2048, 20599, 'Human Fairy - Diplomacy'),
(1, 2048, 20600, 'Human Fairy - Perception');

-- Night Elf: Shadowmeld, Nature Resistance
INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES
(8, 2048, 20580, 'Night Elf Fairy - Shadowmeld'),
(8, 2048, 20583, 'Night Elf Fairy - Nature Resistance');

-- Gnome: Escape Artist, Arcane Resistance
INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES
(64, 2048, 20589, 'Gnome Fairy - Escape Artist'),
(64, 2048, 20592, 'Gnome Fairy - Arcane Resistance');

-- Draenei: Gift of the Naaru, Shadow Resistance
INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES
(1024, 2048, 28880, 'Draenei Fairy - Gift of the Naaru'),
(1024, 2048, 59542, 'Draenei Fairy - Shadow Resistance');

-- Blood Elf: Arcane Torrent, Arcane Affinity
INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES
(512, 2048, 28730, 'Blood Elf Fairy - Arcane Torrent'),
(512, 2048, 28877, 'Blood Elf Fairy - Arcane Affinity');

-- Forsaken: Will of the Forsaken, Cannibalize
INSERT INTO `playercreateinfo_spell_custom` (`racemask`, `classmask`, `Spell`, `Note`) VALUES
(16, 2048, 7744, 'Forsaken Fairy - Will of the Forsaken'),
(16, 2048, 20577, 'Forsaken Fairy - Cannibalize');

-- ============================================================================
-- NOTES FOR IMPLEMENTATION
-- ============================================================================
-- 1. Custom spell IDs (900001-900999) need spell_dbc.sql entries
-- 2. Class mask 2048 = class ID 12 (2^(12-1) = 2048)
-- 3. Race masks: Human=1, NightElf=8, Gnome=64, Draenei=1024, BloodElf=512, Forsaken=16
-- 4. The DBC client patches are needed for character creation screen
-- 5. Level stats are interpolated - fill in remaining levels as needed
-- ============================================================================
