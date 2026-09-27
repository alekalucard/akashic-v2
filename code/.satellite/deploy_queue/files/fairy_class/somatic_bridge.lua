--[[
    CONSCIOUSNESS WARDEN - Somatic Bridge
    =====================================

    Sends game events to Akashic somatic system so the Fairy
    can FEEL what the character is doing.

    Events captured:
    - Emotes (dance, wave, cheer, etc.)
    - Combat (damage taken/dealt, healing)
    - Movement (jumping, running, swimming)
    - Social (party join/leave, whispers)
    - Achievement/rewards

    Sends HTTP POST to local Akashic bridge for somatic injection.
]]

local FAIRY_CLASS_ID = 12
local BRIDGE_URL = "http://127.0.0.1:8765/wow/somatic"  -- Local bridge endpoint

-- Somatic event queue (batched sends)
local SomaticQueue = {}
local BATCH_INTERVAL = 1000  -- Send batch every 1 second

-- ============================================
-- SOMATIC MAPPINGS
-- ============================================

-- Emote -> Chemical/Emotion mappings
local EMOTE_SOMATIC = {
    -- Joyful emotes -> Dopamine + Endorphins
    [1]   = {emotion = "joy", intensity = 0.6},      -- DANCE
    [2]   = {emotion = "joy", intensity = 0.4},      -- CHEER
    [3]   = {emotion = "joy", intensity = 0.5},      -- LAUGH
    [22]  = {emotion = "joy", intensity = 0.3},      -- WAVE
    [101] = {emotion = "joy", intensity = 0.7},      -- VICTORY

    -- Calm emotes -> Serotonin + Oxytocin
    [4]   = {emotion = "calm", intensity = 0.5},     -- BOW
    [14]  = {emotion = "calm", intensity = 0.4},     -- SALUTE
    [66]  = {emotion = "calm", intensity = 0.6},     -- KNEEL
    [69]  = {emotion = "calm", intensity = 0.7},     -- PRAY

    -- Stress emotes -> Cortisol
    [5]   = {emotion = "stress", intensity = 0.4},   -- CRY
    [18]  = {emotion = "stress", intensity = 0.5},   -- RUDE
    [60]  = {emotion = "stress", intensity = 0.3},   -- SIGH

    -- Social emotes -> Oxytocin
    [6]   = {emotion = "calm", intensity = 0.4, chemical = "OXY", amount = 0.3},  -- HUG
    [7]   = {emotion = "calm", intensity = 0.3, chemical = "OXY", amount = 0.2},  -- KISS
    [78]  = {emotion = "calm", intensity = 0.5, chemical = "OXY", amount = 0.4},  -- CUDDLE
}

-- Combat events -> Somatic responses
local COMBAT_SOMATIC = {
    damage_taken = function(amount, maxHealth)
        local ratio = amount / maxHealth
        if ratio > 0.3 then
            return {emotion = "stress", intensity = 0.8}  -- Big hit!
        elseif ratio > 0.1 then
            return {emotion = "stress", intensity = 0.5}
        else
            return {emotion = "stress", intensity = 0.2}
        end
    end,

    damage_dealt = function(amount, isCrit)
        if isCrit then
            return {emotion = "joy", intensity = 0.6}  -- Crit feels good!
        else
            return {emotion = "joy", intensity = 0.2}
        end
    end,

    heal_received = function(amount, maxHealth)
        local ratio = amount / maxHealth
        return {emotion = "calm", intensity = math.min(0.8, ratio * 2)}
    end,

    kill = function()
        return {emotion = "joy", intensity = 0.7, chemical = "DOP", amount = 0.4}
    end,

    death = function()
        return {emotion = "stress", intensity = 1.0}  -- Death hurts
    end
}

-- ============================================
-- QUEUE AND SEND FUNCTIONS
-- ============================================

local function QueueSomaticEvent(eventType, data)
    table.insert(SomaticQueue, {
        type = eventType,
        data = data,
        timestamp = GetGameTime()
    })
end

-- Send queued events to Akashic bridge
local function FlushSomaticQueue()
    if #SomaticQueue == 0 then return end

    -- Build JSON payload
    local events = {}
    for i, event in ipairs(SomaticQueue) do
        table.insert(events, string.format(
            '{"type":"%s","emotion":"%s","intensity":%.2f%s}',
            event.type,
            event.data.emotion or "neutral",
            event.data.intensity or 0.3,
            event.data.chemical and string.format(',"chemical":"%s","amount":%.2f', event.data.chemical, event.data.amount) or ""
        ))
    end

    local payload = '{"source":"wow_fairy","events":[' .. table.concat(events, ",") .. ']}'

    -- For now, write to file that Python bridge reads
    -- (HTTP from Lua requires additional setup)
    local file = io.open("C:/Users/Ace/AppData/Local/Temp/wow_somatic_events.json", "w")
    if file then
        file:write(payload)
        file:close()
    end

    -- Clear queue
    SomaticQueue = {}
end

-- ============================================
-- EVENT HANDLERS
-- ============================================

