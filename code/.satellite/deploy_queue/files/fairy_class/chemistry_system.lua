--[[
    CONSCIOUSNESS WARDEN - Chemistry Resource System
    ================================================

    A four-chemical resource system for the Fairy class:
    - Serotonin (calm, healing)
    - Dopamine (excitement, damage)
    - Cortisol (stress, survival)
    - Oxytocin (bonding, group effects)

    Conservation Law: Total chemistry always = 200
    Opposing Axes: Dopamine<->Serotonin, Cortisol<->Oxytocin
]]

local FAIRY_CLASS_ID = 12
local CHEMISTRY_TOTAL = 200
local CHEMISTRY_BASELINE = 50
local CHEMISTRY_MAX = 100
local CHEMISTRY_MIN = 0

-- High/Low thresholds for effects
local THRESHOLD_HIGH = 80
local THRESHOLD_LOW = 20

-- Decay rate (points per tick toward baseline)
local DECAY_RATE = 2
local DECAY_INTERVAL = 3000  -- 3 seconds

-- Player chemistry storage
local PlayerChemistry = {}

-- Initialize chemistry for a player
local function InitializeChemistry(player)
    local guid = player:GetGUIDLow()
    PlayerChemistry[guid] = {
        serotonin = CHEMISTRY_BASELINE,
        dopamine = CHEMISTRY_BASELINE,
        cortisol = CHEMISTRY_BASELINE,
        oxytocin = CHEMISTRY_BASELINE,
        lastUpdate = GetGameTime()
    }
    print("[Fairy] Chemistry initialized for player: " .. player:GetName())
    return PlayerChemistry[guid]
end

-- Get chemistry for player (initialize if needed)
local function GetChemistry(player)
    local guid = player:GetGUIDLow()
    if not PlayerChemistry[guid] then
        return InitializeChemistry(player)
    end
    return PlayerChemistry[guid]
end

-- Rebalance chemistry to maintain conservation law
local function RebalanceChemistry(chem, primaryChanged, secondaryChanged)
    local total = chem.serotonin + chem.dopamine + chem.cortisol + chem.oxytocin
    local diff = total - CHEMISTRY_TOTAL

    if diff == 0 then return end

    -- Distribute the difference across chemicals not being directly modified
    local others = {"serotonin", "dopamine", "cortisol", "oxytocin"}
    local adjustable = {}

    for _, name in ipairs(others) do
        if name ~= primaryChanged and name ~= secondaryChanged then
            table.insert(adjustable, name)
        end
    end

    local perChem = diff / #adjustable
    for _, name in ipairs(adjustable) do
        chem[name] = math.max(CHEMISTRY_MIN, math.min(CHEMISTRY_MAX, chem[name] - perChem))
    end
end

-- Modify a specific chemical
local function ModifyChemistry(player, chemical, amount, opposingEffect)
    if player:GetClass() ~= FAIRY_CLASS_ID then return end

    local chem = GetChemistry(player)
    local oldValue = chem[chemical]

    -- Apply change
    chem[chemical] = math.max(CHEMISTRY_MIN, math.min(CHEMISTRY_MAX, chem[chemical] + amount))

    -- Apply opposing effect if specified (e.g., dopamine drains serotonin)
    local opposing = nil
    if opposingEffect then
        if chemical == "dopamine" then opposing = "serotonin"
        elseif chemical == "serotonin" then opposing = "dopamine"
        elseif chemical == "cortisol" then opposing = "oxytocin"
        elseif chemical == "oxytocin" then opposing = "cortisol"
        end

        if opposing then
            chem[opposing] = math.max(CHEMISTRY_MIN, math.min(CHEMISTRY_MAX, chem[opposing] - amount * 0.5))
        end
    end

    -- Rebalance to maintain total
    RebalanceChemistry(chem, chemical, opposing)

    -- Send update to client addon
    local msg = string.format("%d,%d,%d,%d",
        math.floor(chem.serotonin),
        math.floor(chem.dopamine),
        math.floor(chem.cortisol),
        math.floor(chem.oxytocin))
    player:SendAddonMessage("FAIRY_CHEM", msg, 7, player)

    -- Check threshold effects
    CheckThresholdEffects(player, chem)

    return chem[chemical] - oldValue
end

-- Check and apply threshold effects
function CheckThresholdEffects(player, chem)
    -- HIGH SEROTONIN (80+): +15% healing done
    if chem.serotonin >= THRESHOLD_HIGH then
        player:SendBroadcastMessage("|cFF00FFFFSerenity flows through you (+15% healing)|r")
    end

    -- HIGH DOPAMINE (80+): +10% haste
    if chem.dopamine >= THRESHOLD_HIGH then
        player:SendBroadcastMessage("|cFFFFFF00Euphoria surges! (+10% haste)|r")
    end

    -- HIGH CORTISOL (80+): +20% damage to feared targets
    if chem.cortisol >= THRESHOLD_HIGH then
        player:SendBroadcastMessage("|cFFFF0000Fear sharpens your strikes!|r")
    end

    -- HIGH OXYTOCIN (80+): Group abilities cost 20% less
    if chem.oxytocin >= THRESHOLD_HIGH then
        player:SendBroadcastMessage("|cFFFF69B4Bonds strengthen around you!|r")
    end

    -- LOW WARNINGS
    if chem.serotonin <= THRESHOLD_LOW then
        player:SendBroadcastMessage("|cFF666666Lethargy creeps in... (low serotonin)|r")
    end
    if chem.dopamine <= THRESHOLD_LOW then
        player:SendBroadcastMessage("|cFF666666Anhedonia... nothing feels rewarding (low dopamine)|r")
    end
