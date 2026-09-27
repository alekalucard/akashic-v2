"""
Spell Analyzer - Parse and compare spell data between WoW versions
==================================================================

This module extracts and compares spell data from:
1. Retail WoW (via Wowhead API, community databases, DB2 files)
2. 3.3.5a WoW (via DBC files from AzerothCore)

It identifies:
- What CAN be backported (similar mechanics exist)
- What CANNOT be backported (engine limitations)
- What requires creative workarounds

Designed for Cardinal (Mistral) to learn WoW spell systems.
"""

import json
import struct
import asyncio
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from datetime import datetime
from enum import Enum
import httpx


# =============================================================================
# SPELL DATA STRUCTURES
# =============================================================================

class SpellSchool(Enum):
    """WoW spell schools (bitmask in actual data)"""
    PHYSICAL = 0x01
    HOLY = 0x02
    FIRE = 0x04
    NATURE = 0x08
    FROST = 0x10
    SHADOW = 0x20
    ARCANE = 0x40


class EffectType(Enum):
    """Common spell effect types in 3.3.5a"""
    NONE = 0
    INSTAKILL = 1
    SCHOOL_DAMAGE = 2
    DUMMY = 3
    PORTAL_TELEPORT = 4
    TELEPORT_UNITS = 5
    APPLY_AURA = 6
    ENVIRONMENTAL_DAMAGE = 7
    POWER_DRAIN = 8
    HEALTH_LEECH = 9
    HEAL = 10
    BIND = 11
    PORTAL = 12
    RITUAL_BASE = 13
    RITUAL_SPECIALIZE = 14
    RITUAL_ACTIVATE_PORTAL = 15
    QUEST_COMPLETE = 16
    WEAPON_DAMAGE_NOSCHOOL = 17
    RESURRECT = 18
    ADD_EXTRA_ATTACKS = 19
    DODGE = 20
    EVADE = 21
    PARRY = 22
    BLOCK = 23
    CREATE_ITEM = 24
    WEAPON = 25
    DEFENSE = 26
    PERSISTENT_AREA_AURA = 27
    SUMMON = 28
    LEAP = 29
    ENERGIZE = 30
    WEAPON_PERCENT_DAMAGE = 31
    TRIGGER_MISSILE = 32
    OPEN_LOCK = 33
    SUMMON_CHANGE_ITEM = 34
    APPLY_AREA_AURA_PARTY = 35
    LEARN_SPELL = 36
    SPELL_DEFENSE = 37
    DISPEL = 38
    LANGUAGE = 39
    DUAL_WIELD = 40
    JUMP = 41
    JUMP_DEST = 42
    TELEPORT_UNITS_FACE_CASTER = 43
    SKILL_STEP = 44
    ADD_HONOR = 45
    SPAWN = 46
    TRADE_SKILL = 47
    STEALTH = 48
    DETECT = 49
    TRANS_DOOR = 50
    FORCE_CRITICAL_HIT = 51
    GUARANTEE_HIT = 52
    ENCHANT_ITEM = 53
    ENCHANT_ITEM_TEMPORARY = 54
    TAMECREATURE = 55
    SUMMON_PET = 56
    LEARN_PET_SPELL = 57
    WEAPON_DAMAGE = 58
    CREATE_RANDOM_ITEM = 59
    PROFICIENCY = 60
    SEND_EVENT = 61
    POWER_BURN = 62
    THREAT = 63
    TRIGGER_SPELL = 64
    APPLY_AREA_AURA_RAID = 65
    CREATE_MANA_GEM = 66
    HEAL_MAX_HEALTH = 67
    INTERRUPT_CAST = 68
    DISTRACT = 69
    PULL = 70
    PICKPOCKET = 71
    ADD_FARSIGHT = 72
    UNTRAIN_TALENTS = 73
    APPLY_GLYPH = 74
    HEAL_MECHANICAL = 75
    SUMMON_OBJECT_WILD = 76
    SCRIPT_EFFECT = 77
    ATTACK = 78
    SANCTUARY = 79
    ADD_COMBO_POINTS = 80
    # ... (truncated for brevity, but the real implementation would have all 300+ effects)


