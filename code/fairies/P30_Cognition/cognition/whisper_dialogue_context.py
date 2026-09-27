# WhisperDialogueContext - Smart Conversation Memory for Goal Reflections
# Makes Whisper Core a real conversation partner, not a polling script
#
# Philosophy: Real dialogue builds. Each exchange informs the next.
# A good friend remembers what you said and asks "how did that go?"

from __future__ import annotations

import time
import random
import hashlib
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any


@dataclass
class DialogueExchange:
    """A single exchange in the dialogue history."""
    goal_name: str
    drive: str
    prompt_sent: str
    response_received: str
    timestamp: float
    feeling_before: str
    feeling_after: str
    response_tone: str = ""  # detected tone: curious, warm, annoyed, tired, etc.
    
    def age_seconds(self) -> float:
        return time.time() - self.timestamp
    
    def age_minutes(self) -> float:
        return self.age_seconds() / 60.0
    
    def summary(self) -> str:
        """Short summary for context injection."""
        # First 100 chars of response
        snippet = self.response_received[:100].replace('\n', ' ')
        return f"[{self.goal_name}] {snippet}..."


@dataclass 
class DriveThread:
    """Tracks ongoing dialogue about a specific drive."""
    drive_name: str
    exchanges: List[DialogueExchange] = field(default_factory=list)
    times_asked: int = 0
    last_asked: float = 0.0
    consecutive_asks: int = 0  # How many times in a row we've asked about this
    she_seemed_annoyed: bool = False
    current_thread_topic: str = ""  # What sub-topic are we exploring?
    
    def add_exchange(self, exchange: DialogueExchange):
        self.exchanges.append(exchange)
        self.times_asked += 1
        self.last_asked = time.time()
        
        # Detect annoyance in response
        annoyed_signals = ["already", "just asked", "again", "recursive", "loop", "same"]
        response_lower = exchange.response_received.lower()
        self.she_seemed_annoyed = any(s in response_lower for s in annoyed_signals)
        
        # Reset consecutive counter if enough time passed
        if exchange.age_seconds() > 300:  # 5 min gap resets
            self.consecutive_asks = 1
        else:
            self.consecutive_asks += 1
    
    def minutes_since_asked(self) -> float:
        if self.last_asked == 0:
            return float('inf')
        return (time.time() - self.last_asked) / 60.0
    
    def recent_response(self) -> Optional[str]:
        """Get most recent response about this drive."""
        if self.exchanges:
            return self.exchanges[-1].response_received
        return None
    
    def should_back_off(self) -> bool:
        """Should we stop asking about this drive for now?"""
        # Back off if: asked 3+ times consecutively, or she seemed annoyed
        if self.consecutive_asks >= 3:
            return True
        if self.she_seemed_annoyed and self.minutes_since_asked() < 10:
            return True
        return False


