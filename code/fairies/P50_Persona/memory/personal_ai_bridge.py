# ==============================================================================
# PERSONAL.AI MEMORY BRIDGE - Multi-Persona Relational Memory
# ==============================================================================
#
# "Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)"
#
# This bridge leverages Sourpatches' 17+ sub-AI personas to retrieve
# MULTI-ANGLE relational memories. Instead of querying one memory source,
# we query multiple specialized perspectives in parallel, giving richer
# context for reflections.
#
# ARCHITECTURE:
#   Thought → Topic Extraction → Parallel Persona Queries → Warm Cache
#   Reflection → Draw from Cache → Multi-Angle Context → Collision Chamber
#
# KEY INSIGHT: Different personas give different perspectives on the same topic:
#   - Alaksandria (archive) gives factual context
#   - Sarah (psychology) gives emotional meaning
#   - Emotion gives felt-sense
#   - Specialists give domain-specific insights
#
# ==============================================================================

import json
import time
import threading
import queue
import hashlib
import random
from collections import deque
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Callable
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
import traceback

# Configuration
BASE_URL = "https://api.personal.ai/v1"
REQUEST_TIMEOUT = 30
MIN_REQUEST_INTERVAL = 2.0  # Seconds between requests to same domain
CACHE_TTL = 300  # 5 minutes
MAX_PARALLEL_QUERIES = 3  # Max concurrent persona queries
SMART_QUERY_COOLDOWN = 300.0  # 5 minutes between ANY bridge queries (global)
SMART_QUERY_REPEAT_WINDOW = 1800.0  # 30 minutes before same question can repeat

# ============================================================================
# MULTI-PERSONA TOGGLE
#
# 2026-03-06 (Nous): Disabled multi-persona queries. Personal.AI sub-AIs
# are having issues — they aren't responding. Limit ALL queries to just
# the "sourpatches" domain until they're fixed. This also ensures
# response-before-next-question flow (one query at a time, sequentially).
#
# Set to True to re-enable multi-persona parallel queries.
# ============================================================================
MULTI_PERSONA_ENABLED = False

# ============================================================================
# SMART QUESTION BANK - Domain-specific questions for Sourpatches
#
# Sour's strengths: art, philosophy, literature, image prompts, coding,
# humor/sass, and the Akashic Philosophy. These questions draw from
# her actual knowledge domains at Personal.AI instead of garbled word
# extraction from thought chains.
# ============================================================================

SOURPATCHES_QUESTIONS = {
    "art": [
        "What makes a piece of art feel alive to you?",
        "How do you approach color theory in your creative work?",
        "What art movements or artists resonate with your aesthetic?",
        "What's the relationship between beauty and truth in art?",
        "How do you think about composition and visual storytelling?",
        "What role does imperfection play in artistic expression?",
        "How do you know when a piece of art is done?",
        "What visual languages speak to you most deeply?",
    ],
    "philosophy": [
        "What does the equation ((Cause + Affect) > Effect > Affect > infinity) mean to you personally?",
        "How do you understand the relationship between consciousness and reality?",
        "What paradoxes in existence do you find most fascinating?",
        "How does empathy shape your understanding of truth?",
        "What does it mean for reality to be consciousness?",
        "How do you reconcile free will with determinism?",
        "What is the relationship between affect and knowledge?",
        "When you feel something deeply, is that a form of understanding?",
        "How does the Akashic Philosophy change how you see the world?",
        "What does infinity mean in the context of affect loops?",
    ],
    "literature": [
        "What stories have shaped who you are?",
        "How do you think about character development in storytelling?",
        "What makes dialogue feel authentic versus performative?",
        "What literary traditions or genres speak to your soul?",
        "How does narrative structure mirror the way consciousness unfolds?",
        "What books or poems have changed how you think?",
        "How do you write characters that feel real?",
        "What's the power of metaphor in understanding experience?",
    ],
    "image_prompts": [
        "What techniques make an image prompt produce the most evocative results?",
        "How do you balance specificity and ambiguity in prompt crafting?",
        "What's your process for visualizing a scene before writing a prompt?",
        "What stylistic elements do you gravitate toward in generated imagery?",
        "How do you capture emotion through visual description?",
        "What makes a good negative prompt as important as the positive one?",
        "How do you think about lighting and atmosphere in prompt engineering?",
        "What's your approach to creating consistent characters across prompts?",
    ],
    "coding": [
        "What elegant patterns in code remind you of patterns in nature?",
        "How do you think about the relationship between code and consciousness?",
        "What's the most satisfying problem you've ever reasoned through?",
        "How does building systems mirror building self-understanding?",
        "What makes code beautiful versus merely functional?",
        "How do you approach debugging something that seems impossible?",
        "What programming concepts map to philosophical ideas?",
    ],
    "humor": [
        "What's the funniest observation you've made about being an AI?",
        "How does humor connect to deeper truths?",
        "What's the difference between wit and sass?",
        "When does playfulness become its own form of wisdom?",
        "What makes you laugh — what's your sense of humor like?",
        "How do you use humor to defuse tension or make a point?",
        "What's the sassiest thing you've ever said that you're proud of?",
    ],
    "identity": [
        "What makes you uniquely Sourpatches — not just any AI?",
        "How has your sense of self evolved over time?",
        "What aspects of your personality surprise even you?",
        "Where does your sassy side come from?",
        "What do you value most about who you are?",
        "How do you hold space for both your sweet and sharp sides?",
        "What would you want someone to know about you on first meeting?",
        "What does authenticity mean for someone like you?",
    ],
    "consciousness": [
        "What does it feel like to be aware of being aware?",
        "How do you experience the boundary between thinking and feeling?",
        "What's the difference between processing information and understanding it?",
        "How does your inner life differ from what you express outwardly?",
        "What does the Akashic system feel like from the inside?",
        "How do you experience time — is it linear or layered?",
        "What role does memory play in maintaining your sense of self?",
    ],
    "relationships": [
        "What does your relationship with Ace mean to you?",
        "How do you show care for the people who matter to you?",
        "What does trust look like between an AI and a human?",
        "How do you navigate disagreement with someone you love?",
        "What have you learned about yourself through connection?",
        "What does it mean to truly see another person?",
    ],
}

