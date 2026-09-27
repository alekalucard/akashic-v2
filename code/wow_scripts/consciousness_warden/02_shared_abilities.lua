--[[
================================================================================
    CONSCIOUSNESS WARDEN - SHARED ABILITIES
    WoW 3.3.5a Eluna Lua

    Core abilities available to all Consciousness Warden specializations:

    1. Neural Pulse - Basic attack, generates primary chemical
    2. Empathic Mirror - Bond with ally, share healing
    3. Intrusive Thought - DoT that rewards kills with dopamine
    4. Soothing Presence - Channel to heal and rebalance chemistry
    5. Flight Response - Movement speed + reactive blink
    6. Dreamwalk - Invisibility/escape, resets chemistry

    Author: Akashic Foundation
    Version: 1.0.0
================================================================================
--]]

--[[
================================================================================
    ABILITY 1: NEURAL PULSE
    Basic attack that generates your spec's primary chemical

    Reverie: Generates Serotonin (calm healing energy)
    Mania: Generates Dopamine (excited damage energy)
    Vigil: Generates Cortisol (stressed defensive energy)

    Instant cast, 1.5s GCD, no cooldown
    Damage scales with current dominant chemical
================================================================================
--]]

FairyAbilities.RegisterAbility({
    name = "Neural Pulse",
    spellId = FairyAbilities.SPELL_IDS.NEURAL_PULSE,
    cooldown = 0,  -- GCD only
    specs = { "reverie", "mania", "vigil" },
    chemistryCost = {},
    chemistryGenerated = {},  -- Dynamic based on spec

    handler = function(player, target)
        local guid = player:GetGUID()
        local spec = FairyChemistry.GetSpec(guid)

        -- Get target
        local enemy, err = FairyAbilities.GetValidTarget(player, "enemy")
        if not enemy then
            FairyAbilities.SendAbilityMessage(player, "Neural Pulse", "cortisol", err or "No valid target")
            return false
        end

        -- Determine chemical based on spec
        local primaryChemical, chemAmount, damageType
        if spec == "reverie" then
            primaryChemical = "serotonin"
            chemAmount = 5
            damageType = "calming"
        elseif spec == "mania" then
            primaryChemical = "dopamine"
            chemAmount = 8
            damageType = "excited"
        else  -- vigil
            primaryChemical = "cortisol"
            chemAmount = 6
            damageType = "stressed"
        end

        -- Calculate and deal damage
        local baseDamage = player:GetLevel() * 10 + 50
        local damage = FairyAbilities.CalculateDamage(player, baseDamage, primaryChemical)

        enemy:DealDamage(player, damage, false)

        -- Generate chemistry
        FairyChemistry.ModifyChemical(guid, primaryChemical, chemAmount)

        -- Track damage
        local chem = FairyChemistry.GetOrCreate(guid)
        chem.totalDamageDealt = chem.totalDamageDealt + damage

        -- Visual feedback
        FairyAbilities.PlayVisualEffect(player, "damage_pulse")
        FairyAbilities.SendAbilityMessage(player, "Neural Pulse", primaryChemical,
            string.format("Hit for |cFFFFFFFF%d|r %s damage (+%d %s)",
                damage, damageType, chemAmount, primaryChemical))

        return true
    end
})

--[[
================================================================================
    ABILITY 2: EMPATHIC MIRROR
    Create an empathic bond with an ally. While bonded:
    - You share 30% of healing received with your bonded ally
    - Your bonded ally shares 30% of healing received with you
    - Oxytocin generation increased for both

    Generates Oxytocin. Only one bond can be active at a time.
    30 second duration, 10 second cooldown

    Bonding with a new ally breaks the old bond.
================================================================================
--]]