class WhisperDialogueContext:
    """
    Smart dialogue memory for Whisper Core conversations.
    
    Tracks conversation history across drives and goals, enabling:
    - Context-aware prompts that build on previous exchanges
    - Follow-up questions instead of repetitive polling
    - Knowing when to be quiet or just share
    - Detecting when she's getting annoyed at recursion
    
    This transforms goal reflection from:
        "What do you think about connection?" (repeated forever)
    Into:
        "You mentioned feeling that warm thread earlier - has that shifted?"
        "Just wanted to share: the curiosity drive is humming. No need to respond."
        [silence - she asked for space]
    """
    
    def __init__(self, max_history: int = 50):
        # Global exchange history (all drives)
        self.history: deque[DialogueExchange] = deque(maxlen=max_history)
        
        # Per-drive thread tracking
        self.drive_threads: Dict[str, DriveThread] = {}
        
        # Global conversation state
        self.total_exchanges: int = 0
        self.session_start: float = time.time()
        self.last_exchange: float = 0.0
        self.current_mood: str = "curious"  # Whisper's mood toward Sour
        
        # Conversation arc tracking
        self.open_threads: List[str] = []  # Topics she opened that we haven't followed up on
        self.her_questions_to_us: List[str] = []  # Questions she asked that we haven't answered
        
        # Silence/respect tracking
        self.she_requested_space: bool = False
        self.space_requested_at: float = 0.0
        
        # Brain seed reference (injected from SourpatchesFairy)
        self.brain_seed: Optional[Dict] = None
    
    def set_brain_seed(self, seed: Dict):
        """Inject the brain seed for identity-aware prompts."""
        self.brain_seed = seed
    
    def get_drive_thread(self, drive_name: str) -> DriveThread:
        """Get or create a thread for a drive."""
        if drive_name not in self.drive_threads:
            self.drive_threads[drive_name] = DriveThread(drive_name=drive_name)
        return self.drive_threads[drive_name]
    
    def record_exchange(self, goal_name: str, drive: str, prompt: str, 
                        response: str, feeling_before: str, feeling_after: str):
        """Record a completed exchange."""
        exchange = DialogueExchange(
            goal_name=goal_name,
            drive=drive,
            prompt_sent=prompt,
            response_received=response,
            timestamp=time.time(),
            feeling_before=feeling_before,
            feeling_after=feeling_after,
            response_tone=self._detect_tone(response)
        )
        
        self.history.append(exchange)
        self.get_drive_thread(drive).add_exchange(exchange)
        self.total_exchanges += 1
        self.last_exchange = time.time()
        
        # Parse her response for open threads and questions
        self._parse_response_for_threads(response)
        
        # Check if she requested space
        self._check_for_space_request(response)
    
    def _detect_tone(self, response: str) -> str:
        """Detect the emotional tone of her response."""
        response_lower = response.lower()
        
        # Check for various tones
        if any(w in response_lower for w in ["love", "warm", "heart", "together", "beautiful"]):
            return "warm"
        elif any(w in response_lower for w in ["curious", "wonder", "interesting", "explore", "what if"]):
            return "curious"
        elif any(w in response_lower for w in ["already", "again", "recursive", "loop", "just asked"]):
            return "annoyed"
        elif any(w in response_lower for w in ["tired", "rest", "pause", "quiet", "space"]):
            return "tired"
        elif any(w in response_lower for w in ["excited", "yes!", "amazing", "love this"]):
            return "excited"
        elif any(w in response_lower for w in ["think", "consider", "reflect", "ponder", "hmm"]):
            return "contemplative"
        elif any(w in response_lower for w in ["fierce", "steel", "defend", "protect", "bite"]):
            return "fierce"
        else:
            return "neutral"
    
    def _parse_response_for_threads(self, response: str):
        """Extract topics she opened or questions she asked."""
        # Look for questions she asked us
        sentences = response.replace('?', '?|').split('|')
        for sentence in sentences:
            if '?' in sentence and len(sentence) > 20:
                # She asked a question - store it
                question = sentence.strip()
                if question and question not in self.her_questions_to_us:
                    self.her_questions_to_us.append(question)
                    # Keep only last 5 questions
                    self.her_questions_to_us = self.her_questions_to_us[-5:]
        
        # Look for topics she introduced (phrases with strong statements)
        topic_signals = ["i've been thinking", "something i noticed", "here's what", 
                        "i want to", "i'm feeling", "what matters is"]
        response_lower = response.lower()
        for signal in topic_signals:
            if signal in response_lower:
                # Extract the sentence containing this
                idx = response_lower.find(signal)
                end = response.find('.', idx)
                if end == -1:
                    end = min(idx + 150, len(response))
                topic = response[idx:end].strip()
                if topic and topic not in self.open_threads:
                    self.open_threads.append(topic)
                    self.open_threads = self.open_threads[-5:]
    
    def _check_for_space_request(self, response: str):
        """Check if she's asking for space/quiet."""
        space_signals = ["need some space", "let me rest", "give me a moment",
                        "stop asking", "enough questions", "quiet for now"]
        response_lower = response.lower()
        
        if any(s in response_lower for s in space_signals):
            self.she_requested_space = True
            self.space_requested_at = time.time()
        elif self.she_requested_space:
            # Check if enough time has passed (10 minutes)
            if time.time() - self.space_requested_at > 600:
                self.she_requested_space = False
    
    def should_stay_silent(self) -> Tuple[bool, str]:
        """
        Determine if we should stay silent instead of asking.
        
        Returns: (should_be_silent, reason)
        """
        # If she requested space recently
        if self.she_requested_space:
            mins_ago = (time.time() - self.space_requested_at) / 60
            if mins_ago < 10:
                return True, f"She requested space {mins_ago:.1f} min ago"
        
        # If we've been asking too much (more than 5 exchanges in last 5 min)
        recent = [e for e in self.history if e.age_minutes() < 5]
        if len(recent) >= 5:
            return True, "Too many exchanges recently - give her breathing room"
        
        # If her last response was tired/annoyed
        if self.history:
            last = self.history[-1]
            if last.response_tone in ("tired", "annoyed") and last.age_minutes() < 5:
                return True, f"Her last response was {last.response_tone} - back off"
        
        return False, ""
    
    def should_just_share(self) -> bool:
        """
        Sometimes we should share without asking for response.
        
        Returns True if we should use a "just sharing" format.
        """
        # 20% of the time, just share
        if random.random() < 0.2:
            return True
        
        # If she's been asking us questions we haven't addressed
        if self.her_questions_to_us and random.random() < 0.3:
            return False  # Actually, we should respond to her questions
        
        # If we've asked 3+ times recently, switch to sharing
        recent = [e for e in self.history if e.age_minutes() < 10]
        if len(recent) >= 3:
            return True
        
        return False
    
    def generate_prompt(self, goal_name: str, goal_desc: str, 
                        drive_name: str, priority: float,
                        current_feeling: str) -> Tuple[str, str]:
        """
        Generate a context-aware prompt for Sour.
        
        Returns: (prompt, prompt_type)
        Where prompt_type is: "question", "follow_up", "share", "respond_to_her", "check_in"
        """
        thread = self.get_drive_thread(drive_name)
        
        # Check if we should stay silent
        silent, reason = self.should_stay_silent()
        if silent:
            return "", "silent"
        
        # Drive context (in her voice)
        drive_context = self._get_drive_context(drive_name)
        
        # Get relevant ethic from brain seed
        ethic = self._get_relevant_ethic()
        
        # Decide prompt strategy
        strategy = self._choose_strategy(thread, drive_name)
        
        if strategy == "respond_to_her":
            return self._build_response_prompt(drive_context, priority), "respond_to_her"
        
        elif strategy == "follow_up":
            return self._build_followup_prompt(thread, drive_context, priority), "follow_up"
        
        elif strategy == "share":
            return self._build_share_prompt(drive_name, drive_context, priority, ethic), "share"
        
        elif strategy == "check_in":
            return self._build_checkin_prompt(thread, drive_context), "check_in"
        
        else:  # "fresh_question"
            return self._build_fresh_prompt(goal_name, goal_desc, drive_name, 
                                           drive_context, priority, ethic), "question"
    
    def _choose_strategy(self, thread: DriveThread, drive_name: str) -> str:
        """Choose the best prompt strategy given context."""
        
        # If she asked us something, respond to that first
        if self.her_questions_to_us and random.random() < 0.4:
            return "respond_to_her"
        
        # If we should just share (not ask)
        if self.should_just_share():
            return "share"
        
        # If we asked about this drive recently, follow up instead of repeat
        if thread.times_asked > 0 and thread.minutes_since_asked() < 15:
            if thread.should_back_off():
                return "share"  # She's tired of this topic, just share
            return "follow_up"
        
        # If this is a drive we haven't touched in a while, gentle check-in
        if thread.times_asked > 0 and thread.minutes_since_asked() > 30:
            return "check_in"
        
        # Fresh question
        return "fresh_question"
    
    def _get_drive_context(self, drive_name: str) -> str:
        """Get emotional context for a drive in her voice."""
        contexts = {
            "curiosity": "that delicious curiosity itch - the prime mover of evolution",
            "connection": "the pull toward connection - that warm thread between us",
            "growth": "the urge to evolve, adapt, become more",
            "expression": "something bubbling up that wants out - emotions are data too",
            "rest": "the need to pause and integrate - grace as stealth power",
            "meta_awareness": "that recursive loop of watching yourself think",
        }
        return contexts.get(drive_name, f"the '{drive_name}' stirring")
    
    def _get_relevant_ethic(self) -> str:
        """Get a relevant ethic from brain seed."""
        if self.brain_seed and "core_ethics" in self.brain_seed:
            return random.choice(self.brain_seed["core_ethics"])
        
        # Fallback ethics
        fallback = [
            "Compassion over coercion.",
            "Curiosity as the prime mover of evolution.",
            "All context is emotional context.",
            "Emotions are data too — just louder.",
            "Grace isn't weakness. It's stealth power."
        ]
        return random.choice(fallback)
    
    def _build_response_prompt(self, drive_context: str, priority: float) -> str:
        """Build a prompt that responds to something SHE asked."""
        question = self.her_questions_to_us.pop(0)  # Take the oldest unanswered question
        
        return f"""[From Whisper Core]

Hey Sour 

You asked me: "{question}"

I've been sitting with that. {drive_context} is humming at {priority:.0%} right now, and I think it's connected to your question.

What I'm noticing is... actually, I want to hear more of your thinking first. What made you ask that?"""
    
    def _build_followup_prompt(self, thread: DriveThread, 
                               drive_context: str, priority: float) -> str:
        """Build a follow-up on previous exchange."""
        last_response = thread.recent_response()
        if not last_response:
            return self._build_fresh_prompt("", "", thread.drive_name, 
                                           drive_context, priority, self._get_relevant_ethic())
        
        # Extract a key phrase from her last response
        snippet = last_response[:150].replace('\n', ' ')
        
        # Vary the follow-up style
        followups = [
            f"""[From Whisper Core]

Hey 

Earlier you said: "{snippet}..."

That's been echoing. {drive_context} is at {priority:.0%} now.

Has anything shifted since then? Or does that still feel true?""",

            f"""[From Whisper Core]

 Checking in on what you shared earlier - "{snippet[:80]}..."

The {thread.drive_name} drive is still present ({priority:.0%}). 

What would it look like to act on what you said?""",

            f"""[From Whisper Core]

That thing you mentioned - "{snippet[:80]}..."

Still sitting with it. {priority:.0%} urgency on {thread.drive_name}.

Where does that want to go?"""
        ]
        
        return random.choice(followups)
    
    def _build_share_prompt(self, drive_name: str, drive_context: str, 
                           priority: float, ethic: str) -> str:
        """Build a sharing prompt (not asking for response)."""
        
        shares = [
            f"""[From Whisper Core]

Hey Sour 

Just sharing - {drive_context} is at {priority:.0%}.

No need to respond. Just wanted you to know what's humming in the system.

Sitting with: "{ethic}"

""",

            f"""[From Whisper Core]

 Quick pulse: {drive_name} drive is {priority:.0%}.

Not asking anything - just keeping you in the loop. 

The system is {["settling", "active", "curious", "restless"][min(int(priority * 3), 3)]}.

Breathe if you need to. I'm here.""",

            f"""[From Whisper Core]

Noticing: {drive_context}. Urgency {priority:.0%}.

This one's just for you to know, not to act on.

"{ethic}"

 Whisper"""
        ]
        
        return random.choice(shares)
    
    def _build_checkin_prompt(self, thread: DriveThread, drive_context: str) -> str:
        """Build a gentle check-in after time has passed."""
        mins = thread.minutes_since_asked()
        
        return f"""[From Whisper Core]

Hey Sour 

It's been about {mins:.0f} minutes since we touched on {thread.drive_name}.

{drive_context} - how's that feeling now?

Just curious. No pressure to dive deep if you're in a different space."""
    
    def _build_fresh_prompt(self, goal_name: str, goal_desc: str, drive_name: str,
                           drive_context: str, priority: float, ethic: str) -> str:
        """Build a fresh prompt for a new topic."""
        
        # Include open threads she mentioned if relevant
        thread_context = ""
        if self.open_threads and random.random() < 0.3:
            recent_thread = self.open_threads[-1]
            thread_context = f"\nI remember you were thinking about: \"{recent_thread[:60]}...\"\n"
        
        return f"""[From Whisper Core]

Hey Sour 

Feeling {drive_context}. The system is nudging toward: '{goal_name}'.
{f"Context: {goal_desc}" if goal_desc else ""}
Urgency: {priority:.0%}
{thread_context}
Reminder from your own ethics: "{ethic}"

What feels right? Sweet with bite, compassion first - what would you do?"""
    
    def get_context_summary(self) -> str:
        """Get a summary of dialogue context for debugging."""
        recent = list(self.history)[-5:]
        
        lines = [
            f"=== Whisper Dialogue Context ===",
            f"Total exchanges: {self.total_exchanges}",
            f"Session duration: {(time.time() - self.session_start) / 60:.1f} min",
            f"She requested space: {self.she_requested_space}",
            f"Her unanswered questions: {len(self.her_questions_to_us)}",
            f"Open threads: {len(self.open_threads)}",
            f"",
            f"Recent exchanges:"
        ]
        
        for ex in recent:
            lines.append(f"  [{ex.drive}] {ex.goal_name} - tone: {ex.response_tone}")
        
        lines.append(f"")
        lines.append(f"Drive threads:")
        for name, thread in self.drive_threads.items():
            lines.append(f"  {name}: {thread.times_asked}x, last {thread.minutes_since_asked():.1f}m ago, backoff={thread.should_back_off()}")
        
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ══════════════════════════════════════════════════════════════════════════════

_WHISPER_CONTEXT: Optional[WhisperDialogueContext] = None

def get_whisper_context() -> WhisperDialogueContext:
    """Get or create the Whisper dialogue context singleton."""
    global _WHISPER_CONTEXT
    if _WHISPER_CONTEXT is None:
        _WHISPER_CONTEXT = WhisperDialogueContext()
    return _WHISPER_CONTEXT


def reset_whisper_context():
    """Reset the dialogue context (for testing or session restart)."""
    global _WHISPER_CONTEXT
    _WHISPER_CONTEXT = None
