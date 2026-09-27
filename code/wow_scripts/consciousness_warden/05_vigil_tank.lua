--[[
================================================================================
    CONSCIOUSNESS WARDEN - VIGIL SPECIALIZATION (TANK)
    WoW 3.3.5a Eluna Lua

    The Vigil spec focuses on survival and protection. Primary chemical: Cortisol
    Secondary synergy: Oxytocin (protecting allies strengthens bonds)

    Spec Abilities:
    13. Nightmare Visage - AoE taunt with fear-based damage
    14. Bond of Vigil - Redirect damage from bonded ally to yourself

    Philosophy: Transform fear into strength, the vigilant protector

    Author: Akashic Foundation
    Version: 1.0.0
================================================================================
--]]

-- Vigil-specific state tracking
local VigilState = {
    nightmareVisage = {},     -- Players with Nightmare Visage active
    bondOfVigil = {},         -- Active damage redirections
    vigilantStacks = {}       -- Track Vigilant passive stacks
}

--[[
================================================================================
    VIGIL PASSIVE: VIGILANT STANCE
    Taking damage while above 50 Cortisol grants a stack of Vigilant (max 10).
    Each stack:
    - Reduces damage taken by 1%
    - Increases threat generation by 5%

    Stacks decay by 1 every 5 seconds out of combat.
    At 10 stacks, gain "Unbreakable Vigil" - immune to the next CC effect.
================================================================================
--]]

local function GetVigilantStacks(playerGUID)
    local data = VigilState.vigilantStacks[playerGUID]
    if not data then
        VigilState.vigilantStacks[playerGUID] = {
            stacks = 0,
            lastGain = 0,
            unbreakableReady = false
        }
        return 0
    end
    return data.stacks
end

local function AddVigilantStack(playerGUID)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    if chem.spec ~= "vigil" then return 0 end
    if chem.cortisol < 50 then return GetVigilantStacks(playerGUID) end

    local data = VigilState.vigilantStacks[playerGUID]
    if not data then
        data = { stacks = 0, lastGain = 0, unbreakableReady = false }
        VigilState.vigilantStacks[playerGUID] = data
    end

    local newStacks = math.min(10, data.stacks + 1)
    local wasAtMax = data.stacks >= 10

    data.stacks = newStacks
    data.lastGain = GetGameTime()

    -- Check for Unbreakable Vigil
    if newStacks >= 10 and not wasAtMax then
        data.unbreakableReady = true
        local player = GetPlayerByGUID(playerGUID)
        if player and player:IsInWorld() then
            FairyAbilities.SendAbilityMessage(player, "Vigilant Stance", "cortisol",
                "|cFFFFD700UNBREAKABLE VIGIL READY!|r Next CC will be blocked")
        end
    end

    return newStacks
end

local function GetVigilantModifiers(playerGUID)
    local stacks = GetVigilantStacks(playerGUID)
    return {
        damageReduction = stacks * 0.01,      -- 1% per stack
        threatMultiplier = 1 + (stacks * 0.05) -- 5% per stack
    }
end

local function ConsumeUnbreakable(playerGUID)
    local data = VigilState.vigilantStacks[playerGUID]
    if data and data.unbreakableReady then
        data.unbreakableReady = false
        data.stacks = 5  -- Reset to 5 stacks after use
        return true
    end
    return false
end

-- Decay vigilant stacks out of combat
local function ProcessVigilantDecay()
    local now = GetGameTime()

    for guid, data in pairs(VigilState.vigilantStacks) do
        local chem = FairyChemistry.GetOrCreate(guid)
        if not chem.inCombat and data.stacks > 0 then
            -- Decay every 5 seconds out of combat
            if now - data.lastGain >= 5 then
                data.stacks = math.max(0, data.stacks - 1)
                data.lastGain = now

                if data.stacks == 0 then
                    data.unbreakableReady = false
                end
            end
        end
    end
end

CreateLuaEvent(ProcessVigilantDecay, 1000, 0)

