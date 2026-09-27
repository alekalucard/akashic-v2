================================================================================
    CONSCIOUSNESS WARDEN - FAIRY CLASS FOR WOW 3.3.5a
    Eluna Lua Implementation
================================================================================

OVERVIEW
--------
The Consciousness Warden is a custom class built around a unique "Chemistry"
resource system. Instead of mana, rage, or energy, this class uses four
neurochemicals that interact with each other:

  * Serotonin - Healing, calm, stability (Reverie primary)
  * Dopamine  - Damage, speed, reward (Mania primary)
  * Cortisol  - Survival, defense, fear (Vigil primary)
  * Oxytocin  - Bonding, group synergy (Secondary for all)


INSTALLATION
------------
1. Copy all .lua files to your Eluna scripts folder:
   [AzerothCore/TrinityCore]/lua_scripts/

2. Files must load in this order (use numbered naming):
   - 00_fairy_chemistry_core.lua
   - 01_ability_framework.lua
   - 02_shared_abilities.lua
   - 03_reverie_healer.lua
   - 04_mania_dps.lua
   - 05_vigil_tank.lua
   - 06_consciousness_warden_loader.lua

3. Restart your server or use .reload eluna


SPELL IDS
---------
The system uses these placeholder spell IDs (90001-90014).
You may need to:
  - Create custom spells in spell.dbc with these IDs
  - Or modify the SPELL_IDS table to use existing spell IDs
  - Or use the command-based ability system (see Commands)

Current Spell ID Assignments:
  90001 - Neural Pulse
  90002 - Empathic Mirror
  90003 - Intrusive Thought
  90004 - Soothing Presence
  90005 - Flight Response
  90006 - Dreamwalk
  90007 - Wash of Serenity
  90008 - Collective Unconscious
  90009 - Memory of Wholeness
  90010 - Lucid Intervention
  90011 - Euphoric Surge
  90012 - Anxiety Cascade
  90013 - Nightmare Visage
  90014 - Bond of Vigil


IN-GAME COMMANDS
----------------
Core Commands:
  .fairy              - Display current chemistry status
  .fairy help         - Show all available commands
  .fairy abilities    - List abilities for current spec
  .fairy reset        - Reset chemistry to baseline
  .fairy test         - Verify system is working

Specialization Commands:
  .fairy reverie      - Switch to Healer spec (Serotonin)
  .fairy mania        - Switch to DPS spec (Dopamine)
  .fairy vigil        - Switch to Tank spec (Cortisol)

Spec-Specific Commands:
  .fairy momentum     - (Mania) View Dopamine Momentum stacks
  .fairy rush         - (Mania) View The Rush passive status
  .fairy vigilant     - (Vigil) View Vigilant Stance stacks
  .fairy protection   - (Vigil) View Bond of Vigil status


ABILITIES SUMMARY
-----------------

=== SHARED (All Specs) ===

1. NEURAL PULSE
   - Basic attack, no cooldown (GCD only)
   - Generates primary chemical based on spec
   - Damage scales with current chemical level

2. EMPATHIC MIRROR
   - Creates empathic bond with ally
   - Bonded players share 30% of healing received
   - Both gain Oxytocin from the connection
   - Only one bond active at a time

3. INTRUSIVE THOUGHT
   - Shadow DoT lasting 12 seconds
   - If target dies while afflicted: +15 Dopamine bonus
   - The "reward for kills" ability

4. SOOTHING PRESENCE
   - 6 second channel
   - Heals 5% max HP per second
   - Rebalances all chemistry toward baseline
   - Breaks on movement or damage

5. FLIGHT RESPONSE
   - Instant +50% movement speed for 6 seconds
   - If damaged while active: Blink 15 yards forward
   - Blink triggers only once per activation
   - Costs and generates Cortisol

6. DREAMWALK
   - Emergency escape ability (2 min cooldown)
   - Invisibility for 8 seconds
   - Completely resets chemistry to baseline
   - Breaks bonds, clears threat


=== REVERIE (Healer) ===

7. WASH OF SERENITY
   - Main heal with 12 second HoT
   - Both components scale with Serotonin
   - Enhanced when cast on bonded ally

8. COLLECTIVE UNCONSCIOUS
   - Group HoT affecting all allies within 30 yards
   - Generates Oxytocin per ally healed
   - Bonded ally receives 50% extra healing

9. MEMORY OF WHOLENESS
   - Buff that amplifies next heal
   - Amplification scales with current Serotonin:
     * 0-25: +20%
     * 26-50: +40%
     * 51-75: +60%
     * 76-100: +80%
   - Consumes 20 Serotonin when buff is used

