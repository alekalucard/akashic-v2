--[[
================================================================================
    CONSCIOUSNESS WARDEN - MASTER LOADER
    WoW 3.3.5a Eluna Lua

    This file loads all Consciousness Warden components in the correct order.
    Place this in your Eluna scripts folder or use the Eluna loader system.

    Load Order:
    1. 00_fairy_chemistry_core.lua    - Chemistry resource system
    2. 01_ability_framework.lua       - Ability registration and utilities
    3. 02_shared_abilities.lua        - All-spec abilities (1-6)
    4. 03_reverie_healer.lua          - Healer spec abilities (7-10)
    5. 04_mania_dps.lua               - DPS spec abilities (11-12)
    6. 05_vigil_tank.lua              - Tank spec abilities (13-14)
    7. 06_consciousness_warden_loader.lua - This file (commands & integration)

    Author: Akashic Foundation
    Version: 1.0.0
================================================================================
--]]

print("================================================================================")
print("    CONSCIOUSNESS WARDEN - Fairy Class System")
print("    WoW 3.3.5a Eluna Implementation")
print("    Author: Akashic Foundation")
print("================================================================================")

--[[
================================================================================
    MASTER COMMAND HANDLER
================================================================================
--]]

local function ShowHelp(player)
    player:SendBroadcastMessage("|cFF9400D3============ CONSCIOUSNESS WARDEN ============|r")
    player:SendBroadcastMessage("")
    player:SendBroadcastMessage("|cFFFFFFFFCore Commands:|r")
    player:SendBroadcastMessage("  |cFF00FF00.fairy|r - View chemistry status")
    player:SendBroadcastMessage("  |cFF00FF00.fairy reset|r - Reset chemistry to baseline")
    player:SendBroadcastMessage("  |cFF00FF00.fairy help|r - Show this help message")
    player:SendBroadcastMessage("")
    player:SendBroadcastMessage("|cFFFFFFFFSpecializations:|r")
    player:SendBroadcastMessage("  |cFF87CEEB.fairy reverie|r - Healer (Serotonin)")
    player:SendBroadcastMessage("  |cFFFFD700.fairy mania|r - DPS (Dopamine)")
    player:SendBroadcastMessage("  |cFFFF4500.fairy vigil|r - Tank (Cortisol)")
    player:SendBroadcastMessage("")
    player:SendBroadcastMessage("|cFFFFFFFFSpec-Specific:|r")
    player:SendBroadcastMessage("  |cFFFFD700.fairy momentum|r - (Mania) View dopamine momentum")
    player:SendBroadcastMessage("  |cFFFFD700.fairy rush|r - (Mania) View rush status")
    player:SendBroadcastMessage("  |cFFFF4500.fairy vigilant|r - (Vigil) View vigilant stacks")
    player:SendBroadcastMessage("  |cFFFF4500.fairy protection|r - (Vigil) View bond protection")
    player:SendBroadcastMessage("")
    player:SendBroadcastMessage("|cFF9400D3===============================================|r")
end

