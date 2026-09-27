--[[
================================================================================
    CONSCIOUSNESS WARDEN - ABILITY FRAMEWORK
    WoW 3.3.5a Eluna Lua

    Provides the foundation for all Consciousness Warden abilities:
    - Ability registration and execution
    - Visual feedback systems
    - Damage/healing calculations with chemistry scaling
    - Spell effect utilities

    Author: Akashic Foundation
    Version: 1.0.0
================================================================================
--]]

-- Global ability registry
FairyAbilities = FairyAbilities or {}

-- Spell IDs (using unused/custom spell slots)
-- These would need to be configured in spell.dbc or use existing spell IDs
local SPELL_IDS = {
    -- All Specs
    NEURAL_PULSE = 90001,
    EMPATHIC_MIRROR = 90002,
    INTRUSIVE_THOUGHT = 90003,
    SOOTHING_PRESENCE = 90004,
    FLIGHT_RESPONSE = 90005,
    DREAMWALK = 90006,

    -- Reverie (Healer)
    WASH_OF_SERENITY = 90007,
    COLLECTIVE_UNCONSCIOUS = 90008,
    MEMORY_OF_WHOLENESS = 90009,
    LUCID_INTERVENTION = 90010,

    -- Mania (DPS)
    EUPHORIC_SURGE = 90011,
    ANXIETY_CASCADE = 90012,

    -- Vigil (Tank)
    NIGHTMARE_VISAGE = 90013,
    BOND_OF_VIGIL = 90014
}

FairyAbilities.SPELL_IDS = SPELL_IDS

--[[
================================================================================
    CHEMISTRY-SCALED CALCULATIONS
================================================================================
--]]

-- Calculate damage based on chemistry state
function FairyAbilities.CalculateDamage(player, baseDamage, scalingChemical)
    local guid = player:GetGUID()
    local chemValue = FairyChemistry.GetChemical(guid, scalingChemical)

    -- Base scaling: 0.5x at 0 chemical, 1.0x at 50, 1.5x at 100
    local multiplier = 0.5 + (chemValue / 100)

    -- Dopamine bonus for damage
    if scalingChemical == "dopamine" then
        local level, value = FairyChemistry.GetChemicalLevel(guid, "dopamine")
        if level == "CRITICAL" then
            multiplier = multiplier * 1.25
        elseif level == "HIGH" then
            multiplier = multiplier * 1.1
        end
    end

    -- Apply player's spell power scaling
    local spellPower = player:GetUInt32Value(1205) or 0  -- PLAYER_FIELD_MOD_DAMAGE_DONE_POS
    local scaledDamage = baseDamage + (spellPower * 0.5)

    return math.floor(scaledDamage * multiplier)
end

-- Calculate healing based on chemistry state
function FairyAbilities.CalculateHealing(player, baseHealing, scalingChemical)
    local guid = player:GetGUID()
    local chemValue = FairyChemistry.GetChemical(guid, scalingChemical or "serotonin")

    -- Base scaling
    local multiplier = 0.5 + (chemValue / 100)

    -- Serotonin bonus for healing
    if scalingChemical == "serotonin" then
        local level, value = FairyChemistry.GetChemicalLevel(guid, "serotonin")
        if level == "CRITICAL" then
            multiplier = multiplier * 1.3
        elseif level == "HIGH" then
            multiplier = multiplier * 1.15
        end
    end

    -- Oxytocin provides group healing bonus
    local oxyLevel, oxyValue = FairyChemistry.GetChemicalLevel(guid, "oxytocin")
    if oxyLevel == "HIGH" or oxyLevel == "CRITICAL" then
        multiplier = multiplier * 1.1
    end

    -- Apply healing power
    local healPower = player:GetUInt32Value(1215) or 0  -- Approximate healing power field
    local scaledHealing = baseHealing + (healPower * 0.7)

    return math.floor(scaledHealing * multiplier)
end

--[[
================================================================================
    VISUAL FEEDBACK SYSTEM
================================================================================
--]]

local CHEMICAL_COLORS = {
    serotonin = "|cFF87CEEB",  -- Light blue (calm)
    dopamine = "|cFFFFD700",   -- Gold (excitement)
    cortisol = "|cFFFF4500",   -- Orange-red (stress)
    oxytocin = "|cFFFF69B4"    -- Pink (bonding)
}

function FairyAbilities.SendAbilityMessage(player, abilityName, chemical, message)
    local color = CHEMICAL_COLORS[chemical] or "|cFF9400D3"
    local prefix = string.format("%s[%s]|r", color, abilityName)
    player:SendBroadcastMessage(prefix .. " " .. message)
end

function FairyAbilities.SendChemistryChange(player, chemical, amount, abilityName)
    local color = CHEMICAL_COLORS[chemical] or "|cFFFFFFFF"
    local sign = amount >= 0 and "+" or ""
    local chemName = chemical:sub(1,1):upper() .. chemical:sub(2)

    player:SendBroadcastMessage(string.format(
        "%s%s%d %s|r from %s",
        color, sign, amount, chemName, abilityName
    ))
end

