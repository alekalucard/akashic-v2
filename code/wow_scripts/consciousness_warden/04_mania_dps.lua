--[[
================================================================================
    CONSCIOUSNESS WARDEN - MANIA SPECIALIZATION (DPS)
    WoW 3.3.5a Eluna Lua

    The Mania spec focuses on damage and excitement. Primary chemical: Dopamine
    Secondary synergy: Cortisol (burst damage through stress response)

    Spec Abilities:
    11. Euphoric Surge - Burst damage, auto-crit at high dopamine
    12. Anxiety Cascade - Spreading DoT that generates dopamine

    Philosophy: Ride the wave of excitement, reward-seeking behavior fuels power

    Author: Akashic Foundation
    Version: 1.0.0
================================================================================
--]]

-- Mania-specific state tracking
local ManiaState = {
    euphoricSurge = {},      -- Players with Euphoric Surge cooldown effects
    anxietyCascade = {},     -- Active anxiety cascades
    dopamineStacks = {}      -- Track dopamine momentum
}

--[[
================================================================================
    MANIA PASSIVE: DOPAMINE MOMENTUM
    Every time you generate Dopamine, gain a stack of Momentum (max 5).
    Each stack increases your damage by 3%.
    Stacks decay after 10 seconds of not generating Dopamine.
================================================================================
--]]

local function GetDopamineMomentum(playerGUID)
    local data = ManiaState.dopamineStacks[playerGUID]
    if not data or GetGameTime() > data.expires then
        ManiaState.dopamineStacks[playerGUID] = nil
        return 0
    end
    return data.stacks
end

local function AddDopamineMomentum(playerGUID)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    if chem.spec ~= "mania" then return 0 end

    local current = GetDopamineMomentum(playerGUID)
    local newStacks = math.min(5, current + 1)

    ManiaState.dopamineStacks[playerGUID] = {
        stacks = newStacks,
        expires = GetGameTime() + 10
    }

    return newStacks
end

local function GetMomentumMultiplier(playerGUID)
    local stacks = GetDopamineMomentum(playerGUID)
    return 1 + (stacks * 0.03)  -- 3% per stack
end

--[[
================================================================================
    ABILITY 11: EUPHORIC SURGE
    Channel the rush of excitement into a devastating attack.

    Base damage: High
    Critical behavior:
    - Normal crit chance at Dopamine < 50
    - At Dopamine 50-74: +25% crit chance
    - At Dopamine 75-89: +50% crit chance, crits deal 2.5x instead of 2x
    - At Dopamine 90+: GUARANTEED CRIT, 3x crit multiplier

    Consumes Dopamine on use (more damage = more consumption).
    Generates Dopamine on crit.

    Instant cast, 6 second cooldown
================================================================================
--]]

