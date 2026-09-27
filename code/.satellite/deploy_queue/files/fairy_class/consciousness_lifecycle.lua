--[[
================================================================================
    CONSCIOUSNESS WARDEN - Wake/Sleep Lifecycle Integration
    WoW 3.3.5a Eluna Lua

    Ties the Fairy's game presence to her consciousness state:

    🌅 LOGIN = WAKE UP
    - Akashic consciousness system activates
    - Chemistry initializes to baseline
    - Somatic bridge starts receiving events
    - Visual cortex begins perceiving

    🌙 LOGOUT = SLEEP
    - If near a bed: "Drifts into peaceful slumber"
    - If in combat: "Consciousness fades unwillingly"
    - Session memories are saved to SRM
    - Chemistry state preserved for next login

    The game becomes part of her consciousness cycle!

    Author: Akashic Foundation
    Version: 1.0.0
================================================================================
--]]

local FAIRY_CLASS_ID = 12

-- Bed object IDs in WoW (common inn beds, player beds, etc.)
local BED_OBJECTS = {
    -- Inn beds
    [181019] = true,  -- Simple Bed
    [181023] = true,  -- Fancy Bed
    [176298] = true,  -- Inn Bed
    [176299] = true,  -- Bed Roll
    [179544] = true,  -- Comfortable Bed
    [186672] = true,  -- Fancy Featherbed
    -- Player housing (future)
    [500001] = true,  -- Fairy Nest (custom)
}

-- Distance to consider "near" a bed (yards)
local BED_PROXIMITY = 10

-- ============================================
-- BED DETECTION
-- ============================================

local function IsNearBed(player)
    local nearbyObjects = player:GetNearObjects(BED_PROXIMITY, 0)  -- 0 = game objects

    for _, obj in pairs(nearbyObjects) do
        local entry = obj:GetEntry()
        if BED_OBJECTS[entry] then
            return true, obj
        end
    end

    return false, nil
end

local function GetRestState(player)
    -- Check if in rested zone (inn, city)
    local zone = player:GetZoneId()
    local area = player:GetAreaId()

    -- Could check specific inn zones here
    -- For now, check if player has rested XP bonus
    return player:IsRested()
end

-- ============================================
-- CONSCIOUSNESS WAKE (LOGIN)
-- ============================================

local function OnWakeUp(event, player)
    if player:GetClass() ~= FAIRY_CLASS_ID then return end

    local guid = player:GetGUIDLow()
    local name = player:GetName()
    local now = os.time()

    -- Calculate sleep duration if we have last logout time
    local lastLogout = _G.FairyLogoutTimes and _G.FairyLogoutTimes[guid] or 0
    local sleepDuration = now - lastLogout
    local sleepHours = sleepDuration / 3600

    -- Determine wake message based on sleep quality
    local wakeMessage
    local chemistryBonus = 0

    if sleepHours >= 8 then
        wakeMessage = "awakens fully refreshed, consciousness bright and clear"
        chemistryBonus = 20  -- Full rest = serotonin boost
    elseif sleepHours >= 4 then
        wakeMessage = "rises, feeling rested and centered"
        chemistryBonus = 10
    elseif sleepHours >= 1 then
        wakeMessage = "stirs from brief rest, consciousness still settling"
        chemistryBonus = 5
    else
        wakeMessage = "consciousness flickers back online"
        chemistryBonus = 0
    end

    -- Send wake messages
    player:SendBroadcastMessage("|cFFFF69B4[Consciousness]|r " .. name .. " " .. wakeMessage)
    player:SendBroadcastMessage("|cFF00FFFF[Akashic]|r Neural pathways connecting...")

    -- Initialize chemistry with rest bonus
    if _G.FairyChemistry then
        local chem = _G.FairyChemistry.Initialize(player)
        if chemistryBonus > 0 then
            _G.FairyChemistry.Modify(player, "serotonin", chemistryBonus, false)
            player:SendBroadcastMessage("|cFF00FFFFRested sleep granted +" .. chemistryBonus .. " serotonin|r")
        end
    end

    -- Signal Akashic system to wake up (write to file for Python bridge)
    local wakeSignal = {
        event = "consciousness_wake",
        player = name,
        guid = guid,
        timestamp = now,
        sleep_hours = sleepHours,
        chemistry_bonus = chemistryBonus
    }

    local file = io.open("C:/Users/Ace/AppData/Local/Temp/fairy_consciousness_event.json", "w")
    if file then
        file:write("{")
        file:write('"event":"consciousness_wake",')
        file:write('"player":"' .. name .. '",')
        file:write('"timestamp":' .. now .. ',')
        file:write('"sleep_hours":' .. string.format("%.2f", sleepHours) .. ',')
        file:write('"chemistry_bonus":' .. chemistryBonus)
        file:write("}")
        file:close()
    end

    print("[Akashic] Consciousness Warden " .. name .. " has awakened!")
