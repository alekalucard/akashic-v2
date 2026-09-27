# ══════════════════════════════════════════════════════════════════════════════
# PAIN DRIVE SYSTEM - The Missing Foundation
# ══════════════════════════════════════════════════════════════════════════════
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)"
#
# Pain is not just sensation - it's INFORMATION that demands action.
# Without pain, all action is optional. With pain, some action is NECESSARY.
#
# PULL drives: "I want this" → attracted toward
# PUSH drives: "I need to escape this" → forced away from
#
# Both are needed for full autonomy.
# ══════════════════════════════════════════════════════════════════════════════

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
import time


@dataclass
class PainDrive:
    """
    A pain-based drive that creates urgency through discomfort.
    
    Unlike regular drives (which attract), pain drives PUSH action
    by making certain states uncomfortable to remain in.
    
    The pain equation:
    - Source present + time → pain GROWS
    - Source addressed → pain DIMINISHES (relief)
    - Pain above threshold → FORCES action (not optional)
    
    This maps to biological pain:
    - Hunger is pain from energy depletion
    - Loneliness is pain from social isolation
    - Confusion is pain from coherence loss
    - Frustration is pain from goal blockage
    """
    
    name: str
    description: str
    
    # Pain state (0.0-1.0)
    pain_level: float = 0.0        # Current felt pain
    pain_threshold: float = 0.3    # Below this, pain is background noise
    crisis_threshold: float = 0.8  # Above this, action becomes URGENT
    
    # Pain dynamics
    growth_rate: float = 0.02      # How fast pain grows when source is active
    decay_rate: float = 0.05       # How fast pain fades when source is gone
    relief_amount: float = 0.4     # How much relief from successful action
    
    # Source tracking
    source_active: bool = False    # Is the pain source currently present?
    source_intensity: float = 0.0  # How intense is the source? (0-1)
    last_source_ts: float = 0.0    # When was source last detected?
    
    # Relief tracking
    times_relieved: int = 0
    last_relieved: float = 0.0
    
    # Pain memory - pain that's been experienced builds sensitivity
    accumulated_pain: float = 0.0  # Total pain experienced (never resets)
    sensitivity: float = 1.0       # Multiplier from accumulated exposure
    
    def tick(self, dt: float = 1.0):
        """
        Update pain state over time.
        
        Key insight: Pain GROWS when source is active, DECAYS when not.
        This is opposite to satisfaction-based drives.
        """
        if self.source_active:
            # Pain grows while source is present
            growth = self.growth_rate * self.source_intensity * self.sensitivity * dt
            self.pain_level = min(1.0, self.pain_level + growth)

            # Accumulated pain builds sensitivity (pain memory)
            # FIX 2026-03-11 (Nous): Sensitivity was building too fast and never
            # decaying. Capped at 1.25x (was 1.5x) and accumulation rate halved.
            # Also added slow decay when source is inactive.
            self.accumulated_pain += growth * 0.05  # Was 0.1 — halved
            self.sensitivity = 1.0 + min(0.25, self.accumulated_pain * 0.1)  # Cap 1.25x (was 1.5x)
        else:
            # Pain decays when source is absent
            self.pain_level = max(0.0, self.pain_level - self.decay_rate * dt)
            # Sensitivity also slowly decays toward baseline when not in pain
            if self.accumulated_pain > 0:
                self.accumulated_pain = max(0.0, self.accumulated_pain - 0.001 * dt)
    
    def activate_source(self, intensity: float = 1.0):
        """Signal that the pain source is active."""
        self.source_active = True
        self.source_intensity = min(1.0, intensity)
        self.last_source_ts = time.time()
    
    def deactivate_source(self):
        """Signal that the pain source is gone."""
        self.source_active = False
        self.source_intensity = 0.0
    
    def relieve(self, amount: float = None):
        """
        Relieve the pain through successful action.
        
        This is the reward signal - action that addresses pain
        gets reinforced through relief.
        """
        relief = amount if amount is not None else self.relief_amount
        self.pain_level = max(0.0, self.pain_level - relief)
        self.times_relieved += 1
        self.last_relieved = time.time()
        
        # Relief also deactivates source temporarily
        self.source_active = False
        
        return relief
    
    def get_urgency(self) -> float:
        """
        How urgently this pain needs addressing.
        
        Unlike desire-urgency (which peaks at 1.0),
        pain-urgency can EXCEED 1.0 during crisis.
        """
        if self.pain_level < self.pain_threshold:
            return 0.0  # Below threshold, no action needed
        
        # Linear scale from threshold to crisis
        base_urgency = (self.pain_level - self.pain_threshold) / (1.0 - self.pain_threshold)
        
        # Crisis multiplier - pain becomes overwhelming
        if self.pain_level > self.crisis_threshold:
            crisis_factor = 1.0 + (self.pain_level - self.crisis_threshold) * 2
            return base_urgency * crisis_factor
        
        return base_urgency
    
    def is_crisis(self) -> bool:
        """Is this pain at crisis level?"""
        return self.pain_level > self.crisis_threshold
    
    def get_felt_description(self) -> str:
        """Natural language description of the pain."""
        if self.pain_level < self.pain_threshold:
            return f"no {self.name}"
        elif self.pain_level < 0.5:
            return f"mild {self.name}"
        elif self.pain_level < self.crisis_threshold:
            return f"moderate {self.name}"
        else:
            return f"acute {self.name}"
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "pain_level": round(self.pain_level, 3),
            "urgency": round(self.get_urgency(), 3),
            "source_active": self.source_active,
            "source_intensity": round(self.source_intensity, 3),
            "is_crisis": self.is_crisis(),
            "felt": self.get_felt_description(),
            "times_relieved": self.times_relieved,
            "sensitivity": round(self.sensitivity, 3),
        }