function FairyAbilities.PlayVisualEffect(player, effectType)
    -- In actual implementation, this would trigger spell visuals
    -- For now, we send descriptive messages
    local effects = {
        heal_burst = "|cFF00FF00* Waves of serenity radiate outward *|r",
        damage_pulse = "|cFFFF0000* Neural energy crackles *|r",
        bond_form = "|cFFFF69B4* Empathic threads connect *|r",
        fear_aura = "|cFF8B0000* Nightmare tendrils emerge *|r",
        calm_aura = "|cFF87CEEB* Peaceful mist surrounds you *|r",
        speed_burst = "|cFFFFD700* Adrenaline surges through you *|r",
        vanish = "|cFF9400D3* You fade into the dreamscape *|r"
    }

    local msg = effects[effectType]
    if msg then
        player:SendBroadcastMessage(msg)
    end
end

--[[
================================================================================
    ABILITY REGISTRATION SYSTEM
================================================================================
--]]

local RegisteredAbilities = {}

function FairyAbilities.RegisterAbility(config)
    local ability = {
        name = config.name,
        spellId = config.spellId,
        cooldown = config.cooldown or 0,
        primaryChemical = config.primaryChemical,
        chemistryGenerated = config.chemistryGenerated or {},
        chemistryCost = config.chemistryCost or {},
        specs = config.specs or { "reverie", "mania", "vigil" },
        handler = config.handler,
        canUse = config.canUse or function() return true end
    }

    RegisteredAbilities[config.name] = ability

    if config.spellId then
        RegisteredAbilities[config.spellId] = ability
    end

    return ability
end

function FairyAbilities.GetAbility(nameOrId)
    return RegisteredAbilities[nameOrId]
end

--[[
================================================================================
    ABILITY EXECUTION
================================================================================
--]]

function FairyAbilities.CanUseAbility(player, abilityName)
    local ability = FairyAbilities.GetAbility(abilityName)
    if not ability then
        return false, "Unknown ability"
    end

    local guid = player:GetGUID()

    -- Check cooldown
    if FairyChemistry.IsOnCooldown(guid, abilityName) then
        local remaining = FairyChemistry.GetCooldownRemaining(guid, abilityName)
        return false, string.format("On cooldown (%.1fs)", remaining)
    end

    -- Check spec restriction
    local spec = FairyChemistry.GetSpec(guid)
    local specAllowed = false
    for _, s in ipairs(ability.specs) do
        if s == spec then
            specAllowed = true
            break
        end
    end
    if not specAllowed then
        return false, "Wrong specialization"
    end

    -- Check chemistry cost
    for chemical, cost in pairs(ability.chemistryCost) do
        local current = FairyChemistry.GetChemical(guid, chemical)
        if current < cost then
            return false, string.format("Insufficient %s (%d/%d)", chemical, current, cost)
        end
    end

    -- Custom check
    local canUse, reason = ability.canUse(player)
    if not canUse then
        return false, reason or "Cannot use this ability"
    end

    return true
end

function FairyAbilities.ExecuteAbility(player, abilityName, target)
    local canUse, reason = FairyAbilities.CanUseAbility(player, abilityName)
    if not canUse then
        FairyAbilities.SendAbilityMessage(player, abilityName, "cortisol",
            "|cFFFF0000Failed:|r " .. reason)
        return false
    end

    local ability = FairyAbilities.GetAbility(abilityName)
    local guid = player:GetGUID()

    -- Consume chemistry costs
    for chemical, cost in pairs(ability.chemistryCost) do
        FairyChemistry.ModifyChemical(guid, chemical, -cost)
    end

    -- Execute the ability handler
    local success = ability.handler(player, target)

    if success then
        -- Apply cooldown
        if ability.cooldown > 0 then
            FairyChemistry.SetCooldown(guid, abilityName, ability.cooldown * 1000)
        end

        -- Generate chemistry
        for chemical, amount in pairs(ability.chemistryGenerated) do
            FairyChemistry.ModifyChemical(guid, chemical, amount)
            FairyAbilities.SendChemistryChange(player, chemical, amount, abilityName)
        end
    end

    return success
end

--[[
================================================================================
    TARGET UTILITY FUNCTIONS
================================================================================
--]]

function FairyAbilities.GetValidTarget(player, targetType)
    local target = player:GetSelection()

    if targetType == "enemy" then
        if not target then return nil, "No target" end
        if not player:IsHostileTo(target) then return nil, "Not hostile" end
        if target:IsDead() then return nil, "Target is dead" end
        return target
    elseif targetType == "friendly" then
        if not target then return player end  -- Self-target
        if player:IsHostileTo(target) then return nil, "Target is hostile" end
        if target:IsDead() then return nil, "Target is dead" end
        return target
    elseif targetType == "any" then
        return target or player
    elseif targetType == "self" then
        return player
    end

    return target
end

function FairyAbilities.GetNearbyAllies(player, range)
    local allies = {}
    local nearbyUnits = player:GetPlayersInRange(range)

    for _, unit in ipairs(nearbyUnits or {}) do
        if not player:IsHostileTo(unit) and not unit:IsDead() then
            table.insert(allies, unit)
        end
    end

    -- Always include self
    table.insert(allies, player)

    return allies
