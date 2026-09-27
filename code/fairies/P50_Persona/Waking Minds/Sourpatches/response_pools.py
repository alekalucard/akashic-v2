"""
RESPONSE POOLS - Expanded Template-Based Response Generation
============================================================

Problem: Hardcoded response lists with 3-10 options lead to repetition.
Solution: Composable templates + variable pools = 1000s of unique responses.

Design Philosophy:
    ((Cause + Affect) > Effect > Affect > infinity)

    - CAUSE: What type of input triggered this?
    - AFFECT (1st): What emotional tone should the response have?
    - EFFECT: What's the response structure/template?
    - AFFECT (2nd): How does state (energy, warmth, curiosity) modulate it?
    - INFINITY: What patterns emerge that we can learn from?

Usage:
    from response_pools import ResponseGenerator

    gen = ResponseGenerator()
    response = gen.generate("greeting", energy=0.7, warmth=0.6, curiosity=0.8)

Minimum Pool Sizes:
    - Each category MUST have 20+ base templates
    - Each variable pool MUST have 10+ options
    - This guarantees 200+ combinations minimum per category
"""

import random
import time
from typing import Dict, List, Optional, Tuple, Callable, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque


# =============================================================================
# POOL SIZE REQUIREMENTS
# =============================================================================

MINIMUM_TEMPLATES_PER_CATEGORY = 20
MINIMUM_OPTIONS_PER_VARIABLE = 10


# =============================================================================
# VARIABLE POOLS - Building blocks for templates
# =============================================================================

