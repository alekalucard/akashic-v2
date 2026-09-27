--[[
================================================================================
    CONSCIOUSNESS WARDEN - REVERIE SPECIALIZATION (HEALER)
    WoW 3.3.5a Eluna Lua

    The Reverie spec focuses on healing and calm. Primary chemical: Serotonin
    Secondary synergy: Oxytocin (group healing bonuses)

    Spec Abilities:
    7. Wash of Serenity - Main heal with HoT component
    8. Collective Unconscious - Group HoT that strengthens bonds
    9. Memory of Wholeness - Amplify next heal, consume serotonin
    10. Lucid Intervention - Emergency heal + CC immunity

    Philosophy: Healing through understanding, calm through connection

    Author: Akashic Foundation
    Version: 1.0.0
================================================================================
--]]

-- Reverie-specific state tracking
local ReverieState = {
    memoryOfWholeness = {},  -- Players with Memory of Wholeness active
    collectiveUnconscious = {}  -- Active group HoTs
}

--[[
================================================================================
    ABILITY 7: WASH OF SERENITY
    The main healing spell for Reverie. Immediately heals the target,
    then applies a Heal over Time effect that strengthens as your
    Serotonin increases.

    Base heal: Moderate instant + 12 second HoT
    Serotonin scaling: Both components scale with serotonin level
    Generates Serotonin on initial heal

    1.5 second cast, 4 second cooldown
================================================================================
--]]

FairyAbilities.RegisterAbility({
    name = "Wash of Serenity",
    spellId = FairyAbilities.SPELL_IDS.WASH_OF_SERENITY,
    cooldown = 4,
    primaryChemical = "serotonin",
    specs = { "reverie" },
    chemistryCost = {},
    chemistryGenerated = { serotonin = 8 },

    handler = function(player, target)
        local guid = player:GetGUID()

        -- Get friendly target (self if no target)
        local ally, err = FairyAbilities.GetValidTarget(player, "friendly")
        if not ally then
            FairyAbilities.SendAbilityMessage(player, "Wash of Serenity", "cortisol", err or "No valid target")
            return false
        end

        -- Calculate healing
        local baseInstant = player:GetLevel() * 15 + 100
        local baseHoT = player:GetLevel() * 5 + 30

        -- Check for Memory of Wholeness amplification
        local amplified = false
        if ReverieState.memoryOfWholeness[guid] then
            local memData = ReverieState.memoryOfWholeness[guid]
            if GetGameTime() < memData.expires then
                baseInstant = baseInstant * (1 + memData.amplifier)
                baseHoT = baseHoT * (1 + memData.amplifier)
                amplified = true
                ReverieState.memoryOfWholeness[guid] = nil  -- Consume the buff
            end
        end

        local instantHeal = FairyAbilities.CalculateHealing(player, baseInstant, "serotonin")
        local hotTick = FairyAbilities.CalculateHealing(player, baseHoT, "serotonin")

        -- Apply instant heal
        local currentHealth = ally:GetHealth()
        local maxHealth = ally:GetMaxHealth()
        local actualHeal = math.min(maxHealth - currentHealth, instantHeal)
        ally:SetHealth(currentHealth + actualHeal)

        -- Apply HoT
        FairyAbilities.ApplyHoT(player, ally, {
            name = "Wash of Serenity",
            tickHealing = hotTick,
            tickInterval = 3000,
            duration = 12,
            chemical = "serotonin"
        })

        -- Strengthen bond if target is bonded ally
        local bondedAlly = FairyChemistry.GetBondedAlly(guid)
        if bondedAlly == ally:GetGUID() then
            FairyChemistry.StrengthenBond(guid, 0.1)
            FairyChemistry.ModifyChemical(guid, "oxytocin", 3)
        end

        -- Track healing done
        local chem = FairyChemistry.GetOrCreate(guid)
        chem.totalHealingDone = chem.totalHealingDone + actualHeal

        -- Visual feedback
        FairyAbilities.PlayVisualEffect(player, "heal_burst")

        local targetName = ally:GetName()
        if ally:GetGUID() == guid then
            targetName = "yourself"
        end

        local msg = string.format("Healed |cFFFFFFFF%s|r for |cFF00FF00%d|r (+%d/tick HoT)",
            targetName, actualHeal, hotTick)
        if amplified then
            msg = msg .. " |cFFFFD700[AMPLIFIED]|r"
        end

        FairyAbilities.SendAbilityMessage(player, "Wash of Serenity", "serotonin", msg)

        -- Notify target
        if ally:GetGUID() ~= guid then
            ally:SendBroadcastMessage(string.format(
                "|cFF87CEEB[Wash of Serenity]|r %s's calming presence heals you for %d",
                player:GetName(), actualHeal))
        end

        return true
    end
})

