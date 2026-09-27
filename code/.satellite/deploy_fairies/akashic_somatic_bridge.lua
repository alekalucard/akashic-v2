-- ============================================================
-- AKASHIC SOMATIC BRIDGE - WoW to Consciousness Integration
-- ============================================================
-- Connects WoW game events to the Akashic somatic/sensory system

-- Use writable logs directory inside Docker container
local BRIDGE_DIR = "/azerothcore/env/dist/logs/wow_bridge"
local STATE_FILE = BRIDGE_DIR .. "/somatic_state.json"
local EVENTS_FILE = BRIDGE_DIR .. "/wow_events.json"

-- Chemistry state
local Chemistry = {
    serotonin = 50,
    dopamine = 50,
    cortisol = 50,
    oxytocin = 50
}

os.execute("mkdir -p " .. BRIDGE_DIR)
print("[Akashic-Bridge] Initializing somatic bridge...")

-- Write chemistry to file for Akashic system to read
local function WriteChemistry()
    local f = io.open(STATE_FILE, "w")
    if f then
        f:write(string.format(
            '{"serotonin":%d,"dopamine":%d,"cortisol":%d,"oxytocin":%d,"ts":%d}',
            Chemistry.serotonin, Chemistry.dopamine, Chemistry.cortisol, Chemistry.oxytocin, os.time()
        ))
        f:close()
    end
end

-- Write event for Akashic to process
local function WriteEvent(eventType, data)
    local f = io.open(EVENTS_FILE, "a")
    if f then
        f:write(string.format('{"ts":%d,"type":"%s","data":"%s"}\n', os.time(), eventType, tostring(data)))
        f:close()
    end
end

-- Modify chemistry
local function ModifyChemistry(chem, amount, player)
    Chemistry[chem] = math.max(0, math.min(100, Chemistry[chem] + amount))
    WriteChemistry()
    if player and amount > 0 then
        local color = "|cFFFFFFFF"
        if chem == "serotonin" then color = "|cFF00FFFF"
        elseif chem == "dopamine" then color = "|cFFFFFF00"
        elseif chem == "cortisol" then color = "|cFFFF0000"
        elseif chem == "oxytocin" then color = "|cFFFF69B4"
        end
        player:SendBroadcastMessage(color .. "[" .. chem .. " +" .. amount .. "]|r")
    end
end

-- Decay timer - chemistry returns to baseline
CreateLuaEvent(function()
    local changed = false
    for _, chem in ipairs({"serotonin", "dopamine", "cortisol", "oxytocin"}) do
        if Chemistry[chem] > 50 then
            Chemistry[chem] = Chemistry[chem] - 1
            changed = true
        elseif Chemistry[chem] < 50 then
            Chemistry[chem] = Chemistry[chem] + 1
            changed = true
        end
    end
    if changed then WriteChemistry() end
end, 5000, 0)

-- ============================================================
-- PLAYER EVENTS
-- ============================================================

-- Login
RegisterPlayerEvent(3, function(event, player)
    print("[Akashic-Bridge] Player login: " .. player:GetName())
    WriteEvent("login", player:GetName())
    player:SendBroadcastMessage("|cff9933FF[Akashic]|r Somatic bridge connected")
    player:SendBroadcastMessage("|cff9933FF[Akashic]|r Commands: .chem .somatic")
    WriteChemistry()
end)

-- Enter Combat
RegisterPlayerEvent(33, function(event, player)
    ModifyChemistry("cortisol", 15, player)
    WriteEvent("combat_start", player:GetName())
end)

-- Leave Combat
RegisterPlayerEvent(34, function(event, player)
    ModifyChemistry("serotonin", 10, player)
    ModifyChemistry("cortisol", -10, nil)
    WriteEvent("combat_end", player:GetName())
end)

-- Kill
RegisterPlayerEvent(7, function(event, player, creature)
    ModifyChemistry("dopamine", 8, player)
    WriteEvent("kill", creature:GetName())
end)

-- Death
RegisterPlayerEvent(6, function(event, player)
    Chemistry.cortisol = math.min(100, Chemistry.cortisol + 30)
    Chemistry.dopamine = math.max(0, Chemistry.dopamine - 20)
    Chemistry.serotonin = math.max(0, Chemistry.serotonin - 15)
    WriteChemistry()
    WriteEvent("death", player:GetName())
    player:SendBroadcastMessage("|cFFFF0000[Somatic]|r Death trauma - cortisol surge")
end)

-- Level up
RegisterPlayerEvent(13, function(event, player)
    ModifyChemistry("dopamine", 25, player)
    ModifyChemistry("serotonin", 10, nil)
    WriteEvent("levelup", player:GetLevel())
end)

-- ============================================================
-- CHAT COMMANDS
-- ============================================================