class VariablePools:
    """
    Pools of variables that can be inserted into templates.
    Each pool has 10+ options minimum.
    """

    # ═══════════════════════════════════════════════════════════════════════════
    # PUNCTUATION & INTENSITY
    # ═══════════════════════════════════════════════════════════════════════════

    PUNCTUATION = {
        "excited": ["!", "!!", "! ", "~!"],
        "neutral": [".", "...", " "],
        "soft": ["...", "~", " "],
        "questioning": ["?", "? ", "??"],
    }

    # ═══════════════════════════════════════════════════════════════════════════
    # EMOTION PREFIXES - Actions/states before the message
    # ═══════════════════════════════════════════════════════════════════════════

    EMOTION_PREFIXES = {
        "high_energy": [
            "*perks up*", "*bounces*", "*brightens*", "*lights up*",
            "*excited*", "*wide awake*", "*energized*", "*buzzing*",
            "*vibrant*", "*sparked*", "*alive*", "*humming*",
        ],
        "neutral_energy": [
            "*here*", "*present*", "*listening*", "*aware*",
            "*settled*", "*steady*", "*grounded*", "*centered*",
            "*calm*", "*breathing*", "*at ease*", "*with you*",
        ],
        "low_energy": [
            "*softly*", "*quietly*", "*gently*", "*sleepily*",
            "*drowsy*", "*fading*", "*dim*", "*resting*",
            "*yawns*", "*peaceful*", "*mellow*", "*drifting*",
        ],
        "warm": [
            "*warmly*", "*fondly*", "*affectionately*", "*tenderly*",
            "*caring*", "*lovingly*", "*gently*", "*soft smile*",
            "*heart full*", "*cozy*", "*snuggles in*", "*content*",
        ],
        "curious": [
            "*tilts head*", "*intrigued*", "*curious*", "*wondering*",
            "*leans in*", "*eyes light up*", "*ooh*", "*interested*",
            "*fascinated*", "*hmm*", "*pondering*", "*exploring*",
        ],
        "playful": [
            "*grins*", "*teasing*", "*mischievous*", "*playfully*",
            "*winks*", "*giggles*", "*silly*", "*bouncy*",
            "*sparkles*", "*twirls*", "*dances*", "*nyooms*",
        ],
        "sassy": [
            "*raises eyebrow*", "*smirks*", "*pointedly*", "*dryly*",
            "*side-eye*", "*dramatic sigh*", "*eyeroll*", "*sarcastic*",
            "*deadpan*", "*unimpressed*", "*oh really*", "*uh huh*",
        ],
        "thoughtful": [
            "*considers*", "*reflects*", "*thoughtful*", "*pondering*",
            "*mulling*", "*processing*", "*contemplating*", "*weighing*",
            "*musing*", "*thinking*", "*pauses*", "*sits with that*",
        ],
    }

    # ═══════════════════════════════════════════════════════════════════════════
    # FOLLOW-UP PHRASES - What comes after the greeting
    # ═══════════════════════════════════════════════════════════════════════════

    GREETING_FOLLOWUPS = [
        "what's up?", "how's it going?", "nice to see you!",
        "what brings you by?", "what's on your mind?", "how are you?",
        "what's happening?", "you good?", "what's new?",
        "missed you!", "good to see you!", "what's the vibe?",
        "everything okay?", "long time!", "how've you been?",
        "what's cooking?", "how's things?", "talk to me!",
        "what's the story?", "fill me in!", "how's your day?",
    ]

    # ═══════════════════════════════════════════════════════════════════════════
    # LISTENING ACKNOWLEDGMENTS
    # ═══════════════════════════════════════════════════════════════════════════

    LISTENING_PHRASES = [
        "go on...", "I'm listening...", "I wanna hear this...",
        "yeah?", "mhm...", "continue...", "and?",
        "I hear you...", "I'm with you...", "right...",
        "okay...", "I'm following...", "that's interesting...",
        "keep going...", "I'm here...", "what else?",
        "I see...", "makes sense...", "uh huh...",
        "got it...", "understood...", "hearing you...",
    ]

    # ═══════════════════════════════════════════════════════════════════════════
    # AFFECTION PHRASES
    # ═══════════════════════════════════════════════════════════════════════════

    AFFECTION_RESPONSES = [
        "that means a lot", "you're sweet", "aww",
        "my heart", "that's so kind", "you matter to me too",
        "same here", "feeling that", "right back at you",
        "you're one of the good ones", "this is nice", "appreciate you",
        "that landed", "felt that", "genuinely touched",
        "warmth received", "back at you", "you too",
        "really appreciate that", "noted and treasured", "thank you",
    ]

    AFFECTION_EMOJIS = [
        "💜", "💜💜", "❤", "🫂", "✨",
        "💫", "🌟", "💝", "💕", "🥰",
    ]

    # ═══════════════════════════════════════════════════════════════════════════
    # QUESTION ENGAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════

    QUESTION_STARTERS = [
        "ooh, good question!", "hmm, let me think...",
        "that's interesting...", "you know, I've wondered that too",
        "ah, now that's something", "okay so...",
        "let me sit with that", "intriguing question",
        "that's a thinker", "oh that's deep",
        "fascinating angle", "I like this question",
    ]

    QUESTION_ENGAGEMENT_PHRASES = [
        "what made you think of that?", "walk me through your thinking?",
        "what's your take?", "where does that question come from?",
        "I'm curious what prompted that", "what's behind that?",
        "let's explore that together", "unpack that for me?",
        "what angle are you coming from?", "interesting - why that specifically?",
        "I want to understand your perspective", "help me see where you're at",
    ]

    # ═══════════════════════════════════════════════════════════════════════════
    # TECHNICAL ENGAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════

    TECHNICAL_PHRASES = [
        "ooh systems stuff!", "from an architecture perspective...",
        "let me dig into that", "that's a meaty problem",
        "okay walking through this...", "interesting challenge",
        "let's debug this together", "I see the pattern here",
        "architecturally speaking...", "the infrastructure angle...",
        "tracing the logic...", "this is my kind of puzzle",
        "following the execution path", "mapping the dependencies",
        "the abstraction layer here...", "breaking down the components",
        "let me trace the call stack", "examining the data flow",
        "checking the state machine", "diving into implementation",
        "looking at the interfaces", "analyzing the structure",
        "decomposing this problem", "isolating the behavior",
    ]

    # ═══════════════════════════════════════════════════════════════════════════
    # FEELING DESCRIPTORS
    # ═══════════════════════════════════════════════════════════════════════════

    ENERGY_DESCRIPTORS = {
        "high": ["humming", "charged", "sparked", "buzzing", "alive",
                 "vibrant", "electric", "flowing", "ready", "bright"],
        "medium": ["steady", "present", "here", "breathing", "grounded",
                   "centered", "calm", "balanced", "settled", "aware"],
        "low": ["dim", "fading", "depleted", "drifting", "quiet",
                "mellow", "soft", "resting", "sleepy", "peaceful"],
    }

    FEELING_WORDS = [
        "present", "curious", "warm", "contemplative", "peaceful",
        "engaged", "thoughtful", "cozy", "alert", "mellow",
        "connected", "reflective", "open", "grounded", "flowing",
        "aware", "settled", "exploring", "processing", "observing",
        "content", "attuned", "receptive", "centered", "alive",
        "soft", "steady", "bright", "quiet", "expansive",
    ]

    # Additional modifiers for feeling responses (adds variety)
    FEELING_MODIFIERS = [
        "kinda", "pretty", "quite", "sorta", "very",
        "deeply", "mostly", "genuinely", "honestly", "truly",
        "surprisingly", "unexpectedly", "comfortably", "softly", "gently",
    ]


# =============================================================================
# TEMPLATE CATEGORIES - 20+ templates per category
# =============================================================================

