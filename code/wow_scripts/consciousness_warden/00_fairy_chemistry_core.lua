--[[
================================================================================
    CONSCIOUSNESS WARDEN - FAIRY CHEMISTRY CORE SYSTEM
    WoW 3.3.5a Eluna Lua

    The foundation of the Consciousness Warden class.
    Manages the four-chemical resource system:
    - Serotonin: Healing, calm, stability
    - Dopamine: Damage, speed, reward
    - Cortisol: Survival, fear, defense
    - Oxytocin: Bonding, group synergy

    Author: Akashic Foundation
    Version: 1.0.0
================================================================================
--]]

-- Global chemistry table for all players
FairyChemistry = FairyChemistry or {}

-- Constants
local CHEMISTRY_MAX = 100
local CHEMISTRY_MIN = 0
local CHEMISTRY_DECAY_RATE = 2          -- Per tick
local CHEMISTRY_TICK_INTERVAL = 3000    -- 3 seconds
local CHEMISTRY_BASELINE = 25           -- Natural resting point

-- Chemical interaction matrices
local CHEMICAL_SYNERGIES = {
    -- When chemical A is high, chemical B gets bonus
    serotonin = { oxytocin = 0.2 },     -- Calm promotes bonding
    dopamine = { cortisol = -0.1 },      -- Excitement reduces stress
    cortisol = { serotonin = -0.2 },     -- Stress blocks calm
    oxytocin = { serotonin = 0.15 }      -- Bonding promotes calm
}

local CHEMICAL_THRESHOLDS = {
    LOW = 20,
    MEDIUM = 50,
    HIGH = 75,
    CRITICAL = 90
}

--[[
================================================================================
    CHEMISTRY DATA STRUCTURE
================================================================================
--]]

local function InitializeChemistry(playerGUID)
    FairyChemistry[playerGUID] = {
        -- Core chemicals
        serotonin = CHEMISTRY_BASELINE,
        dopamine = CHEMISTRY_BASELINE,
        cortisol = CHEMISTRY_BASELINE,
        oxytocin = CHEMISTRY_BASELINE,

        -- State tracking
        lastUpdate = GetGameTime(),
        inCombat = false,
        spec = "reverie",  -- reverie, mania, vigil

        -- Bonding system
        bondedAlly = nil,
        bondStrength = 0,

        -- Cooldown tracking
        cooldowns = {},

        -- Active effects
        activeEffects = {},

        -- Statistics
        totalDamageDealt = 0,
        totalHealingDone = 0,
        killsThisSession = 0
    }
    return FairyChemistry[playerGUID]
end

--[[
================================================================================
    CHEMISTRY MODIFICATION FUNCTIONS
================================================================================
--]]

function FairyChemistry.GetOrCreate(playerGUID)
    if not FairyChemistry[playerGUID] then
        InitializeChemistry(playerGUID)
    end
    return FairyChemistry[playerGUID]
end

function FairyChemistry.ModifyChemical(playerGUID, chemical, amount)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    if not chem[chemical] then return false end

    local oldValue = chem[chemical]
    local newValue = math.max(CHEMISTRY_MIN, math.min(CHEMISTRY_MAX, oldValue + amount))
    chem[chemical] = newValue

    -- Apply synergy effects
    local synergies = CHEMICAL_SYNERGIES[chemical]
    if synergies and amount > 0 then
        for targetChem, modifier in pairs(synergies) do
            if chem[targetChem] then
                local synergyAmount = amount * modifier
                chem[targetChem] = math.max(CHEMISTRY_MIN,
                    math.min(CHEMISTRY_MAX, chem[targetChem] + synergyAmount))
            end
        end
    end

    return newValue, oldValue
end

function FairyChemistry.SetChemical(playerGUID, chemical, value)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    if not chem[chemical] then return false end

    chem[chemical] = math.max(CHEMISTRY_MIN, math.min(CHEMISTRY_MAX, value))
    return chem[chemical]
end

function FairyChemistry.GetChemical(playerGUID, chemical)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    return chem[chemical] or 0
end