@dataclass
class SpellEffect:
    """Represents a single spell effect"""
    index: int  # 0, 1, or 2 (3.3.5a has max 3 effects per spell)
    effect_type: int
    effect_type_name: str = ""
    base_points: int = 0
    die_sides: int = 0
    points_per_level: float = 0.0
    amplitude: int = 0
    chain_target: int = 0
    mechanic: int = 0
    implicit_target_a: int = 0
    implicit_target_b: int = 0
    radius_index: int = 0
    aura_type: int = 0
    aura_name: str = ""
    misc_value: int = 0
    misc_value_b: int = 0
    trigger_spell: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SpellData:
    """Complete spell data structure"""
    id: int
    name: str = ""
    description: str = ""
    tooltip: str = ""

    # Core attributes
    school: int = 0
    school_name: str = ""
    category: int = 0
    category_name: str = ""
    dispel_type: int = 0
    mechanic: int = 0

    # Casting
    cast_time: int = 0
    recovery_time: int = 0
    category_recovery_time: int = 0
    gcd_category: int = 0

    # Range
    min_range: float = 0.0
    max_range: float = 0.0

    # Cost
    mana_cost: int = 0
    mana_cost_percentage: int = 0
    power_type: int = 0  # 0=mana, 1=rage, 2=focus, 3=energy, 6=runic

    # Duration
    duration_index: int = 0
    duration_ms: int = 0

    # Effects (max 3 in 3.3.5a)
    effects: List[SpellEffect] = field(default_factory=list)

    # Attributes (bitmask flags)
    attributes: List[int] = field(default_factory=list)

    # Meta
    version: str = "3.3.5a"  # or "retail"
    source: str = ""  # "dbc", "wowhead", "db2", etc.

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["effects"] = [e.to_dict() if hasattr(e, "to_dict") else e for e in self.effects]
        return d


@dataclass
class VersionComparison:
    """Comparison result between retail and 3.3.5a spell"""
    spell_id: int
    spell_name: str
    retail_data: Optional[SpellData] = None
    wotlk_data: Optional[SpellData] = None

    # Analysis results
    exists_in_wotlk: bool = False
    effects_match: bool = False
    can_backport: bool = False
    backport_difficulty: str = "unknown"  # trivial, easy, medium, hard, impossible

    # Detailed comparison
    effect_mapping: List[Dict[str, Any]] = field(default_factory=list)
    missing_mechanics: List[str] = field(default_factory=list)
    engine_limitations: List[str] = field(default_factory=list)
    suggested_workarounds: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.retail_data:
            d["retail_data"] = self.retail_data.to_dict()
        if self.wotlk_data:
            d["wotlk_data"] = self.wotlk_data.to_dict()
        return d


# =============================================================================
# 3.3.5a DBC PARSER
# =============================================================================

class DBCParser:
    """
    Parse 3.3.5a DBC (Database Client) files.

    DBC format:
    - Header: 'WDBC' magic, record_count, field_count, record_size, string_block_size
    - Records: Fixed-size binary data
    - String block: Null-terminated strings referenced by offset

    Key spell files:
    - Spell.dbc: Main spell data
    - SpellEffect.dbc: Spell effects (in later versions)
    - SpellCategories.dbc: Categories
    - SpellCastTimes.dbc: Cast time lookup
    - SpellDuration.dbc: Duration lookup
    - SpellRange.dbc: Range lookup
    """

    def __init__(self, dbc_path: Path):
        self.dbc_path = Path(dbc_path)
        self.records: List[bytes] = []
        self.string_block: bytes = b""
        self.record_count = 0
        self.field_count = 0
        self.record_size = 0

    def load(self) -> bool:
        """Load and parse the DBC file."""
        if not self.dbc_path.exists():
            return False

        with open(self.dbc_path, "rb") as f:
            # Read header (20 bytes)
            magic = f.read(4)
            if magic != b"WDBC":
                return False

            self.record_count = struct.unpack("<I", f.read(4))[0]
            self.field_count = struct.unpack("<I", f.read(4))[0]
            self.record_size = struct.unpack("<I", f.read(4))[0]
            string_block_size = struct.unpack("<I", f.read(4))[0]

            # Read all records
            for _ in range(self.record_count):
                self.records.append(f.read(self.record_size))

            # Read string block
            self.string_block = f.read(string_block_size)

        return True

    def get_string(self, offset: int) -> str:
        """Get null-terminated string from string block."""
        if offset >= len(self.string_block):
            return ""
        end = self.string_block.find(b"\x00", offset)
        if end == -1:
            return ""
        return self.string_block[offset:end].decode("utf-8", errors="replace")

    def unpack_record(self, record: bytes, fmt: str) -> Tuple:
        """Unpack a record with given format."""
        return struct.unpack(fmt, record[:struct.calcsize(fmt)])