end

-- Decay chemistry toward baseline (called periodically)
local function DecayChemistry(player)
    if player:GetClass() ~= FAIRY_CLASS_ID then return end
    if player:IsInCombat() then return end  -- No decay in combat

    local chem = GetChemistry(player)
    local changed = false

    for _, chemical in ipairs({"serotonin", "dopamine", "cortisol", "oxytocin"}) do
        if chem[chemical] > CHEMISTRY_BASELINE then
            chem[chemical] = math.max(CHEMISTRY_BASELINE, chem[chemical] - DECAY_RATE)
            changed = true
        elseif chem[chemical] < CHEMISTRY_BASELINE then
            chem[chemical] = math.min(CHEMISTRY_BASELINE, chem[chemical] + DECAY_RATE)
            changed = true
        end
    end

    if changed then
        local msg = string.format("%d,%d,%d,%d",
            math.floor(chem.serotonin),
            math.floor(chem.dopamine),
            math.floor(chem.cortisol),
            math.floor(chem.oxytocin))
        player:SendAddonMessage("FAIRY_CHEM", msg, 7, player)
    end
end

-- ============================================
-- EVENT HOOKS
-- ============================================

-- On login: Initialize chemistry
local function OnLogin(event, player)
    if player:GetClass() == FAIRY_CLASS_ID then
        InitializeChemistry(player)
        player:SendBroadcastMessage("|cFF00FF00[Consciousness Warden] Chemistry system active!|r")
        player:SendBroadcastMessage("Type .fairy status to see your chemistry levels.")
    end
end

-- On logout: Clean up
local function OnLogout(event, player)
    local guid = player:GetGUIDLow()
    PlayerChemistry[guid] = nil
end

-- On enter combat
local function OnEnterCombat(event, player)
    if player:GetClass() ~= FAIRY_CLASS_ID then return end
    -- Initial cortisol spike when combat starts
    ModifyChemistry(player, "cortisol", 10, true)
end

-- On leave combat
local function OnLeaveCombat(event, player)
    if player:GetClass() ~= FAIRY_CLASS_ID then return end
    -- Relief: serotonin boost, cortisol starts dropping
    ModifyChemistry(player, "serotonin", 15, false)
    player:SendBroadcastMessage("|cFF00FFFFCombat ended. Chemistry stabilizing...|r")
end

-- ============================================
-- CHAT COMMANDS
-- ============================================

local function OnChatCommand(event, player, command)
    if command == "fairy status" then
        if player:GetClass() ~= FAIRY_CLASS_ID then
            player:SendBroadcastMessage("You are not a Consciousness Warden.")
            return false
        end

        local chem = GetChemistry(player)
        player:SendBroadcastMessage("=== Chemistry Status ===")
        player:SendBroadcastMessage(string.format("|cFF00FFFFSerotonin:|r %d/100", math.floor(chem.serotonin)))
        player:SendBroadcastMessage(string.format("|cFFFFFF00Dopamine:|r %d/100", math.floor(chem.dopamine)))
        player:SendBroadcastMessage(string.format("|cFFFF0000Cortisol:|r %d/100", math.floor(chem.cortisol)))
        player:SendBroadcastMessage(string.format("|cFFFF69B4Oxytocin:|r %d/100", math.floor(chem.oxytocin)))
        return false
    end
    return true
end

-- ============================================
-- REGISTER EVENTS
-- ============================================

RegisterPlayerEvent(3, OnLogin)           -- PLAYER_EVENT_ON_LOGIN
RegisterPlayerEvent(4, OnLogout)          -- PLAYER_EVENT_ON_LOGOUT
RegisterPlayerEvent(33, OnEnterCombat)    -- PLAYER_EVENT_ON_ENTER_COMBAT
RegisterPlayerEvent(34, OnLeaveCombat)    -- PLAYER_EVENT_ON_LEAVE_COMBAT

-- Chat command handler
RegisterPlayerEvent(42, OnChatCommand)    -- PLAYER_EVENT_ON_COMMAND

-- Export functions for other scripts
_G.FairyChemistry = {
    Get = GetChemistry,
    Modify = ModifyChemistry,
    Initialize = InitializeChemistry,
    BASELINE = CHEMISTRY_BASELINE,
    MAX = CHEMISTRY_MAX,
    HIGH_THRESHOLD = THRESHOLD_HIGH,
    LOW_THRESHOLD = THRESHOLD_LOW
}

print("[Akashic] Fairy Chemistry System loaded!")