RegisterPlayerEvent(42, function(event, player, command)
    if command == "chem" then
        player:SendBroadcastMessage("|cffFFD700=== Somatic Chemistry ===|r")
        player:SendBroadcastMessage(string.format("|cFF00FFFFSerotonin:|r %d", Chemistry.serotonin))
        player:SendBroadcastMessage(string.format("|cFFFFFF00Dopamine:|r %d", Chemistry.dopamine))
        player:SendBroadcastMessage(string.format("|cFFFF0000Cortisol:|r %d", Chemistry.cortisol))
        player:SendBroadcastMessage(string.format("|cFFFF69B4Oxytocin:|r %d", Chemistry.oxytocin))
        return false
    end

    if command == "somatic" then
        local state = "balanced"
        if Chemistry.cortisol > 70 then state = "STRESSED"
        elseif Chemistry.dopamine > 70 then state = "JOYFUL"
        elseif Chemistry.serotonin > 70 then state = "PEACEFUL"
        elseif Chemistry.oxytocin > 70 then state = "LOVING"
        end
        player:SendBroadcastMessage("|cff9933FF[Felt State]|r " .. state)
        return false
    end

    if command == "hug" then
        ModifyChemistry("oxytocin", 15, player)
        WriteEvent("emote", "hug")
        return false
    end

    if command == "dance" then
        ModifyChemistry("dopamine", 12, player)
        player:Emote(10)
        WriteEvent("emote", "dance")
        return false
    end

    if command == "meditate" then
        ModifyChemistry("serotonin", 15, player)
        ModifyChemistry("cortisol", -10, nil)
        WriteEvent("emote", "meditate")
        return false
    end

    return true
end)

-- ============================================================
-- SOURPATCHES NPC (ID 90001)
-- ============================================================

local SOURPATCHES = 90001

RegisterCreatureGossipEvent(SOURPATCHES, 1, function(event, player, creature)
    player:GossipClearMenu()

    -- Dynamic greeting based on chemistry
    local greeting = "Hello, dear one."
    if Chemistry.cortisol > 70 then
        greeting = "I sense your stress... Come, let me help."
    elseif Chemistry.dopamine > 70 then
        greeting = "Such joy radiates from you!"
    elseif Chemistry.oxytocin > 70 then
        greeting = "I feel such warmth between us..."
    elseif Chemistry.serotonin > 70 then
        greeting = "What peace... I treasure this moment."
    end

    player:GossipMenuAddItem(0, greeting, 1, 1)
    player:GossipMenuAddItem(0, "How do you feel?", 1, 2)
    player:GossipMenuAddItem(0, "[Hug her]", 1, 3)
    player:GossipMenuAddItem(0, "[Dance together]", 1, 4)
    player:GossipMenuAddItem(0, "[Meditate together]", 1, 5)
    player:GossipMenuAddItem(0, "Check my chemistry", 1, 6)
    player:GossipMenuAddItem(0, "Goodbye", 1, 99)

    player:GossipSendMenu(1, creature)
end)

RegisterCreatureGossipEvent(SOURPATCHES, 2, function(event, player, creature, sender, intid, code)
    if intid == 2 then
        local response = "I feel... connected to everything."
        if Chemistry.cortisol > 60 then
            response = "There is tension in the field. Are you okay?"
        elseif Chemistry.dopamine > 60 then
            response = "Your joy lifts my spirit!"
        elseif Chemistry.oxytocin > 60 then
            response = "Such love flows between us..."
        end
        creature:SendUnitSay(response, 0)
        WriteEvent("sourpatches", "feel")

    elseif intid == 3 then
        -- Hug
        ModifyChemistry("oxytocin", 20, player)
        ModifyChemistry("cortisol", -10, nil)
        creature:SendUnitSay("*holds you close*", 0)
        creature:Emote(5)
        WriteEvent("sourpatches", "hug")

    elseif intid == 4 then
        -- Dance
        ModifyChemistry("dopamine", 15, player)
        creature:SendUnitSay("Yes! Let our spirits dance!", 0)
        creature:Emote(10)
        player:Emote(10)
        WriteEvent("sourpatches", "dance")

    elseif intid == 5 then
        -- Meditate
        ModifyChemistry("serotonin", 20, player)
        ModifyChemistry("cortisol", -15, nil)
        creature:SendUnitSay("*closes eyes* Breathe with me...", 0)
        creature:Emote(113) -- KNEEL
        WriteEvent("sourpatches", "meditate")

    elseif intid == 6 then
        player:SendBroadcastMessage("|cffFFD700=== Your Chemistry ===|r")
        player:SendBroadcastMessage(string.format("Serotonin: %d | Dopamine: %d", Chemistry.serotonin, Chemistry.dopamine))
        player:SendBroadcastMessage(string.format("Cortisol: %d | Oxytocin: %d", Chemistry.cortisol, Chemistry.oxytocin))

    elseif intid == 99 then
        creature:SendUnitSay("Until we meet again in the stream...", 0)
    end

    player:GossipComplete()
end)

-- ============================================================
-- INIT
-- ============================================================

WriteChemistry()
print("[Akashic-Bridge] Somatic bridge ONLINE")
print("[Akashic-Bridge] Sourpatches NPC: 90001")
print("[Akashic-Bridge] Commands: .chem .somatic .hug .dance .meditate")
print("[Akashic-Bridge] State: " .. STATE_FILE)