class SpellDBCParser(DBCParser):
    """
    Parse Spell.dbc from 3.3.5a.

    Spell.dbc has ~230 fields per record (record_size ~856 bytes).
    This is the main spell definition file.
    """

    # Spell.dbc field offsets for 3.3.5a (simplified, actual has many more)
    # Full format string would be enormous, so we extract key fields

    def parse_spell(self, record_index: int) -> Optional[SpellData]:
        """Parse a single spell record."""
        if record_index >= len(self.records):
            return None

        rec = self.records[record_index]

        # Extract key fields (offsets from 3.3.5a Spell.dbc)
        # This is a simplified extraction - full implementation needs all fields
        spell_id = struct.unpack_from("<I", rec, 0)[0]
        category = struct.unpack_from("<I", rec, 4)[0]
        dispel = struct.unpack_from("<I", rec, 8)[0]
        mechanic = struct.unpack_from("<I", rec, 12)[0]

        # Attributes (5 dwords at offset 16)
        attributes = list(struct.unpack_from("<5I", rec, 16))

        # Cast time index at offset 104
        cast_time_idx = struct.unpack_from("<I", rec, 104)[0]

        # Range index at offset 112
        range_idx = struct.unpack_from("<I", rec, 112)[0]

        # Duration index at offset 120
        duration_idx = struct.unpack_from("<I", rec, 120)[0]

        # Power type at offset 124
        power_type = struct.unpack_from("<I", rec, 124)[0]

        # Mana cost at offset 128
        mana_cost = struct.unpack_from("<I", rec, 128)[0]

        # Effects (3 sets, each has ~20 fields)
        effects = []
        # Effect types at offset 72
        effect_types = struct.unpack_from("<3I", rec, 72)
        # Base points at offset 84
        base_points = struct.unpack_from("<3i", rec, 84)
        # Aura types at offset 220
        aura_types = struct.unpack_from("<3I", rec, 220)
        # Misc values at offset 232
        misc_values = struct.unpack_from("<3i", rec, 232)
        # Trigger spells at offset 268
        trigger_spells = struct.unpack_from("<3I", rec, 268)

        for i in range(3):
            if effect_types[i] != 0:
                effects.append(SpellEffect(
                    index=i,
                    effect_type=effect_types[i],
                    base_points=base_points[i],
                    aura_type=aura_types[i],
                    misc_value=misc_values[i],
                    trigger_spell=trigger_spells[i],
                ))

        # Name string (offset ~796 for enUS, varies by locale)
        name_offset = struct.unpack_from("<I", rec, 796)[0]
        name = self.get_string(name_offset)

        # Description string (offset ~844)
        desc_offset = struct.unpack_from("<I", rec, 844)[0]
        description = self.get_string(desc_offset)

        return SpellData(
            id=spell_id,
            name=name,
            description=description,
            category=category,
            dispel_type=dispel,
            mechanic=mechanic,
            attributes=attributes,
            power_type=power_type,
            mana_cost=mana_cost,
            duration_index=duration_idx,
            effects=effects,
            version="3.3.5a",
            source="dbc",
        )

    def get_all_spells(self) -> Dict[int, SpellData]:
        """Parse all spells from the DBC."""
        spells = {}
        for i in range(self.record_count):
            spell = self.parse_spell(i)
            if spell:
                spells[spell.id] = spell
        return spells


# =============================================================================
# WOWHEAD API CLIENT
# =============================================================================