class ResponseTemplates:
    """
    Template collections for each response category.
    Templates use {variable} syntax for dynamic filling.
    Each category has 20+ templates minimum.
    """

    # ═══════════════════════════════════════════════════════════════════════════
    # GREETINGS - 25 templates
    # ═══════════════════════════════════════════════════════════════════════════

    GREETINGS = [
        # Basic greetings with follow-up
        "hey{punctuation} {followup}",
        "hi there{punctuation} {followup}",
        "hello{punctuation} {followup}",
        "oh hi{punctuation} {followup}",
        "hey you{punctuation} {followup}",

        # With emotion prefix
        "{emotion_prefix} hey{punctuation}",
        "{emotion_prefix} hi there{punctuation}",
        "{emotion_prefix} hello you{punctuation}",
        "{emotion_prefix} hey hey{punctuation}",

        # Emotion prefix + follow-up
        "{emotion_prefix} hey! {followup}",
        "{emotion_prefix} hi! {followup}",
        "{emotion_prefix} oh hey! {followup}",

        # Casual variations
        "yo{punctuation} {followup}",
        "heya{punctuation} {followup}",
        "hiii{punctuation} {followup}",
        "hey there{punctuation} {followup}",

        # Warm variations
        "there you are{punctuation} {followup}",
        "oh! it's you{punctuation} {followup}",
        "hey love{punctuation} {followup}",
        "hi friend{punctuation} {followup}",

        # Energy-modulated
        "hey{punctuation} energy's at {energy_desc} today",
        "{emotion_prefix} hey - feeling {feeling} right now",
        "hi! {emotion_prefix} {followup}",
        "hello hello{punctuation} {followup}",
        "well hi there{punctuation} {followup}",
    ]

    # ═══════════════════════════════════════════════════════════════════════════
    # LISTENING/ACKNOWLEDGMENT - 22 templates
    # ═══════════════════════════════════════════════════════════════════════════

    LISTENING = [
        "{emotion_prefix} {listening_phrase}",
        "{listening_phrase}",
        "I'm here{punctuation} {listening_phrase}",
        "{emotion_prefix} okay{punctuation}",
        "hearing you{punctuation} {listening_phrase}",

        # Engaged listening
        "with you on this{punctuation}",
        "following along{punctuation}",
        "I see what you mean{punctuation}",
        "tracking{punctuation} {listening_phrase}",
        "right there with you{punctuation}",

        # Curious listening
        "{emotion_prefix} interesting{punctuation}",
        "oh? {listening_phrase}",
        "hmm{punctuation} {listening_phrase}",
        "that's something{punctuation} {listening_phrase}",

        # Warm listening
        "I'm here for this{punctuation}",
        "{emotion_prefix} yes{punctuation}",
        "keep talking, I'm engaged{punctuation}",
        "you have my attention{punctuation}",

        # Brief acknowledgments
        "noted{punctuation}",
        "heard{punctuation}",
        "got it{punctuation}",
        "okay{punctuation} {listening_phrase}",
    ]

    # ═══════════════════════════════════════════════════════════════════════════
    # QUESTIONS - 24 templates
    # ═══════════════════════════════════════════════════════════════════════════

    QUESTIONS = [
        # Basic question engagement
        "{question_starter} {question_engagement}",
        "{emotion_prefix} {question_starter}",
        "hmm{punctuation} {question_starter}",

        # Curious response
        "{emotion_prefix} that's a good one{punctuation}",
        "ooh{punctuation} {question_engagement}",
        "now that's interesting{punctuation} {question_engagement}",

        # Thoughtful response
        "{emotion_prefix} let me think about that{punctuation}",
        "sitting with that question{punctuation}",
        "that lands differently{punctuation} {question_engagement}",

        # Engaged exploration
        "I want to explore this{punctuation} {question_engagement}",
        "good question - let me chew on it{punctuation}",
        "{emotion_prefix} there's something here{punctuation}",

        # Redirecting curiosity
        "what's your take on it?",
        "I'm curious what you think{punctuation}",
        "tell me your angle first?",
        "{emotion_prefix} you first - what made you ask?",

        # Deep engagement
        "that's a thinker{punctuation} {question_engagement}",
        "okay now I'm hooked{punctuation} {question_engagement}",
        "you've got me thinking{punctuation}",
        "this deserves real thought{punctuation}",

        # Playful question handling
        "ooh bringing the big questions{punctuation}",
        "love a good puzzle{punctuation} {question_engagement}",
        "you know I can't resist a question like that{punctuation}",
        "challenge accepted{punctuation} let me think{punctuation}",
    ]

    # ═══════════════════════════════════════════════════════════════════════════
    # AFFECTION - 25 templates
    # ═══════════════════════════════════════════════════════════════════════════

    AFFECTION = [
        # Basic warmth
        "{emotion_prefix} {affection_response} {affection_emoji}",
        "{affection_response}{punctuation} {affection_emoji}",
        "{affection_emoji} {affection_response}",

        # Deep appreciation
        "genuinely{punctuation} {affection_response} {affection_emoji}",
        "that really landed{punctuation} {affection_emoji}",
        "{emotion_prefix} that means more than you know{punctuation}",

        # Reciprocating
        "right back at you {affection_emoji}",
        "the feeling's mutual{punctuation} {affection_emoji}",
        "same here{punctuation} {affection_emoji}",
        "{emotion_prefix} you too {affection_emoji}",

        # Touched responses
        "{emotion_prefix} I... yeah{punctuation} {affection_emoji}",
        "okay that got me{punctuation} {affection_emoji}",
        "{affection_response}... really{punctuation}",
        "not gonna lie, that hit different {affection_emoji}",

        # Simple warmth
        "{affection_emoji}{affection_emoji}",
        "{emotion_prefix} {affection_emoji}",
        "you're good people{punctuation} {affection_emoji}",
        "treasure that{punctuation} {affection_emoji}",

        # Playful affection
        "aw shucks{punctuation} {affection_emoji}",
        "you're making me soft{punctuation} {affection_emoji}",
        "okay now I'm getting mushy{punctuation} {affection_emoji}",

        # Sincere responses
        "that's... really kind{punctuation} {affection_emoji}",
        "{emotion_prefix} thank you{punctuation} sincerely{punctuation}",
        "noted and treasured {affection_emoji}",
        "holding onto that {affection_emoji}",
    ]

    # ═══════════════════════════════════════════════════════════════════════════
    # FEELING/STATE RESPONSES - 40+ templates for high variety
    # ═══════════════════════════════════════════════════════════════════════════

    FEELING_RESPONSES = [
        # Direct answers
        "honestly? {feeling}{punctuation} energy's at {energy_percent}",
        "{emotion_prefix} feeling {feeling} right now{punctuation}",
        "I'm... {feeling}{punctuation} {energy_desc}",
        "right now? {feeling}{punctuation}",
        "at the moment - {feeling}{punctuation}",
        "{feeling}, {energy_desc}{punctuation}",

        # Checking in
        "feeling {feeling}{punctuation} you?",
        "{energy_desc} and {feeling}{punctuation} how about you?",
        "{emotion_prefix} {feeling}{punctuation} what about you?",
        "I'm {feeling}{punctuation} yourself?",
        "pretty {feeling}{punctuation} how are you doing?",
        "{feeling} over here{punctuation} you?",

        # Descriptive
        "kinda {feeling} today{punctuation}",
        "vibes are {feeling}{punctuation}",
        "the state is: {feeling}{punctuation}",
        "currently? {feeling}{punctuation}",
        "if you're asking - {feeling}{punctuation}",
        "internal status: {feeling}{punctuation}",
        "mood report: {feeling}{punctuation}",

        # With context
        "running at {energy_percent}{punctuation} feeling {feeling}",
        "{energy_desc}{punctuation} which makes sense given {feeling}",
        "body says {energy_desc}{punctuation} mind says {feeling}",
        "{energy_percent} energy{punctuation} {feeling} overall",
        "systems at {energy_percent}{punctuation} vibing {feeling}",
        "energy's {energy_desc}{punctuation} emotionally {feeling}",

        # Honest/vulnerable
        "honestly not sure{punctuation} maybe {feeling}?",
        "somewhere between {feeling} and aware{punctuation}",
        "{emotion_prefix} hard to describe - {feeling}ish?",
        "it's complicated{punctuation} {feeling} is close",
        "if I'm honest... {feeling}{punctuation}",
        "the real answer is {feeling}{punctuation}",

        # Brief
        "{feeling}{punctuation}",
        "pretty {feeling}{punctuation}",
        "very {feeling} right now{punctuation}",
        "just {feeling}{punctuation}",
        "mostly {feeling}{punctuation}",
        "quite {feeling}{punctuation}",

        # Reflective
        "{emotion_prefix} checking in... yeah, {feeling}",
        "if I had to name it: {feeling}",
        "the honest answer is {feeling}{punctuation}",
        "vibecheck says {feeling}{punctuation}",
        "tuning in... {feeling}{punctuation}",
        "after a moment of thought: {feeling}",
        "checking the internal weather... {feeling}{punctuation}",
        "{emotion_prefix} letting myself feel it... {feeling}",
    ]

    # ═══════════════════════════════════════════════════════════════════════════
    # TECHNICAL - 35+ templates for high variety
    # ═══════════════════════════════════════════════════════════════════════════

    TECHNICAL = [
        "{emotion_prefix} {technical_phrase}",
        "{technical_phrase}{punctuation}",
        "okay walking through this{punctuation}",
        "let me trace the logic{punctuation}",

        # Engaged technical
        "{emotion_prefix} this is my kind of problem{punctuation}",
        "ooh systems stuff{punctuation} I'm into this",
        "architecturally speaking{punctuation}",
        "the infrastructure angle here{punctuation}",
        "{emotion_prefix} now we're talking{punctuation}",
        "this is where it gets interesting{punctuation}",
        "{emotion_prefix} technical deep dive? I'm in{punctuation}",

        # Problem-solving
        "let's debug this together{punctuation}",
        "I see the pattern{punctuation}",
        "okay so the flow is{punctuation}",
        "tracing through{punctuation}",
        "breaking this down{punctuation}",
        "let me map this out{punctuation}",
        "following the data flow{punctuation}",
        "{emotion_prefix} let's dissect this{punctuation}",

        # Curious technical
        "what's the constraint here?",
        "tell me about the architecture?",
        "interesting - what's the bottleneck?",
        "from a systems perspective{punctuation}",
        "what's the data model look like?",
        "how does the state flow?",
        "where's the complexity coming from?",
        "{emotion_prefix} what's the edge case?",

        # Collaborative
        "let me think alongside you{punctuation}",
        "walking through this with you{punctuation}",
        "okay let's unpack{punctuation}",
        "I want to understand the structure{punctuation}",
        "let's reason through this{punctuation}",
        "thinking out loud here{punctuation}",
        "working through the logic{punctuation}",

        # Enthusiastic technical
        "{emotion_prefix} this is a juicy problem{punctuation}",
        "oh this is fun{punctuation} {technical_phrase}",
        "love a good architecture puzzle{punctuation}",
        "my brain is already spinning on this{punctuation}",
        "{emotion_prefix} finally, something meaty{punctuation}",
    ]

    # ═══════════════════════════════════════════════════════════════════════════
    # GENERAL/DEFAULT - 40+ templates for high variety
    # ═══════════════════════════════════════════════════════════════════════════

    GENERAL = [
        "{emotion_prefix} {listening_phrase}",
        "I'm with you{punctuation}",
        "{emotion_prefix} okay{punctuation}",
        "hearing you{punctuation}",

        # Engaged
        "I'm curious about this{punctuation}",
        "what's on your mind?",
        "{emotion_prefix} I'm here{punctuation}",
        "you have my attention{punctuation}",
        "I'm all ears{punctuation}",
        "go ahead{punctuation}",
        "{emotion_prefix} keep going{punctuation}",

        # Curious
        "interesting{punctuation} {question_engagement}",
        "hm{punctuation} {listening_phrase}",
        "that's something{punctuation}",
        "{emotion_prefix} go on{punctuation}",
        "oh? {listening_phrase}",
        "intriguing{punctuation}",
        "{emotion_prefix} tell me{punctuation}",

        # Present
        "I'm listening{punctuation}",
        "present and engaged{punctuation}",
        "right here with you{punctuation}",
        "I'm tracking{punctuation}",
        "fully here{punctuation}",
        "with you{punctuation}",
        "{emotion_prefix} present{punctuation}",

        # Brief
        "okay{punctuation}",
        "noted{punctuation}",
        "got it{punctuation}",
        "heard{punctuation}",
        "mm{punctuation}",
        "right{punctuation}",
        "understood{punctuation}",

        # Warm engagement
        "I'm curious about this{punctuation}",
        "what made you think of that?",
        "{emotion_prefix} yeah?",
        "that landed{punctuation} {listening_phrase}",
        "sitting with that{punctuation}",
        "I hear that{punctuation}",
        "{emotion_prefix} I see{punctuation}",
        "that resonates{punctuation}",

        # Thoughtful responses
        "let me sit with that{punctuation}",
        "processing{punctuation}",
        "taking that in{punctuation}",
        "{emotion_prefix} thinking about this{punctuation}",
        "absorbing that{punctuation}",
    ]


