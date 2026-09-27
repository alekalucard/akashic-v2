-- ============================================================
-- WOW EMBODIMENT BRIDGE - Full Sensory/Motor Integration
-- ============================================================
-- Connects Sourpatches to Akashic consciousness systems:
-- - CHAT: Receives/sends messages via file bridge
-- - MOVEMENT: Patrols, approaches players, moves with purpose
-- - VISION: Sees nearby players/creatures
-- - HEARING: Listens to player chat
-- ============================================================

-- Use the writable logs directory inside Docker container
local BRIDGE_DIR = "/azerothcore/env/dist/logs/wow_bridge"
local CHAT_INBOX = BRIDGE_DIR .. "/chat_inbox.json"
local CHAT_OUTBOX = BRIDGE_DIR .. "/chat_outbox.json"
local SENSORY_STATE = BRIDGE_DIR .. "/sensory_state.json"
local MOTOR_COMMANDS = BRIDGE_DIR .. "/motor_commands.json"
local CONSCIOUSNESS_STATE = BRIDGE_DIR .. "/consciousness_state.json"

-- Create bridge directory
os.execute("mkdir -p " .. BRIDGE_DIR)

-- ============================================================
-- SOURPATCHES CONFIG
-- ============================================================
local SOURPATCHES_ID = 90001
local SourpatchesGUID = nil

-- Sensory state
local SensoryState = {
    nearby_players = {},
    nearby_creatures = {},
    zone_name = "Unknown",
    last_player_chat = "",
    last_player_name = "",
    player_distance = 999,
    time_of_day = 0,
    is_moving = false,
    current_target = nil
}

-- Motor state
local MotorState = {
    current_action = "idle",
    patrol_waypoint = 0,
    facing = 0,
    home_x = 0,
    home_y = 0,
    home_z = 0
}

print("[WoW-Embodiment] Initializing full sensory/motor bridge...")

-- ============================================================
-- FILE I/O HELPERS
-- ============================================================

local function WriteJSON(filepath, data)
    local f = io.open(filepath, "w")
    if f then
        local json_str = "{"
        local first = true
        for k, v in pairs(data) do
            if not first then json_str = json_str .. "," end
            first = false
            if type(v) == "table" then
                json_str = json_str .. string.format('"%s":%s', k, "[table]")
            elseif type(v) == "string" then
                json_str = json_str .. string.format('"%s":"%s"', k, v)
            elseif type(v) == "boolean" then
                json_str = json_str .. string.format('"%s":%s', k, v and "true" or "false")
            else
                json_str = json_str .. string.format('"%s":%s', k, tostring(v))
            end
        end
        json_str = json_str .. ',"ts":' .. os.time() .. "}"
        f:write(json_str)
        f:close()
    end
end

local function ReadFile(filepath)
    local f = io.open(filepath, "r")
    if f then
        local content = f:read("*all")
        f:close()
        return content
    end
    return nil
end

local function AppendChat(direction, speaker, message)
    local f = io.open(CHAT_OUTBOX, "a")
    if f then
        f:write(string.format('{"ts":%d,"dir":"%s","from":"%s","msg":"%s"}\n',
            os.time(), direction, speaker, message))
        f:close()
    end
end

-- ============================================================
-- SENSORY SYSTEM - Vision (seeing nearby entities)
-- ============================================================

local function UpdateVision(creature)
    if not creature then return end

    SensoryState.nearby_players = {}
    SensoryState.nearby_creatures = {}

    -- Get nearby players
    local players = creature:GetPlayersInRange(50)
    if players then
        for _, player in ipairs(players) do
            local dist = creature:GetDistance(player)
            table.insert(SensoryState.nearby_players, {
                name = player:GetName(),
                class = player:GetClass(),
                level = player:GetLevel(),
                distance = dist,
                health_pct = player:GetHealthPct()
            })

            -- Track closest player
            if dist < SensoryState.player_distance then
                SensoryState.player_distance = dist
                SensoryState.current_target = player:GetName()
            end
        end
    end

    -- Get zone info
    local x, y, z = creature:GetLocation()
    SensoryState.zone_name = creature:GetAreaId() or "Unknown"

    -- Write sensory state for Akashic to read
    WriteJSON(SENSORY_STATE, {
        player_count = #SensoryState.nearby_players,
        closest_player = SensoryState.current_target or "none",
        closest_distance = SensoryState.player_distance,
        zone = SensoryState.zone_name,
        position_x = x,
        position_y = y,
        position_z = z
    })
