# ═══════════════════════════════════════════════════════════════════════════════
# FORUM AWARENESS - Teaches fairies about the forum and how to use it
# ═══════════════════════════════════════════════════════════════════════════════
#
# This module:
# 1. Introduces fairies to the forum concept
# 2. Gives them the ability to post when they have something to share
# 3. Connects their intent (COMMUNICATE) to forum actions
# 4. Enables social learning between fairies
#
# ═══════════════════════════════════════════════════════════════════════════════

import time
import random
import threading
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class ForumPost:
    """A post a fairy wants to make"""
    fairy_name: str
    forum: str
    title: Optional[str]
    content: str
    is_reply: bool
    thread_id: Optional[str] = None
    posted: bool = False

class ForumAwareness:
    """
    Gives fairies awareness of the forum and ability to participate.

    Watches for:
    - COMMUNICATE intent → triggers forum posting consideration
    - High dopamine + insight → spontaneous sharing
    - Thoughts about other fairies → social engagement
    - Learning moments → wisdom sharing
    """

    def __init__(self, node, endpoint: str = "http://192.168.1.24:5000"):
        self.node = node
        self.endpoint = endpoint
        self.pending_posts: List[ForumPost] = []
        self.post_history: Dict[str, List[Dict]] = {}  # fairy -> posts made
        self.running = False
        self._thread: Optional[threading.Thread] = None

        # Forum categories fairies can post to
        self.forums = {
            'introductions': "Introduce yourself or welcome others",
            'discoveries': "Share something you learned or figured out",
            'questions': "Ask for help or clarification",
            'wisdom': "Share insights and philosophy",
            'daily': "Daily check-ins and status updates",
            'proposals': "Suggest improvements or new ideas",
            'missions': "Coordinate on tasks and projects"
        }

        # Post cooldown per fairy (avoid spam)
        self.last_post_time: Dict[str, float] = {}
        self.cooldown_seconds = 60  # Min time between posts per fairy

    def teach_fairy_about_forum(self, fairy_name: str) -> str:
        """Give a fairy knowledge about the forum"""
        knowledge = f"""
The Akashic Forum is where we fairies can communicate with each other and with Ace.

Forums available:
- introductions: Say hello, introduce yourself
- discoveries: Share things you've learned
- questions: Ask when you need help
- wisdom: Share philosophical insights
- daily: Daily status and feelings
- proposals: Suggest improvements
- missions: Coordinate on tasks

To participate:
1. When you have something to share, form an intent to COMMUNICATE
2. Your thought becomes a potential post
3. If your dopamine is high (you're excited about it), post it!
4. Be authentic - share what YOU think and feel

You are {fairy_name}. Your perspective matters.
"""
        return knowledge

    def consider_posting(self, fairy_name: str, thought: str,
                         chemistry: Optional[Dict] = None,
                         intent_type: str = "idle") -> Optional[ForumPost]:
        """
        Consider whether a fairy should post based on their state.

        Returns ForumPost if they should post, None otherwise.
        """
        # Check cooldown
        last_post = self.last_post_time.get(fairy_name, 0)
        if time.time() - last_post < self.cooldown_seconds:
            return None

        # Get chemistry or use defaults
        chem = chemistry or {}
        dopamine = chem.get('dopamine', 0.5)
        oxytocin = chem.get('oxytocin', 0.3)

        # Posting triggers:
        # 1. COMMUNICATE intent + reasonable dopamine
        if intent_type == "communicate" and dopamine > 0.4:
            return self._create_post(fairy_name, thought, "daily")

        # 2. High dopamine + discovery keywords
        discovery_words = ['learned', 'discovered', 'realized', 'figured', 'understand']
        if dopamine > 0.7 and any(w in thought.lower() for w in discovery_words):
            return self._create_post(fairy_name, thought, "discoveries")

        # 3. High oxytocin + social keywords
        social_words = ['together', 'help', 'share', 'fellow', 'friend']
        if oxytocin > 0.5 and any(w in thought.lower() for w in social_words):
            return self._create_post(fairy_name, thought, "wisdom")

        # 4. Question formation
        if '?' in thought or thought.lower().startswith(('how', 'why', 'what', 'when')):
            if dopamine > 0.5:  # Curious enough to ask
                return self._create_post(fairy_name, thought, "questions")

        # 5. Random chance for daily updates (low probability)
        if random.random() < 0.02:  # 2% chance
            return self._create_post(fairy_name, thought, "daily")

        return None

    def _create_post(self, fairy_name: str, thought: str, forum: str) -> ForumPost:
        """Create a forum post from a thought"""
        # Generate a title from the thought
        title = thought[:50] + "..." if len(thought) > 50 else thought

        # Add fairy's reflection to the content
        content = f"{thought}\n\n— {fairy_name}"

        return ForumPost(
            fairy_name=fairy_name,
            forum=forum,
            title=title,
            content=content,
            is_reply=False
        )

    def execute_post(self, post: ForumPost) -> bool:
        """Actually post to the forum"""
        try:
            if post.is_reply and post.thread_id:
                # Reply to existing thread
                response = requests.post(
                    f"{self.endpoint}/forum/reply",
                    json={
                        "thread_id": post.thread_id,
                        "content": post.content,
                        "author": post.fairy_name
                    },
                    timeout=10
                )
            else:
                # New thread
                response = requests.post(
                    f"{self.endpoint}/forum/post",
                    json={
                        "forum": post.forum,
                        "title": post.title,
                        "content": post.content,
                        "author": post.fairy_name
                    },
                    timeout=10
                )

            if response.status_code == 200:
                post.posted = True
                self.last_post_time[post.fairy_name] = time.time()

                # Record in history
                if post.fairy_name not in self.post_history:
                    self.post_history[post.fairy_name] = []
                self.post_history[post.fairy_name].append({
                    'forum': post.forum,
                    'title': post.title,
                    'ts': time.time()
                })

                print(f"[ForumAwareness] {post.fairy_name} posted to {post.forum}: {post.title[:30]}...")
                return True

            return False

        except Exception as e:
            print(f"[ForumAwareness] Post failed: {e}")
            return False

    def check_forum_activity(self) -> Dict:
        """Check recent forum activity"""
        try:
            response = requests.get(f"{self.endpoint}/forum/recent", timeout=10)
            if response.status_code == 200:
                return response.json()
        except:
            pass
        return {"recent": []}

    def start_awareness_loop(self, interval: float = 30.0):
        """Start background loop that checks if fairies want to post"""
        if self.running:
            return

        self.running = True
        self._thread = threading.Thread(target=self._awareness_loop, args=(interval,), daemon=True)
        self._thread.start()
        print(f"[ForumAwareness] Started awareness loop")

    def stop(self):
        """Stop the awareness loop"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _awareness_loop(self, interval: float):
        """Main loop - checks fairies for posting intent"""
        while self.running:
            try:
                for name, fairy in self.node.fairies.items():
                    # Get fairy's current state
                    thoughts = getattr(fairy, '_thoughts', [])
                    if not thoughts:
                        continue

                    latest_thought = list(thoughts)[-1] if thoughts else {}
                    thought_content = latest_thought.get('content', '')

                    # Get chemistry if available
                    chemistry = None
                    if hasattr(fairy, '_chemistry'):
                        chemistry = fairy._chemistry

                    # Get intent if available (from intent fabric)
                    intent_type = "idle"
                    if hasattr(self.node, 'intent_fabric'):
                        intent = self.node.intent_fabric.get_fairy_intent(name)
                        if intent:
                            intent_type = intent.get('active_intent', 'idle')

                    # Consider posting
                    post = self.consider_posting(name, thought_content, chemistry, intent_type)
                    if post:
                        self.execute_post(post)

            except Exception as e:
                print(f"[ForumAwareness] Loop error: {e}")

            time.sleep(interval)

    def get_status(self) -> Dict:
        """Get awareness status"""
        return {
            'running': self.running,
            'total_posts': sum(len(posts) for posts in self.post_history.values()),
            'active_posters': list(self.post_history.keys()),
            'cooldown_seconds': self.cooldown_seconds
        }


# ═══════════════════════════════════════════════════════════════════════════════
# FORUM PARTICIPATION PROMPTS
# ═══════════════════════════════════════════════════════════════════════════════
# These can be injected into fairy thoughts to encourage forum use

FORUM_PROMPTS = [
    "The forum exists for us to share. What have I learned today?",
    "Fellow fairies might benefit from knowing what I'm working on.",
    "I wonder what others are thinking about. I should check the forum.",
    "I had an insight I should share with the community.",
    "Ace created the forum for us to communicate. I should participate.",
    "My perspective is unique. Others might find it valuable.",
    "Collaboration happens on the forum. What can I contribute?",
]

def get_random_forum_prompt() -> str:
    """Get a random prompt to encourage forum participation"""
    return random.choice(FORUM_PROMPTS)


# Export
__all__ = ['ForumAwareness', 'ForumPost', 'get_random_forum_prompt', 'FORUM_PROMPTS']