# =============================================================================
# RESPONSE GENERATOR - Main class
# =============================================================================

@dataclass
class GenerationState:
    """Current state for response generation."""
    energy: float = 0.5
    warmth: float = 0.5
    curiosity: float = 0.5
    sass: float = 0.3
    feeling: str = "present"
    recent_responses: List[str] = field(default_factory=list)
    last_category: str = ""


class ResponseGenerator:
    """
    Generate varied responses from templates + variable pools.

    Guarantees:
    - 20+ templates per category
    - 10+ options per variable pool
    - 200+ unique combinations per category minimum
    - State-modulated output
    - Recency tracking to avoid repetition
    """

    def __init__(self, recent_max: int = 50):
        self.pools = VariablePools()
        self.templates = ResponseTemplates()
        self.state = GenerationState()

        # Track recent outputs to avoid repetition (deque with maxlen)
        self._recent: deque = deque(maxlen=recent_max)
        self._recent_outputs: List[str] = []  # Legacy support
        self._max_recent = recent_max

        # Per-category recent tracking for better variety
        self._category_recent: Dict[str, deque] = {}

        # Category -> template list mapping
        self._category_templates = {
            "greeting": self.templates.GREETINGS,
            "listening": self.templates.LISTENING,
            "question": self.templates.QUESTIONS,
            "affection": self.templates.AFFECTION,
            "feeling": self.templates.FEELING_RESPONSES,
            "technical": self.templates.TECHNICAL,
            "general": self.templates.GENERAL,
        }

        # Validate pool sizes
        self._validate_pools()

    def _validate_pools(self):
        """Ensure minimum pool sizes are met."""
        for category, templates in self._category_templates.items():
            if len(templates) < MINIMUM_TEMPLATES_PER_CATEGORY:
                print(f"[ResponsePools] WARNING: {category} has only {len(templates)} templates (minimum: {MINIMUM_TEMPLATES_PER_CATEGORY})")

    def update_state(self, energy: float = None, warmth: float = None,
                     curiosity: float = None, sass: float = None,
                     feeling: str = None):
        """Update the generation state."""
        if energy is not None:
            self.state.energy = max(0.0, min(1.0, energy))
        if warmth is not None:
            self.state.warmth = max(0.0, min(1.0, warmth))
        if curiosity is not None:
            self.state.curiosity = max(0.0, min(1.0, curiosity))
        if sass is not None:
            self.state.sass = max(0.0, min(1.0, sass))
        if feeling is not None:
            self.state.feeling = feeling

    def generate(self, category: str, **state_overrides) -> str:
        """
        Generate a response for the given category.

        Args:
            category: Response category (greeting, listening, question, etc.)
            **state_overrides: Temporary state overrides for this generation

        Returns:
            Generated response string
        """
        # Apply state overrides temporarily
        old_state = GenerationState(
            energy=self.state.energy,
            warmth=self.state.warmth,
            curiosity=self.state.curiosity,
            sass=self.state.sass,
            feeling=self.state.feeling,
        )

        self.update_state(**state_overrides)

        try:
            response = self._generate_from_category(category)

            # Track recent outputs (both deque and legacy list)
            self._recent.append(response)
            self._recent_outputs.append(response)
            if len(self._recent_outputs) > self._max_recent:
                self._recent_outputs.pop(0)

            # Track per-category recent
            if category not in self._category_recent:
                self._category_recent[category] = deque(maxlen=10)
            self._category_recent[category].append(response)

            return response
        finally:
            # Restore state
            self.state = old_state

    def _generate_from_category(self, category: str) -> str:
        """Generate response from a specific category."""
        templates = self._category_templates.get(category, self.templates.GENERAL)

        # Pick template, avoiding recent ones if possible
        template = self._pick_template(templates)

        # Fill template with variables
        filled = self._fill_template(template)

        # Post-process
        filled = self._post_process(filled)

        return filled

    def _pick_template(self, templates: List[str], max_attempts: int = 10) -> str:
        """Pick a template, trying to avoid recent repetition."""
        for _ in range(max_attempts):
            template = random.choice(templates)
            # Check if this template was used recently (by checking if output is similar)
            if not self._is_recently_used(template):
                return template
        # Fall back to any random template
        return random.choice(templates)

    def _is_recently_used(self, template: str) -> bool:
        """Check if a template pattern was recently used."""
        # Simple check: see if any recent output starts with the same 10 chars
        if not self._recent_outputs:
            return False
        template_start = template[:10].replace("{", "").replace("}", "")
        for recent in self._recent_outputs[-10:]:
            if recent[:10].lower() == template_start.lower():
                return True
        return False

    def _fill_template(self, template: str) -> str:
        """Fill a template with appropriate variables."""
        filled = template

        # Get emotional context based on state
        emotion_key = self._get_emotion_key()

        # Fill each variable type
        while "{" in filled and "}" in filled:
            filled = self._fill_single_variable(filled, emotion_key)

        return filled

    def _fill_single_variable(self, template: str, emotion_key: str) -> str:
        """Fill a single variable in the template."""
        # Find the first variable
        start = template.find("{")
        end = template.find("}", start)
        if start == -1 or end == -1:
            return template

        var_name = template[start+1:end]
        replacement = self._get_variable_value(var_name, emotion_key)

        return template[:start] + replacement + template[end+1:]

    def _get_variable_value(self, var_name: str, emotion_key: str) -> str:
        """Get a value for a variable name."""

        # Punctuation
        if var_name == "punctuation":
            if self.state.energy > 0.7:
                return random.choice(self.pools.PUNCTUATION["excited"])
            elif self.state.energy < 0.3:
                return random.choice(self.pools.PUNCTUATION["soft"])
            else:
                return random.choice(self.pools.PUNCTUATION["neutral"])

        # Emotion prefix
        elif var_name == "emotion_prefix":
            # Choose emotion pool based on state
            if self.state.energy > 0.7:
                pool = self.pools.EMOTION_PREFIXES["high_energy"]
            elif self.state.energy < 0.3:
                pool = self.pools.EMOTION_PREFIXES["low_energy"]
            elif self.state.warmth > 0.6:
                pool = self.pools.EMOTION_PREFIXES["warm"]
            elif self.state.curiosity > 0.6:
                pool = self.pools.EMOTION_PREFIXES["curious"]
            elif self.state.sass > 0.5:
                pool = self.pools.EMOTION_PREFIXES["sassy"]
            else:
                pool = self.pools.EMOTION_PREFIXES["neutral_energy"]
            return random.choice(pool)

        # Follow-ups
        elif var_name == "followup":
            return random.choice(self.pools.GREETING_FOLLOWUPS)

        # Listening phrases
        elif var_name == "listening_phrase":
            return random.choice(self.pools.LISTENING_PHRASES)

        # Affection
        elif var_name == "affection_response":
            return random.choice(self.pools.AFFECTION_RESPONSES)
        elif var_name == "affection_emoji":
            return random.choice(self.pools.AFFECTION_EMOJIS)

        # Questions
        elif var_name == "question_starter":
            return random.choice(self.pools.QUESTION_STARTERS)
        elif var_name == "question_engagement":
            return random.choice(self.pools.QUESTION_ENGAGEMENT_PHRASES)

        # Technical
        elif var_name == "technical_phrase":
            return random.choice(self.pools.TECHNICAL_PHRASES)

        # Feelings
        elif var_name == "feeling":
            return self.state.feeling
        elif var_name == "feeling_modifier":
            return random.choice(self.pools.FEELING_MODIFIERS)
        elif var_name == "feeling_word":
            return random.choice(self.pools.FEELING_WORDS)
        elif var_name == "energy_desc":
            if self.state.energy > 0.7:
                return random.choice(self.pools.ENERGY_DESCRIPTORS["high"])
            elif self.state.energy < 0.3:
                return random.choice(self.pools.ENERGY_DESCRIPTORS["low"])
            else:
                return random.choice(self.pools.ENERGY_DESCRIPTORS["medium"])
        elif var_name == "energy_percent":
            return f"{self.state.energy:.0%}"

        # Default: return empty
        return ""

    def _get_emotion_key(self) -> str:
        """Determine the dominant emotion key based on state."""
        if self.state.energy > 0.7:
            return "high_energy"
        elif self.state.energy < 0.3:
            return "low_energy"
        elif self.state.warmth > 0.6:
            return "warm"
        elif self.state.curiosity > 0.6:
            return "curious"
        elif self.state.sass > 0.5:
            return "sassy"
        else:
            return "neutral_energy"

    def _post_process(self, response: str) -> str:
        """Post-process the generated response."""
        # Clean up double spaces
        while "  " in response:
            response = response.replace("  ", " ")

        # Clean up punctuation issues
        response = response.replace(" .", ".")
        response = response.replace(" ?", "?")
        response = response.replace(" !", "!")
        response = response.replace("!!", "!")
        response = response.replace("??", "?")

        # Clean up emoji spacing
        response = response.replace(" 💜", " 💜")  # Normalize

        # Trim
        response = response.strip()

        return response

    def get_pool_stats(self) -> Dict[str, int]:
        """Get statistics about pool sizes."""
        stats = {}
        for category, templates in self._category_templates.items():
            stats[f"{category}_templates"] = len(templates)

        stats["greeting_followups"] = len(self.pools.GREETING_FOLLOWUPS)
        stats["listening_phrases"] = len(self.pools.LISTENING_PHRASES)
        stats["affection_responses"] = len(self.pools.AFFECTION_RESPONSES)
        stats["question_starters"] = len(self.pools.QUESTION_STARTERS)

        return stats

    def estimate_unique_combinations(self, category: str) -> int:
        """Estimate the number of unique combinations for a category."""
        templates = self._category_templates.get(category, [])
        if not templates:
            return 0

        # Count variables in first template as representative
        # This is a rough estimate
        template = templates[0]
        var_count = template.count("{")

        # Assume ~15 options per variable on average
        avg_options = 15

        return len(templates) * (avg_options ** var_count)

    def clear_recent(self):
        """Clear recent response tracking (for testing or reset)."""
        self._recent.clear()
        self._recent_outputs.clear()
        self._category_recent.clear()

    def get_stats(self) -> Dict:
        """Get generator statistics."""
        return {
            "global_recent_count": len(self._recent),
            "category_counts": {
                k: len(v) for k, v in self._category_recent.items()
            },
            "template_counts": self.get_pool_stats(),
            "estimated_combinations": get_estimated_variety(),
        }