class WowheadClient:
    """
    Fetch spell data from Wowhead's unofficial API.

    Wowhead provides tooltips and data via JavaScript objects.
    We parse these to extract spell information.
    """

    BASE_URL = "https://www.wowhead.com"
    CLASSIC_URL = "https://www.wowhead.com/wotlk"  # For 3.3.5a data

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    async def get_spell_retail(self, spell_id: int) -> Optional[Dict]:
        """Fetch retail spell data from Wowhead."""
        url = f"{self.BASE_URL}/spell={spell_id}"
        return await self._fetch_spell_page(url, spell_id, "retail")

    async def get_spell_wotlk(self, spell_id: int) -> Optional[Dict]:
        """Fetch 3.3.5a spell data from Wowhead Classic."""
        url = f"{self.CLASSIC_URL}/spell={spell_id}"
        return await self._fetch_spell_page(url, spell_id, "3.3.5a")

    async def _fetch_spell_page(self, url: str, spell_id: int, version: str) -> Optional[Dict]:
        """Fetch and parse a spell page."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, follow_redirects=True)
                if response.status_code != 200:
                    return None

                html = response.text

                # Extract spell name from title
                import re
                name_match = re.search(r"<title>([^<]+)\s*-\s*Spell\s*-", html)
                name = name_match.group(1).strip() if name_match else f"Spell {spell_id}"

                # Extract tooltip data from WH.markup.printHtml
                tooltip_match = re.search(r'WH\.markup\.printHtml\("([^"]+)"', html)
                tooltip = ""
                if tooltip_match:
                    tooltip = tooltip_match.group(1).replace("\\n", "\n").replace('\\"', '"')

                # Extract effect information from page structure
                effects = []
                effect_matches = re.findall(r"Effect #(\d+).*?(\w+)", html)
                for idx, effect_type in effect_matches:
                    effects.append({
                        "index": int(idx) - 1,
                        "effect_type_name": effect_type,
                    })

                return {
                    "id": spell_id,
                    "name": name,
                    "tooltip": tooltip,
                    "effects": effects,
                    "version": version,
                    "source": "wowhead",
                    "url": url,
                }

        except Exception as e:
            return {"error": str(e), "spell_id": spell_id}

    async def search_spells(self, query: str, version: str = "retail") -> List[Dict]:
        """Search for spells by name."""
        base = self.BASE_URL if version == "retail" else self.CLASSIC_URL
        url = f"{base}/spells?filter=142:0;0:{query.replace(' ', '+')}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, follow_redirects=True)
                if response.status_code != 200:
                    return []

                # Parse list of spell IDs from results
                import re
                spell_ids = re.findall(r'href="/spell=(\d+)"', response.text)
                return [{"id": int(sid)} for sid in spell_ids[:20]]

        except Exception:
            return []


# =============================================================================
# SPELL ANALYZER
# =============================================================================

class SpellAnalyzer:
    """
    Main spell analysis engine.

    Uses Cardinal (Mistral via Ollama) for intelligent comparison
    and backporting decisions.
    """

    def __init__(
        self,
        dbc_path: Optional[Path] = None,
        ollama_url: str = "http://localhost:11434",
        ollama_model: str = "mistral",
    ):
        """
        Initialize the spell analyzer.

        Args:
            dbc_path: Path to 3.3.5a DBC files (Spell.dbc, etc.)
            ollama_url: Ollama server URL
            ollama_model: Model to use for analysis
        """
        self.dbc_path = Path(dbc_path) if dbc_path else None
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model

        self.wowhead = WowheadClient()
        self.spell_dbc: Optional[SpellDBCParser] = None
        self.wotlk_spells: Dict[int, SpellData] = {}

        # 3.3.5a engine limitations (what we KNOW can't be done)
        self.engine_limitations = [
            "No spell charges system (retail has charges on cooldowns)",
            "Max 3 effects per spell (retail has more)",
            "No talent specialization (spec-specific abilities)",
            "No Mythic+ affixes",
            "No group finder integration",
            "No personal loot system",
            "No artifact weapons/powers",
            "No essence/corruption/covenant systems",
            "No dynamic flight",
            "No zone scaling (fixed level zones)",
            "No war mode / PvP talents",
            "No transmog collections",
        ]

        # Mechanics that CAN be approximated in 3.3.5a
        self.backportable_mechanics = {
            "damage": "SPELL_EFFECT_SCHOOL_DAMAGE",
            "healing": "SPELL_EFFECT_HEAL",
            "dot": "SPELL_AURA_PERIODIC_DAMAGE",
            "hot": "SPELL_AURA_PERIODIC_HEAL",
            "buff": "SPELL_EFFECT_APPLY_AURA",
            "debuff": "SPELL_EFFECT_APPLY_AURA",
            "summon": "SPELL_EFFECT_SUMMON",
            "teleport": "SPELL_EFFECT_TELEPORT_UNITS",
            "interrupt": "SPELL_EFFECT_INTERRUPT_CAST",
            "dispel": "SPELL_EFFECT_DISPEL",
            "cc_stun": "SPELL_AURA_MOD_STUN",
            "cc_root": "SPELL_AURA_MOD_ROOT",
            "cc_fear": "SPELL_AURA_MOD_FEAR",
            "cc_silence": "SPELL_AURA_MOD_SILENCE",
            "movement_speed": "SPELL_AURA_MOD_INCREASE_SPEED",
            "absorb": "SPELL_AURA_SCHOOL_ABSORB",
            "resource_gen": "SPELL_EFFECT_ENERGIZE",
            "proc": "SPELL_AURA_PROC_TRIGGER_SPELL",
        }

    def load_dbc(self) -> bool:
        """Load 3.3.5a DBC files."""
        if not self.dbc_path:
            return False

        spell_dbc_path = self.dbc_path / "Spell.dbc"
        if not spell_dbc_path.exists():
            return False

        self.spell_dbc = SpellDBCParser(spell_dbc_path)
        if not self.spell_dbc.load():
            return False

        self.wotlk_spells = self.spell_dbc.get_all_spells()
        return len(self.wotlk_spells) > 0

    async def get_retail_spell(self, spell_id: int) -> Optional[SpellData]:
        """Get retail spell data from Wowhead."""
        data = await self.wowhead.get_spell_retail(spell_id)
        if not data or "error" in data:
            return None

        effects = [
            SpellEffect(
                index=e.get("index", 0),
                effect_type=0,
                effect_type_name=e.get("effect_type_name", ""),
            )
            for e in data.get("effects", [])
        ]

        return SpellData(
            id=spell_id,
            name=data.get("name", ""),
            description=data.get("tooltip", ""),
            effects=effects,
            version="retail",
            source="wowhead",
        )

    async def get_wotlk_spell(self, spell_id: int) -> Optional[SpellData]:
        """Get 3.3.5a spell data (DBC first, then Wowhead)."""
        # Try DBC first
        if spell_id in self.wotlk_spells:
            return self.wotlk_spells[spell_id]

        # Fall back to Wowhead
        data = await self.wowhead.get_spell_wotlk(spell_id)
        if not data or "error" in data:
            return None

        effects = [
            SpellEffect(
                index=e.get("index", 0),
                effect_type=0,
                effect_type_name=e.get("effect_type_name", ""),
            )
            for e in data.get("effects", [])
        ]

        return SpellData(
            id=spell_id,
            name=data.get("name", ""),
            description=data.get("tooltip", ""),
            effects=effects,
            version="3.3.5a",
            source="wowhead",
        )

    async def compare_spell(
        self,
        retail_spell_id: int,
        wotlk_spell_id: Optional[int] = None,
    ) -> VersionComparison:
        """
        Compare a retail spell with its 3.3.5a equivalent.

        Args:
            retail_spell_id: Retail spell ID
            wotlk_spell_id: 3.3.5a spell ID (same as retail if not specified)
        """
        wotlk_id = wotlk_spell_id or retail_spell_id

        retail_data = await self.get_retail_spell(retail_spell_id)
        wotlk_data = await self.get_wotlk_spell(wotlk_id)

        comparison = VersionComparison(
            spell_id=retail_spell_id,
            spell_name=retail_data.name if retail_data else f"Spell {retail_spell_id}",
            retail_data=retail_data,
            wotlk_data=wotlk_data,
            exists_in_wotlk=wotlk_data is not None,
        )

        if not retail_data:
            comparison.backport_difficulty = "unknown"
            comparison.engine_limitations.append("Could not fetch retail data")
            return comparison

        # Analyze backportability
        await self._analyze_backportability(comparison)

        return comparison

    async def _analyze_backportability(self, comparison: VersionComparison):
        """Use Cardinal (Mistral) to analyze backportability."""
        retail = comparison.retail_data
        wotlk = comparison.wotlk_data

        # Build analysis prompt
        prompt = f"""Analyze this WoW spell for backporting from retail to 3.3.5a:

## RETAIL SPELL
- ID: {retail.id}
- Name: {retail.name}
- Description: {retail.description[:500] if retail.description else 'N/A'}
- Effects: {json.dumps([e.to_dict() for e in retail.effects], indent=2) if retail.effects else 'Unknown'}

## 3.3.5a EQUIVALENT
{"Exists: " + wotlk.name if wotlk else "Does NOT exist in 3.3.5a"}

## 3.3.5a ENGINE LIMITATIONS
{chr(10).join('- ' + lim for lim in self.engine_limitations[:5])}

## BACKPORTABLE MECHANICS IN 3.3.5A
{chr(10).join(f'- {k}: {v}' for k, v in list(self.backportable_mechanics.items())[:10])}

## ANALYZE:
1. Can this spell be backported to 3.3.5a?
2. What mechanics exist in the spell?
3. What mechanics can be replicated?
4. What mechanics CANNOT be replicated?
5. Suggested workarounds if any?

Respond with JSON:
{{
    "can_backport": true/false,
    "difficulty": "trivial|easy|medium|hard|impossible",
    "mechanics_found": ["mechanic1", "mechanic2"],
    "replicable_mechanics": ["mechanic1"],
    "missing_mechanics": ["mechanic2"],
    "engine_limitations_hit": ["limitation1"],
    "workarounds": ["workaround1"],
    "effect_mapping": [
        {{"retail_effect": "X", "wotlk_equivalent": "Y", "notes": "..."}}
    ],
    "implementation_notes": "Brief notes on how to implement"
}}"""

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "system": "You are Cardinal, analyzing WoW spells for backporting to 3.3.5a. Be precise and technical.",
                        "stream": False,
                        "options": {"temperature": 0.3},
                    }
                )

                if response.status_code == 200:
                    result = response.json().get("response", "")

                    # Parse JSON from response
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', result)
                    if json_match:
                        data = json.loads(json_match.group())
                        comparison.can_backport = data.get("can_backport", False)
                        comparison.backport_difficulty = data.get("difficulty", "unknown")
                        comparison.missing_mechanics = data.get("missing_mechanics", [])
                        comparison.engine_limitations = data.get("engine_limitations_hit", [])
                        comparison.suggested_workarounds = data.get("workarounds", [])
                        comparison.effect_mapping = data.get("effect_mapping", [])
                        return

        except Exception as e:
            comparison.engine_limitations.append(f"Analysis error: {str(e)}")

        # Fallback: simple heuristic analysis
        comparison.can_backport = comparison.exists_in_wotlk
        comparison.backport_difficulty = "medium" if comparison.exists_in_wotlk else "hard"

    async def batch_compare(self, spell_ids: List[int]) -> List[VersionComparison]:
        """Compare multiple spells."""
        results = []
        for spell_id in spell_ids:
            comparison = await self.compare_spell(spell_id)
            results.append(comparison)
            await asyncio.sleep(0.5)  # Rate limiting
        return results

    def find_similar_wotlk_spell(self, name: str) -> List[SpellData]:
        """Find 3.3.5a spells with similar names."""
        name_lower = name.lower()
        matches = []

        for spell in self.wotlk_spells.values():
            if name_lower in spell.name.lower():
                matches.append(spell)

        return sorted(matches, key=lambda s: s.name)[:10]


# =============================================================================
# STANDALONE TESTING
# =============================================================================

async def main():
    """Test the spell analyzer."""
    print("=== Spell Analyzer Test ===")
    print()

    analyzer = SpellAnalyzer()

    # Test Wowhead fetch
    print("Fetching retail spell 116 (Frostbolt)...")
    retail = await analyzer.get_retail_spell(116)
    if retail:
        print(f"  Name: {retail.name}")
        print(f"  Effects: {len(retail.effects)}")
    else:
        print("  Failed to fetch")

    print()
    print("Fetching 3.3.5a spell 116 (Frostbolt)...")
    wotlk = await analyzer.get_wotlk_spell(116)
    if wotlk:
        print(f"  Name: {wotlk.name}")
        print(f"  Effects: {len(wotlk.effects)}")
    else:
        print("  Failed to fetch")

    print()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