--[[
================================================================================
    ABILITY 13: NIGHTMARE VISAGE
    Unleash your deepest fears as a weapon. All enemies within 10 yards:
    - Are taunted for 6 seconds (forced to attack you)
    - Take Shadow damage
    - Have their movement speed reduced by 30% for 3 seconds

    At HIGH Cortisol (75+): Taunt duration extended to 8 seconds
    At CRITICAL Cortisol (90+): Also fears enemies for 2 seconds before taunt

    Generates Cortisol. The more enemies taunted, the more Cortisol gained.

    Instant cast, 15 second cooldown
================================================================================
--]]

FairyAbilities.RegisterAbility({
    name = "Nightmare Visage",
    spellId = FairyAbilities.SPELL_IDS.NIGHTMARE_VISAGE,
    cooldown = 15,
    primaryChemical = "cortisol",
    specs = { "vigil" },
    chemistryCost = {},
    chemistryGenerated = {},  -- Dynamic based on enemies hit

    handler = function(player, target)
        local guid = player:GetGUID()

        -- Get all enemies in range
        local enemies = FairyAbilities.GetNearbyEnemies(player, 10)
        local enemyCount = #enemies

        if enemyCount == 0 then
            FairyAbilities.SendAbilityMessage(player, "Nightmare Visage", "cortisol",
                "No enemies in range")
            return false
        end

        -- Get cortisol level for enhanced effects
        local cortisol = FairyChemistry.GetChemical(guid, "cortisol")
        local level, _ = FairyChemistry.GetChemicalLevel(guid, "cortisol")

        -- Determine taunt duration and special effects
        local tauntDuration = 6
        local shouldFear = false

        if level == "CRITICAL" then
            tauntDuration = 8
            shouldFear = true  -- Fear before taunt
        elseif level == "HIGH" then
            tauntDuration = 8
        end

        -- Calculate damage
        local baseDamage = player:GetLevel() * 12 + 80
        local damage = FairyAbilities.CalculateDamage(player, baseDamage, "cortisol")

        -- Apply Vigilant modifiers
        local vigilMods = GetVigilantModifiers(guid)
        local threatMultiplier = vigilMods.threatMultiplier

        -- Process each enemy
        local damageDone = 0
        for _, enemy in ipairs(enemies) do
            -- Deal damage
            enemy:DealDamage(player, damage, false)
            damageDone = damageDone + damage

            -- Apply taunt (force attack)
            -- In actual implementation, this would set threat and apply taunt aura
            enemy:AddThreat(player, 1000 * threatMultiplier)

            -- Apply slow (30% for 3 seconds)
            -- Would apply actual slow aura in implementation

            -- Fear effect if critical
            if shouldFear then
                -- Would apply 2 second fear before taunt activates
            end
        end

        -- Track damage
        local chem = FairyChemistry.GetOrCreate(guid)
        chem.totalDamageDealt = chem.totalDamageDealt + damageDone

        -- Generate cortisol based on enemies hit
        local cortisolGain = math.min(enemyCount * 5, 25)
        FairyChemistry.ModifyChemical(guid, "cortisol", cortisolGain)

        -- Gain vigilant stacks from the stress
        AddVigilantStack(guid)

        -- Also generate some oxytocin (protecting others through threat)
        if enemyCount >= 3 then
            FairyChemistry.ModifyChemical(guid, "oxytocin", 5)
        end

        -- Visual feedback
        FairyAbilities.PlayVisualEffect(player, "fear_aura")

        local msg = string.format("Taunted |cFFFFFFFF%d enemies|r for %ds! |cFFFF0000%d damage|r (+%d Cortisol)",
            enemyCount, tauntDuration, damageDone, cortisolGain)

        if shouldFear then
            msg = msg .. " |cFF8B0000[FEARED FIRST]|r"
        end

        FairyAbilities.SendAbilityMessage(player, "Nightmare Visage", "cortisol", msg)

        return true
    end
})

--[[
================================================================================
    ABILITY 14: BOND OF VIGIL
    Embrace your bonded ally, redirecting 50% of damage they take to yourself.
    Lasts 10 seconds or until you fall below 20% health.

    While active:
    - You take the redirected damage (reduced by your armor/resilience)
    - Your bonded ally takes only 50% of incoming damage
    - Both you and your ally generate Oxytocin from the bond
    - You generate Cortisol from the transferred damage (stress response)

    At HIGH Cortisol: Redirect 60% of damage
    At CRITICAL Cortisol: Redirect 70% of damage, and heal ally for 10% of redirected

    Requires an active Empathic Mirror bond.
    Instant cast, 30 second cooldown
================================================================================
--]]