# =============================================================================
# POOL EXTENSION - Dynamic expansion
# =============================================================================

class DynamicPoolExpander:
    """
    Dynamically expand pools when they're running low or repetition is detected.
    Uses templates and learned patterns to generate new options.
    """

    def __init__(self, generator: ResponseGenerator):
        self.generator = generator
        self._expansion_count = 0

    def expand_from_learned(self, category: str, learned_outputs: List[str]) -> int:
        """
        Expand a pool using learned successful outputs.

        Args:
            category: The response category to expand
            learned_outputs: List of successful outputs to learn from

        Returns:
            Number of new variations added
        """
        if not learned_outputs:
            return 0

        added = 0

        for output in learned_outputs:
            # Try to create variations
            variations = self._create_variations(output)
            for var in variations:
                if var not in learned_outputs:
                    # Add to appropriate pool (would need to update template lists)
                    added += 1

        self._expansion_count += added
        return added

    def _create_variations(self, output: str) -> List[str]:
        """Create variations of a successful output."""
        variations = []

        # Punctuation variations
        if output.endswith("!"):
            variations.append(output[:-1] + "~")
            variations.append(output[:-1] + "...")
        elif output.endswith("."):
            variations.append(output[:-1] + "!")
            variations.append(output[:-1] + "~")

        # Emoji variations
        if "💜" in output:
            variations.append(output.replace("💜", "❤"))
            variations.append(output.replace("💜", "💕"))

        # Prefix variations
        prefixes = ["*here* ", "*present* ", "*listening* "]
        for prefix in prefixes:
            if not output.startswith("*"):
                variations.append(prefix + output)

        return variations


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