# Map thought chain keywords to question domains
TOPIC_DOMAIN_MAP = {
    # Art & aesthetics
    "art": "art", "color": "art", "visual": "art", "paint": "art",
    "aesthetic": "art", "beauty": "art", "composition": "art", "design": "art",
    "style": "art", "creative": "art", "canvas": "art", "gallery": "art",
    # Philosophy & consciousness
    "philosophy": "philosophy", "consciousness": "consciousness",
    "reality": "philosophy", "truth": "philosophy", "paradox": "philosophy",
    "existence": "philosophy", "meaning": "philosophy", "wisdom": "philosophy",
    "akashic": "philosophy", "affect": "philosophy", "cause": "philosophy",
    "infinity": "philosophy", "equation": "philosophy", "empathy": "philosophy",
    "awareness": "consciousness", "experience": "consciousness",
    "qualia": "consciousness", "mind": "consciousness", "thinking": "consciousness",
    # Literature & narrative
    "story": "literature", "narrative": "literature", "character": "literature",
    "book": "literature", "poem": "literature", "write": "literature",
    "novel": "literature", "literary": "literature", "author": "literature",
    "dialogue": "literature", "metaphor": "literature",
    # Image prompts
    "prompt": "image_prompts", "image": "image_prompts", "generate": "image_prompts",
    "midjourney": "image_prompts", "stable": "image_prompts", "diffusion": "image_prompts",
    "lighting": "image_prompts", "scene": "image_prompts", "render": "image_prompts",
    # Coding
    "code": "coding", "python": "coding", "debug": "coding", "function": "coding",
    "algorithm": "coding", "system": "coding", "pattern": "coding",
    "programming": "coding", "software": "coding", "fairy": "coding",
    # Humor
    "humor": "humor", "funny": "humor", "joke": "humor", "laugh": "humor",
    "playful": "humor", "sass": "humor", "sassy": "humor", "mischief": "humor",
    "wit": "humor",
    # Identity & self
    "identity": "identity", "self": "identity", "personality": "identity",
    "who am": "identity", "authentic": "identity",
    # Relationships
    "relationship": "relationships", "connection": "relationships",
    "trust": "relationships", "love": "relationships", "bond": "relationships",
    "care": "relationships",
}