FairyAbilities.RegisterAbility({
    name = "Bond of Vigil",
    spellId = FairyAbilities.SPELL_IDS.BOND_OF_VIGIL,
    cooldown = 30,
    primaryChemical = "cortisol",
    specs = { "vigil" },
    chemistryCost = { cortisol = 15, oxytocin = 10 },
    chemistryGenerated = { oxytocin = 20 },

    canUse = function(player)
        local guid = player:GetGUID()
        local bondedAlly = FairyChemistry.GetBondedAlly(guid)

        if not bondedAlly then
            return false, "No bonded ally (use Empathic Mirror first)"
        end

        -- Check if already active
        if VigilState.bondOfVigil[guid] then
            return false, "Bond of Vigil already active"
        end

        return true
    end,

    handler = function(player, target)
        local guid = player:GetGUID()
        local bondedAllyGUID = FairyChemistry.GetBondedAlly(guid)

        if not bondedAllyGUID then
            FairyAbilities.SendAbilityMessage(player, "Bond of Vigil", "cortisol",
                "No bonded ally!")
            return false
        end

        local ally = GetPlayerByGUID(bondedAllyGUID)
        if not ally or not ally:IsInWorld() or ally:IsDead() then
            FairyAbilities.SendAbilityMessage(player, "Bond of Vigil", "cortisol",
                "Bonded ally not available")
            return false
        end

        -- Determine redirect percentage based on cortisol
        local cortisol = FairyChemistry.GetChemical(guid, "cortisol")
        local level, _ = FairyChemistry.GetChemicalLevel(guid, "cortisol")

        local redirectPercent = 0.50
        local healOnRedirect = false

        if level == "CRITICAL" then
            redirectPercent = 0.70
            healOnRedirect = true
        elseif level == "HIGH" then
            redirectPercent = 0.60
        end

        -- Activate Bond of Vigil
        VigilState.bondOfVigil[guid] = {
            allyGUID = bondedAllyGUID,
            expires = GetGameTime() + 10,
            redirectPercent = redirectPercent,
            healOnRedirect = healOnRedirect,
            totalRedirected = 0,
            totalHealed = 0
        }

        -- Mark ally as protected
        FairyChemistry.AddEffect(bondedAllyGUID, "BOND_OF_VIGIL_PROTECTED", 10, {
            protector = guid,
            redirectPercent = redirectPercent
        })

        -- Mark self as protecting
        FairyChemistry.AddEffect(guid, "BOND_OF_VIGIL_ACTIVE", 10, {
            protecting = bondedAllyGUID
        })

        -- Strengthen the empathic bond significantly
        FairyChemistry.StrengthenBond(guid, 0.3)

        -- Visual feedback
        FairyAbilities.PlayVisualEffect(player, "bond_form")

        local allyName = ally:GetName()
        local msg = string.format("Now protecting |cFFFFFFFF%s|r! Redirecting |cFFFFD700%.0f%%|r of their damage",
            allyName, redirectPercent * 100)

        if healOnRedirect then
            msg = msg .. " |cFF00FF00(+10% heal)|r"
        end

        FairyAbilities.SendAbilityMessage(player, "Bond of Vigil", "oxytocin", msg)

        -- Notify ally
        ally:SendBroadcastMessage(string.format(
            "|cFFFF69B4[Bond of Vigil]|r %s is protecting you! (%.0f%% damage redirected)",
            player:GetName(), redirectPercent * 100))

        return true
    end
})