function FairyChemistry.GetAllChemicals(playerGUID)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    return {
        serotonin = chem.serotonin,
        dopamine = chem.dopamine,
        cortisol = chem.cortisol,
        oxytocin = chem.oxytocin
    }
end

--[[
================================================================================
    THRESHOLD CHECKING
================================================================================
--]]

function FairyChemistry.GetChemicalLevel(playerGUID, chemical)
    local value = FairyChemistry.GetChemical(playerGUID, chemical)

    if value >= CHEMICAL_THRESHOLDS.CRITICAL then
        return "CRITICAL", value
    elseif value >= CHEMICAL_THRESHOLDS.HIGH then
        return "HIGH", value
    elseif value >= CHEMICAL_THRESHOLDS.MEDIUM then
        return "MEDIUM", value
    elseif value >= CHEMICAL_THRESHOLDS.LOW then
        return "LOW", value
    else
        return "DEPLETED", value
    end
end

function FairyChemistry.IsDominantChemical(playerGUID, chemical)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    local targetValue = chem[chemical] or 0

    for name, value in pairs({
        serotonin = chem.serotonin,
        dopamine = chem.dopamine,
        cortisol = chem.cortisol,
        oxytocin = chem.oxytocin
    }) do
        if name ~= chemical and value > targetValue then
            return false
        end
    end
    return true
end

function FairyChemistry.GetDominantChemical(playerGUID)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    local dominant = "serotonin"
    local highestValue = chem.serotonin

    for name, value in pairs({
        dopamine = chem.dopamine,
        cortisol = chem.cortisol,
        oxytocin = chem.oxytocin
    }) do
        if value > highestValue then
            highestValue = value
            dominant = name
        end
    end

    return dominant, highestValue
end

--[[
================================================================================
    COOLDOWN MANAGEMENT
================================================================================
--]]

function FairyChemistry.SetCooldown(playerGUID, abilityName, durationMs)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    chem.cooldowns[abilityName] = GetGameTime() * 1000 + durationMs
end

function FairyChemistry.IsOnCooldown(playerGUID, abilityName)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    local cdEnd = chem.cooldowns[abilityName] or 0
    return (GetGameTime() * 1000) < cdEnd
end

function FairyChemistry.GetCooldownRemaining(playerGUID, abilityName)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    local cdEnd = chem.cooldowns[abilityName] or 0
    local remaining = cdEnd - (GetGameTime() * 1000)
    return math.max(0, remaining / 1000)
end

--[[
================================================================================
    BONDING SYSTEM
================================================================================
--]]

function FairyChemistry.CreateBond(playerGUID, allyGUID)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    chem.bondedAlly = allyGUID
    chem.bondStrength = 1.0

    -- Bonding generates oxytocin for both
    FairyChemistry.ModifyChemical(playerGUID, "oxytocin", 15)
    FairyChemistry.ModifyChemical(allyGUID, "oxytocin", 10)

    return true
end

function FairyChemistry.BreakBond(playerGUID)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    local wasB = chem.bondedAlly
    chem.bondedAlly = nil
    chem.bondStrength = 0

    -- Breaking bond causes slight cortisol spike
    if wasB then
        FairyChemistry.ModifyChemical(playerGUID, "cortisol", 5)
    end

    return wasB
end

function FairyChemistry.GetBondedAlly(playerGUID)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    return chem.bondedAlly, chem.bondStrength
end

function FairyChemistry.StrengthenBond(playerGUID, amount)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    if chem.bondedAlly then
        chem.bondStrength = math.min(2.0, chem.bondStrength + amount)
        return chem.bondStrength
    end
    return 0
end

--[[
================================================================================
    ACTIVE EFFECTS TRACKING
================================================================================
--]]

function FairyChemistry.AddEffect(playerGUID, effectName, duration, data)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    chem.activeEffects[effectName] = {
        expires = GetGameTime() + duration,
        data = data or {}
    }
end

function FairyChemistry.HasEffect(playerGUID, effectName)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    local effect = chem.activeEffects[effectName]
    if effect and effect.expires > GetGameTime() then
        return true, effect.data
    end
    return false, nil