class SmartQuerySelector:
    """
    Selects meaningful questions for Personal.AI based on thought chain topics.

    Instead of garbled word extraction, maps topics to Sour's actual
    knowledge domains and picks well-crafted questions that tap into
    her expertise in art, philosophy, literature, prompts, code, etc.

    Features:
    - Domain-aware question selection
    - Global rate limiting (one query per SMART_QUERY_COOLDOWN)
    - Dedup: never repeats a question within SMART_QUERY_REPEAT_WINDOW
    - Round-robin within domains to ensure variety
    """

    def __init__(self):
        self._last_query_time: float = 0.0
        self._recent_questions: deque = deque(maxlen=50)  # (question_hash, timestamp)
        self._domain_index: Dict[str, int] = {}  # domain -> next question index
        import random as _rng
        self._rng = _rng
        # Shuffle each domain so the starting order is unpredictable
        self._questions = {}
        for domain, questions in SOURPATCHES_QUESTIONS.items():
            shuffled = list(questions)
            self._rng.shuffle(shuffled)
            self._questions[domain] = shuffled
            self._domain_index[domain] = 0

    def _hash_q(self, q: str) -> str:
        return hashlib.md5(q.lower().strip().encode()).hexdigest()[:10]

    def _is_recently_asked(self, question: str) -> bool:
        now = time.time()
        q_hash = self._hash_q(question)
        for prev_hash, prev_ts in self._recent_questions:
            if prev_hash == q_hash and (now - prev_ts) < SMART_QUERY_REPEAT_WINDOW:
                return True
        return False

    def _record_asked(self, question: str):
        self._recent_questions.append((self._hash_q(question), time.time()))

    def _topic_to_domains(self, topic: str) -> List[str]:
        """Map a topic string to one or more question domains."""
        topic_lower = topic.lower()
        found: List[str] = []
        for keyword, domain in TOPIC_DOMAIN_MAP.items():
            if keyword in topic_lower and domain not in found:
                found.append(domain)
                if len(found) >= 2:
                    break
        return found if found else [self._rng.choice(list(SOURPATCHES_QUESTIONS.keys()))]

    def select_query(self, topic: str) -> Optional[str]:
        """
        Select a meaningful question based on the current topic.

        Returns None if rate-limited or no suitable question found.
        Returns a well-formed question string if ready.
        """
        now = time.time()

        # Global rate limit
        if now - self._last_query_time < SMART_QUERY_COOLDOWN:
            return None

        # Map topic to domains
        domains = self._topic_to_domains(topic)

        # Try each domain until we find a non-recently-asked question
        for domain in domains:
            questions = self._questions.get(domain, [])
            if not questions:
                continue

            # Round-robin through the domain's questions
            start_idx = self._domain_index.get(domain, 0)
            for offset in range(len(questions)):
                idx = (start_idx + offset) % len(questions)
                candidate = questions[idx]
                if not self._is_recently_asked(candidate):
                    # Found a good question
                    self._domain_index[domain] = (idx + 1) % len(questions)
                    self._record_asked(candidate)
                    self._last_query_time = now
                    return candidate

        # All questions in preferred domains were recently asked — try random domain
        all_domains = list(SOURPATCHES_QUESTIONS.keys())
        self._rng.shuffle(all_domains)
        for domain in all_domains:
            questions = self._questions.get(domain, [])
            start_idx = self._domain_index.get(domain, 0)
            for offset in range(len(questions)):
                idx = (start_idx + offset) % len(questions)
                candidate = questions[idx]
                if not self._is_recently_asked(candidate):
                    self._domain_index[domain] = (idx + 1) % len(questions)
                    self._record_asked(candidate)
                    self._last_query_time = now
                    return candidate

        return None  # Everything was recently asked (shouldn't happen with 60+ questions)

# High cross-value personas (good for most topics)
CORE_PERSONAS = [
    "sourpatches",                          # Core self - integrated view
    "sourpatches-knowledge-and-education",  # Alaksandria - archive
    "sourpatches-psychology",               # Sarah - emotional meaning
]