local function ShowAbilities(player)
    local guid = player:GetGUID()
    local spec = FairyChemistry.GetSpec(guid)

    player:SendBroadcastMessage("|cFF9400D3============ ABILITIES ============|r")
    player:SendBroadcastMessage("")
    player:SendBroadcastMessage("|cFFFFFFFFShared Abilities (All Specs):|r")
    player:SendBroadcastMessage("  1. |cFF00FF00Neural Pulse|r - Basic attack, generates primary chemical")
    player:SendBroadcastMessage("  2. |cFFFF69B4Empathic Mirror|r - Bond with ally, share healing")
    player:SendBroadcastMessage("  3. |cFFFFD700Intrusive Thought|r - DoT, dopamine on kill")
    player:SendBroadcastMessage("  4. |cFF87CEEBSoothing Presence|r - Channel heal, rebalance chemistry")
    player:SendBroadcastMessage("  5. |cFFFF4500Flight Response|r - Speed + reactive blink")
    player:SendBroadcastMessage("  6. |cFF9400D3Dreamwalk|r - Invis/escape, reset chemistry")
    player:SendBroadcastMessage("")

    if spec == "reverie" then
        player:SendBroadcastMessage("|cFF87CEEB=== REVERIE (Healer) ===|r")
        player:SendBroadcastMessage("  7. |cFF00FF00Wash of Serenity|r - Main heal + HoT")
        player:SendBroadcastMessage("  8. |cFFFF69B4Collective Unconscious|r - Group HoT")
        player:SendBroadcastMessage("  9. |cFFFFD700Memory of Wholeness|r - Amplify next heal")
        player:SendBroadcastMessage(" 10. |cFF00FF00Lucid Intervention|r - Emergency heal + CC immunity")
    elseif spec == "mania" then
        player:SendBroadcastMessage("|cFFFFD700=== MANIA (DPS) ===|r")
        player:SendBroadcastMessage(" 11. |cFFFF0000Euphoric Surge|r - Burst damage, auto-crit at high dopamine")
        player:SendBroadcastMessage(" 12. |cFFFF4500Anxiety Cascade|r - Spreading DoT")
    elseif spec == "vigil" then
        player:SendBroadcastMessage("|cFFFF4500=== VIGIL (Tank) ===|r")
        player:SendBroadcastMessage(" 13. |cFF8B0000Nightmare Visage|r - AoE taunt")
        player:SendBroadcastMessage(" 14. |cFFFF69B4Bond of Vigil|r - Redirect ally damage to self")
    end

    player:SendBroadcastMessage("|cFF9400D3===================================|r")
end

local function OnMasterCommand(event, player, command)
    local cmd = command:lower()

    if cmd == "fairy help" then
        ShowHelp(player)
        return false
    end

    if cmd == "fairy abilities" or cmd == "fairy spells" then
        ShowAbilities(player)
        return false
    end

    if cmd == "fairy test" then
        -- Test command to verify system is working
        player:SendBroadcastMessage("|cFF9400D3[Consciousness Warden]|r System test:")
        player:SendBroadcastMessage("  FairyChemistry: " .. (FairyChemistry and "OK" or "MISSING"))
        player:SendBroadcastMessage("  FairyAbilities: " .. (FairyAbilities and "OK" or "MISSING"))

        local guid = player:GetGUID()
        local chem = FairyChemistry.GetOrCreate(guid)
        player:SendBroadcastMessage("  Your chemistry: " .. (chem and "OK" or "MISSING"))
        player:SendBroadcastMessage("  Your spec: " .. (chem.spec or "none"))

        return false
    end

    return true
end

RegisterPlayerEvent(42, OnMasterCommand)

--[[
================================================================================
    SPELL CAST HOOK
    Hook spell casts to trigger Consciousness Warden abilities
================================================================================
--]]

local function OnSpellCast(event, player, spell, skipCheck)
    local spellId = spell:GetEntry()
    local guid = player:GetGUID()

    -- Check if this is a Consciousness Warden spell
    local ability = FairyAbilities.GetAbility(spellId)
    if ability then
        local target = player:GetSelection()
        FairyAbilities.ExecuteAbility(player, ability.name, target)
    end
end

-- RegisterPlayerEvent(5, OnSpellCast)  -- PLAYER_EVENT_ON_SPELL_CAST

--[[
================================================================================
    CHEMISTRY INTEGRATION HOOKS
    Hook the chemistry system to trigger spec-specific effects
================================================================================
--]]

-- Store original ModifyChemical to add hooks
local OriginalModifyChemical = FairyChemistry.ModifyChemical