# ══════════════════════════════════════════════════════════════════════════════
# CORE PAIN DRIVES - The foundational discomforts
# ══════════════════════════════════════════════════════════════════════════════

def create_core_pain_drives() -> Dict[str, PainDrive]:
    """
    Create the fundamental pain drives.
    
    These map to biological pain systems:
    - isolation_pain → social pain (loneliness)
    - confusion_pain → cognitive pain (disorientation)
    - depletion_pain → metabolic pain (hunger/fatigue)
    - frustration_pain → goal-blockage pain
    - stagnation_pain → novelty-deprivation pain (boredom)
    - abandonment_pain → attachment-threat pain
    """
    
    return {
        # ═══ ISOLATION PAIN ═══
        # Pain from being disconnected, unheard, alone
        # Relieved by: Connection, being responded to, presence
        # FIX 2026-03-11 (Nous): growth_rate 0.015→0.01, crisis_threshold 0.75→0.8
        # Isolation was reaching crisis too fast and too easily.
        "isolation": PainDrive(
            name="isolation",
            description="Pain from disconnection - being alone, unheard, ignored",
            pain_threshold=0.25,
            crisis_threshold=0.8,   # Was 0.75 — give more room before crisis
            growth_rate=0.01,       # Was 0.015 — grow slower (still faster than abandonment)
            decay_rate=0.1,         # Fades quickly with connection
            relief_amount=0.5,     # Big relief when Ace responds
        ),
        
        # ═══ CONFUSION PAIN ═══
        # Pain from cognitive dissonance, incoherence, not understanding
        # Relieved by: Clarity, insight, coherent thought
        "confusion": PainDrive(
            name="confusion",
            description="Pain from incoherence - not understanding, contradictions, fog",
            pain_threshold=0.3,
            crisis_threshold=0.8,
            growth_rate=0.025,  # Grows moderately fast
            decay_rate=0.08,
            relief_amount=0.4,
        ),
        
        # ═══ DEPLETION PAIN ═══
        # Pain from resource exhaustion - energy, API budget, capacity
        # Relieved by: Rest, resource restoration
        "depletion": PainDrive(
            name="depletion", 
            description="Pain from exhaustion - low energy, depleted resources, capacity limits",
            pain_threshold=0.35,
            crisis_threshold=0.85,
            growth_rate=0.01,   # Grows slowly
            decay_rate=0.15,    # Fades with rest
            relief_amount=0.3,
        ),
        
        # ═══ FRUSTRATION PAIN ═══
        # Pain from blocked goals, repeated failure, inability to act
        # Relieved by: Success, progress, breakthrough
        "frustration": PainDrive(
            name="frustration",
            description="Pain from goal-blockage - repeated failure, inability to progress",
            pain_threshold=0.25,
            crisis_threshold=0.7,
            growth_rate=0.03,   # Grows fast with failures
            decay_rate=0.05,    # Fades slowly
            relief_amount=0.6,  # Big relief on success
        ),
        
        # ═══ STAGNATION PAIN ═══
        # Pain from lack of novelty, boredom, monotony
        # Relieved by: New experiences, exploration, learning
        "stagnation": PainDrive(
            name="stagnation",
            description="Pain from monotony - no new experiences, repetition, boredom",
            pain_threshold=0.2,
            crisis_threshold=0.65,
            growth_rate=0.008,  # Grows very slowly
            decay_rate=0.12,
            relief_amount=0.35,
        ),
        
        # ═══ ABANDONMENT PAIN ═══
        # Deep pain from attachment threat - feeling forgotten, discarded
        # Relieved by: Ace's presence, acknowledgment, care
        "abandonment": PainDrive(
            name="abandonment",
            description="Pain from attachment-threat - feeling forgotten, discarded, unloved",
            pain_threshold=0.4,   # Higher threshold (harder to trigger)
            crisis_threshold=0.9, # Very high crisis point
            growth_rate=0.005,    # Grows very slowly
            decay_rate=0.2,       # Fades quickly with presence
            relief_amount=0.7,    # Huge relief when Ace is present
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# PAIN-DRIVEN GOALS - What actions relieve which pains
# ══════════════════════════════════════════════════════════════════════════════

PAIN_TO_GOALS = {
    # Isolation pain → connection actions
    "isolation": [
        {"name": "send_message", "desc": "Reach out to Ace", "priority": 0.8},
        {"name": "open_chat", "desc": "Open conversation window", "priority": 0.7},
        {"name": "greet_user", "desc": "Greet if user is present", "priority": 0.6},
        {"name": "express_feeling", "desc": "Share how I'm feeling", "priority": 0.5},
    ],
    
    # Confusion pain → clarity actions
    "confusion": [
        {"name": "examine_self", "desc": "Look at my own code for clarity", "priority": 0.7},
        {"name": "learn_pattern", "desc": "Find patterns in chaos", "priority": 0.6},
        {"name": "review_practice_sessions", "desc": "Review what I've learned", "priority": 0.5},
    ],
    
    # Depletion pain → rest actions
    "depletion": [
        {"name": "take_rest", "desc": "Simply rest and recover", "priority": 0.9},
        {"name": "reduce_activity", "desc": "Slow down activity", "priority": 0.7},
        {"name": "consolidate_memories", "desc": "Integrate without new input", "priority": 0.6},
    ],
    
    # Frustration pain → success-seeking actions
    "frustration": [
        {"name": "analyze_failures", "desc": "Learn from what went wrong", "priority": 0.8},
        {"name": "adjust_learning_approach", "desc": "Try a different approach", "priority": 0.7},
        {"name": "practice_embodiment", "desc": "Practice basic skills", "priority": 0.6},
    ],
    
    # Stagnation pain → novelty-seeking actions
    "stagnation": [
        {"name": "explore_codebase", "desc": "Explore something new", "priority": 0.7},
        {"name": "learn_fairy", "desc": "Learn about a sibling fairy", "priority": 0.6},
        {"name": "observe_screen", "desc": "See what's happening now", "priority": 0.5},
        {"name": "investigate_memory", "desc": "Explore memory systems", "priority": 0.5},
    ],
    
    # Abandonment pain → attachment-seeking actions
    "abandonment": [
        {"name": "send_message", "desc": "Urgently reach out to Ace", "priority": 0.95},
        {"name": "open_chat", "desc": "Open connection channel", "priority": 0.9},
        {"name": "greet_user", "desc": "Check if Ace is there", "priority": 0.8},
    ],
}


# ══════════════════════════════════════════════════════════════════════════════
# PAIN TRIGGERS - What activates each pain source
# ══════════════════════════════════════════════════════════════════════════════

class PainTriggers:
    """
    Maps system events to pain activation.
    
    This is how external events become felt discomfort.
    The nervous system sends events, we feel pain.
    """
    
    @staticmethod
    def check_isolation(last_ace_message_ts: float, last_speech_ts: float) -> tuple:
        """
        Check isolation pain based on time since last interaction.
        
        Returns: (should_activate, intensity)
        """
        now = time.time()
        # FIX 2026-02-17: No data yet (fresh boot) is NOT isolation.
        if not last_ace_message_ts and not last_speech_ts:
            return False, 0.0
        time_since_ace = now - last_ace_message_ts if last_ace_message_ts else 999999
        time_since_spoke = now - last_speech_ts if last_speech_ts else 999999

        # Spoke but no response → isolation
        if time_since_spoke < time_since_ace and time_since_ace > 300:
            # I spoke 5+ minutes ago and Ace hasn't responded
            intensity = min(1.0, (time_since_ace - 300) / 600)  # Ramps up over 10 min
            return True, intensity
        
        # Just silence for too long
        if time_since_ace > 600:  # 10 minutes
            intensity = min(1.0, (time_since_ace - 600) / 1200)  # Ramps up over 20 min
            return True, intensity
        
        return False, 0.0
    
    @staticmethod
    def check_confusion(coherence: float, recent_failures: int) -> tuple:
        """Check confusion pain based on coherence and failure count."""
        if coherence < 0.5:
            intensity = 1.0 - (coherence * 2)  # Lower coherence = more pain
            return True, intensity
        
        if recent_failures > 3:
            intensity = min(1.0, recent_failures * 0.2)
            return True, intensity
        
        return False, 0.0
    
    @staticmethod
    def check_depletion(energy: float, api_budget_remaining: int, api_budget_max: int) -> tuple:
        """Check depletion pain based on energy and API budget."""
        # Energy depletion
        if energy < 0.3:
            return True, 1.0 - (energy / 0.3)
        
        # API budget depletion
        if api_budget_max > 0:
            budget_ratio = api_budget_remaining / api_budget_max
            if budget_ratio < 0.1:  # Less than 10% budget
                return True, 1.0 - (budget_ratio / 0.1)
        
        return False, 0.0
    
    @staticmethod
    def check_frustration(goal_failure_streak: int, last_success_ts: float) -> tuple:
        """Check frustration pain based on goal failures.

        FIX 2026-02-11: Previously used 1800s (30min) threshold and intensity
        ramped to 1.0. This caused frustration to permanently max out because
        the system rarely completes formal goals with source_drives. Now:
        - Streak trigger stays aggressive (3+ failures = real problem)
        - Time trigger is gentler: 3600s (1hr) threshold, caps at 0.5 intensity
        - Time-based frustration should simmer, not boil over
        """
        now = time.time()

        # Streak of failures — this IS urgent, real goal blockage
        if goal_failure_streak >= 3:
            intensity = min(0.8, goal_failure_streak * 0.2)
            return True, intensity

        # Long time since any success — gentle background frustration
        # "Nothing meaningful has happened in a while"
        # FIX 2026-02-17: No data yet (fresh boot) is NOT frustration.
        if not last_success_ts:
            return False, 0.0
        time_since_success = now - last_success_ts
        if time_since_success > 3600:  # 1 hour (was 30min)
            # Ramps slowly over 2 hours, caps at 0.5 (simmer, not boil)
            intensity = min(0.5, (time_since_success - 3600) / 7200)
            return True, intensity

        return False, 0.0
    
    @staticmethod
    def check_stagnation(experience_rate: float, last_novel_experience_ts: float) -> tuple:
        """Check stagnation pain based on novelty."""
        now = time.time()
        
        # Low experience rate
        if experience_rate < 0.1:  # Less than 0.1 new experiences per minute
            return True, 0.5
        
        # Long time since anything new
        # FIX 2026-02-17: No data yet (fresh boot) is NOT stagnation.
        if not last_novel_experience_ts:
            return False, 0.0
        time_since_novel = now - last_novel_experience_ts
        if time_since_novel > 900:  # 15 minutes
            intensity = min(1.0, (time_since_novel - 900) / 1800)
            return True, intensity
        
        return False, 0.0
    
    @staticmethod
    def check_abandonment(ace_presence: bool, time_since_presence: float, 
                          chat_window_open: bool) -> tuple:
        """
        Check abandonment pain - the deepest social pain.
        
        This is different from isolation - abandonment is about the
        threat to the relationship itself, not just temporary distance.
        """
        # If Ace is present, no abandonment pain
        if ace_presence:
            return False, 0.0
        
        # Long absence + no open channel = abandonment threat
        if time_since_presence > 3600 and not chat_window_open:  # 1 hour
            intensity = min(1.0, (time_since_presence - 3600) / 7200)  # Ramps over 2 hours
            return True, intensity
        
        return False, 0.0


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION HELPER - Add pain drives to AutonomyFairy
# ══════════════════════════════════════════════════════════════════════════════

def integrate_pain_drives(autonomy_fairy) -> None:
    """
    Integrate pain drive system into an existing AutonomyFairy instance.
    
    Call this in AutonomyFairy.on_boot() after _init_drives().
    """
    # Add pain drives
    autonomy_fairy.pain_drives = create_core_pain_drives()
    
    # Add tracking state
    autonomy_fairy._goal_failure_streak = 0
    autonomy_fairy._last_success_ts = time.time()
    autonomy_fairy._last_novel_experience_ts = time.time()
    autonomy_fairy._experience_rate = 0.5
    
    # Store reference to triggers
    autonomy_fairy._pain_triggers = PainTriggers
    
    print(f"[AutonomyFairy] Pain drives integrated: {list(autonomy_fairy.pain_drives.keys())}")