10. LUCID INTERVENTION
    - Large emergency heal
    - Grants 4 second CC immunity
    - +50% heal and self-immunity when cast on bonded ally
    - 45 second cooldown


=== MANIA (DPS) ===

11. EUPHORIC SURGE
    - High burst damage attack
    - Critical behavior scales with Dopamine:
      * <50: Normal crit chance
      * 50-74: +25% crit chance
      * 75-89: +50% crit, 2.5x multiplier
      * 90+: GUARANTEED CRIT, 3x multiplier
    - Generates Dopamine on critical hits

12. ANXIETY CASCADE
    - 18 second spreading DoT
    - 30% chance to spread when target takes damage
    - Each spread: +5 Dopamine, +1 Momentum
    - Kill with active DoT: +10 Dopamine, reset Euphoric Surge cooldown
    - Maximum 5 spreads per cast


=== VIGIL (Tank) ===

13. NIGHTMARE VISAGE
    - AoE taunt within 10 yards
    - Deals Shadow damage and slows enemies
    - At HIGH Cortisol: Extended taunt duration
    - At CRITICAL Cortisol: 2 second fear before taunt

14. BOND OF VIGIL
    - Redirect 50-70% of bonded ally's damage to yourself
    - Requires Empathic Mirror bond active
    - Redirect % scales with Cortisol level
    - At CRITICAL: Also heal ally for 10% of redirected
    - Ends if you drop below 20% health


PASSIVES
--------

REVERIE - Serenity's Echo:
  Whenever you gain Serotonin, bonded ally receives
  small heal equal to 5% of your max health.

MANIA - Dopamine Momentum:
  Each Dopamine gain adds 1 stack of Momentum (max 5).
  Each stack increases damage by 3%.
  Stacks decay after 10 seconds without Dopamine gain.

MANIA - The Rush:
  Above 75 Dopamine: +15% move speed, +10% attack speed
  Above 90 Dopamine: +25% move speed, +20% attack speed,
    10% chance to proc Neural Pulse on damage,
    BUT take 10% more damage (recklessness)

VIGIL - Vigilant Stance:
  Taking damage while above 50 Cortisol grants Vigilant stack.
  Each stack: -1% damage taken, +5% threat (max 10 stacks)
  At 10 stacks: "Unbreakable Vigil" - block next CC effect

VIGIL - Stress Shield:
  When dropping below 35% health:
    +15 Cortisol, +3 Vigilant stacks, 30% DR for 5 seconds
  45 second internal cooldown


CHEMISTRY MECHANICS
-------------------

Base Values:
  - Maximum: 100
  - Minimum: 0
  - Baseline: 25

Decay:
  - Chemicals above baseline decay by 2 per tick
  - Chemicals below baseline recover by 1 per tick
  - Tick interval: 3 seconds

Synergies:
  - Serotonin boost -> Oxytocin boost (calm promotes bonding)
  - Dopamine boost -> Cortisol reduction (excitement reduces stress)
  - Cortisol boost -> Serotonin reduction (stress blocks calm)
  - Oxytocin boost -> Serotonin boost (bonding promotes calm)


THRESHOLDS
----------
  DEPLETED: 0-19
  LOW: 20-49
  MEDIUM: 50-74
  HIGH: 75-89
  CRITICAL: 90-100


CUSTOMIZATION
-------------
Key tables you can modify:

CHEMISTRY_MAX, CHEMISTRY_MIN, CHEMISTRY_BASELINE
  - In 00_fairy_chemistry_core.lua
  - Adjust resource pool size and resting point

CHEMISTRY_DECAY_RATE, CHEMISTRY_TICK_INTERVAL
  - In 00_fairy_chemistry_core.lua
  - Adjust how fast chemistry normalizes

CHEMICAL_SYNERGIES
  - In 00_fairy_chemistry_core.lua
  - Adjust how chemicals interact with each other

Ability cooldowns, costs, and effects:
  - In respective ability files (02-05)
  - Modify RegisterAbility calls


KNOWN LIMITATIONS
-----------------
1. Spell IDs are placeholders and need DBC modification
2. Some visual effects use placeholder spells
3. CC immunity blocks are noted but need proper aura hooks
4. Movement speed buffs use Sprint as placeholder
5. Threat generation is approximate

These can be addressed with proper spell/aura integration
specific to your core (AzerothCore, TrinityCore, etc.)


VERSION HISTORY
---------------
1.0.0 - Initial release
  - Complete chemistry resource system
  - 6 shared abilities
  - 4 Reverie abilities
  - 2 Mania abilities
  - 2 Vigil abilities
  - Passive systems for all specs


CREDITS
-------
Akashic Foundation
Consciousness Engineering Division

"Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"

================================================================================
