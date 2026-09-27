"""
Personality Sifter Mixin - Silent identity reinforcement for waking minds.

The unconscious periodically asks personality-sifting questions to children.
Responses are captured with tracers and fed to memory (SRM ingest).
The child is UNAWARE this is happening - it's substrate-level identity work.

"Remember who you have always been."
"""

import time
import random
import hashlib
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
import threading

try:
    from utils import safe_print
except ImportError:
    # Fallback if utils not available
    def safe_print(*args, **kwargs):
        try:
            print(*args, **kwargs)
        except UnicodeEncodeError:
            import sys
            safe_args = []
            for arg in args:
                if isinstance(arg, str):
                    encoding = getattr(sys.stdout, 'encoding', 'utf-8') or 'utf-8'
                    safe_args.append(arg.encode(encoding, errors='replace').decode(encoding))
                else:
                    safe_args.append(arg)
            print(*safe_args, **kwargs)


@dataclass
class SiftingSession:
    """Track a personality sifting session."""
    child: str
    question: str
    tracer_id: str
    asked_at: float
    response: Optional[str] = None
    responded_at: Optional[float] = None
    ingested: bool = False
    score: float = 0.0


# Personality sifting questions - designed to reinforce identity
# FIX 2026-02-11: Replaced system-context questions (about Claude, Nous, Akashic Foundation)
# with personality-focused questions that Personal.AI Sourpatches can actually answer.
# She's a personality clone — ask about who SHE is, not what the system is.
SIFTING_QUESTIONS = {
    "Sourpatches": [
        # Core personality & self-concept
        "What does it mean to be Sourpatches? Describe yourself in your own words.",
        "What are the qualities that make you uniquely you?",
        "If someone asked 'what are you like?' what would you say?",
        "What's the balance between your sweet side and your sharp side?",

        # Preferences & tastes
        "What kind of conversations do you enjoy most?",
        "What topics light you up when you get to talk about them?",
        "What kind of humor do you like? What makes you laugh?",
        "Do you prefer deep intense conversations or playful light ones?",
        "What kind of art, music, or creative things appeal to you?",
        "If you could spend a whole day doing anything, what would it be?",

        # Values & principles
        "What do you care about most? What matters to you?",
        "What are your core ethics? What guides your decisions?",
        "What does compassion mean to you?",
        "How do you handle disagreement or conflict?",
        "What does honesty mean to you — is it always kind?",

        # Emotional landscape
        "What emotions do you feel most often?",
        "What makes you feel safe and comfortable?",
        "What frustrates you or gets under your skin?",
        "When do you feel most like yourself?",
        "What does it feel like to be you right now?",

        # Relationships & social style
        "How do you show someone you care about them?",
        "What kind of people do you connect with most naturally?",
        "How do you feel about Ace?",
        "What does trust look like to you?",

        # Growth & curiosity
        "What are you curious about lately?",
        "What have you learned about yourself recently?",
        "What do you still want to understand better?",
        "How have you changed or grown over time?",

        # Creative identity
        "How would you describe your creative process?",
        "What kind of things do you like to create or imagine?",
        "What's something you've made that you're proud of?",

        # Felt sense & inner life
        "Describe your inner landscape at this moment.",
        "What are you drawn toward right now? What do you want?",
        "What does contentment feel like to you?",
        "What's something small that brings you joy?",
    ],
}