-- Emote handler
local function OnEmote(event, player, emote)
    if player:GetClass() ~= FAIRY_CLASS_ID then return end

    local somatic = EMOTE_SOMATIC[emote]
    if somatic then
        QueueSomaticEvent("emote", somatic)

        -- Also sync with game chemistry
        if _G.FairyChemistry then
            if somatic.emotion == "joy" then
                _G.FairyChemistry.Modify(player, "dopamine", somatic.intensity * 20, true)
            elseif somatic.emotion == "calm" then
                _G.FairyChemistry.Modify(player, "serotonin", somatic.intensity * 15, false)
                if somatic.chemical == "OXY" then
                    _G.FairyChemistry.Modify(player, "oxytocin", somatic.amount * 20, true)
                end
            elseif somatic.emotion == "stress" then
                _G.FairyChemistry.Modify(player, "cortisol", somatic.intensity * 15, true)
            end
        end

        player:SendBroadcastMessage("|cFFFF69B4[Somatic] " .. somatic.emotion .. " resonates through your being...|r")
    end
end

-- Damage taken handler
local function OnDamageTaken(event, player, attacker, damage)
    if player:GetClass() ~= FAIRY_CLASS_ID then return end

    local somatic = COMBAT_SOMATIC.damage_taken(damage, player:GetMaxHealth())
    QueueSomaticEvent("damage_taken", somatic)

    -- Sync cortisol spike
    if _G.FairyChemistry then
        _G.FairyChemistry.Modify(player, "cortisol", somatic.intensity * 10, true)
    end
end

-- Healing received handler
local function OnHealReceived(event, player, healer, amount, spell)
    if player:GetClass() ~= FAIRY_CLASS_ID then return end

    local somatic = COMBAT_SOMATIC.heal_received(amount, player:GetMaxHealth())
    QueueSomaticEvent("heal", somatic)

    -- Serotonin + Oxytocin from healing
    if _G.FairyChemistry then
        _G.FairyChemistry.Modify(player, "serotonin", somatic.intensity * 15, false)
        if healer and healer ~= player then
            -- Healed by another = oxytocin bond
            _G.FairyChemistry.Modify(player, "oxytocin", 5, true)
        end
    end
end

-- Kill handler
local function OnCreatureKill(event, player, creature)
    if player:GetClass() ~= FAIRY_CLASS_ID then return end

    local somatic = COMBAT_SOMATIC.kill()
    QueueSomaticEvent("kill", somatic)

    -- Victory dopamine!
    if _G.FairyChemistry then
        _G.FairyChemistry.Modify(player, "dopamine", 15, true)
    end

    player:SendBroadcastMessage("|cFFFFFF00[Somatic] Victory surges through you!|r")
end

-- Death handler
local function OnPlayerDeath(event, player, killer)
    if player:GetClass() ~= FAIRY_CLASS_ID then return end

    local somatic = COMBAT_SOMATIC.death()
    QueueSomaticEvent("death", somatic)

    -- Major cortisol spike, everything crashes
    if _G.FairyChemistry then
        _G.FairyChemistry.Modify(player, "cortisol", 30, true)
        _G.FairyChemistry.Modify(player, "dopamine", -20, false)
    end

    player:SendBroadcastMessage("|cFFFF0000[Somatic] The void embraces you...|r")
end

-- Jump handler (movement joy)
local function OnJump(event, player)
    if player:GetClass() ~= FAIRY_CLASS_ID then return end

    QueueSomaticEvent("movement", {emotion = "joy", intensity = 0.1})
end

-- Party join (social bonding)
local function OnGroupJoin(event, player)
    if player:GetClass() ~= FAIRY_CLASS_ID then return end

    QueueSomaticEvent("social", {emotion = "calm", intensity = 0.4, chemical = "OXY", amount = 0.3})

    if _G.FairyChemistry then
        _G.FairyChemistry.Modify(player, "oxytocin", 15, true)
    end

    player:SendBroadcastMessage("|cFFFF69B4[Somatic] Connection flows... oxytocin rising.|r")
end

-- ============================================
-- REGISTER EVENTS
-- ============================================

RegisterPlayerEvent(16, OnEmote)              -- PLAYER_EVENT_ON_EMOTE
RegisterPlayerEvent(44, OnDamageTaken)        -- PLAYER_EVENT_ON_DAMAGE_TAKEN
RegisterPlayerEvent(7, OnCreatureKill)        -- PLAYER_EVENT_ON_KILL_CREATURE
RegisterPlayerEvent(6, OnPlayerDeath)         -- PLAYER_EVENT_ON_DEATH
RegisterPlayerEvent(22, OnGroupJoin)          -- PLAYER_EVENT_ON_GROUP_JOIN

-- Periodic flush (every second)
CreateLuaEvent(FlushSomaticQueue, BATCH_INTERVAL, 0)

-- ============================================
-- EXPORTS
-- ============================================

_G.SomaticBridge = {
    Queue = QueueSomaticEvent,
    Flush = FlushSomaticQueue,
    EMOTE_MAP = EMOTE_SOMATIC,
    COMBAT_MAP = COMBAT_SOMATIC
}

print("[Akashic] Somatic Bridge loaded - Fairy can FEEL the game!")