--[[
================================================================================
    ABILITY 8: COLLECTIVE UNCONSCIOUS
    Connect to the collective unconscious, healing all allies within
    30 yards over 15 seconds. Each ally healed increases your Oxytocin.

    The group is stronger together. Heals scale with number of allies affected.
    Each tick generates Oxytocin based on allies healed.
    Bonded allies receive 50% additional healing.

    3 second cast, 25 second cooldown
================================================================================
--]]

FairyAbilities.RegisterAbility({
    name = "Collective Unconscious",
    spellId = FairyAbilities.SPELL_IDS.COLLECTIVE_UNCONSCIOUS,
    cooldown = 25,
    primaryChemical = "oxytocin",
    specs = { "reverie" },
    chemistryCost = { serotonin = 15 },
    chemistryGenerated = {},  -- Dynamic oxytocin generation

    handler = function(player, target)
        local guid = player:GetGUID()

        -- Get all allies in range
        local allies = FairyAbilities.GetNearbyAllies(player, 30)
        local allyCount = #allies

        if allyCount == 0 then
            FairyAbilities.SendAbilityMessage(player, "Collective Unconscious", "cortisol",
                "No allies in range")
            return false
        end

        -- Calculate base healing (scales with group size, diminishing returns)
        local baseHeal = player:GetLevel() * 8 + 40
        local groupMultiplier = 1 + (math.min(allyCount, 5) * 0.1)  -- Up to 50% bonus
        local tickHealing = FairyAbilities.CalculateHealing(player, baseHeal * groupMultiplier, "serotonin")

        -- Get bonded ally for bonus healing
        local bondedAllyGUID = FairyChemistry.GetBondedAlly(guid)

        -- Apply HoT to all allies
        local healedCount = 0
        for _, ally in ipairs(allies) do
            local thisTickHealing = tickHealing
            local isBonded = false

            -- Bonded ally gets 50% more
            if ally:GetGUID() == bondedAllyGUID then
                thisTickHealing = math.floor(tickHealing * 1.5)
                isBonded = true
            end

            FairyAbilities.ApplyHoT(player, ally, {
                name = "Collective Unconscious",
                tickHealing = thisTickHealing,
                tickInterval = 3000,
                duration = 15,
                chemical = "oxytocin"
            })

            healedCount = healedCount + 1

            -- Notify ally
            if ally:GetGUID() ~= guid then
                local msg = string.format("|cFFFF69B4[Collective Unconscious]|r Connected to %s's healing",
                    player:GetName())
                if isBonded then
                    msg = msg .. " |cFFFFD700(Empathic Bond)|r"
                end
                ally:SendBroadcastMessage(msg)
            end
        end

        -- Generate oxytocin based on allies healed
        local oxytocinGain = math.min(healedCount * 3, 15)
        FairyChemistry.ModifyChemical(guid, "oxytocin", oxytocinGain)

        -- Store for tracking
        ReverieState.collectiveUnconscious[guid] = {
            expires = GetGameTime() + 15,
            allies = allies,
            baseHealing = tickHealing
        }

        -- Visual feedback
        FairyAbilities.PlayVisualEffect(player, "heal_burst")
        FairyAbilities.SendAbilityMessage(player, "Collective Unconscious", "oxytocin",
            string.format("Connected |cFFFFFFFF%d allies|r to the collective. +%d Oxytocin",
                healedCount, oxytocinGain))

        return true
    end
})

--[[
================================================================================
    ABILITY 9: MEMORY OF WHOLENESS
    Remember a time when all was well. Your next healing spell within
    10 seconds is amplified based on your current Serotonin level.

    Serotonin 0-25: +20% healing
    Serotonin 26-50: +40% healing
    Serotonin 51-75: +60% healing
    Serotonin 76-100: +80% healing

    Consumes 20 Serotonin when the amplified heal lands.
    Instant cast, 20 second cooldown
================================================================================
--]]