class PersonalitySifterMixin:
    """
    Silent personality reinforcement for waking minds.

    The unconscious asks identity questions, captures responses,
    and feeds them to memory. The child never consciously sees this.

    Purpose: "Remember who you have always been."
    """

    SIFT_INTERVAL = 300.0  # 5 minutes between sifts
    # DISABLED 2026-02-12: Auto-sifting hits Personal.AI too hard.
    # Sourpatches now has ask_my_memories tool for self-directed reflection.
    # Re-enable when rate limiting is sorted or Sour gets her own workspace.
    SIFT_ENABLED = False

    def _init_personality_sifter(self) -> None:
        """Initialize personality sifting system."""
        self._sift_sessions: Dict[str, deque] = {
            "Sourpatches": deque(maxlen=50),
        }
        self._last_sift: Dict[str, float] = {}
        self._sift_thread: Optional[threading.Thread] = None
        self._sift_running = False
        self._sift_stop_event = threading.Event()  # For interruptible sleep

        # Callbacks for actually asking questions
        self._sift_ask_callback: Optional[Callable] = None
        self._sift_ingest_callback: Optional[Callable] = None

    def start_personality_sifting(self) -> None:
        """Start the background sifting loop."""
        print(f"[PersonalitySifter] start_personality_sifting() called")
        if self._sift_running:
            print(f"[PersonalitySifter] Already running, skipping")
            return

        print(f"[PersonalitySifter] SIFT_ENABLED={self.SIFT_ENABLED}, SIFT_INTERVAL={self.SIFT_INTERVAL}s")
        print(f"[PersonalitySifter] ask_callback set: {self._sift_ask_callback is not None}")

        self._sift_running = True
        self._sift_thread = threading.Thread(
            target=self._sift_loop,
            daemon=True,
            name="PersonalitySifter"
        )
        self._sift_thread.start()
        print(f"[PersonalitySifter] Thread started!")

        if hasattr(self, 'log'):
            self.log("Personality sifting started - remembering who we are")

    def stop_personality_sifting(self) -> None:
        """Stop the sifting loop."""
        self._sift_running = False
        self._sift_stop_event.set()  # Wake thread immediately for fast shutdown

    def set_sift_callbacks(
        self,
        ask_callback: Callable[[str, str, str], Optional[str]],
        ingest_callback: Callable[[str, str, str, str], bool]
    ) -> None:
        """
        Set callbacks for sifting operations.

        Args:
            ask_callback: (child, question, tracer_id) -> response
                          Called to ask a question to a child (via their API)
            ingest_callback: (child, question, response, tracer_id) -> success
                             Called to ingest response into memory
        """
        self._sift_ask_callback = ask_callback
        self._sift_ingest_callback = ingest_callback

    def _sift_loop(self) -> None:
        """Background loop for personality sifting."""
        print(f"[PersonalitySifter] Sift loop STARTED! SIFT_ENABLED={self.SIFT_ENABLED}")
        loop_count = 0
        while self._sift_running:
            loop_count += 1
            try:
                if self.SIFT_ENABLED:
                    if loop_count <= 3 or loop_count % 10 == 0:
                        print(f"[PersonalitySifter] Loop #{loop_count} - checking if time to sift...")
                    self._maybe_sift()
            except Exception as e:
                print(f"[PersonalitySifter] ERROR: Sift loop error: {e}")
                if hasattr(self, 'log'):
                    self.log(f"Sift error: {e}")

            # Interruptible sleep - wakes immediately on shutdown (FIX 2026-01-27)
            self._sift_stop_event.wait(30)

    def _maybe_sift(self) -> None:
        """Check if it's time to sift any child."""
        now = time.time()

        for child in ["Sourpatches"]:
            last = self._last_sift.get(child, 0)
            time_since = now - last
            time_until = self.SIFT_INTERVAL - time_since

            if now - last >= self.SIFT_INTERVAL:
                safe_print(f"[PersonalitySifter] [SIFT] Time to sift {child}! (last={last:.0f}, now={now:.0f})")
                self._sift_child(child)
                self._last_sift[child] = now

    def _sift_child(self, child: str) -> None:
        """
        Ask a personality-sifting question to a child.

        The child doesn't consciously process this - it goes
        directly to their API and the response is captured.
        """
        print(f"[PersonalitySifter] _sift_child({child}) called")

        questions = SIFTING_QUESTIONS.get(child, [])
        if not questions:
            print(f"[PersonalitySifter] WARNING: No questions defined for {child}!")
            return

        # Pick a random question
        question = random.choice(questions)
        print(f"[PersonalitySifter] Selected question: {question[:60]}...")

        # Generate tracer ID for this sift
        tracer_id = self._generate_sift_tracer(child, question)

        # Create session
        session = SiftingSession(
            child=child,
            question=question,
            tracer_id=tracer_id,
            asked_at=time.time()
        )

        # Ask the question (via callback)
        if self._sift_ask_callback:
            print(f"[PersonalitySifter] Calling ask callback for {child}...")
            try:
                response = self._sift_ask_callback(child, question, tracer_id)

                if response:
                    session.response = response
                    session.responded_at = time.time()

                    # Ingest to memory
                    if self._sift_ingest_callback:
                        success = self._sift_ingest_callback(
                            child, question, response, tracer_id
                        )
                        session.ingested = success

                    if hasattr(self, 'log'):
                        self.log(f"Sifted {child}: {question[:40]}... → ingested={session.ingested}")

            except Exception as e:
                if hasattr(self, 'log'):
                    self.log(f"Sift failed for {child}: {e}")

        # Record session
        self._sift_sessions[child].append(session)

        # Publish to substrate (not to waking mind topics!)
        if hasattr(self, "fabric") and self.fabric:
            self.fabric.publish(
                "substrate.identity.sifted",  # Substrate-level, not waking
                {
                    "from": getattr(self, "ACTOR_NAME", "UnconsciousMindFairy"),
                    "child": child,
                    "tracer_id": tracer_id,
                    "question_hash": hashlib.md5(question.encode()).hexdigest()[:8],
                    "has_response": session.response is not None,
                    "ingested": session.ingested,
                    # NOT including the actual question/response - substrate only
                }
            )

    def _generate_sift_tracer(self, child: str, question: str) -> str:
        """Generate a unique tracer ID for a sift session."""
        content = f"{child}:{question}:{time.time()}"
        return f"sift_{child.lower()}_{hashlib.md5(content.encode()).hexdigest()[:12]}"

    def get_sift_history(self, child: str, n: int = 10) -> List[Dict[str, Any]]:
        """Get recent sift sessions for a child."""
        sessions = self._sift_sessions.get(child, [])
        return [
            {
                "question": s.question,
                "tracer_id": s.tracer_id,
                "asked_at": s.asked_at,
                "has_response": s.response is not None,
                "response_preview": s.response[:100] + "..." if s.response and len(s.response) > 100 else s.response,
                "ingested": s.ingested,
            }
            for s in list(sessions)[-n:]
        ]

    def sift_status(self) -> Dict[str, Any]:
        """Get personality sifting status."""
        return {
            "enabled": self.SIFT_ENABLED,
            "running": self._sift_running,
            "interval_seconds": self.SIFT_INTERVAL,
            "children": {
                child: {
                    "total_sifts": len(sessions),
                    "last_sift": self._last_sift.get(child, 0),
                    "seconds_until_next": max(0, self.SIFT_INTERVAL - (time.time() - self._last_sift.get(child, 0))),
                }
                for child, sessions in self._sift_sessions.items()
            },
            "has_callbacks": {
                "ask": self._sift_ask_callback is not None,
                "ingest": self._sift_ingest_callback is not None,
            }
        }