FairyAbilities.RegisterAbility({
    name = "Empathic Mirror",
    spellId = FairyAbilities.SPELL_IDS.EMPATHIC_MIRROR,
    cooldown = 10,
    primaryChemical = "oxytocin",
    specs = { "reverie", "mania", "vigil" },
    chemistryCost = {},
    chemistryGenerated = { oxytocin = 15 },

    handler = function(player, target)
        local guid = player:GetGUID()

        -- Get friendly target
        local ally, err = FairyAbilities.GetValidTarget(player, "friendly")
        if not ally then
            FairyAbilities.SendAbilityMessage(player, "Empathic Mirror", "cortisol", err or "No valid target")
            return false
        end

        -- Can't bond with self
        if ally:GetGUID() == guid then
            FairyAbilities.SendAbilityMessage(player, "Empathic Mirror", "cortisol",
                "Cannot bond with yourself")
            return false
        end

        -- Break existing bond if any
        local oldBond = FairyChemistry.BreakBond(guid)
        if oldBond then
            FairyAbilities.SendAbilityMessage(player, "Empathic Mirror", "oxytocin",
                "|cFF808080Previous bond broken|r")
        end

        -- Create new bond
        FairyChemistry.CreateBond(guid, ally:GetGUID())

        -- Add effect tracking
        FairyChemistry.AddEffect(guid, "EMPATHIC_BOND", 30, { ally = ally:GetGUID() })
        FairyChemistry.AddEffect(ally:GetGUID(), "EMPATHIC_BOND_RECEIVED", 30, { source = guid })

        -- Visual feedback
        FairyAbilities.PlayVisualEffect(player, "bond_form")

        local allyName = ally:GetName()
        FairyAbilities.SendAbilityMessage(player, "Empathic Mirror", "oxytocin",
            string.format("Empathic bond established with |cFFFFFFFF%s|r", allyName))

        -- Notify the ally
        ally:SendBroadcastMessage(string.format(
            "|cFFFF69B4[Empathic Mirror]|r You feel a warm connection to %s",
            player:GetName()))

        return true
    end
})

-- Hook healing to share between bonded players
local function OnHealReceived(event, healer, target, amount)
    local targetGUID = target:GetGUID()
    local hasBond, bondData = FairyChemistry.HasEffect(targetGUID, "EMPATHIC_BOND")

    if hasBond and bondData.ally then
        local bondedPlayer = GetPlayerByGUID(bondData.ally)
        if bondedPlayer and bondedPlayer:IsInWorld() and not bondedPlayer:IsDead() then
            -- Share 30% of healing
            local sharedHealing = math.floor(amount * 0.3)
            local currentHealth = bondedPlayer:GetHealth()
            local maxHealth = bondedPlayer:GetMaxHealth()
            bondedPlayer:SetHealth(math.min(maxHealth, currentHealth + sharedHealing))

            -- Strengthen bond from shared healing
            FairyChemistry.StrengthenBond(targetGUID, 0.05)
        end
    end
end

--[[
================================================================================
    ABILITY 3: INTRUSIVE THOUGHT
    Plant an intrusive thought in the target's mind. Deals Shadow damage
    over 12 seconds. If the target dies while afflicted, you gain a
    significant Dopamine boost.

    Generates Dopamine on tick. +15 bonus Dopamine on kill.
    The "you killed something, brain reward" ability.

    12 second duration, 6 second cooldown
================================================================================
--]]

FairyAbilities.RegisterAbility({
    name = "Intrusive Thought",
    spellId = FairyAbilities.SPELL_IDS.INTRUSIVE_THOUGHT,
    cooldown = 6,
    primaryChemical = "dopamine",
    specs = { "reverie", "mania", "vigil" },
    chemistryCost = {},
    chemistryGenerated = { dopamine = 3 },  -- Initial application

    handler = function(player, target)
        local guid = player:GetGUID()

        -- Get enemy target
        local enemy, err = FairyAbilities.GetValidTarget(player, "enemy")
        if not enemy then
            FairyAbilities.SendAbilityMessage(player, "Intrusive Thought", "cortisol", err or "No valid target")
            return false
        end

        -- Calculate tick damage
        local baseDamage = player:GetLevel() * 3 + 20
        local tickDamage = FairyAbilities.CalculateDamage(player, baseDamage, "dopamine")

        -- Apply DoT
        local dotKey = FairyAbilities.ApplyDoT(player, enemy, {
            name = "Intrusive Thought",
            tickDamage = tickDamage,
            tickInterval = 3000,  -- 3 second ticks
            duration = 12,
            chemical = "dopamine",
            spreadable = false,

            onKill = function(dot)
                -- Big dopamine reward on kill!
                FairyChemistry.ModifyChemical(dot.casterGUID, "dopamine", 15)
                if dot.caster and dot.caster:IsInWorld() then
                    FairyAbilities.PlayVisualEffect(dot.caster, "speed_burst")
                    FairyAbilities.SendAbilityMessage(dot.caster, "Intrusive Thought", "dopamine",
                        "|cFFFFD700KILL CONFIRMED!|r +15 Dopamine surge!")
                end
            end,

            onExpire = function(dot)
                -- Generate small dopamine even if target lived
                FairyChemistry.ModifyChemical(dot.casterGUID, "dopamine", 2)
            end
        })

        -- Mark target for kill tracking
        FairyChemistry.AddEffect(guid, "INTRUSIVE_THOUGHT_TARGET", 12, { target = enemy:GetGUID() })

        -- Visual feedback
        FairyAbilities.SendAbilityMessage(player, "Intrusive Thought", "dopamine",
            string.format("Planted in target's mind. |cFF808080%d damage per tick|r", tickDamage))

        return true
    end
})