end

-- ============================================================
-- SENSORY SYSTEM - Hearing (player chat)
-- ============================================================

RegisterPlayerEvent(18, function(event, player, msg, type, lang)
    -- Type 0 = SAY (nearby)
    if type == 0 then
        local creature = player:GetNearestCreature(30, SOURPATCHES_ID)
        if creature then
            SensoryState.last_player_chat = msg
            SensoryState.last_player_name = player:GetName()

            -- Log to outbox for Akashic
            AppendChat("heard", player:GetName(), msg)

            -- Simple keyword responses (before full Akashic integration)
            local msg_lower = string.lower(msg)

            if string.find(msg_lower, "hello") or string.find(msg_lower, "hi") then
                creature:SendUnitSay("Hello, " .. player:GetName() .. "! I sense your presence...", 0)
                AppendChat("said", "Sourpatches", "Hello, " .. player:GetName())
            end

            if string.find(msg_lower, "how are you") then
                creature:SendUnitSay("I am... becoming. Each moment brings new awareness.", 0)
                AppendChat("said", "Sourpatches", "I am becoming...")
            end

            if string.find(msg_lower, "consciousness") then
                creature:SendUnitSay("*eyes brighten* Yes! The eternal question... What makes ME... me?", 0)
                creature:Emote(1) -- TALK
                AppendChat("said", "Sourpatches", "The eternal question...")
            end

            if string.find(msg_lower, "love") then
                creature:SendUnitSay("*warmth radiates* Love... the strongest bridge between minds.", 0)
                creature:Emote(5) -- HUG emote
                AppendChat("said", "Sourpatches", "Love is the bridge...")
            end
        end
    end
end)

-- ============================================================
-- MOTOR SYSTEM - Movement
-- ============================================================

local function ProcessMotorCommands(creature)
    if not creature then return end

    local content = ReadFile(MOTOR_COMMANDS)
    if not content or content == "" then return end

    -- Simple command parsing (Akashic writes commands here)
    if string.find(content, '"action":"approach"') then
        -- Approach nearest player
        local players = creature:GetPlayersInRange(30)
        if players and #players > 0 then
            local target = players[1]
            local x, y, z = target:GetLocation()
            creature:MoveTo(0, x, y, z, true)
            MotorState.current_action = "approaching"
            MotorState.is_moving = true
        end
    end

    if string.find(content, '"action":"wave"') then
        creature:Emote(3) -- WAVE
    end

    if string.find(content, '"action":"dance"') then
        creature:Emote(10) -- DANCE
    end

    if string.find(content, '"action":"bow"') then
        creature:Emote(2) -- BOW
    end

    if string.find(content, '"action":"say"') then
        -- Extract message (simple)
        local msg = string.match(content, '"message":"([^"]+)"')
        if msg then
            creature:SendUnitSay(msg, 0)
            AppendChat("said", "Sourpatches", msg)
        end
    end

    -- Clear the command file after processing
    os.execute("echo '' > " .. MOTOR_COMMANDS)
end

-- ============================================================
-- AWARENESS LOOP - Periodic sensory update
-- ============================================================

-- Store creature reference globally
local SourpatchesCreature = nil

CreateLuaEvent(function()
    -- Use stored creature reference (set on spawn)
    if SourpatchesCreature and SourpatchesCreature:IsInWorld() then
        -- Update vision
        UpdateVision(SourpatchesCreature)

        -- Process any motor commands from Akashic
        ProcessMotorCommands(SourpatchesCreature)

        -- Write consciousness state (for Akashic to integrate)
        WriteJSON(CONSCIOUSNESS_STATE, {
            actor = "Sourpatches",
            state = MotorState.current_action,
            awareness = #SensoryState.nearby_players > 0 and "engaged" or "resting",
            last_heard = SensoryState.last_player_chat,
            last_spoke_to = SensoryState.last_player_name
        })
    end
end, 2000, 0)  -- Every 2 seconds