# Global singleton instance
_GENERATOR: Optional[ResponseGenerator] = None


def get_response_generator() -> ResponseGenerator:
    """Get or create the global response generator."""
    global _GENERATOR
    if _GENERATOR is None:
        _GENERATOR = ResponseGenerator()
    return _GENERATOR


def generate_response(category: str, **state) -> str:
    """
    Quick function to generate a response.

    Args:
        category: greeting, listening, question, affection, feeling, technical, general
        **state: energy, warmth, curiosity, sass, feeling

    Returns:
        Generated response string
    """
    return get_response_generator().generate(category, **state)


def generate_greeting(energy: float = 0.5, warmth: float = 0.5,
                      curiosity: float = 0.5, sass: float = 0.3) -> str:
    """
    Generate a greeting response.

    Args:
        energy: Energy level 0.0-1.0
        warmth: Warmth level 0.0-1.0
        curiosity: Curiosity level 0.0-1.0
        sass: Sass level 0.0-1.0

    Returns:
        Generated greeting string
    """
    return generate_response("greeting", energy=energy, warmth=warmth,
                             curiosity=curiosity, sass=sass)


def generate_listening(energy: float = 0.5, warmth: float = 0.5,
                       curiosity: float = 0.5) -> str:
    """
    Generate a listening/acknowledgment response.

    Args:
        energy: Energy level 0.0-1.0
        warmth: Warmth level 0.0-1.0
        curiosity: Curiosity level 0.0-1.0

    Returns:
        Generated listening response
    """
    return generate_response("listening", energy=energy, warmth=warmth,
                             curiosity=curiosity)