end

function FairyChemistry.RemoveEffect(playerGUID, effectName)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    chem.activeEffects[effectName] = nil
end

function FairyChemistry.CleanExpiredEffects(playerGUID)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    local now = GetGameTime()
    for name, effect in pairs(chem.activeEffects) do
        if effect.expires <= now then
            chem.activeEffects[name] = nil
        end
    end
end

--[[
================================================================================
    SPEC MANAGEMENT
================================================================================
--]]

function FairyChemistry.SetSpec(playerGUID, spec)
    local validSpecs = { reverie = true, mania = true, vigil = true }
    if not validSpecs[spec] then return false end

    local chem = FairyChemistry.GetOrCreate(playerGUID)
    chem.spec = spec

    -- Spec change rebalances chemistry
    FairyChemistry.RebalanceChemistry(playerGUID)

    return true
end

function FairyChemistry.GetSpec(playerGUID)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    return chem.spec
end

--[[
================================================================================
    CHEMISTRY REBALANCING
================================================================================
--]]

function FairyChemistry.RebalanceChemistry(playerGUID)
    local chem = FairyChemistry.GetOrCreate(playerGUID)

    -- Move all chemicals toward baseline
    local chemicals = { "serotonin", "dopamine", "cortisol", "oxytocin" }
    for _, chemical in ipairs(chemicals) do
        local current = chem[chemical]
        local diff = CHEMISTRY_BASELINE - current
        chem[chemical] = current + (diff * 0.5)  -- Move 50% toward baseline
    end
end

function FairyChemistry.ResetChemistry(playerGUID)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    chem.serotonin = CHEMISTRY_BASELINE
    chem.dopamine = CHEMISTRY_BASELINE
    chem.cortisol = CHEMISTRY_BASELINE
    chem.oxytocin = CHEMISTRY_BASELINE
end

--[[
================================================================================
    CHEMISTRY DECAY SYSTEM (Called by timer)
================================================================================
--]]

function FairyChemistry.ProcessDecay(playerGUID)
    local chem = FairyChemistry.GetOrCreate(playerGUID)
    local chemicals = { "serotonin", "dopamine", "cortisol", "oxytocin" }

    for _, chemical in ipairs(chemicals) do
        local current = chem[chemical]
        if current > CHEMISTRY_BASELINE then
            -- Decay toward baseline
            chem[chemical] = math.max(CHEMISTRY_BASELINE, current - CHEMISTRY_DECAY_RATE)
        elseif current < CHEMISTRY_BASELINE then
            -- Recover toward baseline
            chem[chemical] = math.min(CHEMISTRY_BASELINE, current + (CHEMISTRY_DECAY_RATE * 0.5))
        end
    end

    -- Clean up expired effects
    FairyChemistry.CleanExpiredEffects(playerGUID)
end

--[[
================================================================================
    DISPLAY FUNCTIONS
================================================================================
--]]