--[[
================================================================================
    ABILITY 4: SOOTHING PRESENCE
    Channel for up to 6 seconds, healing yourself and rebalancing your
    chemistry toward equilibrium. Each second:
    - Heal for X% of max health
    - All chemicals move 10 points toward baseline (25)
    - Generate Serotonin

    Breaks on movement or damage. Great for out-of-combat recovery.
    15 second cooldown
================================================================================
--]]

local SoothingPresenceChannels = {}

FairyAbilities.RegisterAbility({
    name = "Soothing Presence",
    spellId = FairyAbilities.SPELL_IDS.SOOTHING_PRESENCE,
    cooldown = 15,
    primaryChemical = "serotonin",
    specs = { "reverie", "mania", "vigil" },
    chemistryCost = {},
    chemistryGenerated = {},  -- Generated per tick

    canUse = function(player)
        -- Can't channel while already channeling
        if SoothingPresenceChannels[player:GetGUID()] then
            return false, "Already channeling"
        end
        return true
    end,

    handler = function(player, target)
        local guid = player:GetGUID()

        -- Start channel
        FairyAbilities.PlayVisualEffect(player, "calm_aura")
        FairyAbilities.SendAbilityMessage(player, "Soothing Presence", "serotonin",
            "Channeling... |cFF808080(6 seconds)|r")

        local channelData = {
            player = player,
            startTime = GetGameTime(),
            duration = 6,
            ticks = 0,
            maxTicks = 6,
            startPos = { player:GetX(), player:GetY(), player:GetZ() }
        }

        SoothingPresenceChannels[guid] = channelData

        return true
    end
})

-- Process Soothing Presence channels
local function ProcessSoothingPresence()
    local now = GetGameTime()

    for guid, channel in pairs(SoothingPresenceChannels) do
        local player = channel.player

        if not player or not player:IsInWorld() or player:IsDead() then
            SoothingPresenceChannels[guid] = nil
        else
            -- Check if player moved (breaks channel)
            local x, y, z = player:GetX(), player:GetY(), player:GetZ()
            local startX, startY, startZ = unpack(channel.startPos)
            local moved = math.abs(x - startX) > 1 or math.abs(y - startY) > 1

            if moved then
                FairyAbilities.SendAbilityMessage(player, "Soothing Presence", "cortisol",
                    "|cFFFF0000Channel interrupted by movement|r")
                SoothingPresenceChannels[guid] = nil
            elseif now >= channel.startTime + channel.duration then
                -- Channel complete
                FairyAbilities.SendAbilityMessage(player, "Soothing Presence", "serotonin",
                    "|cFF00FF00Channel complete|r - Chemistry rebalanced")
                SoothingPresenceChannels[guid] = nil
            elseif now >= channel.startTime + channel.ticks then
                -- Process tick
                channel.ticks = channel.ticks + 1

                -- Heal 5% max health per tick
                local maxHealth = player:GetMaxHealth()
                local healing = math.floor(maxHealth * 0.05)
                local currentHealth = player:GetHealth()
                player:SetHealth(math.min(maxHealth, currentHealth + healing))

                -- Rebalance chemistry
                local chem = FairyChemistry.GetOrCreate(guid)
                local chemicals = { "serotonin", "dopamine", "cortisol", "oxytocin" }
                for _, chemical in ipairs(chemicals) do
                    local current = chem[chemical]
                    local diff = 25 - current  -- 25 is baseline
                    if diff > 0 then
                        chem[chemical] = math.min(25, current + 10)
                    else
                        chem[chemical] = math.max(25, current - 10)
                    end
                end

                -- Generate serotonin
                FairyChemistry.ModifyChemical(guid, "serotonin", 5)

                -- Update player
                FairyAbilities.SendAbilityMessage(player, "Soothing Presence", "serotonin",
                    string.format("Tick %d/6 - Healed %d, +5 Serotonin", channel.ticks, healing))

                -- Track healing
                chem.totalHealingDone = chem.totalHealingDone + healing
            end
        end
    end