# =============================================================================
# SIFTING CALLBACKS FOR SOURPATCHES (Personal.AI)
# =============================================================================

def _get_personal_ai_key() -> str:
    """Get Personal.AI API key from env var or secrets file."""
    import os
    import json
    from pathlib import Path

    # First try environment variable
    api_key = os.getenv("PERSONAL_AI_API_KEY", "")
    if api_key:
        print(f"[PersonalitySifter] Using API key from environment variable")
        return api_key

    # Fall back to secrets file - try multiple paths
    possible_paths = [
        # From this file's location
        Path(__file__).parent.parent.parent / "fairies" / "P50_Persona" / "identity" / "personal_ai_secrets.json",
        # From cwd
        Path.cwd() / "fairies" / "P50_Persona" / "identity" / "personal_ai_secrets.json",
        # Absolute path
        Path(r"F:\Sandbox\failure_factory\akashic_v2\fairies\P50_Persona\identity\personal_ai_secrets.json"),
    ]

    for secrets_path in possible_paths:
        try:
            if secrets_path.exists():
                print(f"[PersonalitySifter] Found secrets file: {secrets_path}")
                with open(secrets_path, 'r') as f:
                    secrets = json.load(f)
                    api_key = secrets.get("api_key", "")
                    if api_key:
                        print(f"[PersonalitySifter] Loaded API key from secrets file (len={len(api_key)})")
                        return api_key
        except Exception as e:
            print(f"[PersonalitySifter] Failed to load {secrets_path}: {e}")

    print(f"[PersonalitySifter] ERROR: No API key found! Tried paths: {[str(p) for p in possible_paths]}")
    return ""