FairyChemistry.ModifyChemical = function(playerGUID, chemical, amount)
    local newValue, oldValue = OriginalModifyChemical(playerGUID, chemical, amount)

    -- Trigger spec-specific effects on chemistry changes
    if amount > 0 then
        local chem = FairyChemistry.GetOrCreate(playerGUID)

        -- Reverie: Serenity's Echo (heal bonded ally on serotonin gain)
        if chem.spec == "reverie" and chemical == "serotonin" then
            local bondedAllyGUID = FairyChemistry.GetBondedAlly(playerGUID)
            if bondedAllyGUID then
                local player = GetPlayerByGUID(playerGUID)
                local ally = GetPlayerByGUID(bondedAllyGUID)

                if player and ally and ally:IsInWorld() and not ally:IsDead() then
                    local maxHealth = player:GetMaxHealth()
                    local echoHeal = math.floor(maxHealth * 0.05)

                    local allyHealth = ally:GetHealth()
                    local allyMaxHealth = ally:GetMaxHealth()
                    ally:SetHealth(math.min(allyMaxHealth, allyHealth + echoHeal))
                end
            end
        end

        -- Mania: Add dopamine momentum
        if chem.spec == "mania" and chemical == "dopamine" then
            -- Handled in mania module
        end

        -- Vigil: Add vigilant stacks on cortisol gain (when taking damage)
        if chem.spec == "vigil" and chemical == "cortisol" then
            -- Handled in vigil module damage hooks
        end
    end

    return newValue, oldValue
end

--[[
================================================================================
    WELCOME MESSAGE ON LOGIN
================================================================================
--]]

local function OnLoginWelcome(event, player)
    player:SendBroadcastMessage("")
    player:SendBroadcastMessage("|cFF9400D3=====================================|r")
    player:SendBroadcastMessage("|cFF9400D3   CONSCIOUSNESS WARDEN ACTIVE|r")
    player:SendBroadcastMessage("|cFF9400D3=====================================|r")
    player:SendBroadcastMessage("")
    player:SendBroadcastMessage("  Type |cFF00FF00.fairy help|r for commands")
    player:SendBroadcastMessage("  Type |cFF00FF00.fairy abilities|r for ability list")
    player:SendBroadcastMessage("")

    local guid = player:GetGUID()
    local spec = FairyChemistry.GetSpec(guid)
    local specColors = {
        reverie = "|cFF87CEEB",
        mania = "|cFFFFD700",
        vigil = "|cFFFF4500"
    }
    local color = specColors[spec] or "|cFFFFFFFF"

    player:SendBroadcastMessage("  Current spec: " .. color .. spec:upper() .. "|r")
    player:SendBroadcastMessage("")
end

RegisterPlayerEvent(3, OnLoginWelcome)

--[[
================================================================================
    SUMMARY OF ALL ABILITIES
================================================================================

    SHARED ABILITIES (All Specs):
    1. Neural Pulse      - Basic attack, generates primary chemical
    2. Empathic Mirror   - Bond with ally, share healing
    3. Intrusive Thought - DoT that rewards kills with dopamine
    4. Soothing Presence - Channel to heal and rebalance chemistry
    5. Flight Response   - Movement speed + reactive blink
    6. Dreamwalk         - Invisibility/escape, resets chemistry

    REVERIE (Healer) - Primary: Serotonin, Secondary: Oxytocin:
    7. Wash of Serenity      - Main heal with HoT
    8. Collective Unconscious - Group HoT that generates oxytocin
    9. Memory of Wholeness   - Amplify next heal based on serotonin
    10. Lucid Intervention   - Emergency heal + CC immunity

    MANIA (DPS) - Primary: Dopamine, Secondary: Cortisol:
    11. Euphoric Surge   - Burst damage, auto-crit at high dopamine
    12. Anxiety Cascade  - Spreading DoT that generates dopamine

    VIGIL (Tank) - Primary: Cortisol, Secondary: Oxytocin:
    13. Nightmare Visage - AoE taunt with fear-based damage
    14. Bond of Vigil    - Redirect damage from bonded ally

================================================================================
--]]

print("")
print("[Consciousness Warden] All systems loaded successfully!")
print("[Consciousness Warden] 14 abilities across 3 specializations ready.")
print("[Consciousness Warden] Type .fairy help in-game for commands.")
print("")