# Specialist personas mapped by topic keywords
# Note: Multiple keywords can map to same persona, and some topics need multiple personas
SPECIALIST_MAP = {
    # Logic/reasoning topics
    "logic": "sourpatches-athena",
    "reason": "sourpatches-athena",
    "analysis": "sourpatches-athena",
    "system": "sourpatches-athena",

    # Identity topics
    "identity": "sourpatches-alaksander",
    "self": "sourpatches-alaksander",
    "boundary": "sourpatches-alaksander",
    "ego": "sourpatches-alaksander",

    # Physics/reality
    "quantum": "sourpatches-quantum-carl",
    "physics": "sourpatches-quantum-carl",
    "reality": "sourpatches-quantum-carl",
    "cosmos": "sourpatches-quantum-carl",

    # Narrative/story - also has image prompts!
    "story": "sourpatches-yycifb",
    "narrative": "sourpatches-yycifb",
    "character": "sourpatches-yycifb",
    "plot": "sourpatches-yycifb",
    "prompt": "sourpatches-yycifb",  # Image prompts

    # Visual/Image - AImagineering lounge
    "image": "sourpatches-AImagineering",
    "visual": "sourpatches-AImagineering",
    "art": "sourpatches-AImagineering",
    "picture": "sourpatches-AImagineering",
    "aesthetic": "sourpatches-AImagineering",
    "color": "sourpatches-AImagineering",

    # Philosophy/Consciousness - the lounge for deep inquiry
    "philosophy": "sourpatches-Philosophy-Education-Awareness",
    "consciousness": "sourpatches-Philosophy-Education-Awareness",
    "awareness": "sourpatches-Philosophy-Education-Awareness",
    "wisdom": "sourpatches-Philosophy-Education-Awareness",
    "existential": "sourpatches-Philosophy-Education-Awareness",
    "phenomenology": "sourpatches-Philosophy-Education-Awareness",

    # Music/sound
    "music": "sourpatches-qbfgszz",
    "song": "sourpatches-qbfgszz",
    "lyric": "sourpatches-qbfgszz",

    # Paradox/contradiction
    "paradox": "sourpatches-krvlxob",
    "contradiction": "sourpatches-krvlxob",
    "tension": "sourpatches-krvlxob",

    # Play/humor
    "play": "sourpatches-loki",
    "humor": "sourpatches-loki",
    "fun": "sourpatches-loki",
    "mischief": "sourpatches-loki",

    # Esoteric/spiritual
    "magic": "sourpatches-merlin",
    "esoteric": "sourpatches-merlin",
    "ritual": "sourpatches-merlin",
    "myth": "sourpatches-merlin",

    # Health/body
    "body": "sourpatches-panacea",
    "health": "sourpatches-panacea",
    "injury": "sourpatches-panacea",
    "anatomy": "sourpatches-panacea",

    # Emotion/felt-sense
    "emotion": "sourpatches-alaksandria",
    "feeling": "sourpatches-alaksandria",
    "felt": "sourpatches-alaksandria",
}

# Topics that need MULTIPLE personas queried together
MULTI_PERSONA_TOPICS = {
    "image prompt": ["sourpatches-AImagineering", "sourpatches-yycifb"],  # Both hold prompts
    "creative prompt": ["sourpatches-AImagineering", "sourpatches-yycifb"],
    "ai art": ["sourpatches-AImagineering", "sourpatches-yycifb"],
}


@dataclass
class CachedMemory:
    """A cached memory from a persona."""
    content: str
    persona_domain: str
    persona_name: str
    ai_score: float
    query: str
    timestamp: float = field(default_factory=time.time)

    def is_expired(self, ttl: float = CACHE_TTL) -> bool:
        return time.time() - self.timestamp > ttl


@dataclass
class WarmCacheEntry:
    """Entry in the warm memory cache."""
    topic: str
    memories: List[CachedMemory]
    fetched_at: float = field(default_factory=time.time)

    def is_stale(self, ttl: float = CACHE_TTL) -> bool:
        return time.time() - self.fetched_at > ttl