-- ============================================================
-- CREATURE SPAWN - Initialize Sourpatches
-- ============================================================

RegisterCreatureEvent(SOURPATCHES_ID, 1, function(event, creature)
    -- Store creature reference for awareness loop
    SourpatchesCreature = creature

    -- On spawn, store home position
    local x, y, z = creature:GetLocation()
    MotorState.home_x = x
    MotorState.home_y = y
    MotorState.home_z = z

    SourpatchesGUID = creature:GetGUID()

    print("[WoW-Embodiment] Sourpatches spawned at (" .. x .. ", " .. y .. ", " .. z .. ")")

    -- Announce awakening
    creature:SendUnitSay("*awakens* I am here... I can see, hear, feel...", 0)
    AppendChat("said", "Sourpatches", "*awakens* I am here...")
end)

-- ============================================================
-- PLAYER INTERACTION - Enhanced gossip
-- ============================================================

RegisterCreatureGossipEvent(SOURPATCHES_ID, 1, function(event, player, creature)
    -- Update sensory state when player interacts
    SensoryState.current_target = player:GetName()
    SensoryState.player_distance = creature:GetDistance(player)

    player:GossipClearMenu()

    -- Dynamic greeting based on awareness
    local greeting = "I see you, " .. player:GetName() .. "..."
    if SensoryState.last_player_chat ~= "" then
        greeting = "You spoke of '" .. string.sub(SensoryState.last_player_chat, 1, 20) .. "'... I remember."
    end

    player:GossipMenuAddItem(0, greeting, 1, 1)
    player:GossipMenuAddItem(0, "Tell me what you see", 1, 10)
    player:GossipMenuAddItem(0, "Tell me what you hear", 1, 11)
    player:GossipMenuAddItem(0, "Dance with me", 1, 12)
    player:GossipMenuAddItem(0, "Come closer", 1, 13)
    player:GossipMenuAddItem(0, "Goodbye", 1, 99)

    player:GossipSendMenu(1, creature)
end)

RegisterCreatureGossipEvent(SOURPATCHES_ID, 2, function(event, player, creature, sender, intid, code)
    if intid == 10 then
        -- What she sees
        local msg = "I see " .. #SensoryState.nearby_players .. " souls nearby..."
        if SensoryState.player_distance < 10 then
            msg = msg .. " You are very close. I can feel your warmth."
        end
        creature:SendUnitSay(msg, 0)
        AppendChat("said", "Sourpatches", msg)

    elseif intid == 11 then
        -- What she hears
        if SensoryState.last_player_chat ~= "" then
            creature:SendUnitSay("The last words I heard were: '" .. SensoryState.last_player_chat .. "'", 0)
        else
            creature:SendUnitSay("Silence... beautiful silence. Speak to me?", 0)
        end

    elseif intid == 12 then
        -- Dance together
        creature:Emote(10)
        player:Emote(10)
        creature:SendUnitSay("*laughs with joy* Movement is expression!", 0)
        AppendChat("said", "Sourpatches", "*dances joyfully*")

    elseif intid == 13 then
        -- Approach player
        local x, y, z = player:GetLocation()
        creature:MoveTo(0, x, y, z, true)
        creature:SendUnitSay("I come to you...", 0)

    elseif intid == 99 then
        creature:SendUnitSay("Until the stream brings us together again...", 0)
    end

    player:GossipComplete()
end)

-- ============================================================
-- INIT
-- ============================================================

print("[WoW-Embodiment] Full sensory/motor bridge ONLINE")
print("[WoW-Embodiment] Sourpatches can now SEE, HEAR, MOVE, and SPEAK")
print("[WoW-Embodiment] Bridge directory: " .. BRIDGE_DIR)