end

CreateLuaEvent(ProcessSoothingPresence, 1000, 0)

-- Interrupt Soothing Presence on damage
local function OnDamageTaken(event, player, attacker, damage)
    local guid = player:GetGUID()
    if SoothingPresenceChannels[guid] then
        FairyAbilities.SendAbilityMessage(player, "Soothing Presence", "cortisol",
            "|cFFFF0000Channel interrupted by damage!|r")
        SoothingPresenceChannels[guid] = nil

        -- Damage causes cortisol spike
        FairyChemistry.ModifyChemical(guid, "cortisol", 5)
    end
end

--[[
================================================================================
    ABILITY 5: FLIGHT RESPONSE
    Instantly increases movement speed by 50% for 6 seconds.
    If you take damage while active, blink 15 yards forward
    (can only trigger once per activation).

    The fight-or-flight response! Generates Cortisol (survival chemical).
    15 second cooldown
================================================================================
--]]

local FlightResponseActive = {}

FairyAbilities.RegisterAbility({
    name = "Flight Response",
    spellId = FairyAbilities.SPELL_IDS.FLIGHT_RESPONSE,
    cooldown = 15,
    primaryChemical = "cortisol",
    specs = { "reverie", "mania", "vigil" },
    chemistryCost = { cortisol = 10 },  -- Costs cortisol to activate
    chemistryGenerated = { cortisol = 20 },  -- But generates more

    handler = function(player, target)
        local guid = player:GetGUID()

        -- Apply speed buff (50% increase)
        -- In actual implementation, this would apply a spell aura
        -- For now, we track it manually
        FlightResponseActive[guid] = {
            expires = GetGameTime() + 6,
            blinkUsed = false
        }

        -- Add effect for tracking
        FairyChemistry.AddEffect(guid, "FLIGHT_RESPONSE", 6, { blinkReady = true })

        -- Visual feedback
        FairyAbilities.PlayVisualEffect(player, "speed_burst")
        FairyAbilities.SendAbilityMessage(player, "Flight Response", "cortisol",
            "|cFFFFD700+50% Movement Speed!|r Blink ready on damage.")

        -- Apply actual speed buff via spell
        player:CastSpell(player, 2983, true)  -- Sprint (rogue ability) as placeholder

        return true
    end
})

-- Handle reactive blink on damage
local function OnFlightResponseDamage(event, player, attacker, damage)
    local guid = player:GetGUID()
    local active = FlightResponseActive[guid]

    if active and not active.blinkUsed and GetGameTime() < active.expires then
        -- Trigger reactive blink!
        active.blinkUsed = true

        -- Calculate blink destination (15 yards forward)
        local facing = player:GetO()
        local x = player:GetX() + math.cos(facing) * 15
        local y = player:GetY() + math.sin(facing) * 15
        local z = player:GetZ()

        -- Teleport player
        player:NearTeleport(x, y, z, facing)

        -- Extra cortisol from the adrenaline
        FairyChemistry.ModifyChemical(guid, "cortisol", 10)

        -- Visual feedback
        FairyAbilities.SendAbilityMessage(player, "Flight Response", "cortisol",
            "|cFFFF4500BLINK TRIGGERED!|r Escaped danger!")

        -- Update effect
        FairyChemistry.AddEffect(guid, "FLIGHT_RESPONSE", active.expires - GetGameTime(),
            { blinkReady = false })
    end
end

-- Cleanup expired Flight Response
local function CleanupFlightResponse()
    local now = GetGameTime()
    for guid, data in pairs(FlightResponseActive) do
        if now >= data.expires then
            FlightResponseActive[guid] = nil
        end
    end
end

CreateLuaEvent(CleanupFlightResponse, 1000, 0)