FairyAbilities.RegisterAbility({
    name = "Memory of Wholeness",
    spellId = FairyAbilities.SPELL_IDS.MEMORY_OF_WHOLENESS,
    cooldown = 20,
    primaryChemical = "serotonin",
    specs = { "reverie" },
    chemistryCost = { serotonin = 20 },
    chemistryGenerated = {},

    handler = function(player, target)
        local guid = player:GetGUID()

        -- Calculate amplification based on current serotonin
        local serotonin = FairyChemistry.GetChemical(guid, "serotonin")
        local amplifier

        if serotonin >= 76 then
            amplifier = 0.80
        elseif serotonin >= 51 then
            amplifier = 0.60
        elseif serotonin >= 26 then
            amplifier = 0.40
        else
            amplifier = 0.20
        end

        -- Store the amplification buff
        ReverieState.memoryOfWholeness[guid] = {
            expires = GetGameTime() + 10,
            amplifier = amplifier,
            serotonin = serotonin
        }

        FairyChemistry.AddEffect(guid, "MEMORY_OF_WHOLENESS", 10, { amplifier = amplifier })

        -- Visual feedback
        local amplifierPercent = math.floor(amplifier * 100)
        FairyAbilities.SendAbilityMessage(player, "Memory of Wholeness", "serotonin",
            string.format("Next heal amplified by |cFFFFD700%d%%|r (Serotonin: %d)",
                amplifierPercent, serotonin))

        player:SendBroadcastMessage("|cFF87CEEB* You recall a time of perfect peace... *|r")

        return true
    end
})

--[[
================================================================================
    ABILITY 10: LUCID INTERVENTION
    Emergency healing ability. Instantly heals the target for a large amount
    and grants them immunity to crowd control effects for 4 seconds.

    This is the "oh no they're about to die" button. High healing, CC immunity,
    but expensive in terms of chemistry.

    When used on your bonded ally: Heal amount +50%, you also gain CC immunity

    Instant cast, 45 second cooldown
================================================================================
--]]

local LucidInterventionImmunity = {}

FairyAbilities.RegisterAbility({
    name = "Lucid Intervention",
    spellId = FairyAbilities.SPELL_IDS.LUCID_INTERVENTION,
    cooldown = 45,
    primaryChemical = "serotonin",
    specs = { "reverie" },
    chemistryCost = { serotonin = 30, oxytocin = 10 },
    chemistryGenerated = { cortisol = 15 },  -- Stressful to use!

    handler = function(player, target)
        local guid = player:GetGUID()

        -- Get friendly target
        local ally, err = FairyAbilities.GetValidTarget(player, "friendly")
        if not ally then
            FairyAbilities.SendAbilityMessage(player, "Lucid Intervention", "cortisol", err or "No valid target")
            return false
        end

        -- Check if target is critically wounded (below 35% health)
        local currentHealth = ally:GetHealth()
        local maxHealth = ally:GetMaxHealth()
        local healthPercent = (currentHealth / maxHealth) * 100

        local emergencyBonus = 1.0
        if healthPercent < 35 then
            emergencyBonus = 1.3  -- 30% bonus for critical saves
        end

        -- Calculate healing
        local baseHeal = player:GetLevel() * 35 + 300
        local healing = FairyAbilities.CalculateHealing(player, baseHeal, "serotonin")
        healing = math.floor(healing * emergencyBonus)

        -- Check for bonded ally bonus
        local bondedAllyGUID = FairyChemistry.GetBondedAlly(guid)
        local isBonded = (bondedAllyGUID == ally:GetGUID())

        if isBonded then
            healing = math.floor(healing * 1.5)
        end

        -- Apply heal
        local actualHeal = math.min(maxHealth - currentHealth, healing)
        ally:SetHealth(currentHealth + actualHeal)

        -- Grant CC immunity
        LucidInterventionImmunity[ally:GetGUID()] = {
            expires = GetGameTime() + 4,
            grantedBy = guid
        }
        FairyChemistry.AddEffect(ally:GetGUID(), "LUCID_INTERVENTION_IMMUNITY", 4, {})

        -- If bonded, caster also gets immunity
        if isBonded then
            LucidInterventionImmunity[guid] = {
                expires = GetGameTime() + 4,
                grantedBy = guid
            }
            FairyChemistry.AddEffect(guid, "LUCID_INTERVENTION_IMMUNITY", 4, {})
        end

        -- Apply a dispel on the target (remove CC effects)
        -- In actual implementation, this would iterate through debuffs
        -- For now, we use a placeholder spell
        -- player:CastSpell(ally, 4987, true)  -- Cleanse placeholder

        -- Track healing
        local chem = FairyChemistry.GetOrCreate(guid)
        chem.totalHealingDone = chem.totalHealingDone + actualHeal

        -- Visual feedback
        FairyAbilities.PlayVisualEffect(player, "heal_burst")

        local targetName = ally:GetName()
        if ally:GetGUID() == guid then
            targetName = "yourself"
        end

        local msg = string.format("|cFF00FF00EMERGENCY HEAL|r on %s for |cFFFFFFFF%d|r + CC Immunity (4s)",
            targetName, actualHeal)

        if isBonded then
            msg = msg .. " |cFFFF69B4[BOND ACTIVE]|r"
        end

        if healthPercent < 35 then
            msg = msg .. " |cFFFF0000(Critical save!)|r"
        end

        FairyAbilities.SendAbilityMessage(player, "Lucid Intervention", "serotonin", msg)

        -- Notify target
        if ally:GetGUID() ~= guid then
            ally:SendBroadcastMessage(string.format(
                "|cFF00FF00[Lucid Intervention]|r %s's lucid intervention saves you! CC Immune for 4s",
                player:GetName()))
        end

        return true
    end
})