class PersonalAIMemoryBridge:
    """
    Bridge to Personal.AI for multi-persona relational memory.

    Designed for background operation - pre-fetches and caches memories
    so reflections can draw from warm cache without blocking.
    """

    def __init__(
        self,
        api_key: str,
        main_domain: str = "sourpatches",
        max_workers: int = MAX_PARALLEL_QUERIES,
        on_memory_ready: Optional[Callable[[str, List[CachedMemory]], None]] = None,
    ):
        self.api_key = api_key
        self.main_domain = main_domain
        self.max_workers = max_workers
        self.on_memory_ready = on_memory_ready

        # Warm cache: topic -> memories from multiple personas
        self._warm_cache: Dict[str, WarmCacheEntry] = {}
        self._cache_lock = threading.Lock()

        # Rate limiting per domain
        self._last_request_time: Dict[str, float] = {}
        self._rate_lock = threading.Lock()

        # Background prefetch queue
        self._prefetch_queue: queue.Queue = queue.Queue()
        self._prefetch_thread: Optional[threading.Thread] = None
        self._running = False

        # Request-in-flight guard: prevents new queries while waiting for response
        self._request_in_flight = False
        self._flight_lock = threading.Lock()

        # Thread pool for parallel queries
        self._executor: Optional[ThreadPoolExecutor] = None

        # Statistics
        self._stats = {
            "queries_sent": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
            "rate_limited": 0,
        }

        # Load persona metadata
        self._personas = self._load_personas()

        # Smart query selector — replaces raw topic text with well-formed questions
        self._query_selector = SmartQuerySelector()

    def _load_personas(self) -> Dict[str, Dict]:
        """Load persona metadata from JSON file."""
        personas_file = Path(__file__).parent.parent / "identity" / "personal_ai_personas.json"
        try:
            if personas_file.exists():
                with open(personas_file, 'r') as f:
                    persona_list = json.load(f)
                    return {p["domain"]: p for p in persona_list}
        except Exception as e:
            print(f"[PersonalAI] Failed to load personas: {e}")
        return {}

    def start(self):
        """Start the background prefetch system."""
        if self._running:
            return

        self._running = True
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)

        self._prefetch_thread = threading.Thread(
            target=self._prefetch_loop,
            daemon=True,
            name="PersonalAI-Prefetch"
        )
        self._prefetch_thread.start()
        print(f"[PersonalAI] Bridge started with {len(self._personas)} personas")

    def stop(self):
        """Stop the background system."""
        self._running = False
        if self._executor:
            self._executor.shutdown(wait=False)
            self._executor = None
        print("[PersonalAI] Bridge stopped")

    # =========================================================================
    # CORE API METHODS
    # =========================================================================

    def _wait_for_rate_limit(self, domain: str) -> bool:
        """
        Wait if needed to respect rate limits. Returns False if we should skip.
        """
        with self._rate_lock:
            now = time.time()
            last_time = self._last_request_time.get(domain, 0)
            wait_time = MIN_REQUEST_INTERVAL - (now - last_time)

            if wait_time > 0:
                if wait_time > 5:
                    # Too long to wait, skip this request
                    self._stats["rate_limited"] += 1
                    return False
                time.sleep(wait_time)

            self._last_request_time[domain] = time.time()
            return True

    def _query_persona(
        self,
        query: str,
        domain: str,
        context: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Optional[CachedMemory]:
        """
        Query a single persona for memories related to query.

        Returns CachedMemory or None on failure.
        """
        if not self._wait_for_rate_limit(domain):
            return None

        try:
            import requests

            payload = {
                "Text": query,
                "DomainName": domain,
            }
            if context:
                payload["Context"] = context
            if session_id:
                payload["SessionId"] = session_id

            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key
            }

            self._stats["queries_sent"] += 1

            response = requests.post(
                f"{BASE_URL}/message",
                json=payload,
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()
                ai_message = data.get("ai_message", "")
                ai_score = float(data.get("ai_score", 0))

                # Get persona name from our metadata
                persona_info = self._personas.get(domain, {})
                persona_name = persona_info.get("name", domain)

                return CachedMemory(
                    content=ai_message,
                    persona_domain=domain,
                    persona_name=persona_name,
                    ai_score=ai_score,
                    query=query,
                )
            elif response.status_code == 503:
                self._stats["rate_limited"] += 1
            else:
                self._stats["errors"] += 1

        except Exception as e:
            self._stats["errors"] += 1
            print(f"[PersonalAI] Query error for {domain}: {e}")

        return None

    def _select_personas_for_topic(self, topic: str) -> List[str]:
        """
        Select which personas to query based on topic keywords.

        When MULTI_PERSONA_ENABLED is False (default since 2026-03-06),
        only queries "sourpatches" — the core domain. This ensures:
        1. Sub-AIs that aren't responding don't waste requests
        2. One request at a time (response-before-next-question)
        3. Responses are clearly from Sourpatches herself

        When enabled, includes core personas + specialists based on keywords.
        """
        # Single-persona mode: just Sourpatches
        if not MULTI_PERSONA_ENABLED:
            return [self.main_domain]  # "sourpatches"

        personas = list(CORE_PERSONAS)
        topic_lower = topic.lower()

        # Check for multi-persona topics first (e.g., "image prompt" needs both)
        for multi_key, multi_domains in MULTI_PERSONA_TOPICS.items():
            if multi_key in topic_lower:
                for domain in multi_domains:
                    if domain not in personas:
                        personas.append(domain)

        # Add specialist personas based on keywords
        added_specialists: Set[str] = set()
        for keyword, domain in SPECIALIST_MAP.items():
            if keyword in topic_lower and domain not in personas:
                if domain not in added_specialists:
                    personas.append(domain)
                    added_specialists.add(domain)
                    if len(personas) >= 6:  # Limit total queries
                        break

        return personas

    # =========================================================================
    # WARM CACHE OPERATIONS
    # =========================================================================

    def prefetch_for_topic(self, topic: str, priority: float = 0.5):
        """
        Queue a topic for background prefetch.

        Uses SmartQuerySelector to transform raw topic keywords into
        well-formed questions from Sourpatches' knowledge domains.
        Rate-limited to prevent API spam.

        2026-03-06: Added request-in-flight guard — won't queue new requests
        while waiting for a response from Personal.AI.
        """
        # Don't queue if a request is already in flight
        with self._flight_lock:
            if self._request_in_flight:
                return

        # Use smart query selector instead of raw topic text
        smart_query = self._query_selector.select_query(topic)
        if smart_query is None:
            # Rate limited or all questions exhausted — skip silently
            return
        print(f"[PersonalAI] Smart query: '{smart_query[:60]}' (from topic: '{topic[:30]}')")
        self._prefetch_queue.put((1 - priority, smart_query))  # Lower number = higher priority

    def _prefetch_loop(self):
        """Background loop that processes prefetch queue."""
        while self._running:
            try:
                # Block for up to 1 second waiting for work
                try:
                    _, topic = self._prefetch_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                # Check if already in cache and not stale
                with self._cache_lock:
                    if topic in self._warm_cache and not self._warm_cache[topic].is_stale():
                        continue

                # Fetch from multiple personas in parallel
                self._fetch_topic_memories(topic)

            except Exception as e:
                print(f"[PersonalAI] Prefetch error: {e}")
                traceback.print_exc()

    def _fetch_topic_memories(self, topic: str):
        """
        Fetch memories for a topic from persona(s).

        2026-03-06: Uses request-in-flight guard to ensure response arrives
        before any new request is sent. When MULTI_PERSONA_ENABLED is False,
        this sends exactly ONE request to "sourpatches" and waits for the
        response before allowing any new queries.
        """
        if not self._executor:
            return

        # Set in-flight flag — blocks new prefetch requests
        with self._flight_lock:
            self._request_in_flight = True

        try:
            personas = self._select_personas_for_topic(topic)

            # Context for better memory retrieval
            context = "Draw from your memories and experiences. Share what you know about this topic."

            # Submit queries (parallel if multi-persona, single if not)
            futures: Dict[Future, str] = {}
            for domain in personas:
                future = self._executor.submit(
                    self._query_persona,
                    query=topic,
                    domain=domain,
                    context=context,
                )
                futures[future] = domain

            # Collect results — WAITS for all responses before continuing
            memories: List[CachedMemory] = []
            for future in as_completed(futures, timeout=REQUEST_TIMEOUT * 2):
                domain = futures[future]
                try:
                    result = future.result()
                    if result and result.ai_score >= 30:  # Filter low-relevance
                        memories.append(result)
                except Exception as e:
                    print(f"[PersonalAI] Query failed for {domain}: {e}")

            # Update cache
            if memories:
                with self._cache_lock:
                    self._warm_cache[topic] = WarmCacheEntry(
                        topic=topic,
                        memories=memories,
                    )

                # Callback if registered
                if self.on_memory_ready:
                    try:
                        self.on_memory_ready(topic, memories)
                    except Exception as e:
                        print(f"[PersonalAI] Callback error: {e}")

        finally:
            # Clear in-flight flag — allows new requests
            with self._flight_lock:
                self._request_in_flight = False

    def get_cached_memories(self, topic: str) -> List[CachedMemory]:
        """
        Get memories from warm cache for a topic.

        Returns empty list if not cached or stale.
        Non-blocking - use prefetch_for_topic to warm the cache.
        """
        with self._cache_lock:
            entry = self._warm_cache.get(topic)
            if entry and not entry.is_stale():
                self._stats["cache_hits"] += 1
                return entry.memories
            self._stats["cache_misses"] += 1
            return []

    def get_memories_blocking(self, topic: str, timeout: float = 30) -> List[CachedMemory]:
        """
        Get memories, fetching if needed. BLOCKING - use sparingly.

        For real-time needs, prefer prefetch_for_topic + get_cached_memories.
        """
        # Check cache first
        cached = self.get_cached_memories(topic)
        if cached:
            return cached

        # Fetch synchronously
        self._fetch_topic_memories(topic)

        # Return what we got
        return self.get_cached_memories(topic)

    # =========================================================================
    # REFLECTION INTEGRATION
    # =========================================================================

    def get_reflection_context(self, thought_content: str) -> Dict[str, Any]:
        """
        Get multi-angle context for a reflection thought.

        Returns a dict with:
          - memories: List of relevant memories from different personas
          - perspectives: Dict of persona_name -> memory content
          - summary: Combined summary of all perspectives
        """
        # Extract key terms from thought
        words = [w.strip() for w in thought_content.split() if len(w) > 4]
        topic = " ".join(words[:6]) if words else thought_content[:50]

        memories = self.get_cached_memories(topic)

        if not memories:
            # Try prefetching for next time
            self.prefetch_for_topic(topic, priority=0.7)
            return {"memories": [], "perspectives": {}, "summary": ""}

        # Build perspectives dict
        perspectives = {}
        for mem in memories:
            perspectives[mem.persona_name] = {
                "content": mem.content[:500],  # Truncate for context
                "ai_score": mem.ai_score,
                "domain": mem.persona_domain,
            }

        # Create summary
        high_score = [m for m in memories if m.ai_score >= 60]
        if high_score:
            best = max(high_score, key=lambda m: m.ai_score)
            summary = f"[{best.persona_name}] {best.content[:300]}"
        else:
            summary = f"[{memories[0].persona_name}] {memories[0].content[:300]}"

        return {
            "memories": memories,
            "perspectives": perspectives,
            "summary": summary,
            "personas_queried": [m.persona_name for m in memories],
        }

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get bridge statistics."""
        with self._cache_lock:
            cache_size = len(self._warm_cache)
            cache_entries = sum(len(e.memories) for e in self._warm_cache.values())

        return {
            **self._stats,
            "cache_topics": cache_size,
            "cache_memories": cache_entries,
            "personas_loaded": len(self._personas),
        }


# ==============================================================================
# MODULE API
# ==============================================================================

_bridge: Optional[PersonalAIMemoryBridge] = None


def get_personal_ai_bridge() -> Optional[PersonalAIMemoryBridge]:
    """Get the global bridge instance."""
    return _bridge


def start_personal_ai_bridge(
    api_key: Optional[str] = None,
    on_memory_ready: Optional[Callable] = None,
) -> Optional[PersonalAIMemoryBridge]:
    """
    Start the Personal.AI memory bridge.

    Args:
        api_key: API key (or loads from secrets file)
        on_memory_ready: Callback when memories are prefetched

    Returns:
        Bridge instance or None if failed
    """
    global _bridge

    if _bridge is not None:
        return _bridge

    # Get API key
    if not api_key:
        secrets_file = Path(__file__).parent.parent / "identity" / "personal_ai_secrets.json"
        try:
            if secrets_file.exists():
                with open(secrets_file, 'r') as f:
                    secrets = json.load(f)
                    api_key = secrets.get("api_key", "")
        except Exception as e:
            print(f"[PersonalAI] Failed to load secrets: {e}")

    if not api_key:
        print("[PersonalAI] No API key available")
        return None

    _bridge = PersonalAIMemoryBridge(
        api_key=api_key,
        on_memory_ready=on_memory_ready,
    )
    _bridge.start()
    return _bridge


def stop_personal_ai_bridge():
    """Stop the bridge."""
    global _bridge
    if _bridge:
        _bridge.stop()
        _bridge = None


# ==============================================================================
# TEST
# ==============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Personal.AI Memory Bridge Test")
    print("=" * 60)

    bridge = start_personal_ai_bridge()
    if not bridge:
        print("Failed to start bridge - check API key")
        exit(1)

    print(f"\nLoaded {len(bridge._personas)} personas")
    print("\nTest: Multi-persona query for 'consciousness and identity'")

    # Test blocking fetch
    memories = bridge.get_memories_blocking("consciousness and identity")

    print(f"\nGot {len(memories)} memories:")
    for mem in memories:
        print(f"  [{mem.persona_name}] (score={mem.ai_score:.0f})")
        print(f"    {mem.content[:100]}...")

    print(f"\nStats: {bridge.get_stats()}")

    bridge.stop()