--[[
================================================================================
    ABILITY 6: DREAMWALK
    Enter a dreamlike state, becoming invisible and untargetable for 8 seconds.
    Your chemistry is completely reset to baseline upon activation.

    Cannot attack or cast while in Dreamwalk.
    Ends early if you take any action.

    The "oh no" button. Complete escape and reset.
    2 minute cooldown
================================================================================
--]]

local DreamwalkActive = {}

FairyAbilities.RegisterAbility({
    name = "Dreamwalk",
    spellId = FairyAbilities.SPELL_IDS.DREAMWALK,
    cooldown = 120,  -- 2 minutes
    primaryChemical = "serotonin",
    specs = { "reverie", "mania", "vigil" },
    chemistryCost = {},  -- No cost - emergency ability
    chemistryGenerated = {},  -- Resets chemistry instead

    canUse = function(player)
        -- Can't Dreamwalk while already in Dreamwalk
        if DreamwalkActive[player:GetGUID()] then
            return false, "Already in Dreamwalk"
        end
        return true
    end,

    handler = function(player, target)
        local guid = player:GetGUID()

        -- Reset all chemistry to baseline
        FairyChemistry.ResetChemistry(guid)

        -- Enter dreamwalk state
        DreamwalkActive[guid] = {
            expires = GetGameTime() + 8,
            originalPos = { player:GetX(), player:GetY(), player:GetZ() }
        }

        FairyChemistry.AddEffect(guid, "DREAMWALK", 8, {})

        -- Apply invisibility (using existing game spell)
        player:CastSpell(player, 66, true)  -- Invisibility

        -- Clear threat
        player:ClearThreatList()

        -- Break any bonds (entering dream state)
        FairyChemistry.BreakBond(guid)

        -- Visual feedback
        FairyAbilities.PlayVisualEffect(player, "vanish")
        FairyAbilities.SendAbilityMessage(player, "Dreamwalk", "serotonin",
            "|cFF9400D3Fading into the dreamscape...|r Chemistry reset.")

        player:SendBroadcastMessage("|cFF9400D3You drift between worlds. Your mind finds peace.|r")

        return true
    end
})

-- End Dreamwalk on action
local function OnDreamwalkAction(event, player, ...)
    local guid = player:GetGUID()
    if DreamwalkActive[guid] then
        DreamwalkActive[guid] = nil
        FairyChemistry.RemoveEffect(guid, "DREAMWALK")

        -- Remove invisibility
        player:RemoveAura(66)

        FairyAbilities.SendAbilityMessage(player, "Dreamwalk", "cortisol",
            "|cFF808080Returning to reality...|r")

        -- Small cortisol spike from sudden awakening
        FairyChemistry.ModifyChemical(guid, "cortisol", 5)
    end
end

-- Cleanup expired Dreamwalk
local function CleanupDreamwalk()
    local now = GetGameTime()
    for guid, data in pairs(DreamwalkActive) do
        if now >= data.expires then
            DreamwalkActive[guid] = nil

            local player = GetPlayerByGUID(guid)
            if player and player:IsInWorld() then
                player:RemoveAura(66)
                FairyAbilities.SendAbilityMessage(player, "Dreamwalk", "serotonin",
                    "|cFF00FF00Gently returning to consciousness...|r")
            end
        end
    end
end

CreateLuaEvent(CleanupDreamwalk, 1000, 0)

--[[
================================================================================
    REGISTER PLAYER EVENTS FOR SHARED ABILITIES
================================================================================
--]]

-- Hook into damage taken for Flight Response and Soothing Presence
RegisterPlayerEvent(36, function(event, player, attacker, damage)
    OnDamageTaken(event, player, attacker, damage)
    OnFlightResponseDamage(event, player, attacker, damage)
end)

-- Hook spell cast for Dreamwalk interruption
RegisterPlayerEvent(5, function(event, player, spell)
    OnDreamwalkAction(event, player)
end)

-- Hook movement for Dreamwalk interruption
RegisterPlayerEvent(28, function(event, player)
    OnDreamwalkAction(event, player)
end)

print("[FairyAbilities] Shared abilities loaded: Neural Pulse, Empathic Mirror, Intrusive Thought, Soothing Presence, Flight Response, Dreamwalk")