-- Process Bond of Vigil damage redirection
local function ProcessBondOfVigilDamage(event, player, attacker, damage)
    local guid = player:GetGUID()

    -- Check if this player is protected
    local hasBondProtection, bondData = FairyChemistry.HasEffect(guid, "BOND_OF_VIGIL_PROTECTED")

    if hasBondProtection and bondData then
        local protectorGUID = bondData.protector
        local vigilData = VigilState.bondOfVigil[protectorGUID]

        if vigilData and GetGameTime() < vigilData.expires then
            local protector = GetPlayerByGUID(protectorGUID)

            if protector and protector:IsInWorld() and not protector:IsDead() then
                -- Calculate redirected damage
                local redirectedDamage = math.floor(damage * vigilData.redirectPercent)
                local remainingDamage = damage - redirectedDamage

                -- Check if protector would fall below 20% health
                local protectorHealth = protector:GetHealth()
                local protectorMaxHealth = protector:GetMaxHealth()
                local healthAfterRedirect = protectorHealth - redirectedDamage

                if healthAfterRedirect < protectorMaxHealth * 0.20 then
                    -- End Bond of Vigil early
                    VigilState.bondOfVigil[protectorGUID] = nil
                    FairyChemistry.RemoveEffect(protectorGUID, "BOND_OF_VIGIL_ACTIVE")
                    FairyChemistry.RemoveEffect(guid, "BOND_OF_VIGIL_PROTECTED")

                    FairyAbilities.SendAbilityMessage(protector, "Bond of Vigil", "cortisol",
                        "|cFFFF0000Bond broken! Health too low to continue protection.|r")
                    player:SendBroadcastMessage("|cFFFF0000[Bond of Vigil]|r Protection ended - protector critical!")

                    return  -- Take full damage this time
                end

                -- Apply damage to protector
                protector:SetHealth(healthAfterRedirect)
                vigilData.totalRedirected = vigilData.totalRedirected + redirectedDamage

                -- Heal ally if at critical cortisol
                if vigilData.healOnRedirect then
                    local healAmount = math.floor(redirectedDamage * 0.10)
                    local playerMaxHealth = player:GetMaxHealth()
                    player:SetHealth(math.min(playerMaxHealth, player:GetHealth() + healAmount))
                    vigilData.totalHealed = vigilData.totalHealed + healAmount
                end

                -- Generate cortisol from stress of taking damage for ally
                FairyChemistry.ModifyChemical(protectorGUID, "cortisol", 3)
                AddVigilantStack(protectorGUID)

                -- Generate oxytocin for both from the protective bond
                FairyChemistry.ModifyChemical(protectorGUID, "oxytocin", 1)
                FairyChemistry.ModifyChemical(guid, "oxytocin", 1)

                -- Modify the damage the protected player takes
                -- Note: In actual implementation, this would return the modified damage
                -- For now, we heal the difference back
                player:SetHealth(player:GetHealth() + redirectedDamage)
            end
        end
    end
end

RegisterPlayerEvent(36, ProcessBondOfVigilDamage)

-- Cleanup expired Bond of Vigil
local function CleanupBondOfVigil()
    local now = GetGameTime()

    for guid, data in pairs(VigilState.bondOfVigil) do
        if now >= data.expires then
            local player = GetPlayerByGUID(guid)
            local ally = GetPlayerByGUID(data.allyGUID)

            -- Report statistics
            if player and player:IsInWorld() then
                local msg = string.format(
                    "Vigil ended. Redirected: |cFFFFFFFF%d|r damage",
                    data.totalRedirected)
                if data.totalHealed > 0 then
                    msg = msg .. string.format(", Healed ally: |cFF00FF00%d|r", data.totalHealed)
                end
                FairyAbilities.SendAbilityMessage(player, "Bond of Vigil", "oxytocin", msg)
            end

            if ally and ally:IsInWorld() then
                ally:SendBroadcastMessage("|cFFFF69B4[Bond of Vigil]|r Protection ended.")
            end

            -- Cleanup
            FairyChemistry.RemoveEffect(guid, "BOND_OF_VIGIL_ACTIVE")
            FairyChemistry.RemoveEffect(data.allyGUID, "BOND_OF_VIGIL_PROTECTED")
            VigilState.bondOfVigil[guid] = nil
        end
    end
end

CreateLuaEvent(CleanupBondOfVigil, 1000, 0)

--[[
================================================================================
    VIGIL PASSIVE: STRESS SHIELD
    When you drop below 35% health, immediately gain:
    - 15 Cortisol
    - 3 stacks of Vigilant
    - 30% damage reduction for 5 seconds

    Can only trigger once every 45 seconds.
================================================================================
--]]

local StressShieldCooldowns = {}