end

function FairyAbilities.GetNearbyEnemies(player, range)
    local enemies = {}
    local nearbyUnits = player:GetCreaturesInRange(range)

    for _, unit in ipairs(nearbyUnits or {}) do
        if player:IsHostileTo(unit) and not unit:IsDead() then
            table.insert(enemies, unit)
        end
    end

    return enemies
end

--[[
================================================================================
    DoT/HoT SYSTEM
================================================================================
--]]

local ActiveDoTs = {}
local ActiveHoTs = {}

function FairyAbilities.ApplyDoT(caster, target, config)
    local key = caster:GetGUID() .. "_" .. target:GetGUID() .. "_" .. config.name

    ActiveDoTs[key] = {
        caster = caster,
        casterGUID = caster:GetGUID(),
        target = target,
        targetGUID = target:GetGUID(),
        name = config.name,
        tickDamage = config.tickDamage,
        tickInterval = config.tickInterval or 3000,
        duration = config.duration,
        chemical = config.chemical or "dopamine",
        expires = GetGameTime() + config.duration,
        lastTick = GetGameTime(),
        spreadable = config.spreadable or false,
        onExpire = config.onExpire,
        onKill = config.onKill
    }

    return key
end

function FairyAbilities.ApplyHoT(caster, target, config)
    local key = caster:GetGUID() .. "_" .. target:GetGUID() .. "_" .. config.name

    ActiveHoTs[key] = {
        caster = caster,
        casterGUID = caster:GetGUID(),
        target = target,
        targetGUID = target:GetGUID(),
        name = config.name,
        tickHealing = config.tickHealing,
        tickInterval = config.tickInterval or 3000,
        duration = config.duration,
        chemical = config.chemical or "serotonin",
        expires = GetGameTime() + config.duration,
        lastTick = GetGameTime()
    }

    return key
end

function FairyAbilities.RemoveDoT(key)
    ActiveDoTs[key] = nil
end

function FairyAbilities.RemoveHoT(key)
    ActiveHoTs[key] = nil
end

-- Process DoTs and HoTs
local function ProcessPeriodicEffects()
    local now = GetGameTime()

    -- Process DoTs
    for key, dot in pairs(ActiveDoTs) do
        if now >= dot.expires then
            -- DoT expired
            if dot.onExpire then
                dot.onExpire(dot)
            end
            ActiveDoTs[key] = nil
        elseif now >= dot.lastTick + (dot.tickInterval / 1000) then
            -- Apply tick
            if dot.target and dot.target:IsInWorld() and not dot.target:IsDead() then
                local caster = dot.caster
                if caster and caster:IsInWorld() then
                    local damage = FairyAbilities.CalculateDamage(caster, dot.tickDamage, dot.chemical)
                    dot.target:DealDamage(caster, damage, false)
                    dot.lastTick = now

                    -- Check for kill
                    if dot.target:IsDead() and dot.onKill then
                        dot.onKill(dot)
                    end
                end
            else
                ActiveDoTs[key] = nil
            end
        end
    end

    -- Process HoTs
    for key, hot in pairs(ActiveHoTs) do
        if now >= hot.expires then
            ActiveHoTs[key] = nil
        elseif now >= hot.lastTick + (hot.tickInterval / 1000) then
            if hot.target and hot.target:IsInWorld() and not hot.target:IsDead() then
                local caster = hot.caster
                if caster and caster:IsInWorld() then
                    local healing = FairyAbilities.CalculateHealing(caster, hot.tickHealing, hot.chemical)
                    local currentHealth = hot.target:GetHealth()
                    local maxHealth = hot.target:GetMaxHealth()
                    hot.target:SetHealth(math.min(maxHealth, currentHealth + healing))
                    hot.lastTick = now
                end
            else
                ActiveHoTs[key] = nil
            end
        end
    end
end

-- Register periodic effect processor (runs every second)
CreateLuaEvent(ProcessPeriodicEffects, 1000, 0)

--[[
================================================================================
    COMMAND HANDLER FOR TESTING
================================================================================
--]]

local function OnCommand(event, player, command)
    local cmd = command:lower()

    if cmd == "fairy" then
        FairyChemistry.SendChemistryStatus(player)
        return false
    end

    if cmd:match("^fairy spec") then
        local spec = cmd:match("fairy spec (%w+)")
        if spec then
            if FairyChemistry.SetSpec(player:GetGUID(), spec) then
                player:SendBroadcastMessage("|cFF9400D3[Consciousness Warden]|r Spec changed to: " .. spec)
            else
                player:SendBroadcastMessage("|cFFFF0000Invalid spec. Use: reverie, mania, vigil|r")
            end
        end
        return false
    end

    if cmd == "fairy reset" then
        FairyChemistry.ResetChemistry(player:GetGUID())
        player:SendBroadcastMessage("|cFF9400D3[Consciousness Warden]|r Chemistry reset to baseline.")
        return false
    end

    return true  -- Let other handlers process
end

RegisterPlayerEvent(42, OnCommand)  -- PLAYER_EVENT_ON_COMMAND

print("[FairyAbilities] Framework loaded successfully.")