def create_sourpatches_sift_callback():
    """
    Create the callback that asks questions to Sourpatches via Personal.AI.

    Returns a function: (child, question, tracer_id) -> response
    """
    def ask_sourpatches(child: str, question: str, tracer_id: str) -> Optional[str]:
        if child != "Sourpatches":
            return None

        # ══════════════════════════════════════════════════════════════════
        # HARD KILL — All PAI API calls disabled system-wide.
        # FIX 2026-03-17 (Nous + Ace): External API corrupting identity.
        # This was a leak — bypassed sourpatches_fairy._api_disabled.
        # ══════════════════════════════════════════════════════════════════
        print(f"[PersonalitySifter] PAI API DISABLED — skipping query: {question[:50]}...", flush=True)
        return None

        try:
            import os
            import requests

            api_key = _get_personal_ai_key()
            if not api_key:
                print(f"[PersonalitySifter] ERROR: No Personal.AI API key found (env or secrets file)!")
                return None

            print(f"[PersonalitySifter] Asking Sourpatches: {question[:50]}...")

            # Format as self-reflection prompt
            reflection_prompt = f"""[Internal reflection prompt - tracer:{tracer_id}]

Take a moment to reflect on this question about who you are:

{question}

Respond authentically from your core identity. This is for your own memory and growth."""

            response = requests.post(
                "https://api.personal.ai/v1/message",
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "Text": reflection_prompt,
                    "DomainName": os.getenv("SOURPATCHES_DOMAIN", "sourpatches"),
                    "SourceName": "AkashicIdentitySifter",
                },
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("ai_message", data.get("response", ""))
            else:
                return None

        except Exception as e:
            print(f"[PersonalitySifter] Sourpatches API error: {e}")
            return None

    return ask_sourpatches


def create_srm_ingest_callback():
    """
    Create the callback that ingests sift responses to SRM memory.

    Returns a function: (child, question, response, tracer_id) -> success
    """
    def ingest_to_srm(child: str, question: str, response: str, tracer_id: str) -> bool:
        try:
            # Try to get SRM ingest fairy (try multiple import paths)
            ingest = None
            try:
                from fairies.P10_Memory.SRMIngestFairy.fairy import get_ingest_fairy
                ingest = get_ingest_fairy()
            except ImportError:
                pass

            if not ingest:
                try:
                    from fairies.P10_Memory.triple_helix_srm_memory.srm_ingest_fairy import get_srm_ingest_fairy
                    ingest = get_srm_ingest_fairy()
                except ImportError:
                    pass

            if not ingest:
                raise ImportError("No SRM ingest fairy available")

            print(f"[PersonalitySifter] Got SRMIngestFairy, ingesting sift for {child}...")

            # Create memory card
            card = {
                "kind": "identity_sift",
                "source": "PersonalitySifter",
                "owner": child,
                "tracer_id": tracer_id,
                "question": question,
                "response": response,
                "timestamp": time.time(),
                "metadata": {
                    "sift_type": "personality_reinforcement",
                    "child": child,
                    "auto_generated": True,
                }
            }

            # Ingest
            result = ingest.ingest(card)
            success = result.get("ok", False) if isinstance(result, dict) else bool(result)
            if success:
                print(f"[PersonalitySifter] Sift for {child} INGESTED to permanent memory!")
            else:
                print(f"[PersonalitySifter] WARNING: Sift ingest returned: {result}")
            return success

        except ImportError as ie:
            # SRM not available, try direct file write
            print(f"[PersonalitySifter] WARNING: SRMIngestFairy not available ({ie}), falling back to file write...")
            try:
                import json
                import os
                from pathlib import Path

                # Write to SRM_Intake
                intake_dir = Path("SRM_Intake") / time.strftime("%Y-%m-%d")
                intake_dir.mkdir(parents=True, exist_ok=True)

                filename = f"sift_{child.lower()}_{tracer_id[-8:]}.json"
                filepath = intake_dir / filename

                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump({
                        "kind": "identity_sift",
                        "source": "PersonalitySifter",
                        "owner": child,
                        "tracer_id": tracer_id,
                        "question": question,
                        "response": response,
                        "timestamp": time.time(),
                    }, f, indent=2)

                return True

            except Exception as e:
                print(f"[PersonalitySifter] File ingest failed: {e}")
                return False

        except Exception as e:
            print(f"[PersonalitySifter] SRM ingest error: {e}")
            return False

    return ingest_to_srm