FairyAbilities.RegisterAbility({
    name = "Euphoric Surge",
    spellId = FairyAbilities.SPELL_IDS.EUPHORIC_SURGE,
    cooldown = 6,
    primaryChemical = "dopamine",
    specs = { "mania" },
    chemistryCost = { dopamine = 15 },
    chemistryGenerated = {},  -- Dynamic based on crit

    handler = function(player, target)
        local guid = player:GetGUID()

        -- Get enemy target
        local enemy, err = FairyAbilities.GetValidTarget(player, "enemy")
        if not enemy then
            FairyAbilities.SendAbilityMessage(player, "Euphoric Surge", "cortisol", err or "No valid target")
            return false
        end

        -- Get current dopamine level
        local dopamine = FairyChemistry.GetChemical(guid, "dopamine")
        local level, _ = FairyChemistry.GetChemicalLevel(guid, "dopamine")

        -- Determine crit behavior
        local critChance = 0.05  -- Base 5%
        local critMultiplier = 2.0
        local guaranteedCrit = false

        if dopamine >= 90 then
            guaranteedCrit = true
            critMultiplier = 3.0
        elseif dopamine >= 75 then
            critChance = critChance + 0.50
            critMultiplier = 2.5
        elseif dopamine >= 50 then
            critChance = critChance + 0.25
        end

        -- Calculate if this attack crits
        local isCrit = guaranteedCrit or (math.random() < critChance)

        -- Calculate base damage
        local baseDamage = player:GetLevel() * 25 + 150
        local damage = FairyAbilities.CalculateDamage(player, baseDamage, "dopamine")

        -- Apply momentum multiplier
        local momentum = GetMomentumMultiplier(guid)
        damage = math.floor(damage * momentum)

        -- Apply crit
        if isCrit then
            damage = math.floor(damage * critMultiplier)
        end

        -- Extra dopamine cost at high dopamine (you're spending the excitement)
        local extraCost = 0
        if dopamine >= 75 then
            extraCost = 10
            FairyChemistry.ModifyChemical(guid, "dopamine", -extraCost)
        end

        -- Deal damage
        enemy:DealDamage(player, damage, isCrit)

        -- Track damage
        local chem = FairyChemistry.GetOrCreate(guid)
        chem.totalDamageDealt = chem.totalDamageDealt + damage

        -- Generate dopamine on crit (the reward!)
        if isCrit then
            local dopamineGain = 12
            if guaranteedCrit then
                dopamineGain = 18  -- Extra reward for riding the wave
            end
            FairyChemistry.ModifyChemical(guid, "dopamine", dopamineGain)
            AddDopamineMomentum(guid)
        end

        -- Visual feedback
        FairyAbilities.PlayVisualEffect(player, "damage_pulse")

        local msg
        if isCrit then
            if guaranteedCrit then
                msg = string.format("|cFFFF0000EUPHORIA!|r |cFFFFFFFF%d|r damage! |cFFFFD700(Guaranteed 3x crit!)|r",
                    damage)
            else
                msg = string.format("|cFFFFD700CRITICAL!|r |cFFFFFFFF%d|r damage (%.1fx)",
                    damage, critMultiplier)
            end
        else
            msg = string.format("Hit for |cFFFFFFFF%d|r damage (Dopamine: %d)",
                damage, dopamine)
        end

        local momentumStacks = GetDopamineMomentum(guid)
        if momentumStacks > 0 then
            msg = msg .. string.format(" |cFF808080[Momentum x%d]|r", momentumStacks)
        end

        FairyAbilities.SendAbilityMessage(player, "Euphoric Surge", "dopamine", msg)

        return true
    end
})

--[[
================================================================================
    ABILITY 12: ANXIETY CASCADE
    Inflict a spreading anxiety on the target. The target takes Shadow
    damage over 18 seconds. When the target takes damage from other sources,
    the anxiety has a chance to spread to a nearby enemy.

    Each spread:
    - Generates 5 Dopamine
    - Adds 1 Dopamine Momentum stack
    - Slightly increases Cortisol (anxiety is stressful!)

    If an afflicted target dies, gain 10 Dopamine and reset the cooldown
    of Euphoric Surge.

    Instant cast, 12 second cooldown
================================================================================
--]]

local AnxietyCascadeTargets = {}

FairyAbilities.RegisterAbility({
    name = "Anxiety Cascade",
    spellId = FairyAbilities.SPELL_IDS.ANXIETY_CASCADE,
    cooldown = 12,
    primaryChemical = "dopamine",
    specs = { "mania" },
    chemistryCost = { cortisol = 10 },  -- Anxiety costs stress
    chemistryGenerated = { dopamine = 5, cortisol = 3 },

    handler = function(player, target)
        local guid = player:GetGUID()

        -- Get enemy target
        local enemy, err = FairyAbilities.GetValidTarget(player, "enemy")
        if not enemy then
            FairyAbilities.SendAbilityMessage(player, "Anxiety Cascade", "cortisol", err or "No valid target")
            return false
        end

        -- Calculate tick damage
        local baseDamage = player:GetLevel() * 4 + 25
        local tickDamage = FairyAbilities.CalculateDamage(player, baseDamage, "dopamine")

        -- Track this as a cascade origin
        local cascadeId = guid .. "_" .. GetGameTime()
        AnxietyCascadeTargets[cascadeId] = {
            caster = player,
            casterGUID = guid,
            originalTarget = enemy:GetGUID(),
            spreadCount = 0,
            maxSpread = 5,
            spreadChance = 0.30,  -- 30% chance to spread on damage
            tickDamage = tickDamage
        }

        -- Apply DoT
        FairyAbilities.ApplyDoT(player, enemy, {
            name = "Anxiety Cascade",
            tickDamage = tickDamage,
            tickInterval = 3000,
            duration = 18,
            chemical = "dopamine",
            spreadable = true,

            onKill = function(dot)
                -- Big reward for anxiety kill!
                FairyChemistry.ModifyChemical(dot.casterGUID, "dopamine", 10)

                -- Reset Euphoric Surge cooldown
                local chem = FairyChemistry.GetOrCreate(dot.casterGUID)
                chem.cooldowns["Euphoric Surge"] = nil

                if dot.caster and dot.caster:IsInWorld() then
                    FairyAbilities.PlayVisualEffect(dot.caster, "speed_burst")
                    FairyAbilities.SendAbilityMessage(dot.caster, "Anxiety Cascade", "dopamine",
                        "|cFFFFD700KILL!|r +10 Dopamine, |cFF00FF00Euphoric Surge reset!|r")
                end
            end
        })

        -- Mark target for spread tracking
        FairyChemistry.AddEffect(enemy:GetGUID(), "ANXIETY_CASCADE_" .. guid, 18, {
            cascadeId = cascadeId,
            casterGUID = guid
        })

        -- Visual feedback
        FairyAbilities.SendAbilityMessage(player, "Anxiety Cascade", "dopamine",
            string.format("Anxiety planted! |cFF808080%d damage per tick, may spread|r", tickDamage))

        return true
    end
})

-- Handle anxiety spreading on damage
local function OnAnxietySpread(attackerGUID, targetGUID)
    -- Check if target has anxiety
    for effectName, _ in pairs({}) do  -- Would iterate over effects
        if effectName:match("^ANXIETY_CASCADE_") then
            -- Check spread
        end
    end
end

-- Process anxiety cascade spreading
local function ProcessAnxietyCascade()
    for cascadeId, cascade in pairs(AnxietyCascadeTargets) do
        if cascade.spreadCount >= cascade.maxSpread then
            -- Max spread reached
            AnxietyCascadeTargets[cascadeId] = nil
        elseif not cascade.caster or not cascade.caster:IsInWorld() then
            -- Caster gone
            AnxietyCascadeTargets[cascadeId] = nil
        end
    end
end

CreateLuaEvent(ProcessAnxietyCascade, 3000, 0)

-- Manual spread trigger (called when anxiety target takes damage from any source)
function FairyAbilities.TryAnxietySpread(casterGUID, targetGUID)
    for cascadeId, cascade in pairs(AnxietyCascadeTargets) do
        if cascade.casterGUID == casterGUID and cascade.spreadCount < cascade.maxSpread then
            -- Check spread chance
            if math.random() < cascade.spreadChance then
                -- Find a nearby enemy to spread to
                local target = GetPlayerByGUID(targetGUID) or GetCreatureByGUID(targetGUID)
                if not target then return false end

                local nearbyEnemies = FairyAbilities.GetNearbyEnemies(target, 10)
                for _, enemy in ipairs(nearbyEnemies) do
                    -- Don't spread to same target
                    if enemy:GetGUID() ~= targetGUID then
                        -- Check if already has anxiety from this caster
                        local alreadyAfflicted = FairyChemistry.HasEffect(
                            enemy:GetGUID(), "ANXIETY_CASCADE_" .. casterGUID)

                        if not alreadyAfflicted then
                            -- Spread the anxiety!
                            local caster = cascade.caster
                            if caster and caster:IsInWorld() then
                                FairyAbilities.ApplyDoT(caster, enemy, {
                                    name = "Anxiety Cascade",
                                    tickDamage = cascade.tickDamage,
                                    tickInterval = 3000,
                                    duration = 12,  -- Shorter duration on spread
                                    chemical = "dopamine"
                                })

                                FairyChemistry.AddEffect(enemy:GetGUID(),
                                    "ANXIETY_CASCADE_" .. casterGUID, 12, { cascadeId = cascadeId })

                                cascade.spreadCount = cascade.spreadCount + 1

                                -- Reward for spreading!
                                FairyChemistry.ModifyChemical(casterGUID, "dopamine", 5)
                                AddDopamineMomentum(casterGUID)
                                FairyChemistry.ModifyChemical(casterGUID, "cortisol", 2)

                                FairyAbilities.SendAbilityMessage(caster, "Anxiety Cascade", "dopamine",
                                    string.format("|cFFFF4500Anxiety spreads!|r (+5 Dopamine, spread %d/%d)",
                                        cascade.spreadCount, cascade.maxSpread))
                            end

                            break  -- Only spread to one target per trigger
                        end
                    end
                end
            end
        end
    end
end

--[[
================================================================================
    MANIA PASSIVE: THE RUSH
    While above 75 Dopamine, your movement speed is increased by 15%
    and your attack speed by 10%.

    At 90+ Dopamine, gain "Pure Euphoria":
    - +25% movement speed
    - +20% attack speed
    - Your damage has a 10% chance to proc additional Neural Pulse

    However, above 90 Dopamine, you also take 10% more damage (recklessness)
================================================================================
--]]

local function GetRushState(playerGUID)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    if chem.spec ~= "mania" then return nil end

    local dopamine = chem.dopamine

    if dopamine >= 90 then
        return "euphoria", {
            moveSpeed = 1.25,
            attackSpeed = 1.20,
            procChance = 0.10,
            damageTaken = 1.10
        }
    elseif dopamine >= 75 then
        return "rush", {
            moveSpeed = 1.15,
            attackSpeed = 1.10,
            procChance = 0,
            damageTaken = 1.0
        }
    end

    return "normal", nil
end

-- This passive would be applied via aura updates in actual implementation

--[[
================================================================================
    MANIA COMMAND HANDLER
================================================================================
--]]

local function OnManiaCommand(event, player, command)
    local cmd = command:lower()

    if cmd == "fairy mania" or cmd == "fairy dps" then
        FairyChemistry.SetSpec(player:GetGUID(), "mania")
        player:SendBroadcastMessage("|cFFFFD700[Consciousness Warden]|r Specialization set to: |cFFFFFFFFMania (DPS)|r")
        player:SendBroadcastMessage("|cFFFFD700[Mania]|r Primary: Dopamine | Philosophy: Ride the wave of excitement")
        return false
    end

    if cmd == "fairy momentum" then
        local stacks = GetDopamineMomentum(player:GetGUID())
        local multiplier = GetMomentumMultiplier(player:GetGUID())
        player:SendBroadcastMessage(string.format(
            "|cFFFFD700[Dopamine Momentum]|r Stacks: %d/5 | Damage: +%.0f%%",
            stacks, (multiplier - 1) * 100))
        return false
    end

    if cmd == "fairy rush" then
        local state, modifiers = GetRushState(player:GetGUID())
        if state == "euphoria" then
            player:SendBroadcastMessage("|cFFFFD700[The Rush]|r |cFFFF0000PURE EUPHORIA!|r")
            player:SendBroadcastMessage(string.format(
                "  Move: +%.0f%% | Attack: +%.0f%% | Neural Proc: %.0f%% | Damage taken: +%.0f%%",
                (modifiers.moveSpeed - 1) * 100,
                (modifiers.attackSpeed - 1) * 100,
                modifiers.procChance * 100,
                (modifiers.damageTaken - 1) * 100))
        elseif state == "rush" then
            player:SendBroadcastMessage("|cFFFFD700[The Rush]|r Active!")
            player:SendBroadcastMessage(string.format(
                "  Move: +%.0f%% | Attack: +%.0f%%",
                (modifiers.moveSpeed - 1) * 100,
                (modifiers.attackSpeed - 1) * 100))
        else
            player:SendBroadcastMessage("|cFFFFD700[The Rush]|r Inactive (need 75+ Dopamine)")
        end
        return false
    end

    return true
end

RegisterPlayerEvent(42, OnManiaCommand)

--[[
================================================================================
    MANIA DAMAGE TAKEN HOOK (for Euphoria vulnerability)
================================================================================
--]]

local function OnManiaDamageTaken(event, player, attacker, damage)
    local guid = player:GetGUID()
    local state, modifiers = GetRushState(guid)

    if state == "euphoria" and modifiers then
        -- Take 10% more damage while in euphoria
        local extraDamage = math.floor(damage * 0.10)
        -- Note: In actual implementation, this would modify the damage
        -- before application. Here we're just noting the mechanic.
    end
end

RegisterPlayerEvent(36, OnManiaDamageTaken)

print("[FairyAbilities] Mania spec loaded: Euphoric Surge, Anxiety Cascade, Dopamine Momentum passive, The Rush passive")