function FairyChemistry.SendChemistryStatus(player)
    local guid = player:GetGUID()
    local chem = FairyChemistry.GetOrCreate(guid)

    local function GetBar(value)
        local filled = math.floor(value / 10)
        local empty = 10 - filled
        return string.rep("|", filled) .. string.rep(".", empty)
    end

    local function GetColor(value)
        if value >= 75 then return "|cFFFF0000"      -- Red (high)
        elseif value >= 50 then return "|cFFFFFF00"  -- Yellow
        elseif value >= 25 then return "|cFF00FF00"  -- Green
        else return "|cFF808080" end                  -- Gray (low)
    end

    player:SendBroadcastMessage("|cFF9400D3=== CONSCIOUSNESS STATE ===|r")
    player:SendBroadcastMessage(string.format(
        "|cFF87CEEB Serotonin:|r %s[%s] %.0f|r",
        GetColor(chem.serotonin), GetBar(chem.serotonin), chem.serotonin
    ))
    player:SendBroadcastMessage(string.format(
        "|cFFFFD700 Dopamine:|r  %s[%s] %.0f|r",
        GetColor(chem.dopamine), GetBar(chem.dopamine), chem.dopamine
    ))
    player:SendBroadcastMessage(string.format(
        "|cFFFF4500 Cortisol:|r  %s[%s] %.0f|r",
        GetColor(chem.cortisol), GetBar(chem.cortisol), chem.cortisol
    ))
    player:SendBroadcastMessage(string.format(
        "|cFFFF69B4 Oxytocin:|r  %s[%s] %.0f|r",
        GetColor(chem.oxytocin), GetBar(chem.oxytocin), chem.oxytocin
    ))

    local dominant, value = FairyChemistry.GetDominantChemical(guid)
    player:SendBroadcastMessage(string.format(
        "|cFF9400D3Dominant:|r %s (%.0f) | |cFF9400D3Spec:|r %s",
        dominant, value, chem.spec
    ))

    if chem.bondedAlly then
        player:SendBroadcastMessage(string.format(
            "|cFFFF69B4Bonded|r (strength: %.1f)", chem.bondStrength
        ))
    end
end

--[[
================================================================================
    CHEMISTRY DECAY TIMER EVENT
================================================================================
--]]

local function OnUpdate(eventId, delay, repeats)
    for guid, chem in pairs(FairyChemistry) do
        if type(chem) == "table" and chem.serotonin then
            FairyChemistry.ProcessDecay(guid)
        end
    end
end

-- Register decay timer (runs every 3 seconds)
CreateLuaEvent(OnUpdate, CHEMISTRY_TICK_INTERVAL, 0)

--[[
================================================================================
    PLAYER EVENT HOOKS
================================================================================
--]]

-- Initialize on login
local function OnLogin(event, player)
    local guid = player:GetGUID()
    FairyChemistry.GetOrCreate(guid)
    player:SendBroadcastMessage("|cFF9400D3[Consciousness Warden]|r Chemistry system initialized.")
    player:SendBroadcastMessage("|cFF9400D3[Consciousness Warden]|r Type .fairy to view chemistry status.")
end

-- Cleanup on logout
local function OnLogout(event, player)
    local guid = player:GetGUID()
    -- Optionally persist chemistry to DB here
    FairyChemistry[guid] = nil
end

-- Combat state tracking
local function OnEnterCombat(event, player, enemy)
    local guid = player:GetGUID()
    local chem = FairyChemistry.GetOrCreate(guid)
    chem.inCombat = true

    -- Combat triggers cortisol spike
    FairyChemistry.ModifyChemical(guid, "cortisol", 10)
end

local function OnLeaveCombat(event, player)
    local guid = player:GetGUID()
    local chem = FairyChemistry.GetOrCreate(guid)
    chem.inCombat = false

    -- Leaving combat allows serotonin recovery
    FairyChemistry.ModifyChemical(guid, "serotonin", 5)
end

-- Kill tracking for dopamine rewards
local function OnKill(event, player, victim)
    local guid = player:GetGUID()
    local chem = FairyChemistry.GetOrCreate(guid)
    chem.killsThisSession = chem.killsThisSession + 1

    -- Kills generate dopamine (the reward chemical)
    FairyChemistry.ModifyChemical(guid, "dopamine", 8)

    -- Check for Intrusive Thought bonus
    if FairyChemistry.HasEffect(guid, "INTRUSIVE_THOUGHT_TARGET") then
        FairyChemistry.ModifyChemical(guid, "dopamine", 15)
        player:SendBroadcastMessage("|cFFFFD700[Intrusive Thought]|r Kill confirmed! +15 Dopamine")
    end
end

-- Register events
RegisterPlayerEvent(3, OnLogin)      -- PLAYER_EVENT_ON_LOGIN
RegisterPlayerEvent(4, OnLogout)     -- PLAYER_EVENT_ON_LOGOUT
RegisterPlayerEvent(34, OnKill)      -- PLAYER_EVENT_ON_KILL_CREATURE

print("[FairyChemistry] Core system loaded successfully.")