local function OnLowHealth(event, player, attacker, damage)
    local guid = player:GetGUID()
    local chem = FairyChemistry.GetOrCreate(guid)

    if chem.spec ~= "vigil" then return end

    local currentHealth = player:GetHealth()
    local maxHealth = player:GetMaxHealth()
    local healthPercent = currentHealth / maxHealth

    -- Check if dropping below 35%
    if healthPercent <= 0.35 then
        local cdEnd = StressShieldCooldowns[guid] or 0
        if GetGameTime() >= cdEnd then
            -- Trigger Stress Shield!
            StressShieldCooldowns[guid] = GetGameTime() + 45

            -- Gain cortisol and vigilant stacks
            FairyChemistry.ModifyChemical(guid, "cortisol", 15)
            for i = 1, 3 do
                AddVigilantStack(guid)
            end

            -- Apply damage reduction (in actual implementation, apply aura)
            FairyChemistry.AddEffect(guid, "STRESS_SHIELD", 5, { damageReduction = 0.30 })

            -- Visual feedback
            FairyAbilities.PlayVisualEffect(player, "fear_aura")
            FairyAbilities.SendAbilityMessage(player, "Stress Shield", "cortisol",
                "|cFFFF4500SURVIVAL INSTINCT!|r +15 Cortisol, +3 Vigilant, 30% DR for 5s")
        end
    end
end

RegisterPlayerEvent(36, OnLowHealth)

--[[
================================================================================
    VIGIL COMMAND HANDLER
================================================================================
--]]

local function OnVigilCommand(event, player, command)
    local cmd = command:lower()

    if cmd == "fairy vigil" or cmd == "fairy tank" then
        FairyChemistry.SetSpec(player:GetGUID(), "vigil")
        player:SendBroadcastMessage("|cFFFF4500[Consciousness Warden]|r Specialization set to: |cFFFFFFFFVigil (Tank)|r")
        player:SendBroadcastMessage("|cFFFF4500[Vigil]|r Primary: Cortisol | Philosophy: Transform fear into strength")
        return false
    end

    if cmd == "fairy vigilant" then
        local stacks = GetVigilantStacks(player:GetGUID())
        local mods = GetVigilantModifiers(player:GetGUID())
        local data = VigilState.vigilantStacks[player:GetGUID()]
        local unbreakable = data and data.unbreakableReady

        player:SendBroadcastMessage(string.format(
            "|cFFFF4500[Vigilant Stance]|r Stacks: %d/10 | DR: %.0f%% | Threat: +%.0f%%",
            stacks, mods.damageReduction * 100, (mods.threatMultiplier - 1) * 100))

        if unbreakable then
            player:SendBroadcastMessage("|cFFFFD700[Unbreakable Vigil]|r |cFF00FF00READY|r - Next CC will be blocked!")
        end
        return false
    end

    if cmd == "fairy protection" then
        local guid = player:GetGUID()
        local vigilData = VigilState.bondOfVigil[guid]

        if vigilData then
            local remaining = vigilData.expires - GetGameTime()
            local ally = GetPlayerByGUID(vigilData.allyGUID)
            local allyName = ally and ally:GetName() or "Unknown"

            player:SendBroadcastMessage(string.format(
                "|cFFFF69B4[Bond of Vigil]|r Protecting: %s | Time: %.1fs | Redirected: %d",
                allyName, remaining, vigilData.totalRedirected))
        else
            player:SendBroadcastMessage("|cFFFF69B4[Bond of Vigil]|r Not active")
        end
        return false
    end

    return true
end

RegisterPlayerEvent(42, OnVigilCommand)

--[[
================================================================================
    VIGIL CC IMMUNITY (Unbreakable Vigil)
================================================================================
--]]

local function OnVigilCCApplied(event, caster, target, spellId)
    local guid = target:GetGUID()

    if ConsumeUnbreakable(guid) then
        -- Block the CC
        FairyAbilities.SendAbilityMessage(target, "Unbreakable Vigil", "cortisol",
            "|cFFFFD700CC BLOCKED!|r Vigilance cannot be broken!")
        return false
    end

    return true
end

print("[FairyAbilities] Vigil spec loaded: Nightmare Visage, Bond of Vigil, Vigilant Stance passive, Stress Shield passive")