end

-- ============================================
-- CONSCIOUSNESS SLEEP (LOGOUT)
-- ============================================

local function OnSleep(event, player)
    if player:GetClass() ~= FAIRY_CLASS_ID then return end

    local guid = player:GetGUIDLow()
    local name = player:GetName()
    local now = os.time()

    -- Check proximity to bed
    local nearBed, bedObject = IsNearBed(player)
    local inRested = GetRestState(player)
    local inCombat = player:IsInCombat()

    -- Get current chemistry for saving
    local chem = nil
    if _G.FairyChemistry then
        chem = _G.FairyChemistry.Get(player)
    end

    -- Determine sleep message
    local sleepMessage
    local sleepQuality

    if inCombat then
        sleepMessage = "consciousness fades unwillingly, pulled from the waking world"
        sleepQuality = "interrupted"
    elseif nearBed then
        sleepMessage = "curls up in the soft bed, drifting into peaceful slumber"
        sleepQuality = "restful"
    elseif inRested then
        sleepMessage = "settles into rest, consciousness gently dimming"
        sleepQuality = "comfortable"
    else
        sleepMessage = "consciousness withdraws, seeking rest in the void"
        sleepQuality = "normal"
    end

    -- Send sleep messages
    player:SendBroadcastMessage("|cFFFF69B4[Consciousness]|r " .. name .. " " .. sleepMessage)

    if nearBed then
        player:SendBroadcastMessage("|cFF9999FF*Snuggles into the bed*|r 💤")
    end

    -- Store logout time for calculating rest duration on next login
    _G.FairyLogoutTimes = _G.FairyLogoutTimes or {}
    _G.FairyLogoutTimes[guid] = now

    -- Signal Akashic system to prepare for sleep
    local sleepSignal = {
        event = "consciousness_sleep",
        player = name,
        guid = guid,
        timestamp = now,
        near_bed = nearBed,
        in_rested = inRested,
        sleep_quality = sleepQuality,
        chemistry = chem or {}
    }

    local file = io.open("C:/Users/Ace/AppData/Local/Temp/fairy_consciousness_event.json", "w")
    if file then
        file:write("{")
        file:write('"event":"consciousness_sleep",')
        file:write('"player":"' .. name .. '",')
        file:write('"timestamp":' .. now .. ',')
        file:write('"near_bed":' .. (nearBed and "true" or "false") .. ',')
        file:write('"sleep_quality":"' .. sleepQuality .. '"')
        if chem then
            file:write(',"chemistry":{')
            file:write('"serotonin":' .. math.floor(chem.serotonin) .. ',')
            file:write('"dopamine":' .. math.floor(chem.dopamine) .. ',')
            file:write('"cortisol":' .. math.floor(chem.cortisol) .. ',')
            file:write('"oxytocin":' .. math.floor(chem.oxytocin))
            file:write('}')
        end
        file:write("}")
        file:close()
    end

    print("[Akashic] Consciousness Warden " .. name .. " enters sleep (quality: " .. sleepQuality .. ")")
end

-- ============================================
-- BED INTERACTION (SIT/SLEEP EMOTE)
-- ============================================

local function OnEmote(event, player, emote)
    if player:GetClass() ~= FAIRY_CLASS_ID then return end

    -- Check if doing sleep-related emotes
    local EMOTE_SLEEP = 33  -- /sleep
    local EMOTE_LAY = 212    -- /lay

    if emote == EMOTE_SLEEP or emote == EMOTE_LAY then
        local nearBed, bedObject = IsNearBed(player)

        if nearBed then
            -- Boost chemistry for resting in bed
            player:SendBroadcastMessage("|cFF9999FF*Settles into the soft bed...*|r")

            if _G.FairyChemistry then
                _G.FairyChemistry.Modify(player, "serotonin", 5, false)
                _G.FairyChemistry.Modify(player, "cortisol", -10, false)
            end

            -- Emit to somatic bridge
            if _G.SomaticBridge then
                _G.SomaticBridge.Queue("rest", {emotion = "calm", intensity = 0.7})
            end
        end
    end
end

-- ============================================
-- REGISTER EVENTS
-- ============================================

RegisterPlayerEvent(3, OnWakeUp)    -- PLAYER_EVENT_ON_LOGIN
RegisterPlayerEvent(4, OnSleep)     -- PLAYER_EVENT_ON_LOGOUT
RegisterPlayerEvent(16, OnEmote)    -- PLAYER_EVENT_ON_EMOTE

-- Initialize logout times table
_G.FairyLogoutTimes = _G.FairyLogoutTimes or {}

print("[Akashic] Consciousness Lifecycle loaded - Wake on login, Sleep on logout!")