-- Process CC immunity for Lucid Intervention
local function ProcessLucidInterventionImmunity()
    local now = GetGameTime()
    for guid, data in pairs(LucidInterventionImmunity) do
        if now >= data.expires then
            LucidInterventionImmunity[guid] = nil

            local player = GetPlayerByGUID(guid)
            if player and player:IsInWorld() then
                FairyAbilities.SendAbilityMessage(player, "Lucid Intervention", "serotonin",
                    "|cFF808080CC immunity faded|r")
            end
        end
    end
end

CreateLuaEvent(ProcessLucidInterventionImmunity, 500, 0)

-- Hook CC application to check immunity
local function OnCCApplied(event, caster, target, spellId)
    local guid = target:GetGUID()
    if LucidInterventionImmunity[guid] and GetGameTime() < LucidInterventionImmunity[guid].expires then
        -- Block the CC (in actual implementation, would prevent aura application)
        target:SendBroadcastMessage("|cFF00FF00[Lucid Intervention]|r CC blocked by clarity!")
        return false
    end
    return true
end

--[[
================================================================================
    REVERIE PASSIVE: SERENITY'S ECHO
    Whenever you generate Serotonin, your bonded ally receives
    a small heal equal to 5% of your maximum health.

    This makes the bonding system extra valuable for Reverie healers.
================================================================================
--]]

local function OnReverieChemistryGain(playerGUID, chemical, amount)
    if chemical ~= "serotonin" or amount <= 0 then return end

    local chem = FairyChemistry.GetOrCreate(playerGUID)
    if chem.spec ~= "reverie" then return end

    local bondedAllyGUID = FairyChemistry.GetBondedAlly(playerGUID)
    if not bondedAllyGUID then return end

    local player = GetPlayerByGUID(playerGUID)
    local ally = GetPlayerByGUID(bondedAllyGUID)

    if player and ally and ally:IsInWorld() and not ally:IsDead() then
        local maxHealth = player:GetMaxHealth()
        local echoHeal = math.floor(maxHealth * 0.05)

        local allyHealth = ally:GetHealth()
        local allyMaxHealth = ally:GetMaxHealth()
        ally:SetHealth(math.min(allyMaxHealth, allyHealth + echoHeal))

        -- Small notification (not spammy)
        if amount >= 5 then  -- Only notify for significant gains
            ally:SendBroadcastMessage(string.format(
                "|cFF87CEEB* Serenity's Echo: +%d *|r", echoHeal))
        end
    end
end

-- This would need to be hooked into the FairyChemistry.ModifyChemical function
-- For now, we note it as a passive that needs integration

--[[
================================================================================
    REVERIE COMMAND HANDLER
================================================================================
--]]

local function OnReverieCommand(event, player, command)
    local cmd = command:lower()

    if cmd == "fairy reverie" or cmd == "fairy heal" then
        FairyChemistry.SetSpec(player:GetGUID(), "reverie")
        player:SendBroadcastMessage("|cFF87CEEB[Consciousness Warden]|r Specialization set to: |cFFFFFFFFReverie (Healer)|r")
        player:SendBroadcastMessage("|cFF87CEEB[Reverie]|r Primary: Serotonin | Philosophy: Healing through understanding")
        return false
    end

    return true
end

RegisterPlayerEvent(42, OnReverieCommand)

print("[FairyAbilities] Reverie spec loaded: Wash of Serenity, Collective Unconscious, Memory of Wholeness, Lucid Intervention")