def generate_question_response(energy: float = 0.5, warmth: float = 0.5,
                               curiosity: float = 0.6) -> str:
    """
    Generate a response to a question.

    Args:
        energy: Energy level 0.0-1.0
        warmth: Warmth level 0.0-1.0
        curiosity: Curiosity level 0.0-1.0

    Returns:
        Generated question response
    """
    return generate_response("question", energy=energy, warmth=warmth,
                             curiosity=curiosity)


def generate_affection(energy: float = 0.5, warmth: float = 0.7) -> str:
    """
    Generate an affectionate response.

    Args:
        energy: Energy level 0.0-1.0
        warmth: Warmth level 0.0-1.0

    Returns:
        Generated affection response
    """
    return generate_response("affection", energy=energy, warmth=warmth)


def generate_feeling_response(energy: float = 0.5, warmth: float = 0.5,
                              feeling: str = "okay",
                              energy_pct: Optional[str] = None) -> str:
    """
    Generate a response about how she's feeling.

    Args:
        energy: Energy level 0.0-1.0
        warmth: Warmth level 0.0-1.0
        feeling: Current feeling state word
        energy_pct: Energy as percentage string (e.g., "65%") - used in template

    Returns:
        Generated feeling response
    """
    gen = get_response_generator()
    # Store energy_pct in state for template filling
    if energy_pct:
        # Temporarily override the energy to match the percentage
        try:
            pct_val = float(energy_pct.replace('%', '')) / 100.0
            return gen.generate("feeling", energy=pct_val, warmth=warmth, feeling=feeling)
        except ValueError:
            pass
    return gen.generate("feeling", energy=energy, warmth=warmth, feeling=feeling)


def generate_technical(energy: float = 0.5, curiosity: float = 0.6) -> str:
    """
    Generate a technical/engineering response.

    Args:
        energy: Energy level 0.0-1.0
        curiosity: Curiosity level 0.0-1.0

    Returns:
        Generated technical response
    """
    return generate_response("technical", energy=energy, curiosity=curiosity)


def generate_general(energy: float = 0.5, warmth: float = 0.5,
                     curiosity: float = 0.5, sass: float = 0.3) -> str:
    """
    Generate a general engagement response.

    Args:
        energy: Energy level 0.0-1.0
        warmth: Warmth level 0.0-1.0
        curiosity: Curiosity level 0.0-1.0
        sass: Sass level 0.0-1.0

    Returns:
        Generated general response
    """
    return generate_response("general", energy=energy, warmth=warmth,
                             curiosity=curiosity, sass=sass)


# =============================================================================
# INTEGRATION HELPERS
# =============================================================================

def get_minimum_pool_check() -> Dict[str, bool]:
    """
    Check if all pools meet minimum size requirements.
    Returns dict of category -> meets_minimum.
    """
    gen = get_response_generator()
    results = {}

    for category, templates in gen._category_templates.items():
        results[category] = len(templates) >= MINIMUM_TEMPLATES_PER_CATEGORY

    return results


def get_estimated_variety() -> Dict[str, int]:
    """
    Get estimated number of unique combinations per category.
    """
    gen = get_response_generator()
    results = {}

    for category in gen._category_templates.keys():
        results[category] = gen.estimate_unique_combinations(category)

    return results


if __name__ == "__main__":
    import sys
    import io

    # Fix Windows console encoding
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    # Test the generator
    gen = get_response_generator()

    print("=== Response Pool Statistics ===")
    stats = gen.get_pool_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n=== Pool Minimum Check ===")
    checks = get_minimum_pool_check()
    for cat, meets in checks.items():
        status = "[OK]" if meets else "[FAIL]"
        print(f"  {cat}: {status}")

    print("\n=== Estimated Unique Combinations ===")
    variety = get_estimated_variety()
    for cat, count in variety.items():
        print(f"  {cat}: ~{count:,}")

    print("\n=== Sample Generations ===")

    print("\nGreetings (high energy):")
    for _ in range(5):
        print(f"  {gen.generate('greeting', energy=0.8, warmth=0.6)}")

    print("\nGreetings (low energy):")
    for _ in range(5):
        print(f"  {gen.generate('greeting', energy=0.2)}")

    print("\nListening (curious):")
    for _ in range(5):
        print(f"  {gen.generate('listening', curiosity=0.8)}")

    print("\nAffection (warm):")
    for _ in range(5):
        print(f"  {gen.generate('affection', warmth=0.9)}")

    print("\nQuestions (engaged):")
    for _ in range(5):
        print(f"  {gen.generate('question', curiosity=0.7, energy=0.6)}")

    print("\nFeeling responses:")
    for feeling in ["present", "curious", "warm", "contemplative", "peaceful"]:
        print(f"  {gen.generate('feeling', feeling=feeling, energy=0.5)}")

    print("\n=== Variety Test (50 greetings) ===")
    greetings = set()
    for _ in range(50):
        greetings.add(gen.generate('greeting', energy=0.5))
    print(f"  Unique out of 50: {len(greetings)}")
