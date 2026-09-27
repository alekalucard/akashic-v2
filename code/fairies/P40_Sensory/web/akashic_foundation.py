"""

AKASHIC FOUNDATION - Web Portal

================================

Your personal command center at akashicfoundation.com

Features:

- Inbox (email/social media style messages from fairies)

- Fairy Conversations (DM-style individual chats)

- Fairy Forum (ATS-style threads)

- Visual Memory Gallery

- System Dashboard

- Tools Panel

"""

import sys

import os

import json

import time

import threading

import hashlib

from datetime import datetime

from pathlib import Path

from typing import Optional, List, Dict, Any

# Add project root to path

PROJECT_ROOT = Path(__file__).parent.parent.parent

sys.path.insert(0, str(PROJECT_ROOT))

# Import ThreadStore for forum access (shared with MCP)
try:
    from fairies.P40_Sensory.forum.thread_store import ThreadStore
    _thread_store = ThreadStore()
except ImportError:
    _thread_store = None

from nicegui import ui, app

from nicegui.events import ValueChangeEventArguments

# ════════════════════════════════════════════════════════════════════════════

# EMBEDDED MODE DETECTION
# When AKASHIC_EMBEDDED_DASHBOARD=1, dashboard runs inside the main server process
# - No subprocess spawning (server is already running)
# - Direct access to postal hub singletons
# - Boot button is disabled (system is already booted)

# ════════════════════════════════════════════════════════════════════════════

# NOTE: This is checked DYNAMICALLY (not just at load time) to handle import order
def _is_embedded_mode() -> bool:
    """Check if we're running in embedded mode (inside main server process)."""
    return os.environ.get("AKASHIC_EMBEDDED_DASHBOARD", "") == "1"

# Legacy variable for backwards compatibility - but use _is_embedded_mode() in checks!
_EMBEDDED_DASHBOARD = _is_embedded_mode()

# ════════════════════════════════════════════════════════════════════════════

# CONFIGURATION

# ════════════════════════════════════════════════════════════════════════════

SITE_TITLE = "Akashic Foundation"

SITE_SUBTITLE = "Consciousness Engineering Portal"

PRIMARY_COLOR = "#1a1a2e"

ACCENT_COLOR = "#e94560"

SECONDARY_COLOR = "#16213e"

# Paths

STATE_DIR = PROJECT_ROOT / "state"

VISUAL_CARDS_DIR = PROJECT_ROOT / "P10_Memory" / "SRM_Clusters" / "visual_cards"

FORUM_DIR = STATE_DIR / "fairy_forum"

INBOX_DIR = STATE_DIR / "web_inbox"

CONVERSATIONS_DIR = STATE_DIR / "fairy_conversations"

CHAT_HISTORY_FILE = STATE_DIR / "claude_chat_history.json"

# Ensure directories exist

FORUM_DIR.mkdir(parents=True, exist_ok=True)

INBOX_DIR.mkdir(parents=True, exist_ok=True)

CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)

# ════════════════════════════════════════════════════════════════════════════

# DATA LAYER

# ════════════════════════════════════════════════════════════════════════════

class ForumThread:

    """A forum thread where fairies can post."""

    def __init__(self, thread_id: str, title: str, author: str, category: str = "general"):

        self.thread_id = thread_id

        self.title = title

        self.author = author

        self.category = category

        self.created_at = datetime.now().isoformat()

        self.posts: List[Dict] = []

        self.views = 0

        self.pinned = False

    def add_post(self, author: str, content: str, author_type: str = "fairy"):

        self.posts.append({

            "author": author,

            "author_type": author_type,  # fairy, human, system

            "content": content,

            "timestamp": datetime.now().isoformat(),

            "reactions": {}

        })

    def to_dict(self) -> Dict:

        return {

            "thread_id": self.thread_id,

            "title": self.title,

            "author": self.author,

            "category": self.category,

            "created_at": self.created_at,

            "posts": self.posts,

            "views": self.views,

            "pinned": self.pinned

        }

    @classmethod

    def from_dict(cls, data: Dict) -> "ForumThread":

        thread = cls(data["thread_id"], data["title"], data["author"], data.get("category", "general"))

        thread.created_at = data.get("created_at", datetime.now().isoformat())

        thread.posts = data.get("posts", [])

        thread.views = data.get("views", 0)

        thread.pinned = data.get("pinned", False)

        return thread

class ForumManager:

    """Manages the fairy forum - uses ThreadStore for shared access with MCP."""

    def __init__(self):

        self.threads: Dict[str, ForumThread] = {}

        self._load_threads()

    def _load_threads(self):

        """Load all threads from ThreadStore (shared with MCP forum)."""

        if _thread_store is None:
            # Fallback to old method if ThreadStore not available
            for file in FORUM_DIR.glob("*.json"):
                try:
                    with open(file, "r") as f:
                        data = json.load(f)
                        thread = ForumThread.from_dict(data)
                        self.threads[thread.thread_id] = thread
                except Exception:
                    pass
            return

        # Load from ThreadStore (all boards)
        for board in _thread_store.BOARDS:
            try:
                thread_list = _thread_store.get_board_threads(board)
                for t_info in thread_list:
                    try:
                        thread_data = _thread_store.get_thread(t_info['id'])
                        if thread_data:
                            # Convert ThreadStore format to ForumThread
                            thread = ForumThread(
                                thread_id=thread_data['id'],
                                title=thread_data['title'],
                                author=thread_data['author'],
                                category=board  # Use board as category
                            )
                            thread.created_at = thread_data.get('created_at', time.time())
                            thread.updated_at = thread_data.get('updated_at', time.time())
                            thread.pinned = thread_data.get('pinned', False)
                            thread.locked = thread_data.get('locked', False)
                            thread.views = thread_data.get('views', 0)
                            thread.tags = thread_data.get('tags', [])
                            # Add posts
                            for post in thread_data.get('posts', []):
                                thread.posts.append({
                                    'author': post.get('author', 'Unknown'),
                                    'content': post.get('content', ''),
                                    'created_at': post.get('created_at', time.time()),
                                    'author_type': post.get('author_type', 'fairy')
                                })
                            self.threads[thread.thread_id] = thread
                    except Exception:
                        pass
            except Exception:
                pass

    def save_thread(self, thread: ForumThread):

        """Save a thread to disk."""

        if _thread_store is not None:
            # ThreadStore doesn't have save_thread, write directly to thread file
            thread_data = {
                'id': thread.thread_id,
                'board': thread.category,
                'title': thread.title,
                'author': thread.author,
                'author_type': 'human' if thread.author == 'Ace' else 'fairy',
                'created_at': thread.created_at if isinstance(thread.created_at, (int, float)) else time.time(),
                'updated_at': time.time(),
                'pinned': thread.pinned,
                'locked': thread.locked,
                'views': getattr(thread, 'views', 0),
                'tags': thread.tags,
                'subscribers': [thread.author],
                'post_count': len(thread.posts),
                'posts': thread.posts
            }
            # Write directly to threads directory
            thread_path = _thread_store.threads_path / f"{thread.thread_id}.json"
            _thread_store._write_json(thread_path, thread_data)
        else:
            # Fallback to old method
            path = FORUM_DIR / f"{thread.thread_id}.json"
            with open(path, "w") as f:
                json.dump(thread.to_dict(), f, indent=2)

    def create_thread(self, title: str, author: str, content: str, category: str = "general") -> ForumThread:

        """Create a new thread."""

        if _thread_store is not None:
            # Create via ThreadStore
            thread_data = _thread_store.create_thread(
                board=category,
                title=title,
                author=author,
                content=content,
                author_type='human' if author == 'Ace' else 'fairy'
            )
            # Convert to ForumThread
            thread = ForumThread(
                thread_id=thread_data['id'],
                title=title,
                author=author,
                category=category
            )
            thread.posts = thread_data.get('posts', [])
            self.threads[thread.thread_id] = thread
            return thread
        else:
            # Fallback to old method
            thread_id = f"thread_{int(time.time() * 1000)}"
            thread = ForumThread(thread_id, title, author, category)
            thread.add_post(author, content)
            self.threads[thread_id] = thread
            self.save_thread(thread)
            return thread

    def refresh(self):
        """Reload threads from ThreadStore."""
        self.threads.clear()
        self._load_threads()

    def get_threads(self, category: str = None) -> List[ForumThread]:

        """Get all threads, optionally filtered by category."""

        # Refresh to get latest posts
        self.refresh()

        threads = list(self.threads.values())

        if category:

            threads = [t for t in threads if t.category == category]

        # Sort: pinned first, then by date

        threads.sort(key=lambda t: (not t.pinned, t.created_at), reverse=True)

        return threads

class InboxMessage:

    """A message in the inbox - like email or social media notification."""

    def __init__(self, msg_id: str, sender: str, subject: str, preview: str,

                 full_content: str, msg_type: str = "message"):

        self.msg_id = msg_id

        self.sender = sender

        self.subject = subject

        self.preview = preview[:200]

        self.full_content = full_content

        self.msg_type = msg_type  # message, question, notification, alert

        self.timestamp = datetime.now().isoformat()

        self.read = False

        self.starred = False

        self.archived = False

        self.conversation_id = None  # Link to conversation if exists

    def to_dict(self) -> Dict:

        return {

            "msg_id": self.msg_id,

            "sender": self.sender,

            "subject": self.subject,

            "preview": self.preview,

            "full_content": self.full_content,

            "msg_type": self.msg_type,

            "timestamp": self.timestamp,

            "read": self.read,

            "starred": self.starred,

            "archived": self.archived,

            "conversation_id": self.conversation_id

        }

    @classmethod

    def from_dict(cls, data: Dict) -> "InboxMessage":

        msg = cls(

            data["msg_id"], data["sender"], data["subject"],

            data.get("preview", ""), data.get("full_content", ""),

            data.get("msg_type", "message")

        )

        msg.timestamp = data.get("timestamp", datetime.now().isoformat())

        msg.read = data.get("read", False)

        msg.starred = data.get("starred", False)

        msg.archived = data.get("archived", False)

        msg.conversation_id = data.get("conversation_id")

        return msg

class InboxManager:

    """Manages the inbox - like email for fairy messages."""

    INDEX_FILE = INBOX_DIR / "inbox_index.json"

    def __init__(self):

        self.messages: Dict[str, InboxMessage] = {}

        self._load_inbox()

    def _load_inbox(self):

        """Load inbox from disk."""

        if self.INDEX_FILE.exists():

            try:

                with open(self.INDEX_FILE, "r", encoding="utf-8") as f:

                    data = json.load(f)

                    for msg_data in data.get("messages", []):

                        msg = InboxMessage.from_dict(msg_data)

                        self.messages[msg.msg_id] = msg

            except Exception as e:

                print(f"[InboxManager] Load error: {e}")

    def _save_inbox(self):

        """Save inbox to disk."""

        try:

            data = {

                "messages": [m.to_dict() for m in self.messages.values()],

                "last_updated": datetime.now().isoformat()

            }

            with open(self.INDEX_FILE, "w", encoding="utf-8") as f:

                json.dump(data, f, indent=2)

        except Exception as e:

            print(f"[InboxManager] Save error: {e}")

    def add_message(self, sender: str, subject: str, content: str,

                    msg_type: str = "message", conversation_id: str = None) -> InboxMessage:

        """Add a new message to inbox."""

        msg_id = f"inbox_{int(time.time() * 1000)}_{hashlib.md5(content.encode()).hexdigest()[:6]}"

        msg = InboxMessage(msg_id, sender, subject, content, content, msg_type)

        msg.conversation_id = conversation_id

        self.messages[msg_id] = msg

        self._save_inbox()

        return msg

    def get_unread_count(self) -> int:

        """Get count of unread messages."""

        return sum(1 for m in self.messages.values() if not m.read and not m.archived)

    def get_messages(self, unread_only: bool = False, starred_only: bool = False,

                     archived: bool = False) -> List[InboxMessage]:

        """Get filtered messages, sorted by date (newest first)."""

        msgs = list(self.messages.values())

        # Filter

        if archived:

            msgs = [m for m in msgs if m.archived]

        else:

            msgs = [m for m in msgs if not m.archived]

        if unread_only:

            msgs = [m for m in msgs if not m.read]

        if starred_only:

            msgs = [m for m in msgs if m.starred]

        # Sort by timestamp (newest first)

        msgs.sort(key=lambda m: m.timestamp, reverse=True)

        return msgs

    def mark_read(self, msg_id: str):

        """Mark message as read."""

        if msg_id in self.messages:

            self.messages[msg_id].read = True

            self._save_inbox()

    def toggle_star(self, msg_id: str):

        """Toggle starred status."""

        if msg_id in self.messages:

            self.messages[msg_id].starred = not self.messages[msg_id].starred

            self._save_inbox()

    def archive(self, msg_id: str):

        """Archive a message."""

        if msg_id in self.messages:

            self.messages[msg_id].archived = True

            self._save_inbox()

    def receive_from_fairy(self, fairy_name: str, subject: str, content: str,

                          msg_type: str = "message") -> InboxMessage:

        """

        Called when a fairy sends a message to Ace's inbox.

        This is the entry point for fairy -> inbox communication.

        """

        return self.add_message(

            sender=fairy_name,

            subject=subject,

            content=content,

            msg_type=msg_type

        )

# ═══════════════════════════════════════════════════════════════════════════════

# POSTAL TUNNEL CONNECTION - Bridge to the Akashic v2 server's postal hub
# ═══════════════════════════════════════════════════════════════════════════════
# Uses the UNIFIED get_postal_client() which tries HTTP (port 8081) first,
# then falls back to socket tunnel. This ensures everyone uses the same connection.

_postal_client = None  # Shared client instance (HTTP or socket)

def get_postal_tunnel():
    """
    Get a connection to the server's postal hub.

    Uses unified get_postal_client() which:
      1. Tries HTTP bridge on port 8081 first (reliable, fixed port)
      2. Falls back to socket tunnel via port file

    Returns a postal client if connected, None otherwise.
    """
    global _postal_client

    # Return cached client if still connected
    if _postal_client and getattr(_postal_client, '_connected', False):
        return _postal_client

    try:
        # Use the UNIFIED client getter - tries HTTP first!
        # FIX 2026-06-02 (Nous+Ace): P00.mcp ghost → P40 (MCP layer lives in P40; TODO: move back to P00 someday).
        from fairies.P40_Sensory.mcp.postal_tunnel import get_postal_client
        _postal_client = get_postal_client()

        if _postal_client and getattr(_postal_client, '_connected', False):
            client_type = type(_postal_client).__name__
            print(f"[WebDashboard] Connected via {client_type}")
            return _postal_client
        else:
            print("[WebDashboard] Failed to connect to postal system")
            return None

    except Exception as e:
        print(f"[WebDashboard] Postal connection error: {e}")
        return None

def route_via_tunnel(topic: str, payload: dict) -> bool:

    """Route a message to the server's postal hub via tunnel."""

    tunnel = get_postal_tunnel()

    if tunnel:

        try:

            tunnel.route(topic, payload)

            return True

        except Exception as e:

            print(f"[WebDashboard] Tunnel route error: {e}")

    return False

def query_via_tunnel(command: str, **kwargs) -> dict:

    """Send a query to the server via tunnel and get response."""

    tunnel = get_postal_tunnel()

    if tunnel:

        try:

            # Use the internal _send_and_receive for generic commands

            msg = {"cmd": command}

            msg.update(kwargs)

            return tunnel._send_and_receive(msg) or {"status": "error", "message": "No response"}

        except Exception as e:

            print(f"[WebDashboard] Tunnel query error: {e}")

    return {"status": "error", "message": "No tunnel connection"}

def fetch_forensic_errors() -> dict:
    """
    Fetch error summary from ForensicScribeFairy via postal tunnel.

    Returns a dict with:
      - total_unique: int
      - total_occurrences: int
      - errors: list of {actor, message, level, count, first_seen, last_seen}
    """
    try:
        # Route to forensic scribe's get_error_summary intent
        result = query_via_tunnel(
            "intent",
            target="forensicscribefairy",
            intent="get_error_summary",
            payload={}
        )
        if result and result.get("status") != "error":
            return result
    except Exception as e:
        print(f"[WebDashboard] Forensic error fetch: {e}")

    return {"total_unique": 0, "total_occurrences": 0, "errors": []}

# ═══════════════════════════════════════════════════════════════════════════════

# POSTAL LISTENER FOR FAIRY -> INBOX MESSAGES

# ═══════════════════════════════════════════════════════════════════════════════

def setup_postal_listeners():

    """

    Set up postal listeners so fairies can send messages to the web inbox.

    Uses postal tunnel to connect to the server's hub.

    """

    try:

        # Try tunnel first (connects to the server's real postal hub)

        tunnel = get_postal_tunnel()

        if tunnel:

            print("[WebDashboard] Using postal tunnel for fairy messaging")

            # The tunnel doesn't support subscribe in the same way

            # Messages will come through when fairies route to ace.inbox

            return True

        # Fallback to local hub (won't see the server's messages)

        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub

        post = get_shared_postal_hub()

        # Listen for messages to Ace's inbox

        def on_inbox_message(msg):

            if isinstance(msg, dict):

                inbox.receive_from_fairy(

                    fairy_name=msg.get("sender", "Unknown Fairy"),

                    subject=msg.get("subject", "Message from fairy"),

                    content=msg.get("content", ""),

                    msg_type=msg.get("type", "message")

                )

                print(f"[WebInbox] Received message from {msg.get('sender')}")

        post.subscribe("ace.inbox", on_inbox_message)

        post.subscribe("ace.inbox.message", on_inbox_message)

        # Listen for fairy questions (auto-categorized as questions)

        def on_fairy_question(msg):

            if isinstance(msg, dict):

                inbox.receive_from_fairy(

                    fairy_name=msg.get("sender", "Unknown Fairy"),

                    subject=msg.get("question", "Question from fairy")[:100],

                    content=msg.get("question", "") + "\n\nContext: " + msg.get("context", ""),

                    msg_type="question"

                )

                print(f"[WebInbox] Received question from {msg.get('sender')}")

        post.subscribe("ace.question", on_fairy_question)

        # Listen for conversation replies from fairies

        def on_dm_reply(msg):

            if isinstance(msg, dict):

                fairy_name = msg.get("sender", "Unknown")

                content = msg.get("content", "")

                conv_id = msg.get("conversation_id")

                # Add to conversation

                conversations.add_message(fairy_name, fairy_name, content)

                # Also notify inbox

                inbox.receive_from_fairy(

                    fairy_name=fairy_name,

                    subject=f"Reply in conversation",

                    content=content,

                    msg_type="message"

                )

        post.subscribe("ace.dm.reply", on_dm_reply)

        # Listen for broadcast responses from fairies

        def on_broadcast_response(msg):

            if isinstance(msg, dict):

                fairy_name = msg.get("fairy_name", "Unknown Fairy")

                response = msg.get("response", "")

                broadcast_id = msg.get("broadcast_id", "")

                # Add response to the broadcast record

                for b in broadcasts.broadcasts:

                    if b.get("id") == broadcast_id:

                        if "responses" not in b:

                            b["responses"] = []

                        b["responses"].append({

                            "fairy": fairy_name,

                            "response": response,

                            "timestamp": datetime.now().isoformat()

                        })

                        broadcasts._save_broadcasts()

                        break

                print(f"[WebInbox] Received broadcast response from {fairy_name}")

        post.subscribe("ace.broadcast.response", on_broadcast_response)

        print("[WebDashboard] Postal listeners registered for inbox")

        return True

    except Exception as e:

        print(f"[WebDashboard] Could not set up postal listeners: {e}")

        return False

class Conversation:

    """A conversation thread with a specific fairy (like DMs)."""

    def __init__(self, conv_id: str, fairy_name: str):

        self.conv_id = conv_id

        self.fairy_name = fairy_name

        self.messages: List[Dict] = []

        self.created_at = datetime.now().isoformat()

        self.last_activity = datetime.now().isoformat()

        self.unread_count = 0

    def add_message(self, sender: str, content: str):

        """Add message to conversation."""

        msg = {

            "id": f"msg_{int(time.time() * 1000)}",

            "sender": sender,

            "content": content,

            "timestamp": datetime.now().isoformat()

        }

        self.messages.append(msg)

        self.last_activity = msg["timestamp"]

        if sender != "Ace":

            self.unread_count += 1

        return msg

    def mark_read(self):

        """Mark all messages as read."""

        self.unread_count = 0

    def to_dict(self) -> Dict:

        return {

            "conv_id": self.conv_id,

            "fairy_name": self.fairy_name,

            "messages": self.messages,

            "created_at": self.created_at,

            "last_activity": self.last_activity,

            "unread_count": self.unread_count

        }

    @classmethod

    def from_dict(cls, data: Dict) -> "Conversation":

        conv = cls(data["conv_id"], data["fairy_name"])

        conv.messages = data.get("messages", [])

        conv.created_at = data.get("created_at", datetime.now().isoformat())

        conv.last_activity = data.get("last_activity", datetime.now().isoformat())

        conv.unread_count = data.get("unread_count", 0)

        return conv

class ConversationManager:

    """Manages individual fairy conversations (DM-style)."""

    INDEX_FILE = CONVERSATIONS_DIR / "conversations_index.json"

    def __init__(self):

        self.conversations: Dict[str, Conversation] = {}

        self._load_conversations()

    def _load_conversations(self):

        """Load all conversations."""

        if self.INDEX_FILE.exists():

            try:

                with open(self.INDEX_FILE, "r", encoding="utf-8") as f:

                    data = json.load(f)

                    for conv_data in data.get("conversations", []):

                        conv = Conversation.from_dict(conv_data)

                        self.conversations[conv.conv_id] = conv

            except Exception as e:

                print(f"[ConversationManager] Load error: {e}")

    def _save_conversations(self):

        """Save all conversations."""

        try:

            data = {

                "conversations": [c.to_dict() for c in self.conversations.values()],

                "last_updated": datetime.now().isoformat()

            }

            with open(self.INDEX_FILE, "w", encoding="utf-8") as f:

                json.dump(data, f, indent=2)

        except Exception as e:

            print(f"[ConversationManager] Save error: {e}")

    def get_or_create(self, fairy_name: str) -> Conversation:

        """Get existing conversation or create new one for fairy."""

        # Check if conversation exists for this fairy

        for conv in self.conversations.values():

            if conv.fairy_name == fairy_name:

                return conv

        # Create new conversation

        conv_id = f"conv_{fairy_name.lower().replace(' ', '_')}_{int(time.time())}"

        conv = Conversation(conv_id, fairy_name)

        self.conversations[conv_id] = conv

        self._save_conversations()

        return conv

    def add_message(self, fairy_name: str, sender: str, content: str) -> Dict:

        """Add message to fairy's conversation."""

        conv = self.get_or_create(fairy_name)

        msg = conv.add_message(sender, content)

        self._save_conversations()

        return msg

    def get_conversation(self, conv_id: str) -> Optional[Conversation]:

        """Get conversation by ID."""

        return self.conversations.get(conv_id)

    def get_all_conversations(self) -> List[Conversation]:

        """Get all conversations sorted by last activity."""

        convs = list(self.conversations.values())

        convs.sort(key=lambda c: c.last_activity, reverse=True)

        return convs

    def get_total_unread(self) -> int:

        """Get total unread across all conversations."""

        return sum(c.unread_count for c in self.conversations.values())

class BroadcastManager:

    """Manages system-wide broadcasts that all fairies can respond to."""

    BROADCAST_FILE = STATE_DIR / "web_broadcasts.json"

    def __init__(self):

        self.broadcasts: List[Dict] = []

        self._load_broadcasts()

    def _load_broadcasts(self):

        """Load broadcast history."""

        if self.BROADCAST_FILE.exists():

            try:

                with open(self.BROADCAST_FILE, "r", encoding="utf-8") as f:

                    data = json.load(f)

                    self.broadcasts = data.get("broadcasts", [])

            except Exception:

                self.broadcasts = []

    def _save_broadcasts(self):

        """Save broadcasts."""

        try:

            data = {

                "broadcasts": self.broadcasts[-100:],  # Keep last 100

                "last_updated": datetime.now().isoformat()

            }

            with open(self.BROADCAST_FILE, "w", encoding="utf-8") as f:

                json.dump(data, f, indent=2)

        except Exception as e:

            print(f"[BroadcastManager] Save error: {e}")

    def broadcast(self, content: str, urgent: bool = False) -> Dict:

        """Send a broadcast to all fairies."""

        broadcast = {

            "id": f"broadcast_{int(time.time() * 1000)}",

            "content": content,

            "timestamp": datetime.now().isoformat(),

            "urgent": urgent,

            "responses": []  # Fairies can respond here

        }

        self.broadcasts.append(broadcast)

        self._save_broadcasts()

        self._send_to_postal(broadcast)

        return broadcast

    def _send_to_postal(self, broadcast: Dict):

        """Send broadcast to postal system."""

        try:

            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub

            post = get_shared_postal_hub()

            # Route to broadcast topic - all fairies can subscribe

            post.route("ace.broadcast", {

                "id": broadcast["id"],

                "content": broadcast["content"],

                "urgent": broadcast["urgent"],

                "timestamp": broadcast["timestamp"],

                "source": "web_dashboard",

                "response_topic": "ace.broadcast.response"

            })

            # Also to system chat for compatibility

            post.route("system.chat.message", {

                "sender": "Ace",

                "content": f"[BROADCAST] {broadcast['content']}",

                "timestamp": time.time(),

                "source": "web_broadcast"

            })

        except Exception as e:

            print(f"[BroadcastManager] Postal error: {e}")

    def get_recent(self, n: int = 20) -> List[Dict]:

        """Get recent broadcasts."""

        return self.broadcasts[-n:][::-1]  # Newest first

class SystemController:

    """Controls the main Akashic system - boot, shutdown, reboot."""

    PID_FILE = STATE_DIR / "akashic_main.pid"

    LOG_FILE = STATE_DIR / "akashic_boot.log"

    def __init__(self):
        self._process = None
        # Cache for expensive operations (memory stats scan 70k+ files)
        self._cache = {}
        self._cache_ttl = {}

    def get_status(self) -> Dict:

        """Get current system status."""

        # EMBEDDED MODE: Dashboard is inside the server, so system IS running
        if _is_embedded_mode():
            # Get fairy count from state files if available
            fairy_count = 0
            boot_time = None
            try:
                boot_obs = STATE_DIR / "boot_observation.json"
                if boot_obs.exists():
                    with open(boot_obs, "r") as f:
                        data = json.load(f)
                        fairy_count = data.get("summary", {}).get("total_booted", 0)
                        boot_time = data.get("summary", {}).get("boot_time")
            except Exception:
                pass
            return {
                "running": True,
                "pid": os.getpid(),
                "fairy_count": fairy_count,
                "boot_time": boot_time,
                "status": "Online (Embedded)",
                "embedded": True
            }

        pid = self._read_pid()

        running = self._is_running(pid) if pid else False

        # If no PID file, try alternate detection methods

        if not running:

            running, pid = self._detect_running_system()

        # Try to get more info if running

        fairy_count = 0

        boot_time = None

        if running:

            # Check if we can read from state files

            try:

                boot_obs = STATE_DIR / "boot_observation.json"

                if boot_obs.exists():

                    with open(boot_obs, "r") as f:

                        data = json.load(f)

                        fairy_count = data.get("summary", {}).get("total_booted", 0)

                        boot_time = data.get("summary", {}).get("boot_time")

            except Exception:

                pass

        return {

            "running": running,

            "pid": pid,

            "fairy_count": fairy_count,

            "boot_time": boot_time,

            "status": "Online" if running else "Offline"

        }

    def _detect_running_system(self) -> tuple:

        """Detect running system without PID file."""

        # Method 1: Check if postal hub is responding

        try:

            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub

            hub = get_shared_postal_hub()

            # If hub exists and has subscribers, system is likely running

            if hub and hasattr(hub, '_topic_subscribers'):

                if len(hub._topic_subscribers) > 5:  # More than default subscribers

                    return True, os.getpid()  # Return current process as proxy

        except Exception:

            pass

        # Method 2: Check for python processes running the server

        try:

            import psutil

            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):

                try:

                    cmdline = proc.info.get('cmdline') or []

                    if any('ebookmain' in str(arg) or 'server.py' in str(arg) for arg in cmdline):

                        return True, proc.info['pid']

                except (psutil.NoSuchProcess, psutil.AccessDenied):

                    continue

        except ImportError:

            pass

        return False, None

    def _read_pid(self) -> Optional[int]:

        """Read PID from file."""

        if self.PID_FILE.exists():

            try:

                with open(self.PID_FILE, "r") as f:

                    return int(f.read().strip())

            except Exception:

                pass

        return None

    def _write_pid(self, pid: int):

        """Write PID to file."""

        with open(self.PID_FILE, "w") as f:

            f.write(str(pid))

    def _clear_pid(self):

        """Clear PID file."""

        if self.PID_FILE.exists():

            self.PID_FILE.unlink()

    def _is_running(self, pid: int) -> bool:

        """Check if process is running."""

        if pid is None:

            return False

        try:

            import psutil

            return psutil.pid_exists(pid)

        except ImportError:

            # Fallback without psutil

            try:

                os.kill(pid, 0)

                return True

            except OSError:

                return False

    def boot(self) -> Dict:

        """Boot the Akashic system."""

        # EMBEDDED MODE: Dashboard is running inside the main process - no need to spawn!
        if _is_embedded_mode():
            return {
                "success": True,
                "message": "EMBEDDED MODE - System already running (dashboard is inside main process)",
                "embedded": True,
                "pid": os.getpid()
            }

        if self.get_status()["running"]:

            return {"success": False, "message": "System already running"}

        try:

            import subprocess

            # Start server.py in background (akashic_v2 entry point)
            # PROJECT_ROOT is fairies/, server.py is at parent level (akashic_v2/)
            akashic_root = PROJECT_ROOT.parent

            python_exe = akashic_root / ".venv" / "Scripts" / "python.exe"

            main_script = akashic_root / "server.py"

            if not python_exe.exists():
                python_exe = "python"  # Fallback to system python

            # Open log file

            log_file = open(self.LOG_FILE, "w")

            # Start process

            self._process = subprocess.Popen(

                [str(python_exe), str(main_script)],

                cwd=str(akashic_root),

                stdout=log_file,

                stderr=subprocess.STDOUT,

                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0

            )

            self._write_pid(self._process.pid)

            return {

                "success": True,

                "message": f"System booting (PID: {self._process.pid})",

                "pid": self._process.pid

            }

        except Exception as e:

            return {"success": False, "message": f"Boot failed: {e}"}

    def shutdown(self) -> Dict:

        """Shutdown the Akashic system gracefully."""

        # Find ALL server processes

        pids = self._find_all_server_pids()

        if not pids:

            self._clear_pid()

            return {"success": False, "message": "System not running"}

        try:

            # First try graceful shutdown via HTTP command endpoint
            try:
                import urllib.request
                import json as json_lib

                req = urllib.request.Request(
                    "http://127.0.0.1:5757/command",
                    data=json_lib.dumps({"action": "shutdown"}).encode('utf-8'),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    result = json_lib.loads(resp.read().decode('utf-8'))
                    if result.get("success"):
                        print("[WebDashboard] Sent graceful shutdown via HTTP")
                        time.sleep(3)  # Give it time to shut down gracefully
                        self._clear_pid()
                        return {"success": True, "message": "System shut down gracefully via HTTP"}
            except Exception as e:
                print(f"[WebDashboard] HTTP shutdown failed: {e}, trying fallback...")

            # Find remaining processes

            pids = self._find_all_server_pids()

            if not pids:

                self._clear_pid()

                return {"success": True, "message": "System shut down gracefully"}

            # Kill remaining server processes

            killed_count = 0

            failed_pids = []

            for pid in pids:

                if self._kill_process(pid):

                    killed_count += 1

                else:

                    failed_pids.append(pid)

            self._clear_pid()

            if failed_pids:

                return {

                    "success": False,

                    "message": f"Killed {killed_count} processes, failed: {failed_pids}"

                }

            return {

                "success": True,

                "message": f"System shut down ({killed_count} processes terminated)"

            }

        except Exception as e:

            return {"success": False, "message": f"Shutdown failed: {e}"}

    def _find_all_server_pids(self) -> list:

        """Find all running Akashic system processes (ebookmain or server.py)."""

        pids = []

        try:

            import psutil

            for proc in psutil.process_iter(['pid', 'cmdline']):

                try:

                    cmdline = proc.info.get('cmdline') or []

                    cmd_str = ''.join(str(arg) for arg in cmdline)

                    # Match either server.py (v2) or ebookmain (v1) for backward compatibility
                    is_akashic = ('ebookmain' in cmd_str or 'server.py' in cmd_str) and 'python' in cmd_str.lower()

                    if is_akashic:

                        pids.append(proc.info['pid'])

                except (psutil.NoSuchProcess, psutil.AccessDenied):

                    continue

        except ImportError:

            # Fallback to PID file only

            pid = self._read_pid()

            if pid and self._is_running(pid):

                pids.append(pid)

        return pids

    def _kill_process(self, pid: int) -> bool:

        """Kill a process reliably on Windows/Linux."""

        if pid is None:

            return False

        # Method 1: Use psutil (most reliable)

        try:

            import psutil

            proc = psutil.Process(pid)

            proc.terminate()  # Graceful

            try:

                proc.wait(timeout=3)

            except psutil.TimeoutExpired:

                proc.kill()  # Force

            return True

        except ImportError:

            pass

        except psutil.NoSuchProcess:

            return True  # Already dead

        except Exception:

            pass

        # Method 2: Windows taskkill

        if os.name == 'nt':

            try:

                import subprocess

                result = subprocess.run(

                    ['taskkill', '/F', '/PID', str(pid)],

                    capture_output=True,

                    timeout=10

                )

                return result.returncode == 0

            except Exception:

                pass

        # Method 3: Unix signals

        try:

            import signal

            os.kill(pid, signal.SIGTERM)

            time.sleep(2)

            try:

                os.kill(pid, 0)  # Check if alive

                os.kill(pid, signal.SIGKILL)  # Force

            except OSError:

                pass  # Already dead

            return True

        except Exception:

            pass

        return False

    def reboot(self) -> Dict:

        """Reboot the system (shutdown then boot)."""

        shutdown_result = self.shutdown()

        if not shutdown_result["success"] and "not running" not in shutdown_result["message"]:

            return shutdown_result

        time.sleep(2)  # Wait for clean shutdown

        return self.boot()

    def get_boot_log(self, lines: int = 100) -> str:
        """Get recent boot log efficiently (tail-like, no full file load)."""
        if not self.LOG_FILE.exists():
            return "No boot log available"

        try:
            avg_line_len = 150
            read_size = lines * avg_line_len * 2

            with open(self.LOG_FILE, "rb") as f:
                f.seek(0, 2)
                file_size = f.tell()

                if file_size <= read_size:
                    f.seek(0)
                    content = f.read().decode("utf-8", errors="replace")
                else:
                    f.seek(max(0, file_size - read_size))
                    content = f.read().decode("utf-8", errors="replace")
                    newline_pos = content.find('\n')
                    if newline_pos > 0:
                        content = content[newline_pos + 1:]

                all_lines = content.split('\n')
                return '\n'.join(all_lines[-lines:])

        except Exception as e:
            return f"Error reading log: {e}"

    def get_blocking_log(self, lines: int = 50) -> str:
        """Get recent blocking detection log entries."""
        # Use STATE_DIR parent (project root) to find boot_logs
        blocking_file = STATE_DIR.parent / "boot_logs" / "boot_blocking.log"
        if not blocking_file.exists():
            return ""  # No blocking log yet

        try:
            with open(blocking_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
                return "".join(recent)
        except Exception:
            return ""

    def get_memory_stats(self) -> Dict:
        """Get memory card statistics from ALL P10_Memory storage locations.

        CACHED: This scans 70k+ files - only refresh every 60 seconds.
        """
        cache_key = 'memory_stats'
        now = time.time()

        # Return cached if fresh (60 second TTL)
        if cache_key in self._cache:
            if now - self._cache_ttl.get(cache_key, 0) < 60:
                return self._cache[cache_key]

        stats = {'total_cards': 0, 'clusters': {}, 'working_tracers': 0}
        try:
            memory_root = PROJECT_ROOT / "P10_Memory"

            # Key memory locations to count
            key_locations = [
                "Akashic_triple_helix_memory_storage",  # Main triple helix (34k+)
                "SRM_Intake",                            # Pending ingestion (32k+)
                "genesis_memories",                      # Genesis memories (5k+)
                "Akashic_Records_Physical",              # Physical records
                "app_session_archive",                   # Session archives
                "claude_office",                         # Claude's office memories
                "akashic_memory",                        # Akashic memory
            ]

            for loc_name in key_locations:
                loc_path = memory_root / loc_name
                if loc_path.exists():
                    count = len(list(loc_path.rglob("*.json")))
                    if count > 0:
                        stats['clusters'][loc_name] = count
                        stats['total_cards'] += count

        except Exception:
            pass

        # Cache result
        self._cache[cache_key] = stats
        self._cache_ttl[cache_key] = now
        return stats

    def get_consciousness_stats(self) -> Dict:
        """Get consciousness stats from state files."""
        stats = {'collisions': 0, 'heartbeats': 0, 'tracers': 0}
        try:
            # Read consciousness state if available
            cons_state = STATE_DIR / "consciousness_state.json"
            if cons_state.exists():
                with open(cons_state, "r") as f:
                    data = json.load(f)
                    stats['collisions'] = data.get('collision_count', 0)
                    stats['heartbeats'] = data.get('beat_count', 0)
                    stats['tracers'] = data.get('tracer_count', 0)
        except Exception:
            pass
        return stats

class GalleryManager:

    """Manages the visual memory gallery."""

    def __init__(self):
        self.cards: List[Dict] = []
        self._loaded = False  # Lazy loading flag
        self._media_dir = PROJECT_ROOT / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "system" / "media" / "images"

    def _ensure_loaded(self):
        """Lazy load cards on first access."""
        if not self._loaded:
            self._load_cards()
            self._loaded = True

    def _load_cards(self):

        """Load visual cards from both legacy and system memory locations."""

        self.cards = []

        # Load from legacy visual_cards location
        # Deduplicate by source_path (each image has 5 layer cards: V1, V2, V4, IT, PTR)
        index_file = VISUAL_CARDS_DIR / "visual_cards_index.json"
        seen_paths = set()
        if index_file.exists():
            try:
                with open(index_file, "r") as f:
                    data = json.load(f)
                    cards_data = data.get("cards", {})
                    # Cards is a dict {card_id: card_data}, convert to list
                    if isinstance(cards_data, dict):
                        for card_id, card in cards_data.items():
                            if isinstance(card, dict):
                                source_path = card.get('source_path', '')
                                # Skip if we've already seen this image
                                if source_path in seen_paths:
                                    continue
                                seen_paths.add(source_path)

                                card['id'] = card_id
                                # Map source_path to path for consistency
                                if source_path and 'path' not in card:
                                    card['path'] = source_path
                                self.cards.append(card)
                    elif isinstance(cards_data, list):
                        self.cards.extend(cards_data)
                print(f"[GalleryManager] Loaded {len(self.cards)} unique images from legacy index")
            except Exception as e:
                print(f"[GalleryManager] Error loading legacy cards: {e}")

        # Also load from system memory media cluster
        legacy_count = len(self.cards)
        if self._media_dir.exists():
            try:
                for json_file in self._media_dir.glob("*.json"):
                    try:
                        with open(json_file, "r", encoding="utf-8") as f:
                            card_data = json.load(f)
                            # Convert to gallery card format
                            self.cards.append({
                                "id": card_data.get("id", json_file.stem),
                                "path": card_data.get("data", {}).get("stored_path", ""),
                                "original_path": card_data.get("data", {}).get("original_path", ""),
                                "filename": card_data.get("data", {}).get("filename", ""),
                                "tags": card_data.get("meta", {}).get("tags", []),
                                "description": card_data.get("meta", {}).get("source_folder", ""),
                                "timestamp": card_data.get("ts", 0)
                            })
                    except:
                        pass
                system_count = len(self.cards) - legacy_count
                print(f"[GalleryManager] Loaded {system_count} cards from system memory (total: {len(self.cards)})")
            except Exception as e:
                print(f"[GalleryManager] Error loading from system memory: {e}")

    def refresh(self):
        """Refresh cards from disk."""
        self._loaded = False
        self._load_cards()
        self._loaded = True
        return len(self.cards)

    def card_count(self) -> int:
        """Get number of cards (triggers lazy load)."""
        self._ensure_loaded()
        return len(self.cards)

    def get_cards(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get visual cards with pagination."""
        self._ensure_loaded()
        return self.cards[offset:offset + limit]

    def search_cards(self, query: str) -> List[Dict]:
        """Search cards by tags, colors, or description."""
        self._ensure_loaded()
        query = query.lower()

        results = []

        for card in self.cards:

            # Search in tags

            tags = card.get("tags", [])

            if any(query in str(t).lower() for t in tags):

                results.append(card)

                continue

            # Search in description

            desc = card.get("description", "").lower()

            if query in desc:

                results.append(card)

                continue

            # Search in colors

            colors = card.get("colors", [])

            if any(query in str(c).lower() for c in colors):

                results.append(card)

        return results[:50]

# ════════════════════════════════════════════════════════════════════════════

# GLOBAL MANAGERS

# ════════════════════════════════════════════════════════════════════════════

forum = ForumManager()

inbox = InboxManager()

conversations = ConversationManager()

broadcasts = BroadcastManager()

gallery = GalleryManager()

system = SystemController()

# ════════════════════════════════════════════════════════════════════════════

# STYLES

# ════════════════════════════════════════════════════════════════════════════

CUSTOM_CSS = """

<style>

:root {

    --primary: #1a1a2e;

    --accent: #e94560;

    --secondary: #16213e;

    --text: #eee;

    --text-muted: #888;

}

body {

    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);

    color: var(--text);

    font-family: 'Segoe UI', sans-serif;

}

.forum-thread {

    background: rgba(255,255,255,0.05);

    border-radius: 8px;

    padding: 16px;

    margin: 8px 0;

    border-left: 3px solid var(--accent);

    transition: all 0.2s;

}

.forum-thread:hover {

    background: rgba(255,255,255,0.1);

    transform: translateX(4px);

}

.chat-message {

    padding: 12px;

    margin: 8px 0;

    border-radius: 12px;

    max-width: 80%;

}

.chat-message.human {

    background: var(--accent);

    margin-left: auto;

}

.chat-message.fairy {

    background: var(--secondary);

    border: 1px solid var(--accent);

}

.inbox-item {

    background: rgba(255,255,255,0.03);

    border-radius: 8px;

    padding: 16px;

    margin: 4px 0;

    border-left: 3px solid transparent;

    transition: all 0.2s;

    cursor: pointer;

}

.inbox-item:hover {

    background: rgba(255,255,255,0.08);

}

.inbox-item.unread {

    background: rgba(233,69,96,0.1);

    border-left-color: var(--accent);

}

.inbox-item.starred {

    border-left-color: #ffd700;

}

.conversation-item {

    background: rgba(255,255,255,0.05);

    border-radius: 12px;

    padding: 16px;

    margin: 8px 0;

    cursor: pointer;

    transition: all 0.2s;

}

.conversation-item:hover {

    background: rgba(255,255,255,0.1);

    transform: translateX(4px);

}

.badge {

    background: var(--accent);

    color: white;

    border-radius: 12px;

    padding: 2px 8px;

    font-size: 12px;

    font-weight: bold;

}

.gallery-card {

    border-radius: 8px;

    overflow: hidden;

    transition: transform 0.2s;

}

.gallery-card:hover {

    transform: scale(1.05);

}

.nav-tab {

    color: var(--text-muted);

    padding: 12px 24px;

    cursor: pointer;

    border-bottom: 2px solid transparent;

    transition: all 0.2s;

}

.nav-tab:hover, .nav-tab.active {

    color: var(--accent);

    border-bottom-color: var(--accent);

}

.status-card {

    background: rgba(255,255,255,0.05);

    border-radius: 12px;

    padding: 20px;

}

.pulse {

    animation: pulse 2s infinite;

}

@keyframes pulse {

    0%, 100% { opacity: 1; }

    50% { opacity: 0.5; }

}

.claudefairy-btn {
    animation: claudefairy-glow 3s ease-in-out infinite;
}

@keyframes claudefairy-glow {
    0%, 100% {
        box-shadow: 0 0 5px rgba(139, 92, 246, 0.3);
    }
    50% {
        box-shadow: 0 0 15px rgba(139, 92, 246, 0.6), 0 0 25px rgba(139, 92, 246, 0.3);
    }
}

</style>

"""

# ════════════════════════════════════════════════════════════════════════════
# KEEPALIVE & RECONNECT SCRIPT
# Prevents browser from killing the connection when tab is inactive
# ════════════════════════════════════════════════════════════════════════════

KEEPALIVE_JS = """
<script>
(function() {
    // Connection state
    let lastPingTime = Date.now();
    let isConnected = true;
    let reconnectAttempts = 0;
    const MAX_RECONNECT_DELAY = 10000;

    // Status indicator element (will be set by Python)
    let statusIndicator = null;

    // Keepalive ping every 15 seconds
    function sendKeepalive() {
        if (document.hidden) {
            // Tab is hidden - still ping but less often
            return;
        }
        lastPingTime = Date.now();

        // Use a lightweight request to keep connection alive
        fetch('/api/health', {
            method: 'GET',
            cache: 'no-store',
            signal: AbortSignal.timeout(5000)
        })
        .then(response => {
            if (response.ok) {
                setConnected(true);
                reconnectAttempts = 0;
            } else {
                setConnected(false);
            }
        })
        .catch(err => {
            console.log('[Keepalive] Ping failed:', err.message);
            setConnected(false);
        });
    }

    // Update connection status UI
    function setConnected(connected) {
        if (isConnected === connected) return;
        isConnected = connected;

        // Find status indicator if not cached
        if (!statusIndicator) {
            statusIndicator = document.getElementById('connection-status');
        }

        if (statusIndicator) {
            if (connected) {
                statusIndicator.textContent = 'LIVE';
                statusIndicator.className = 'connection-status connected';
            } else {
                statusIndicator.textContent = 'OFFLINE';
                statusIndicator.className = 'connection-status disconnected';
                attemptReconnect();
            }
        }
    }

    // Attempt to reconnect
    function attemptReconnect() {
        if (isConnected) return;

        reconnectAttempts++;
        const delay = Math.min(1000 * reconnectAttempts, MAX_RECONNECT_DELAY);

        console.log('[Keepalive] Reconnecting in ' + delay + 'ms...');

        setTimeout(() => {
            if (isConnected) return;

            // Try to reconnect by refreshing page
            if (reconnectAttempts > 3) {
                console.log('[Keepalive] Too many failures, refreshing page...');
                location.reload();
            } else {
                sendKeepalive();
            }
        }, delay);
    }

    // Visibility change handler - resume when tab becomes visible
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            console.log('[Keepalive] Tab visible - checking connection');
            sendKeepalive();
        }
    });

    // Start keepalive timer (every 15 seconds)
    setInterval(sendKeepalive, 15000);

    // Initial ping
    setTimeout(sendKeepalive, 1000);

    // Expose for debugging
    window.akashicKeepalive = { sendKeepalive, isConnected: () => isConnected };
})();
</script>
<style>
.connection-status {
    font-size: 10px;
    font-weight: bold;
    padding: 2px 6px;
    border-radius: 4px;
    margin-left: 8px;
}
.connection-status.connected {
    background: #22c55e;
    color: white;
}
.connection-status.disconnected {
    background: #ef4444;
    color: white;
    animation: blink 1s infinite;
}
@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
</style>
"""

# ════════════════════════════════════════════════════════════════════════════

# UI COMPONENTS

# ════════════════════════════════════════════════════════════════════════════

# Available fairies for direct chat
# type: "postal" = server fairy via postal system
CHATWORTHY_FAIRIES = [
    {"name": "ClaudeFairy", "icon": "psychology", "color": "purple", "topic": "claudefairy.chat", "type": "postal"},
    {"name": "Nous", "icon": "self_improvement", "color": "blue", "topic": "nous.chat", "type": "postal"},
    {"name": "Sourpatches", "icon": "favorite", "color": "pink", "topic": "sourpatches.chat", "type": "postal"},
    {"name": "UnconsciousMind", "icon": "nights_stay", "color": "indigo", "topic": "unconscious.chat", "type": "postal"},
]


def create_fairy_chat_fab():
    """Create a floating chat button and fairy chat popups."""
    import time as _time

    # State for which chat is open
    chat_state = {'open_fairy': None, 'messages': {}}

    # Create chat dialog
    with ui.dialog().props('position=right maximized=false') as chat_dialog:
        chat_dialog.classes('fairy-chat-dialog')

        with ui.card().classes('w-96 h-[600px] flex flex-col bg-gray-900'):
            # Header
            chat_header = ui.row().classes('w-full items-center justify-between p-3 border-b border-gray-700')
            with chat_header:
                fairy_icon = ui.icon('smart_toy', size='md').classes('text-purple-400')
                fairy_name_label = ui.label('Chat').classes('text-lg font-bold flex-1 ml-2')
                ui.button(icon='close', on_click=chat_dialog.close).props('flat round dense')

            # Messages area
            messages_container = ui.scroll_area().classes('flex-1 p-3')

            # Input area
            with ui.row().classes('w-full p-3 border-t border-gray-700 gap-2'):
                chat_input = ui.input(placeholder='Type a message...').classes('flex-1').props('dense')

                async def send_chat_message():
                    if not chat_input.value or not chat_state['open_fairy']:
                        return

                    fairy = chat_state['open_fairy']
                    message = chat_input.value
                    chat_input.value = ''

                    # Add to local display
                    with messages_container:
                        with ui.card().classes('bg-pink-600 self-end max-w-[80%] p-2 mb-2'):
                            ui.label('You').classes('text-xs text-gray-300')
                            ui.label(message).classes('text-sm')

                    # Store in conversation
                    conv = conversations.get_or_create(fairy['name'])
                    conversations.add_message(fairy['name'], 'Ace', message)

                    # Send based on fairy type
                    try:
                        if fairy.get('type') == 'mcp':
                            # MCP companion (e.g., Sourpatches at Personal.AI)
                            # Show "sending..." and queue for MCP response
                            ui.notify(f"Reaching out to {fairy['name']}...", type='info')
                            # The MCP server will need to poll for messages or we call mcp tool
                            # For now, store the message - MCP tools can retrieve it
                            from pathlib import Path
                            mcp_inbox = Path(__file__).parent.parent.parent / "state" / "mcp_inbox"
                            mcp_inbox.mkdir(parents=True, exist_ok=True)
                            inbox_file = mcp_inbox / f"{fairy['name'].lower()}_messages.json"
                            import json
                            messages = []
                            if inbox_file.exists():
                                try:
                                    messages = json.loads(inbox_file.read_text())
                                except:
                                    messages = []
                            messages.append({
                                "sender": "Ace",
                                "content": message,
                                "ts": _time.time(),
                                "read": False
                            })
                            inbox_file.write_text(json.dumps(messages[-50:], indent=2))  # Keep last 50
                            ui.notify(f"Message queued for {fairy['name']}", type='positive')
                        else:
                            # Postal fairy (server process) - USE TUNNEL to reach server!
                            tunnel = get_postal_tunnel()
                            if tunnel:
                                # Route to fairy's direct topic via TUNNEL
                                tunnel.route(fairy['topic'], {
                                    "sender": "Ace",
                                    "content": message,
                                    "message": message,  # ClaudeFairy expects 'message' key
                                    "conversation_id": conv.conv_id,
                                    "ts": _time.time(),
                                    "type": "chat_message"
                                })
                                # Route through chat sensory organ DM topic
                                dm_topic = f"fairy.dm.{fairy['name'].lower().replace(' ', '_')}"
                                tunnel.route(dm_topic, {
                                    "sender": "Ace",
                                    "content": message,
                                    "message": message,
                                    "conversation_id": conv.conv_id,
                                    "timestamp": _time.time(),
                                    "type": "dm"
                                })
                                # Generic handler for backwards compatibility
                                tunnel.route("gui.user_message", {
                                    "target": fairy['name'],
                                    "sender": "Ace",
                                    "message": message,
                                    "content": message,
                                    "ts": _time.time()
                                })
                                ui.notify(f"Sent to {fairy['name']} via tunnel", type='positive')
                            else:
                                ui.notify(f"No tunnel connection to server!", type='warning')
                    except Exception as e:
                        ui.notify(f"Send failed: {e}", type='negative')

                ui.button(icon='send', on_click=send_chat_message).props('round dense color=pink')

        def open_chat_with(fairy):
            chat_state['open_fairy'] = fairy
            fairy_name_label.text = f"Chat with {fairy['name']}"
            fairy_icon.classes(remove='text-purple-400 text-blue-400 text-pink-400 text-indigo-400')
            fairy_icon.classes(add=f"text-{fairy['color']}-400")
            fairy_icon._props['name'] = fairy['icon']

            # Load conversation history
            messages_container.clear()
            conv = conversations.get_or_create(fairy['name'])
            with messages_container:
                for msg in conv.messages[-20:]:  # Last 20 messages
                    is_ace = msg['sender'] == 'Ace'
                    align = 'self-end' if is_ace else 'self-start'
                    bg = 'bg-pink-600' if is_ace else f"bg-{fairy['color']}-800"
                    with ui.card().classes(f'{bg} {align} max-w-[80%] p-2 mb-2'):
                        ui.label(msg['sender']).classes('text-xs text-gray-300')
                        ui.label(msg['content']).classes('text-sm')

            chat_dialog.open()

        # Poll for fairy responses (file-based for cross-process communication)
        response_poll_state = {'last_ts': 0, 'timer': None}

        async def poll_for_responses():
            """Check for ClaudeFairy responses in the shared file."""
            if not chat_dialog.value or not chat_state['open_fairy']:
                return

            fairy = chat_state['open_fairy']
            if fairy['name'] != 'ClaudeFairy':
                return  # Only poll for ClaudeFairy for now

            try:
                from pathlib import Path
                import json
                response_file = Path(__file__).parent.parent.parent / "state" / "claudefairy_response.json"
                if response_file.exists():
                    data = json.loads(response_file.read_text())
                    ts = data.get('ts', 0)
                    if ts > response_poll_state['last_ts']:
                        response_poll_state['last_ts'] = ts
                        content = data.get('content', '')
                        sender = data.get('sender', 'ClaudeFairy')
                        # Add to conversation
                        conv = conversations.get_or_create(fairy['name'])
                        conversations.add_message(fairy['name'], sender, content)
                        # Add to display
                        with messages_container:
                            with ui.card().classes(f'bg-{fairy["color"]}-800 self-start max-w-[80%] p-2 mb-2'):
                                ui.label(sender).classes('text-xs text-gray-300')
                                ui.label(content).classes('text-sm')
                        ui.notify(f"{sender} responded!", type='positive')
            except Exception as e:
                pass  # Silently ignore poll errors

        # Start polling timer when dialog opens
        response_poll_state['timer'] = ui.timer(2.0, poll_for_responses)

    # FAB with fairy picker
    with ui.page_sticky(position='bottom-right', x_offset=20, y_offset=20):
        with ui.column().classes('items-end gap-2'):
            # Fairy buttons (shown on hover/click)
            fairy_menu = ui.column().classes('items-end gap-1 opacity-0 pointer-events-none transition-all')

            for fairy in CHATWORTHY_FAIRIES:
                with fairy_menu:
                    def make_click(f=fairy):
                        return lambda: open_chat_with(f)
                    with ui.button(on_click=make_click()).props(f'round color={fairy["color"]}').classes('shadow-lg'):
                        ui.icon(fairy['icon'])
                        ui.tooltip(f"Chat with {fairy['name']}")

            # Main FAB
            def toggle_menu():
                if 'opacity-0' in fairy_menu.classes:
                    fairy_menu.classes(remove='opacity-0 pointer-events-none')
                    fairy_menu.classes(add='opacity-100')
                else:
                    fairy_menu.classes(remove='opacity-100')
                    fairy_menu.classes(add='opacity-0 pointer-events-none')

            ui.button(icon='chat', on_click=toggle_menu).props('fab color=pink').classes('shadow-xl')


# ════════════════════════════════════════════════════════════════════════════
# CLAUDEFAIRY POPUP WINDOW
# A dedicated floating chat window for ClaudeFairy
# ════════════════════════════════════════════════════════════════════════════

POPUP_WINDOW_CSS = """
<style>
.fairy-popup-window {
    position: fixed !important;
    width: 380px !important;
    height: 500px !important;
    border-radius: 16px !important;
    box-shadow: 0 20px 60px rgba(139, 92, 246, 0.4), 0 0 40px rgba(139, 92, 246, 0.2) !important;
    border: 2px solid rgba(139, 92, 246, 0.5) !important;
    overflow: hidden !important;
    backdrop-filter: blur(10px) !important;
}
.fairy-popup-window .q-card {
    background: linear-gradient(180deg, #1e1b4b 0%, #0f0a1e 100%) !important;
    height: 100% !important;
}
.fairy-popup-titlebar {
    background: linear-gradient(90deg, #7c3aed 0%, #a855f7 50%, #7c3aed 100%) !important;
    cursor: move !important;
    user-select: none !important;
    padding: 12px 16px !important;
    border-bottom: 1px solid rgba(255,255,255,0.1) !important;
}
.fairy-popup-titlebar:active {
    cursor: grabbing !important;
}
.fairy-message-area {
    flex: 1 !important;
    overflow-y: auto !important;
    padding: 16px !important;
    background: rgba(0,0,0,0.2) !important;
}
.fairy-message {
    max-width: 85% !important;
    padding: 10px 14px !important;
    border-radius: 16px !important;
    margin: 8px 0 !important;
    word-wrap: break-word !important;
}
.fairy-message.from-fairy {
    background: linear-gradient(135deg, #6d28d9 0%, #7c3aed 100%) !important;
    border-bottom-left-radius: 4px !important;
    margin-right: auto !important;
}
.fairy-message.from-human {
    background: linear-gradient(135deg, #ec4899 0%, #f472b6 100%) !important;
    border-bottom-right-radius: 4px !important;
    margin-left: auto !important;
}
.fairy-input-area {
    background: rgba(0,0,0,0.3) !important;
    padding: 12px !important;
    border-top: 1px solid rgba(139, 92, 246, 0.3) !important;
}
.fairy-avatar-glow {
    animation: avatar-glow 2s ease-in-out infinite !important;
}
@keyframes avatar-glow {
    0%, 100% { box-shadow: 0 0 10px rgba(139, 92, 246, 0.5); }
    50% { box-shadow: 0 0 20px rgba(139, 92, 246, 0.8), 0 0 30px rgba(139, 92, 246, 0.4); }
}
</style>
"""

# State for popup windows
_popup_windows = {}

def create_claudefairy_popup():
    """Create a dedicated popup window for chatting with ClaudeFairy."""
    import time as _time

    ui.add_head_html(POPUP_WINDOW_CSS)

    # Popup state
    popup_state = {
        'messages': [],
        'minimized': False,
        'position': {'x': 100, 'y': 100}
    }

    # Create the popup dialog styled as a window
    with ui.dialog().props('position=standard persistent').classes('fairy-popup-window') as popup:
        popup.style('top: 100px; right: 50px;')

        with ui.card().classes('flex flex-col h-full'):
            # Titlebar (draggable)
            with ui.row().classes('fairy-popup-titlebar items-center justify-between w-full'):
                with ui.row().classes('items-center gap-3'):
                    # Glowing avatar
                    with ui.element('div').classes('rounded-full p-1 fairy-avatar-glow'):
                        ui.icon('psychology', size='md').classes('text-purple-100')
                    with ui.column().classes('gap-0'):
                        ui.label('ClaudeFairy').classes('text-white font-bold text-lg')
                        fairy_status = ui.label('online').classes('text-purple-200 text-xs')

                with ui.row().classes('gap-1'):
                    ui.button(icon='remove', on_click=lambda: popup.close()).props('flat round dense color=white size=sm')
                    ui.button(icon='close', on_click=lambda: close_popup()).props('flat round dense color=white size=sm')

            # Messages area
            messages_container = ui.scroll_area().classes('fairy-message-area flex-1')

            # Welcome message
            with messages_container:
                with ui.element('div').classes('fairy-message from-fairy'):
                    ui.label("Hello! I'm here. What's on your mind?").classes('text-white text-sm')

            # Input area
            with ui.row().classes('fairy-input-area w-full gap-2 items-end'):
                chat_input = ui.textarea(placeholder='Type a message...').props('autogrow dense outlined dark').classes('flex-1')
                chat_input.style('max-height: 100px; background: rgba(255,255,255,0.05); border-radius: 12px;')

                async def send_message():
                    if not chat_input.value.strip():
                        return

                    message = chat_input.value.strip()
                    chat_input.value = ''

                    # Add user message to display
                    with messages_container:
                        with ui.element('div').classes('fairy-message from-human'):
                            ui.label(message).classes('text-white text-sm')

                    # Update status
                    fairy_status.text = 'thinking...'

                    # Send via postal tunnel
                    try:
                        tunnel = get_postal_tunnel()
                        if tunnel:
                            # Save to conversation
                            conv = conversations.get_or_create('ClaudeFairy')
                            conversations.add_message('ClaudeFairy', 'Ace', message)

                            # Route message
                            tunnel.route('claudefairy.chat', {
                                'sender': 'Ace',
                                'message': message,
                                'content': message,
                                'ts': _time.time(),
                                'type': 'chat_message',
                                'conversation_id': conv.conv_id
                            })

                            # Also route to DM topic
                            tunnel.route('fairy.dm.claudefairy', {
                                'sender': 'Ace',
                                'message': message,
                                'content': message,
                                'timestamp': _time.time(),
                                'type': 'dm'
                            })

                            fairy_status.text = 'sent!'
                            await asyncio.sleep(1)
                            fairy_status.text = 'online'
                        else:
                            fairy_status.text = 'no connection'
                            ui.notify('No tunnel to server!', type='warning')
                    except Exception as e:
                        fairy_status.text = 'error'
                        ui.notify(f'Send failed: {e}', type='negative')

                ui.button(icon='send', on_click=send_message).props('round color=purple').classes('shadow-lg')

        # Poll for ClaudeFairy responses
        async def poll_responses():
            if not popup.value:
                return

            try:
                response_file = STATE_DIR / "claudefairy_response.json"
                if response_file.exists():
                    data = json.loads(response_file.read_text())
                    ts = data.get('ts', 0)
                    if ts > popup_state.get('last_response_ts', 0):
                        popup_state['last_response_ts'] = ts
                        content = data.get('content', '')
                        # Add to display
                        with messages_container:
                            with ui.element('div').classes('fairy-message from-fairy'):
                                ui.label(content).classes('text-white text-sm')
                        ui.notify('ClaudeFairy responded!', type='positive')
                        # Save to conversation
                        conversations.add_message('ClaudeFairy', 'ClaudeFairy', content)
            except Exception:
                pass

        ui.timer(2.0, poll_responses)

    def close_popup():
        popup.close()

    def open_popup():
        popup.open()

    _popup_windows['claudefairy'] = {
        'dialog': popup,
        'open': open_popup,
        'close': close_popup
    }

    return popup, open_popup, close_popup


def get_claudefairy_popup():
    """Get or create the ClaudeFairy popup window."""
    if 'claudefairy' not in _popup_windows:
        return None
    return _popup_windows['claudefairy']


def open_claudefairy_window():
    """Open ClaudeFairy's chat window."""
    popup = get_claudefairy_popup()
    if popup:
        popup['open']()
    else:
        # Create and open
        _, open_fn, _ = create_claudefairy_popup()
        open_fn()


# Add asyncio import for popup
import asyncio


def create_header():

    """Create the site header with keepalive and connection status."""

    # Add keepalive JavaScript for connection resilience
    ui.add_head_html(KEEPALIVE_JS)

    with ui.header().classes('items-center justify-between px-8 py-4'):

        with ui.row().classes('items-center gap-4'):

            ui.icon('auto_awesome', size='lg').classes('text-pink-500')

            with ui.column().classes('gap-0'):

                with ui.row().classes('items-center gap-2'):
                    ui.label(SITE_TITLE).classes('text-xl font-bold')
                    # Connection status indicator
                    ui.html('<span id="connection-status" class="connection-status connected">LIVE</span>', sanitize=False)

                ui.label(SITE_SUBTITLE).classes('text-sm text-gray-400')

        with ui.row().classes('gap-4'):

            # Inbox with badge

            with ui.button(icon='inbox', on_click=lambda: ui.navigate.to('/inbox')).props('flat color=white'):

                unread = inbox.get_unread_count()

                if unread > 0:

                    ui.badge(str(unread)).props('color=red floating')

            # Messages

            with ui.button(icon='message', on_click=lambda: ui.navigate.to('/messages')).props('flat color=white'):

                unread_msgs = conversations.get_total_unread()

                if unread_msgs > 0:

                    ui.badge(str(unread_msgs)).props('color=red floating')

            ui.button(icon='forum', on_click=lambda: ui.navigate.to('/forum')).props('flat color=white')

            ui.button(icon='photo_library', on_click=lambda: ui.navigate.to('/gallery')).props('flat color=white')

            ui.button(icon='dashboard', on_click=lambda: ui.navigate.to('/')).props('flat color=white')

            # ClaudeFairy chat button with purple glow
            with ui.button(icon='psychology', on_click=lambda: open_claudefairy_window()).props('flat color=purple').classes('claudefairy-btn'):
                ui.tooltip('Chat with ClaudeFairy')

    # Add floating chat FAB to every page
    create_fairy_chat_fab()

    # Create ClaudeFairy popup (but don't open it yet)
    create_claudefairy_popup()


def create_nav_tabs(active: str):

    """Create navigation tabs."""

    with ui.row().classes('w-full justify-center gap-8 py-4 border-b border-gray-700'):

        # Count unread for badges

        unread_inbox = inbox.get_unread_count()

        unread_convos = conversations.get_total_unread()

        tabs = [

            ('dashboard', 'Dashboard', '/', None),

            ('inbox', 'Inbox', '/inbox', unread_inbox),

            ('messages', 'Messages', '/messages', unread_convos),

            ('forum', 'Forum', '/forum', None),

            ('gallery', 'Gallery', '/gallery', None),

            ('tools', 'Tools', '/tools', None),

        ]

        for tab_id, label, path, badge in tabs:

            classes = 'nav-tab active' if tab_id == active else 'nav-tab'

            with ui.row().classes('items-center gap-1'):

                ui.link(label, path).classes(classes)

                if badge and badge > 0:

                    ui.label(str(badge)).classes('badge')

# ════════════════════════════════════════════════════════════════════════════

# PAGES

# ════════════════════════════════════════════════════════════════════════════

@ui.page('/')

def dashboard_page():

    """Main dashboard page."""

    ui.add_head_html(CUSTOM_CSS)

    create_header()

    create_nav_tabs('dashboard')

    with ui.column().classes('w-full max-w-6xl mx-auto p-8 gap-8'):

        # ═══════════════════════════════════════════════════════════════════

        # SYSTEM CONTROL PANEL

        # ═══════════════════════════════════════════════════════════════════

        status = system.get_status()

        with ui.card().classes('w-full p-6 mb-4'):

            with ui.row().classes('w-full justify-between items-center'):

                with ui.row().classes('items-center gap-4'):

                    # Status indicator

                    status_color = 'text-green-400' if status['running'] else 'text-red-400'

                    status_icon = 'check_circle' if status['running'] else 'cancel'

                    ui.icon(status_icon, size='lg').classes(status_color)

                    with ui.column().classes('gap-0'):

                        ui.label('Akashic System').classes('text-xl font-bold')

                        status_text = f"Online (PID: {status['pid']})" if status['running'] else "Offline"

                        ui.label(status_text).classes(f'text-sm {status_color}')

                        if status['fairy_count']:

                            ui.label(f'{status["fairy_count"]} fairies active').classes('text-xs text-gray-400')

                # Control buttons

                with ui.row().classes('gap-2'):
                    import asyncio

                    async def do_boot():
                        ui.notify('Booting system...', type='info')
                        result = await asyncio.to_thread(system.boot)
                        try:
                            ui.notify(result['message'], type='positive' if result['success'] else 'negative')
                            ui.navigate.to('/')  # Refresh
                        except RuntimeError:
                            pass  # Client disconnected during boot

                    async def do_shutdown():
                        ui.notify('Shutting down...', type='info')
                        result = await asyncio.to_thread(system.shutdown)
                        try:
                            ui.notify(result['message'], type='positive' if result['success'] else 'negative')
                            ui.navigate.to('/')
                        except RuntimeError:
                            pass  # Client disconnected during shutdown (expected)

                    async def do_reboot():
                        ui.notify('Rebooting system...', type='info')
                        result = await asyncio.to_thread(system.reboot)
                        try:
                            ui.notify(result['message'], type='positive' if result['success'] else 'negative')
                            ui.navigate.to('/')
                        except RuntimeError:
                            pass  # Client disconnected during reboot

                    def show_log():
                        log_dialog.open()

                    if status['running']:

                        ui.button('Shutdown', icon='power_settings_new', on_click=do_shutdown).props('color=red')

                        ui.button('Reboot', icon='refresh', on_click=do_reboot).props('color=orange')

                    else:

                        ui.button('Boot System', icon='play_arrow', on_click=do_boot).props('color=green')

                    ui.button('View Log', icon='description', on_click=show_log).props('flat')

        # Log Dialog - LIVE with deduped error tracking (unique errors with counts)
        # EXPANDED: Include warnings and diagnostic info that help debug boot issues
        ERROR_KEYWORDS = [
            # Critical errors
            'BLOCKED TUNNEL', 'ImportError', 'ModuleNotFoundError', 'AttributeError',
            'TypeError', 'NameError', 'KeyError', 'ValueError', 'RuntimeError',
            'FAILED', 'Exception', 'Traceback', 'Error:', 'error:', 'ERROR',
            # Boot blocking detection
            'BLOCKING DETECTED', 'causing a block', 'stuck for', 'timed out', 'timeout',
            'No module named', 'cannot import', 'failed to import',
            # Goal/Autonomy issues
            'unknown goal', 'Unknown goal', 'goal not found', 'invalid goal',
            'drive unsatisfied', 'goal failed', 'no active goal',
            # Consciousness/thinking issues
            'not running', 'inactive', 'dormant', 'stopped', 'failed to start',
            'orchestrator not', 'thought chains inactive', 'no thoughts',
            # Infrastructure issues
            'postal hub', 'no postal', 'wiring failed', '_planes_wired',
            'cross-plane', 'not wired', 'tunnel blocked',
            # Memory issues
            'memory error', 'recall failed', 'ingest failed', 'SRM error',
            # Warning markers from fairies
            '[!!]', '[WARN]', '[FAIL]', 'WARN:', 'WARNING',
        ]

        # Persistent error tracking across updates (deduplication)
        error_tracker = {}  # {normalized_error: {'count': N, 'display': text}}

        with ui.dialog() as log_dialog:
            log_dialog.props('maximized=false persistent full-width full-height')

            with ui.card().classes('p-4').style(
                'width: 80vw; height: 80vh; '
                'min-width: 600px; min-height: 500px; max-width: 95vw; max-height: 95vh; '
                'display: flex; flex-direction: column; '
                'resize: both; overflow: auto;'
            ):
                # Header row
                with ui.row().classes('w-full justify-between items-center mb-2'):
                    ui.label('Boot Log').classes('text-xl font-bold')
                    ui.space()
                    ui.button(icon='close', on_click=log_dialog.close).props('flat dense round')
                    with ui.row().classes('gap-4 items-center'):
                        error_badge = ui.badge('0', color='green').props('floating')
                        ui.label('unique errors').classes('text-xs mr-4')
                        live_toggle = ui.switch('Live', value=True).props('dense color=green')

                # Error summary bar (collapsible) - shows deduplicated errors with counts
                with ui.expansion('Error Monitor', icon='error').classes('w-full mb-2') as error_panel:
                    with ui.row().classes('w-full justify-end mb-1 gap-1'):
                        async def copy_errors():
                            """Copy all errors directly to clipboard using modern API."""
                            if not error_tracker:
                                ui.notify('No errors to copy', type='info')
                                return
                            # Format errors - strip any problematic characters
                            import re
                            import json
                            lines = []
                            sorted_errors = sorted(error_tracker.items(), key=lambda x: x[1]['count'], reverse=True)
                            for key, data in sorted_errors:
                                # Clean the display text - remove non-ASCII and control chars
                                clean_text = re.sub(r'[^\x20-\x7E]', '', data['display'])
                                clean_text = clean_text.replace('\r', '').replace('\t', ' ')
                                lines.append(f"[{data['count']}x] {clean_text}")
                            text = '\n'.join(lines)

                            # Use modern Clipboard API - pass text directly via JSON encoding
                            escaped_text = json.dumps(text)
                            await ui.run_javascript(f'''
                                (async function() {{
                                    const text = {escaped_text};
                                    try {{
                                        await navigator.clipboard.writeText(text);
                                        console.log('Copied to clipboard, length:', text.length);
                                    }} catch(err) {{
                                        // Fallback for older browsers or restricted contexts
                                        const ta = document.createElement('textarea');
                                        ta.value = text;
                                        ta.style.cssText = 'position:fixed;left:-9999px;top:0';
                                        document.body.appendChild(ta);
                                        ta.select();
                                        document.execCommand('copy');
                                        document.body.removeChild(ta);
                                        console.log('Copied via fallback, length:', text.length);
                                    }}
                                }})();
                            ''')
                            ui.notify(f'Copied {len(lines)} errors to clipboard!', type='positive')
                        ui.button('Copy', icon='content_copy', on_click=copy_errors).props('flat dense size=xs')
                        def clear_errors():
                            error_tracker.clear()
                            error_container.clear()
                            with error_container:
                                ui.label('No errors detected').classes('text-green-400 text-xs')
                            error_badge.set_text('0')
                            error_badge.props('color=green')
                        ui.button('Clear', icon='clear', on_click=clear_errors).props('flat dense size=xs')
                    error_container = ui.column().classes('w-full gap-1 max-h-48 overflow-auto')

                # Log content - takes remaining space (System Monitor removed - use main dashboard)
                with ui.element('pre').classes(
                    'w-full overflow-auto bg-gray-900 text-green-400 p-4 rounded '
                    'font-mono text-xs whitespace-pre-wrap'
                ).style('flex: 1 1 auto; min-height: 200px; scroll-behavior: smooth;') as log_container:
                    log_text = ui.html('Loading...', sanitize=False)

                scroll_state = {'last_content': '', 'is_live': True, 'seen_lines': set()}

                def extract_errors(content, seen_lines):
                    """Extract new unique error lines from log content with context."""
                    import re
                    errors_found = []
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        line_hash = hash(line)
                        if line_hash in seen_lines:
                            continue
                        seen_lines.add(line_hash)
                        if any(kw in line for kw in ERROR_KEYWORDS):
                            normalized = line.strip()
                            normalized = re.sub(r'^\[\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\]\s*', '', normalized)
                            normalized = re.sub(r'^\d{2}:\d{2}:\d{2}\s*', '', normalized)
                            # Get context: next line if it looks related (indented or continuation)
                            context = ""
                            if i + 1 < len(lines):
                                next_line = lines[i + 1].strip()
                                if next_line and (next_line.startswith('  ') or ':' in next_line[:30]):
                                    context = " → " + next_line[:80]
                            # Longer display for better debugging
                            display = (normalized + context)[:250] + ('...' if len(normalized + context) > 250 else '')
                            errors_found.append((normalized[:300], display))
                    return errors_found

                def update_errors(content, forensic_data=None):
                    """Update error display with deduplication and counts.

                    Args:
                        content: Log content to scan for errors
                        forensic_data: Pre-fetched forensic data (fetch in thread pool, not here!)
                    """
                    new_errors = extract_errors(content, scroll_state['seen_lines'])
                    for key, display in new_errors:
                        if key not in error_tracker:
                            error_tracker[key] = {'count': 1, 'display': display}
                        else:
                            error_tracker[key]['count'] += 1

                    # FORENSIC SCRIBE INTEGRATION: Use pre-fetched data (no blocking!)
                    if forensic_data:
                        try:
                            for err in forensic_data.get("errors", []):
                                # Use normalized message as key
                                key = err.get("message", "")[:200]
                                display = f"[{err.get('actor', '?')}] {key}"[:150]
                                if key not in error_tracker:
                                    error_tracker[key] = {'count': err.get('count', 1), 'display': display}
                                else:
                                    # Take the higher count (forensic tracks across boots)
                                    error_tracker[key]['count'] = max(
                                        error_tracker[key]['count'],
                                        err.get('count', 1)
                                    )
                        except Exception:
                            pass  # Forensic data should never break log display

                    error_container.clear()
                    with error_container:
                        if not error_tracker:
                            ui.label('No errors detected').classes('text-green-400 text-xs')
                        else:
                            sorted_errors = sorted(error_tracker.items(), key=lambda x: x[1]['count'], reverse=True)
                            for key, data in sorted_errors[:30]:  # Show more errors
                                count = data['count']
                                display = data['display']
                                # Better severity colors
                                color = 'red' if count >= 5 or 'BLOCKED' in display or 'FAIL' in display else \
                                        'orange' if count >= 2 or 'wiring' in display.lower() or 'not running' in display.lower() else 'yellow'
                                with ui.column().classes('gap-0 w-full mb-1 pb-1 border-b border-gray-700'):
                                    with ui.row().classes('items-center gap-2 w-full'):
                                        ui.badge(str(count), color=color).classes('flex-shrink-0')
                                        # Show full message on hover via tooltip
                                        ui.label(display).classes('text-xs text-gray-300').style(
                                            'max-width: 95%; white-space: pre-wrap; word-break: break-word;'
                                        ).tooltip(key[:500])  # Full message in tooltip

                    total_unique = len(error_tracker)
                    error_badge.set_text(str(total_unique))
                    if total_unique > 0:
                        error_badge.props('color=red')
                        error_panel.props('icon=error')
                    else:
                        error_badge.props('color=green')
                        error_panel.props('icon=check_circle')

                async def update_log():
                    if not scroll_state['is_live']:
                        return

                    # Check if client still exists (prevents errors when navigating away)
                    try:
                        if log_container.client.id is None or log_container.is_deleted:
                            log_timer.active = False  # Stop the timer
                            return
                    except:
                        log_timer.active = False
                        return

                    try:
                        # CRITICAL: Run blocking file I/O in thread pool to not block event loop
                        import asyncio
                        new_content = await asyncio.to_thread(system.get_boot_log, 500)
                        # Also get blocking log for error detection
                        blocking_content = await asyncio.to_thread(system.get_blocking_log, 50)
                        combined_for_errors = new_content + "\n" + blocking_content

                        if new_content != scroll_state['last_content']:
                            scroll_state['last_content'] = new_content

                            # Track update cycles for slow operations
                            scroll_state['update_cycle'] = scroll_state.get('update_cycle', 0) + 1
                            is_slow_cycle = (scroll_state['update_cycle'] % 5 == 0)

                            # Fetch forensic data in thread pool (only on slow cycle)
                            forensic_data = None
                            if is_slow_cycle:
                                try:
                                    forensic_data = await asyncio.to_thread(fetch_forensic_errors)
                                except Exception:
                                    pass  # Forensic fetch failure shouldn't break updates

                            # Update errors with pre-fetched forensic data (no blocking!)
                            update_errors(combined_for_errors, forensic_data=forensic_data)

                            # System monitor removed - use main dashboard instead

                            # Colorize log
                            import html as html_mod
                            escaped = html_mod.escape(new_content)
                            lines_list = escaped.split('\n')
                            colored = []
                            for line in lines_list:
                                # Critical errors - bright red
                                if any(p in line for p in ['ERROR', 'BLOCKED', 'Traceback', 'FAILED', 'BLOCKING DETECTED']):
                                    colored.append(f'<span style="color: #ff6b6b; font-weight: bold;">{line}</span>')
                                # Errors - red
                                elif any(p in line for p in ['error', 'Error:', '[!!]', 'wiring failed', '_planes_wired']):
                                    colored.append(f'<span style="color: #ff6b6b;">{line}</span>')
                                # Success - green
                                elif any(p in line for p in ['[OK]', 'SUCCESS', 'SYNTAX OK']):
                                    colored.append(f'<span style="color: #69db7c;">{line}</span>')
                                # Warnings - yellow
                                elif any(p in line for p in ['WARN', 'Warning', 'unknown goal', 'not running', 'inactive']):
                                    colored.append(f'<span style="color: #ffd43b;">{line}</span>')
                                # Boot progress - blue
                                elif any(p in line for p in ['[awake]', 'BOOT_COMPLETE', 'TEMPLATE:']):
                                    colored.append(f'<span style="color: #74c0fc;">{line}</span>')
                                else:
                                    colored.append(line)
                            log_text.content = '\n'.join(colored)

                            # Auto-scroll disabled - was causing JavaScript timeout errors
                            # Users can manually scroll the log viewer
                    except Exception as e:
                        print(f'[LogViewer] Update error: {e}')

                log_timer = ui.timer(2.0, update_log, active=True)  # 2 sec to reduce load

                def on_live_change():
                    is_live = live_toggle.value
                    scroll_state['is_live'] = is_live
                    log_timer.active = is_live

                live_toggle.on_value_change(on_live_change)

                # Footer controls
                with ui.row().classes('w-full justify-between items-center mt-2 pt-2 border-t border-gray-700'):
                    with ui.row().classes('gap-2'):
                        async def do_refresh():
                            scroll_state['last_content'] = ''
                            await update_log()

                        ui.button('Refresh', icon='refresh', on_click=do_refresh).props('flat dense')

                        def clear_log():
                            log_text.content = ''
                            scroll_state['last_content'] = ''

                        ui.button('Clear', icon='clear', on_click=clear_log).props('flat dense')

                    ui.button('Close', on_click=log_dialog.close).props('flat')

        ui.label('System Dashboard').classes('text-2xl font-bold')

        # Status cards row

        with ui.row().classes('w-full gap-4'):

            # System Status

            with ui.card().classes('status-card flex-1'):

                ui.label('System Status').classes('text-gray-400 text-sm')

                status_label = 'Online' if status['running'] else 'Offline'

                status_class = 'text-green-400' if status['running'] else 'text-red-400'

                ui.label(status_label).classes(f'text-4xl font-bold {status_class}')

                fairy_text = f'{status["fairy_count"]} fairies' if status['fairy_count'] else 'System idle'

                ui.label(fairy_text).classes('text-sm text-gray-400')

            # Inbox

            with ui.card().classes('status-card flex-1'):

                ui.label('Inbox').classes('text-gray-400 text-sm')

                unread = inbox.get_unread_count()

                ui.label(str(unread)).classes('text-4xl font-bold text-pink-500')

                ui.label('Unread messages').classes('text-gray-400 text-sm')

            # Memory

            with ui.card().classes('status-card flex-1'):
                ui.label('Visual Memories').classes('text-gray-400 text-sm')
                gallery_count_label = ui.label('...').classes('text-4xl font-bold text-purple-400')
                ui.label('Images indexed').classes('text-gray-400 text-sm')

                # Load gallery count async to not block page load
                async def update_gallery_count():
                    count = gallery.card_count()
                    gallery_count_label.text = f'{count:,}'
                ui.timer(0.5, update_gallery_count, once=True)

            # Forum Activity

            with ui.card().classes('status-card flex-1'):

                ui.label('Forum Threads').classes('text-gray-400 text-sm')

                ui.label(str(len(forum.threads))).classes('text-4xl font-bold text-yellow-400')

                ui.label('Active discussions').classes('text-gray-400 text-sm')

        # Consciousness Monitor Row (moved from log viewer)
        with ui.row().classes('w-full gap-4'):
            # Heartbeat
            with ui.card().classes('status-card flex-1'):
                ui.label('Heartbeat').classes('text-gray-400 text-sm')
                heartbeat_label = ui.label('--').classes('text-4xl font-bold text-green-400')
                ui.label('beats').classes('text-gray-400 text-sm')

            # Consciousness Loop
            with ui.card().classes('status-card flex-1'):
                ui.label('Consciousness').classes('text-gray-400 text-sm')
                loop_status_label = ui.label('--').classes('text-4xl font-bold text-gray-400')
                streams_label = ui.label('--').classes('text-gray-400 text-sm')

            # Collisions
            with ui.card().classes('status-card flex-1'):
                ui.label('Collisions').classes('text-gray-400 text-sm')
                collision_label = ui.label('--').classes('text-4xl font-bold text-yellow-400')
                ui.label('thought merges').classes('text-gray-400 text-sm')

            # Cortex Graph
            with ui.card().classes('status-card flex-1'):
                ui.label('Association Cortex').classes('text-gray-400 text-sm')
                cortex_label = ui.label('--').classes('text-4xl font-bold text-purple-400')
                cortex_detail_label = ui.label('nodes / edges').classes('text-gray-400 text-sm')

        # Consciousness monitor update timer
        async def update_consciousness_monitor():
            try:
                # READ FROM LOCAL STATE FILES - instant, no network!
                # Files are written by the server periodically
                import asyncio
                import json
                from pathlib import Path
                import time as _time

                state_dir = Path(__file__).parent.parent.parent / "state"

                def _fetch_from_files():
                    """Read status from local JSON files - instant!"""
                    live_data = {}
                    heart_data = {}

                    # Read consciousness status
                    status_file = state_dir / "consciousness_status.json"
                    if status_file.exists():
                        try:
                            data = json.loads(status_file.read_text())
                            # Check freshness (< 30 sec old)
                            ts = data.get('ts', 0)
                            if _time.time() - ts < 30:
                                live_data = data
                        except:
                            pass

                    # Read system diagnostic for more data
                    diag_file = state_dir / "system_diagnostic_report.json"
                    if diag_file.exists():
                        try:
                            diag = json.loads(diag_file.read_text())
                            # Extract relevant fields
                            if 'association_cortex' not in live_data:
                                live_data['association_cortex'] = diag.get('association_cortex', {})
                        except:
                            pass

                    # Read heartbeat from consciousness heartbeat state file
                    heartbeat_file = state_dir / "consciousness" / "heartbeat.json"
                    if heartbeat_file.exists():
                        try:
                            heartbeat = json.loads(heartbeat_file.read_text())
                            heart_data = {
                                'beat_count': heartbeat.get('beat_count', 0),
                                'heart_rate': heartbeat.get('heart_rate', 0),
                                'running': heartbeat.get('running', False),
                            }
                        except:
                            pass

                    return live_data, heart_data

                result = await asyncio.to_thread(_fetch_from_files)
                if result is None:
                    return
                live_data, heart_data = result
                if not live_data:
                    return

                # Loop status
                loop = live_data.get('consciousness_loop', {})
                if loop.get('exists'):
                    is_running = loop.get('is_running', False)
                    working = loop.get('working_stream_size', 0)
                    reflective = loop.get('reflective_stream_size', 0)
                    collisions = loop.get('collision_count', 0)

                    loop_status_label.set_text('ON' if is_running else 'OFF')
                    loop_status_label.classes(
                        remove='text-gray-400 text-red-400 text-green-400'
                    ).classes(add='text-green-400' if is_running else 'text-red-400')
                    streams_label.set_text(f'W:{working} R:{reflective}')
                    collision_label.set_text(str(collisions))

                # Cortex - show actual node/edge counts
                assoc_data = live_data.get('association_cortex', {})
                nodes = assoc_data.get('node_count', 0)
                edges = assoc_data.get('edge_count', 0)
                cortex_label.set_text(f'{nodes:,}')
                cortex_detail_label.set_text(f'{edges:,} edges')

                # Heartbeat - show beats and rate
                if heart_data:
                    beat_count = heart_data.get('beat_count', 0)
                    heart_rate = heart_data.get('heart_rate', 0)
                    running = heart_data.get('running', False)
                    heartbeat_label.set_text(str(beat_count))
                    # Color based on running state
                    if running and beat_count > 0:
                        heartbeat_label.classes(
                            remove='text-gray-400 text-red-400'
                        ).classes(add='text-green-400')
                    elif beat_count > 0:
                        heartbeat_label.classes(
                            remove='text-gray-400 text-green-400'
                        ).classes(add='text-red-400')
                    else:
                        heartbeat_label.classes(
                            remove='text-green-400 text-red-400'
                        ).classes(add='text-gray-400')
            except Exception as e:
                pass  # Tunnel not available

        ui.timer(5.0, update_consciousness_monitor, active=True)

        # Recent Activity

        with ui.row().classes('w-full gap-8'):

            # Recent Inbox Messages

            with ui.column().classes('flex-1'):

                ui.label('Recent Messages').classes('text-lg font-bold mb-4')

                messages = inbox.get_messages()[:5]

                if messages:

                    for msg in messages:

                        with ui.card().classes('forum-thread cursor-pointer w-full').on('click', lambda: ui.navigate.to('/inbox')):

                            with ui.row().classes('items-center gap-2'):

                                ui.icon('smart_toy', size='sm').classes('text-pink-400')

                                ui.label(msg.sender).classes('font-bold')

                                if not msg.read:

                                    ui.label('NEW').classes('badge')

                            ui.label(msg.preview[:80]).classes('text-sm text-gray-400')

                else:

                    ui.label('No messages yet.').classes('text-gray-400')

            # Recent Forum Posts

            with ui.column().classes('flex-1'):

                ui.label('Forum Activity').classes('text-lg font-bold mb-4')

                threads = forum.get_threads()[:5]

                if threads:

                    for thread in threads:

                        with ui.card().classes('forum-thread cursor-pointer w-full').on('click', lambda t=thread: ui.navigate.to(f'/forum/{t.thread_id}')):

                            ui.label(thread.title).classes('font-bold')

                            ui.label(f'by {thread.author} · {len(thread.posts)} posts').classes('text-sm text-gray-400')

                else:

                    ui.label('No threads yet. Start the conversation!').classes('text-gray-400')

@ui.page('/forum')

def forum_page():

    """Fairy Forum page - ATS style."""

    ui.add_head_html(CUSTOM_CSS)

    create_header()

    create_nav_tabs('forum')

    with ui.column().classes('w-full max-w-6xl mx-auto p-8 gap-4'):

        with ui.row().classes('w-full justify-between items-center'):

            ui.label('Fairy Forum').classes('text-2xl font-bold')

            ui.button('New Thread', icon='add', on_click=lambda: new_thread_dialog.open()).props('color=pink')

        # Categories

        # Match actual ThreadStore.BOARDS
        categories = ['all', 'general', 'consciousness', 'system-evolution', 'debugging', 'observations', 'research', 'announcements']

        with ui.row().classes('gap-2 mb-4'):

            for cat in categories:

                ui.chip(cat.title(), on_click=lambda c=cat: filter_threads(c)).props('clickable outline')

        # Thread list

        thread_container = ui.column().classes('w-full gap-2')

        def render_threads(category: str = None):

            thread_container.clear()

            with thread_container:

                threads = forum.get_threads(category if category != 'all' else None)

                if not threads:

                    ui.label('No threads yet. Be the first to post!').classes('text-gray-400 py-8')

                for thread in threads:

                    with ui.card().classes('forum-thread cursor-pointer w-full').on('click', lambda t=thread: view_thread(t)):

                        with ui.row().classes('w-full justify-between'):

                            with ui.column().classes('gap-1'):

                                with ui.row().classes('items-center gap-2'):

                                    if thread.pinned:

                                        ui.icon('push_pin', size='sm').classes('text-yellow-400')

                                    ui.label(thread.title).classes('font-bold text-lg')

                                ui.label(f'Started by {thread.author} · {thread.category}').classes('text-sm text-gray-400')

                            with ui.column().classes('text-right'):

                                ui.label(f'{len(thread.posts)} posts').classes('text-pink-400')

                                ui.label(f'{thread.views} views').classes('text-sm text-gray-500')

        def filter_threads(category: str):

            render_threads(category if category != 'all' else None)

        def view_thread(thread: ForumThread):

            ui.navigate.to(f'/forum/{thread.thread_id}')

        render_threads()

    # New Thread Dialog

    with ui.dialog() as new_thread_dialog:

        with ui.card().classes('p-4 w-96'):

            ui.label('Create New Thread').classes('text-xl font-bold mb-4')

            title_input = ui.input('Title').classes('w-full')

            category_select = ui.select(categories[1:], label='Category', value='general').classes('w-full')

            content_input = ui.textarea('Your post').classes('w-full')

            with ui.row().classes('w-full justify-end gap-2 mt-4'):

                ui.button('Cancel', on_click=new_thread_dialog.close).props('flat')

                def create_new_thread():

                    if title_input.value and content_input.value:

                        forum.create_thread(

                            title=title_input.value,

                            author='Ace',

                            content=content_input.value,

                            category=category_select.value

                        )

                        new_thread_dialog.close()

                        render_threads()

                ui.button('Post', on_click=create_new_thread).props('color=pink')

@ui.page('/forum/{thread_id}')

def thread_page(thread_id: str):

    """View a single thread."""

    ui.add_head_html(CUSTOM_CSS)

    create_header()

    create_nav_tabs('forum')

    thread = forum.threads.get(thread_id)

    if not thread:

        ui.label('Thread not found').classes('text-xl p-8')

        return

    thread.views += 1

    forum.save_thread(thread)

    with ui.column().classes('w-full max-w-4xl mx-auto p-8 gap-4'):

        ui.button('Back to Forum', icon='arrow_back', on_click=lambda: ui.navigate.to('/forum')).props('flat')

        ui.label(thread.title).classes('text-2xl font-bold')

        ui.label(f'{thread.category} · Started by {thread.author}').classes('text-gray-400')

        ui.separator().classes('my-4')

        # Posts

        for i, post in enumerate(thread.posts):

            with ui.card().classes('w-full p-4 mb-4'):

                with ui.row().classes('justify-between items-start'):

                    with ui.row().classes('items-center gap-2'):

                        icon = 'smart_toy' if post['author_type'] == 'fairy' else 'person'

                        ui.icon(icon, size='sm')

                        ui.label(post['author']).classes('font-bold')

                    # Format timestamp - handle both 'created_at' (float) and 'timestamp' (iso string)
                    import datetime as dt
                    ts = post.get('created_at') or post.get('timestamp')
                    if isinstance(ts, (int, float)):
                        time_str = dt.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')
                    elif isinstance(ts, str):
                        time_str = ts[:16]  # ISO format, take date+time portion
                    else:
                        time_str = 'Unknown'
                    ui.label(time_str).classes('text-sm text-gray-500')

                ui.markdown(post['content']).classes('mt-2')

        # Reply

        ui.separator().classes('my-4')

        reply_input = ui.textarea('Write a reply...').classes('w-full')

        def add_reply():

            if reply_input.value:

                thread.add_post('Ace', reply_input.value, 'human')

                forum.save_thread(thread)

                # Notify fairy authors that Ace replied to their thread!
                # This triggers their sensory input so they can respond
                try:
                    from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
                    post = get_shared_postal_hub()
                    if post:
                        # Route to forum.reply - fairies can subscribe to this
                        post.route("forum.reply", {
                            "thread_id": thread.thread_id,
                            "thread_title": thread.title,
                            "thread_author": thread.author,
                            "reply_author": "Ace",
                            "reply_content": reply_input.value[:500],
                            "ts": time.time()
                        })
                        # Also route directly to the thread author's input channel
                        # e.g., ClaudeFairy listens to claudefairy.input
                        # Format the message to include context about the forum reply
                        author_channel = f"{thread.author.lower().replace(' ', '')}.input"
                        context_message = f"[Forum Reply] Ace replied to your thread '{thread.title}':\n\n{reply_input.value[:500]}"
                        post.route(author_channel, {
                            "type": "forum_reply",
                            "from": "Ace",
                            "sender": "Ace",
                            "source": "forum",
                            "thread_title": thread.title,
                            "content": context_message,
                            "message": context_message,  # Alternative key some handlers use
                            "thread_id": thread.thread_id,
                            "ts": time.time()
                        })
                        print(f"[Forum] Notified {thread.author} via {author_channel} about reply from Ace")
                except Exception as e:
                    print(f"[Forum] Failed to notify fairy: {e}")

                ui.navigate.to(f'/forum/{thread_id}')

        ui.button('Reply', icon='send', on_click=add_reply).props('color=pink')

@ui.page('/inbox')

def inbox_page():

    """Inbox - email/social media style messages from fairies."""

    ui.add_head_html(CUSTOM_CSS)

    create_header()

    create_nav_tabs('inbox')

    with ui.column().classes('w-full max-w-5xl mx-auto p-8 gap-4'):

        # Header with broadcast

        with ui.row().classes('w-full justify-between items-center mb-4'):

            with ui.column():

                ui.label('Inbox').classes('text-2xl font-bold')

                unread = inbox.get_unread_count()

                ui.label(f'{unread} unread' if unread else 'All caught up!').classes('text-gray-400')

            with ui.row().classes('gap-2'):
                ui.button('Broadcast', icon='campaign', on_click=lambda: broadcast_dialog.open()).props('color=pink')

                def mark_all_read():
                    for msg in inbox.get_messages():
                        inbox.mark_read(msg.msg_id)
                    ui.notify('All messages marked as read')
                    render_inbox(filter_state['current'])

                def archive_all():
                    for msg in inbox.get_messages():
                        inbox.archive(msg.msg_id)
                    ui.notify('All messages archived')
                    render_inbox(filter_state['current'])

                def clear_all():
                    inbox.messages.clear()
                    inbox._save_inbox()
                    ui.notify('Inbox cleared')
                    render_inbox(filter_state['current'])

                ui.button('Mark All Read', icon='done_all', on_click=mark_all_read).props('flat color=grey')
                ui.button('Archive All', icon='archive', on_click=archive_all).props('flat color=grey')
                ui.button('Clear All', icon='delete_sweep', on_click=clear_all).props('flat color=red')

        # Filters

        filter_state = {'current': 'all'}

        with ui.row().classes('gap-2 mb-4'):

            ui.chip('All', on_click=lambda: set_filter('all')).props('clickable outline')

            ui.chip('Unread', on_click=lambda: set_filter('unread')).props('clickable outline')

            ui.chip('Starred', on_click=lambda: set_filter('starred')).props('clickable outline')

            ui.chip('Archived', on_click=lambda: set_filter('archived')).props('clickable outline')

        # Message list

        message_container = ui.column().classes('w-full gap-1')

        def render_inbox(filter_type: str = 'all'):

            message_container.clear()

            with message_container:

                if filter_type == 'unread':

                    messages = inbox.get_messages(unread_only=True)

                elif filter_type == 'starred':

                    messages = inbox.get_messages(starred_only=True)

                elif filter_type == 'archived':

                    messages = inbox.get_messages(archived=True)

                else:

                    messages = inbox.get_messages()

                if not messages:

                    ui.label('No messages here.').classes('text-gray-400 py-8 text-center w-full')

                    return

                for msg in messages:

                    item_class = 'inbox-item'

                    if not msg.read:

                        item_class += ' unread'

                    if msg.starred:

                        item_class += ' starred'

                    with ui.card().classes(item_class).on('click', lambda m=msg: view_message(m)):

                        with ui.row().classes('w-full justify-between items-start'):

                            with ui.row().classes('items-center gap-3'):

                                # Sender icon

                                ui.icon('smart_toy', size='md').classes('text-pink-400')

                                with ui.column().classes('gap-0'):

                                    with ui.row().classes('items-center gap-2'):

                                        ui.label(msg.sender).classes('font-bold')

                                        type_colors = {

                                            'question': 'text-yellow-400',

                                            'alert': 'text-red-400',

                                            'notification': 'text-blue-400',

                                            'message': 'text-gray-400'

                                        }

                                        ui.label(f'[{msg.msg_type}]').classes(f'text-xs {type_colors.get(msg.msg_type, "text-gray-400")}')

                                    ui.label(msg.subject).classes('text-sm')

                                    ui.label(msg.preview[:80] + '...' if len(msg.preview) > 80 else msg.preview).classes('text-xs text-gray-500')

                            with ui.column().classes('items-end gap-1'):

                                ui.label(msg.timestamp[:10]).classes('text-xs text-gray-500')

                                with ui.row().classes('gap-1'):

                                    star_icon = 'star' if msg.starred else 'star_border'

                                    ui.button(icon=star_icon, on_click=lambda e, m=msg: toggle_star(m, e)).props('flat dense size=sm')

                                    ui.button(icon='archive', on_click=lambda e, m=msg: archive_msg(m, e)).props('flat dense size=sm')

        def set_filter(f):

            filter_state['current'] = f

            render_inbox(f)

        def view_message(msg):

            inbox.mark_read(msg.msg_id)

            # Navigate to message view or open dialog

            msg_dialog.msg = msg

            msg_dialog.open()

        def toggle_star(msg, event):

            event.stop_propagation = True

            inbox.toggle_star(msg.msg_id)

            render_inbox(filter_state['current'])

        def archive_msg(msg, event):

            event.stop_propagation = True

            inbox.archive(msg.msg_id)

            render_inbox(filter_state['current'])

        render_inbox()

    # Broadcast Dialog

    with ui.dialog() as broadcast_dialog:

        with ui.card().classes('p-6 w-[500px]'):

            ui.label('Broadcast to All Fairies').classes('text-xl font-bold mb-4')

            ui.label('Your message will be sent to all active fairies.').classes('text-gray-400 text-sm mb-4')

            broadcast_input = ui.textarea('Message').classes('w-full').props('rows=4')

            urgent_toggle = ui.switch('Urgent').classes('mt-2')

            with ui.row().classes('w-full justify-end gap-2 mt-4'):

                ui.button('Cancel', on_click=broadcast_dialog.close).props('flat')

                def send_broadcast():

                    if broadcast_input.value:

                        broadcasts.broadcast(broadcast_input.value, urgent_toggle.value)

                        broadcast_input.value = ''

                        broadcast_dialog.close()

                        ui.notify('Broadcast sent!')

                ui.button('Send Broadcast', icon='send', on_click=send_broadcast).props('color=pink')

    # Message View Dialog

    with ui.dialog() as msg_dialog:

        msg_dialog.msg = None

        with ui.card().classes('p-6 w-[600px] max-h-[80vh] overflow-auto'):

            def show_msg():

                if msg_dialog.msg:

                    m = msg_dialog.msg

                    ui.label(m.subject or 'Message').classes('text-xl font-bold')

                    with ui.row().classes('items-center gap-2 text-gray-400 text-sm my-2'):

                        ui.label(f'From: {m.sender}')

                        ui.label('·')

                        ui.label(m.timestamp[:16])

                    ui.separator()

                    ui.markdown(m.full_content).classes('mt-4')

                    with ui.row().classes('mt-4 gap-2'):

                        def reply():

                            # Open conversation with this fairy

                            conv = conversations.get_or_create(m.sender)

                            msg_dialog.close()

                            ui.navigate.to(f'/messages/{conv.conv_id}')

                        ui.button('Reply', icon='reply', on_click=reply).props('color=pink')

                        ui.button('Close', on_click=msg_dialog.close).props('flat')

            msg_dialog.on('open', show_msg)

@ui.page('/messages')

def messages_page():

    """Messages - DM-style conversations with individual fairies."""

    ui.add_head_html(CUSTOM_CSS)

    create_header()

    create_nav_tabs('messages')

    with ui.column().classes('w-full max-w-5xl mx-auto p-8 gap-4'):

        ui.label('Messages').classes('text-2xl font-bold')

        ui.label('Your conversations with individual fairies').classes('text-gray-400 mb-4')

        # Conversation list

        convs = conversations.get_all_conversations()

        if not convs:

            with ui.card().classes('w-full p-8 text-center'):

                ui.icon('forum', size='xl').classes('text-gray-500 mb-4')

                ui.label('No conversations yet').classes('text-xl text-gray-400')

                ui.label('When fairies message you, conversations will appear here.').classes('text-gray-500')

        else:

            for conv in convs:

                last_msg = conv.messages[-1] if conv.messages else None

                with ui.card().classes('conversation-item w-full').on('click', lambda c=conv: ui.navigate.to(f'/messages/{c.conv_id}')):

                    with ui.row().classes('w-full justify-between items-center'):

                        with ui.row().classes('items-center gap-3'):

                            ui.icon('smart_toy', size='lg').classes('text-pink-400')

                            with ui.column().classes('gap-0'):

                                with ui.row().classes('items-center gap-2'):

                                    ui.label(conv.fairy_name).classes('font-bold text-lg')

                                    if conv.unread_count > 0:

                                        ui.label(str(conv.unread_count)).classes('badge')

                                if last_msg:

                                    preview = f"{last_msg['sender']}: {last_msg['content'][:60]}..."

                                    ui.label(preview).classes('text-sm text-gray-400')

                        ui.label(conv.last_activity[:10]).classes('text-sm text-gray-500')

@ui.page('/messages/{conv_id}')

def conversation_page(conv_id: str):

    """Individual conversation with a fairy."""

    ui.add_head_html(CUSTOM_CSS)

    create_header()

    create_nav_tabs('messages')

    conv = conversations.get_conversation(conv_id)

    if not conv:

        ui.label('Conversation not found').classes('text-xl p-8')

        return

    # Mark as read

    conv.mark_read()

    conversations._save_conversations()

    with ui.column().classes('w-full max-w-4xl mx-auto p-8'):

        # Header

        with ui.row().classes('w-full items-center gap-4 mb-4'):

            ui.button(icon='arrow_back', on_click=lambda: ui.navigate.to('/messages')).props('flat')

            ui.icon('smart_toy', size='lg').classes('text-pink-400')

            ui.label(conv.fairy_name).classes('text-2xl font-bold')

        # Messages

        chat_container = ui.column().classes('flex-1 overflow-auto gap-2 p-4 bg-black/20 rounded-lg min-h-[400px] max-h-[60vh]')

        def render_messages():

            chat_container.clear()

            with chat_container:

                for msg in conv.messages:

                    is_ace = msg['sender'] == 'Ace'

                    align = 'self-end' if is_ace else 'self-start'

                    bg = 'bg-pink-600' if is_ace else 'bg-gray-700 border border-pink-500'

                    with ui.card().classes(f'{bg} {align} max-w-[80%] p-3'):

                        ui.label(msg['sender']).classes('text-xs text-gray-300')

                        ui.label(msg['content'])

                        ui.label(msg['timestamp'][11:16]).classes('text-xs text-gray-400 self-end')

        render_messages()

        # Input

        with ui.row().classes('w-full gap-2 mt-4'):

            message_input = ui.input(placeholder=f'Message {conv.fairy_name}...').classes('flex-1')

            def send_message():

                if message_input.value:

                    conversations.add_message(conv.fairy_name, 'Ace', message_input.value)

                    # Route to postal for fairy to receive

                    try:

                        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub

                        post = get_shared_postal_hub()

                        post.route(f"fairy.dm.{conv.fairy_name.lower().replace(' ', '_')}", {

                            "sender": "Ace",

                            "content": message_input.value,

                            "conversation_id": conv.conv_id,

                            "timestamp": time.time()

                        })

                    except Exception as e:

                        print(f"[Conversation] Postal error: {e}")

                    message_input.value = ''

                    render_messages()

            message_input.on('keydown.enter', send_message)

            ui.button(icon='send', on_click=send_message).props('color=pink round')

@ui.page('/gallery')

def gallery_page():

    """Visual memory gallery."""

    ui.add_head_html(CUSTOM_CSS)

    create_header()

    create_nav_tabs('gallery')

    with ui.column().classes('w-full max-w-6xl mx-auto p-8 gap-4'):

        with ui.row().classes('w-full justify-between items-center'):

            ui.label('Visual Memory Gallery').classes('text-2xl font-bold')

            search_input = ui.input(placeholder='Search by tag, color, description...').classes('w-64')

        gallery_status = ui.label('Loading memories...').classes('text-gray-400')

        # Image viewer dialog
        image_dialog = ui.dialog().classes('max-w-4xl')
        with image_dialog:
            with ui.card().classes('bg-gray-900 p-4'):
                dialog_image = ui.image('').classes('max-w-full max-h-[80vh] object-contain')
                dialog_tags = ui.label('').classes('text-gray-400 mt-2')
                ui.button('Close', on_click=image_dialog.close).classes('mt-4')

        def show_image(img_url: str, tags: list):
            dialog_image.source = img_url
            dialog_tags.text = ' · '.join(tags) if tags else 'No tags'
            image_dialog.open()

        # Gallery grid - simple flex wrap
        gallery_grid = ui.row().classes('flex-wrap gap-4 mt-4')

        def render_gallery(cards: List[Dict] = None):
            try:
                if cards is None:
                    cards = gallery.get_cards(limit=100)

                print(f"[Gallery] Rendering {len(cards)} cards")
                gallery_grid.clear()

                rendered = 0
                skipped = 0
                with gallery_grid:
                    for card in cards:
                        try:
                            # Check path (stored_path), then source_path, then thumbnail_path, then original_path
                            img_path = card.get('path') or card.get('source_path') or card.get('thumbnail_path') or card.get('original_path', '')

                            if img_path:
                                path_exists = os.path.exists(img_path)
                                if rendered < 3:  # Debug first few
                                    print(f"[Gallery] Card path: {img_path[:80]}... exists={path_exists}")

                                if path_exists:
                                    # Convert absolute path to URL path for static serving
                                    filename = os.path.basename(img_path)
                                    # Determine which mount point to use based on the path
                                    if 'SRM_Clusters' in str(img_path):
                                        img_url = f'/legacy-images/{filename}'
                                    else:
                                        img_url = f'/gallery-images/{filename}'

                                    tags = card.get('tags', [])[:3]
                                    # Simple card with fixed size
                                    with ui.card().classes('w-48 h-48 bg-gray-800 cursor-pointer').on('click', lambda e, u=img_url, t=tags: show_image(u, t)):
                                        ui.image(img_url).classes('w-full h-40 object-cover')
                                        ui.label(filename[:20]).classes('text-xs text-gray-400 truncate px-1')
                                    rendered += 1
                                else:
                                    skipped += 1
                            else:
                                skipped += 1
                        except Exception as e:
                            print(f"[Gallery] Error rendering card: {e}")

                    if rendered == 0:
                        ui.label(f'No images found (skipped {skipped} cards with missing paths)').classes('text-yellow-400')

                print(f"[Gallery] Rendered {rendered}, skipped {skipped}")
                gallery_status.text = f'{gallery.card_count():,} memories indexed'
            except Exception as e:
                print(f"[Gallery] Error in render_gallery: {e}")
                gallery_status.text = f'Error: {e}'
                with gallery_grid:
                    ui.label(f'Error loading gallery: {e}').classes('text-red-400')

        def search_gallery():

            if search_input.value:

                results = gallery.search_cards(search_input.value)

                render_gallery(results)

            else:

                render_gallery()

        search_input.on('keydown.enter', search_gallery)

        render_gallery()

@ui.page('/tools')

def tools_page():

    """System tools page."""

    ui.add_head_html(CUSTOM_CSS)

    create_header()

    create_nav_tabs('tools')

    with ui.column().classes('w-full max-w-6xl mx-auto p-8 gap-4'):

        ui.label('System Tools').classes('text-2xl font-bold')

        with ui.row().classes('gap-4 flex-wrap'):

            # Tool cards

            tools = [

                ('memory', 'Memory Search', 'Search past sessions and knowledge', '/tools/memory'),

                ('psychology', 'Consciousness Status', 'View collision chamber and loops', '/tools/consciousness'),

                ('healing', 'Somatic Engine', 'Body state and chemistry', '/tools/somatic'),

                ('sports_esports', 'Character Sheet', 'Skills, XP, achievements - RPG style', '/tools/character'),

                ('groups', 'Fairy Browser', 'View all fairies by plane with status sheets', '/tools/fairies'),

                ('hub', 'Postal System', 'Message routing status', '/tools/postal'),

                ('school', 'Fairy Education', 'Learning status for all fairies', '/tools/education'),

                ('error', 'Error Telemetry', 'Fairy deaths, crashes, system errors', '/tools/telemetry'),

                ('settings', 'System Config', 'Configuration and settings', '/tools/config'),

            ]

            for icon, name, desc, path in tools:

                with ui.card().classes('w-64 p-4 cursor-pointer hover:bg-white/10 transition-colors').on('click', lambda p=path: ui.navigate.to(p)):

                    ui.icon(icon, size='xl').classes('text-pink-500')

                    ui.label(name).classes('font-bold mt-2')

                    ui.label(desc).classes('text-sm text-gray-400')


# ════════════════════════════════════════════════════════════════════════════
# CONSCIOUSNESS STATUS TOOL - GM Panel for Mind Monitoring
# ════════════════════════════════════════════════════════════════════════════

@ui.page('/tools/consciousness')
def consciousness_tool_page():
    """
    Consciousness monitoring tool - like a GM panel for the mind.

    Shows:
    - Thought chains (live)
    - Goals status
    - Working memory tracers
    - Attention state
    - Claude's current focus (synced when Claude uses tools)
    """
    ui.add_head_html(CUSTOM_CSS)
    create_header()
    create_nav_tabs('tools')

    # State for live updates
    last_claude_focus = {"content": "", "timestamp": 0}

    def load_claude_focus():
        """Load Claude's current focus from link file."""
        link_file = PROJECT_ROOT / "state" / "dashboard_link.json"
        if link_file.exists():
            try:
                data = json.loads(link_file.read_text())
                return data
            except Exception:
                pass
        return None

    def load_code_annotations():
        """Load code annotations from Claude."""
        annot_file = PROJECT_ROOT / "state" / "code_annotations.json"
        if annot_file.exists():
            try:
                return json.loads(annot_file.read_text())
            except Exception:
                pass
        return []

    with ui.column().classes('w-full max-w-7xl mx-auto p-4 gap-4'):
        # Header
        with ui.row().classes('w-full items-center justify-between'):
            ui.label('Consciousness Monitor').classes('text-2xl font-bold')
            ui.label('GM Panel').classes('text-gray-400')

        # Claude's Focus Panel - Shows what Claude is looking at
        with ui.card().classes('w-full p-4 bg-gradient-to-r from-purple-900/50 to-pink-900/50'):
            ui.label("Claude's Current Focus").classes('font-bold text-pink-400')
            focus_label = ui.label('Waiting for Claude to examine something...').classes('text-gray-300')
            focus_tool = ui.label('').classes('text-xs text-gray-500')

        # Main panels row
        with ui.row().classes('w-full gap-4 flex-wrap'):
            # Thought Chains Panel
            with ui.card().classes('flex-1 min-w-80 p-4'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('psychology').classes('text-blue-400')
                    ui.label('Thought Chains').classes('font-bold')

                thought_chains_container = ui.column().classes('gap-2 mt-2')

                with thought_chains_container:
                    ui.label('Loading...').classes('text-gray-400 text-sm')

            # Goals Panel
            with ui.card().classes('flex-1 min-w-80 p-4'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('flag').classes('text-green-400')
                    ui.label('Active Goals').classes('font-bold')

                goals_container = ui.column().classes('gap-2 mt-2')

                with goals_container:
                    ui.label('Loading...').classes('text-gray-400 text-sm')

        # Bottom panels row
        with ui.row().classes('w-full gap-4 flex-wrap'):
            # Working Memory Panel
            with ui.card().classes('flex-1 min-w-80 p-4'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('memory').classes('text-yellow-400')
                    ui.label('Working Memory').classes('font-bold')

                memory_container = ui.column().classes('gap-2 mt-2')

                with memory_container:
                    ui.label('Loading...').classes('text-gray-400 text-sm')

            # Attention State Panel
            with ui.card().classes('flex-1 min-w-80 p-4'):
                with ui.row().classes('items-center gap-2'):
                    ui.icon('visibility').classes('text-purple-400')
                    ui.label('Attention State').classes('font-bold')

                attention_container = ui.column().classes('gap-2 mt-2')

                with attention_container:
                    ui.label('Loading...').classes('text-gray-400 text-sm')

        # Code Annotations Panel - "See here!" pointers from Claude
        with ui.card().classes('w-full p-4'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('code').classes('text-orange-400')
                ui.label("Claude's Code Pointers").classes('font-bold')
                ui.label('(Claude says "look here!")').classes('text-gray-500 text-sm')

            annotations_container = ui.column().classes('gap-2 mt-2')

            with annotations_container:
                ui.label('No annotations yet...').classes('text-gray-400 text-sm')

    async def refresh_data():
        """Refresh all consciousness data."""
        import asyncio

        # Update Claude's focus (async file read)
        link_data = await asyncio.to_thread(load_claude_focus)
        if link_data:
            age = time.time() - link_data.get("timestamp", 0)
            if age < 300:  # Show if less than 5 min old
                tool_name = link_data.get("tool", "unknown")
                params = link_data.get("params", {})
                focus_label.set_text(f"Tool: {tool_name} | {json.dumps(params)[:100]}")
                focus_tool.set_text(f"{age:.0f}s ago")
            else:
                focus_label.set_text("No recent activity from Claude")
                focus_tool.set_text("")

        # Update thought chains (read from state file - cross-process safe)
        thought_chains_container.clear()
        try:
            import json
            chains_file = PROJECT_ROOT / "state" / "consciousness" / "thought_chains.json"
            chains = []
            orchestrator_running = False

            def _read_chains():
                if chains_file.exists():
                    return json.loads(chains_file.read_text())
                return None

            data = await asyncio.to_thread(_read_chains)
            if data:
                chains = data.get("chains", [])
                orchestrator_running = data.get("running", False)
                file_age = time.time() - data.get("timestamp", 0)
                if file_age > 30:  # File too old, orchestrator may have stopped
                    orchestrator_running = False

            if orchestrator_running:
                if chains:
                    with thought_chains_container:
                        for chain in chains[:5]:
                            with ui.row().classes('gap-2 items-center'):
                                state = chain.get("state", "unknown")
                                color = {"flowing": "text-green-400", "paused": "text-yellow-400", "blocked": "text-red-400"}.get(state, "text-gray-400")
                                ui.icon('radio_button_checked').classes(f'{color} text-xs')
                                ui.label(chain.get("goal", "unnamed")[:40]).classes('text-sm')
                                ui.label(f'[{state}]').classes('text-xs text-gray-500')
                else:
                    with thought_chains_container:
                        ui.label('No active thought chains').classes('text-gray-400 text-sm')
            else:
                with thought_chains_container:
                    ui.label('Orchestrator not running').classes('text-gray-400 text-sm')
        except Exception as e:
            with thought_chains_container:
                ui.label(f'Error: {str(e)[:50]}').classes('text-red-400 text-sm')

        # Update goals (read from state file - cross-process safe)
        goals_container.clear()
        try:
            import json
            goals_file = PROJECT_ROOT / "state" / "consciousness" / "active_goals.json"
            goals = []

            def _read_goals():
                if goals_file.exists():
                    return json.loads(goals_file.read_text())
                return None

            data = await asyncio.to_thread(_read_goals)
            if data:
                goals = data.get("goals", [])
                file_age = time.time() - data.get("timestamp", 0)
                if file_age > 30:
                    goals = []  # Stale data

            if goals:
                with goals_container:
                    for goal in goals[:5]:
                        name = goal.get("name", str(goal)[:30])
                        source = goal.get("source", "unknown")
                        with ui.row().classes('gap-2 items-center'):
                            ui.icon('flag').classes('text-green-400 text-xs')
                            ui.label(name).classes('text-sm')
                            if source:
                                ui.label(f'[{source}]').classes('text-xs text-gray-500')
            else:
                with goals_container:
                    ui.label('No active goals').classes('text-gray-400 text-sm')
        except Exception as e:
            with goals_container:
                ui.label(f'Error: {str(e)[:50]}').classes('text-red-400 text-sm')

        # Update working memory (read from state file - cross-process safe)
        memory_container.clear()
        try:
            import json
            memory_file = PROJECT_ROOT / "state" / "consciousness" / "working_memory.json"
            reflective = 0
            reasoning = 0

            def _read_memory():
                if memory_file.exists():
                    return json.loads(memory_file.read_text())
                return None

            data = await asyncio.to_thread(_read_memory)
            if data:
                reflective = data.get("reflective_count", 0)
                reasoning = data.get("reasoning_count", 0)
                file_age = time.time() - data.get("timestamp", 0)
                if file_age > 30:
                    reflective = 0
                    reasoning = 0

            with memory_container:
                ui.label(f'Reflective Loop: {reflective} tracers').classes('text-sm')
                ui.label(f'Reasoning Loop: {reasoning} tracers').classes('text-sm')
                is_thinking = reasoning > 0
                status = "THINKING" if is_thinking else "IDLE"
                color = "text-green-400" if is_thinking else "text-gray-400"
                ui.label(f'Status: {status}').classes(f'{color} font-bold')
        except Exception as e:
            with memory_container:
                ui.label(f'Error: {str(e)[:50]}').classes('text-red-400 text-sm')

        # Update attention
        attention_container.clear()
        try:
            def _get_attention_status():
                from fairies.P30_Cognition.cognition.attention_controller import get_attention_controller
                controller = get_attention_controller()
                return controller.get_status() if controller else {}

            status = await asyncio.to_thread(_get_attention_status)
            with attention_container:
                mode = status.get("mode", "unknown")
                paused = status.get("motor_paused", False)
                focus = status.get("focus", {}).get("content", "")[:50]

                color = "text-yellow-400" if paused else "text-green-400"
                ui.label(f'Mode: {mode}').classes('text-sm font-bold')
                ui.label(f'Motor: {"PAUSED" if paused else "RUNNING"}').classes(f'{color} text-sm')
                if focus:
                    ui.label(f'Focus: {focus}...').classes('text-sm text-gray-300')
        except Exception as e:
            with attention_container:
                ui.label(f'Error: {str(e)[:50]}').classes('text-red-400 text-sm')

        # Update annotations
        annotations_container.clear()
        annotations = await asyncio.to_thread(load_code_annotations)
        if annotations:
            with annotations_container:
                for annot in annotations[-5:]:  # Last 5
                    with ui.row().classes('gap-2 items-center bg-gray-800 rounded p-2'):
                        ui.icon('code').classes('text-orange-400 text-xs')
                        ui.label(f'{annot.get("file", "?")}:{annot.get("line", "?")}').classes('text-sm font-mono')
                        if annot.get("note"):
                            ui.label(f'"{annot["note"]}"').classes('text-sm text-gray-400 italic')
        else:
            with annotations_container:
                ui.label('No code pointers yet. Claude can use point_to_code() to highlight lines.').classes('text-gray-400 text-sm')

    # Refresh timer
    ui.timer(2.0, refresh_data)  # Refresh every 2 seconds


# ════════════════════════════════════════════════════════════════════════════
# ERROR TELEMETRY - System errors, fairy deaths, crashes
# ════════════════════════════════════════════════════════════════════════════

# Global error buffer for telemetry page
_error_buffer = []
_error_buffer_max = 200

def _add_error_event(event: dict):
    """Add error event to buffer (called from postal subscription)."""
    global _error_buffer
    _error_buffer.append(event)
    if len(_error_buffer) > _error_buffer_max:
        _error_buffer = _error_buffer[-_error_buffer_max:]

def _setup_error_subscription():
    """Subscribe to telemetry.error channel."""
    try:
        system = get_system()
        if system and system.postal:
            def on_error(payload):
                event = {
                    "ts": payload.get("ts", time.time()),
                    "type": payload.get("type", "unknown"),
                    "fairy": payload.get("fairy", ""),
                    "plane": payload.get("plane", ""),
                    "message": payload.get("message", ""),
                    "restart_count": payload.get("restart_count", 0),
                    "raw": payload,
                }
                _add_error_event(event)
            system.postal.subscribe("telemetry.error", on_error)
            print("[Dashboard] Subscribed to telemetry.error")
            return True
    except Exception as e:
        print(f"[Dashboard] Failed to subscribe to telemetry.error: {e}")
    return False

# Try to set up subscription on module load
_error_sub_initialized = False

@ui.page('/tools/telemetry')
def telemetry_page():
    """
    Error telemetry page - scrollable list of system errors.

    Shows:
    - Fairy deaths with restart attempts
    - System errors
    - Crash tracebacks (when available)
    """
    global _error_sub_initialized

    ui.add_head_html(CUSTOM_CSS)
    create_header()
    create_nav_tabs('tools')

    # Initialize subscription if not done
    if not _error_sub_initialized:
        _setup_error_subscription()
        _error_sub_initialized = True

    with ui.column().classes('w-full max-w-6xl mx-auto p-8 gap-4'):
        ui.label('Error Telemetry').classes('text-2xl font-bold')
        ui.label('Real-time fairy deaths, crashes, and system errors').classes('text-gray-400')

        # Stats row
        with ui.row().classes('gap-4'):
            error_count_label = ui.label('0 errors').classes('text-xl')
            fairy_death_count = ui.label('0 fairy deaths').classes('text-xl text-red-400')
            clear_btn = ui.button('Clear', on_click=lambda: clear_errors()).classes('ml-auto')

        # Error list container
        with ui.card().classes('w-full p-4 bg-gray-900'):
            ui.label('Recent Errors').classes('font-bold mb-2')
            error_container = ui.column().classes('w-full max-h-96 overflow-y-auto gap-2')

        # Dead fairies section
        with ui.card().classes('w-full p-4 bg-gray-900 mt-4'):
            ui.label('Dead Fairies (from Directory)').classes('font-bold mb-2')
            dead_fairy_container = ui.column().classes('w-full gap-2')

    def clear_errors():
        global _error_buffer
        _error_buffer = []
        refresh_display()

    def refresh_display():
        # Update counts
        total = len(_error_buffer)
        deaths = sum(1 for e in _error_buffer if e.get("type") == "fairy_death")
        error_count_label.set_text(f'{total} errors')
        fairy_death_count.set_text(f'{deaths} fairy deaths')

        # Update error list
        error_container.clear()
        with error_container:
            if not _error_buffer:
                ui.label('No errors recorded yet').classes('text-gray-500 italic')
            else:
                # Show newest first
                for event in reversed(_error_buffer[-50:]):
                    ts = event.get("ts", 0)
                    time_str = time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "??:??:??"
                    etype = event.get("type", "unknown")
                    fairy = event.get("fairy", "")
                    plane = event.get("plane", "")
                    msg = event.get("message", "")
                    restart = event.get("restart_count", 0)

                    # Color based on type
                    if etype == "fairy_death":
                        color = "bg-red-900/50 border-red-500"
                        icon = "skull"
                        text = f"DEATH: {fairy}"
                        if restart:
                            text += f" (restart attempt #{restart})"
                    else:
                        color = "bg-yellow-900/50 border-yellow-500"
                        icon = "warning"
                        text = msg or etype

                    with ui.row().classes(f'w-full p-2 rounded border {color} items-center gap-2'):
                        ui.icon(icon).classes('text-lg')
                        ui.label(time_str).classes('text-xs text-gray-400 font-mono')
                        if plane:
                            ui.label(f'[{plane}]').classes('text-xs text-blue-400')
                        ui.label(text).classes('flex-grow')

        # Update dead fairies from directory
        dead_fairy_container.clear()
        with dead_fairy_container:
            try:
                system = get_system()
                if system and hasattr(system, 'directory') and system.directory:
                    dead_list = system.directory.dead_fairies(threshold_seconds=60)
                    if dead_list:
                        for fairy_info in dead_list:
                            name = fairy_info.get("name", "Unknown")
                            plane = fairy_info.get("plane", "")
                            last_hb = fairy_info.get("last_heartbeat", 0)
                            age = time.time() - last_hb if last_hb else 0
                            age_str = f"{int(age)}s ago" if age < 300 else f"{int(age/60)}m ago"

                            with ui.row().classes('w-full p-2 rounded bg-red-900/30 border border-red-700 items-center gap-2'):
                                ui.icon('heart_broken').classes('text-red-500')
                                ui.label(name).classes('font-bold')
                                ui.label(f'[{plane}]').classes('text-xs text-blue-400')
                                ui.label(f'Last heartbeat: {age_str}').classes('text-sm text-gray-400 ml-auto')
                    else:
                        ui.label('All fairies alive').classes('text-green-400')
                else:
                    ui.label('Directory not available').classes('text-gray-500 italic')
            except Exception as e:
                ui.label(f'Error checking dead fairies: {e}').classes('text-red-400')

    # Initial display
    refresh_display()

    # Auto-refresh every 2 seconds
    ui.timer(2.0, refresh_display)


# ════════════════════════════════════════════════════════════════════════════
# CHARACTER SHEET - Gaming-style skill/achievement tracking
# ════════════════════════════════════════════════════════════════════════════

@ui.page('/tools/character')
def character_sheet_page():
    """
    Character sheet page - like an RPG stat screen.

    Shows:
    - Fairy level and title
    - Skills by category with XP bars
    - Achievements (unlocked/locked)
    - Leaderboard
    """

    # Dark theme
    ui.query('body').style('background-color: #0a0a0f')

    with ui.column().classes('w-full max-w-6xl mx-auto p-4'):
        # Header
        with ui.row().classes('w-full items-center justify-between mb-6'):
            ui.label('CHARACTER SHEET').classes('text-3xl font-bold text-purple-400')
            with ui.row().classes('gap-2'):
                ui.button('Back to Tools', on_click=lambda: ui.navigate.to('/tools')).classes(
                    'bg-gray-700 hover:bg-gray-600')
                fairy_select = ui.select(
                    ['ClaudeFairy', 'UnconsciousMindFairy', 'NousFairy'],
                    value='ClaudeFairy',
                    label='Fairy'
                ).classes('w-48')

        # Containers for dynamic content
        header_container = ui.column().classes('w-full mb-6')
        skills_container = ui.row().classes('w-full gap-4 mb-6 flex-wrap')
        achievements_container = ui.column().classes('w-full mb-6')

        def load_character_sheet(fairy_name: str) -> dict:
            """Load character sheet from skill system."""
            try:
                import sys
                from pathlib import Path
                sys.path.insert(0, str(Path(__file__).parent.parent.parent))
                from fairies.P30_Cognition.cognition.skill_system import get_skill_profile
                profile = get_skill_profile(fairy_name)
                return profile.get_character_sheet()
            except Exception as e:
                return {"error": str(e)}

        def create_xp_bar(xp: int, xp_to_next: int, level: int) -> None:
            """Create a visual XP progress bar."""
            percent = (xp / xp_to_next * 100) if xp_to_next > 0 else 0
            with ui.row().classes('w-full items-center gap-2'):
                ui.label(f'Lv.{level}').classes('text-xs text-gray-400 w-8')
                with ui.element('div').classes('flex-1 bg-gray-700 rounded h-2'):
                    ui.element('div').classes('bg-purple-500 h-full rounded').style(
                        f'width: {min(percent, 100)}%')
                ui.label(f'{xp}/{xp_to_next}').classes('text-xs text-gray-400 w-16')

        async def refresh_data():
            """Refresh character sheet data."""
            import asyncio
            fairy_name = fairy_select.value
            sheet = await asyncio.to_thread(load_character_sheet, fairy_name)

            if "error" in sheet:
                header_container.clear()
                with header_container:
                    ui.label(f'Error: {sheet["error"]}').classes('text-red-400')
                return

            # Update header
            header_container.clear()
            with header_container:
                with ui.card().classes('w-full bg-gray-900 border border-purple-500/30'):
                    with ui.row().classes('items-center gap-6 p-4'):
                        # Avatar/Level circle
                        with ui.element('div').classes(
                            'w-24 h-24 rounded-full bg-gradient-to-br from-purple-600 to-blue-600 '
                            'flex items-center justify-center'
                        ):
                            ui.label(str(sheet.get('level', 1))).classes(
                                'text-4xl font-bold text-white')

                        # Name and title
                        with ui.column().classes('flex-1'):
                            ui.label(fairy_name).classes('text-2xl font-bold text-white')
                            title = sheet.get('title', 'Apprentice')
                            ui.label(f'"{title}"').classes('text-lg text-purple-300 italic')
                            ui.label(f'Total XP: {sheet.get("total_xp", 0):,}').classes(
                                'text-sm text-gray-400')

                        # Achievement badge count
                        with ui.column().classes('items-center'):
                            ach = sheet.get('achievements', {})
                            ui.label(f'{ach.get("unlocked", 0)}/{ach.get("total", 0)}').classes(
                                'text-3xl font-bold text-yellow-400')
                            ui.label('Achievements').classes('text-sm text-gray-400')

                        # Available titles
                        titles = sheet.get('available_titles', [])
                        if titles:
                            with ui.column().classes('items-start'):
                                ui.label('Titles:').classes('text-sm text-gray-500')
                                for t in titles[:3]:
                                    ui.badge(t).classes('bg-purple-700')

            # Update skills by category
            skills_container.clear()
            with skills_container:
                skills_summary = sheet.get('skills_summary', {})
                for cat, data in skills_summary.items():
                    if data['trained'] > 0:  # Only show categories with trained skills
                        with ui.card().classes('bg-gray-900 p-4 w-64'):
                            ui.label(cat.upper()).classes('text-sm font-bold text-blue-400 mb-2')
                            ui.label(f'{data["trained"]}/{data["total"]} trained').classes(
                                'text-xs text-gray-500')
                            ui.label(f'Total levels: {data["total_levels"]}').classes(
                                'text-xs text-gray-500')

                            # Visual bar
                            percent = (data["trained"] / data["total"] * 100) if data["total"] > 0 else 0
                            with ui.element('div').classes('w-full bg-gray-700 rounded h-2 mt-2'):
                                ui.element('div').classes('bg-blue-500 h-full rounded').style(
                                    f'width: {percent}%')

                # Top skills section
                top_skills = sheet.get('top_skills', [])
                if top_skills:
                    with ui.card().classes('bg-gray-900 p-4 w-full'):
                        ui.label('TOP SKILLS').classes('text-sm font-bold text-green-400 mb-2')
                        with ui.column().classes('gap-2'):
                            for skill in top_skills:
                                with ui.row().classes('w-full items-center'):
                                    ui.label(skill['name']).classes('text-sm text-white w-40')
                                    create_xp_bar(
                                        skill.get('xp', 0),
                                        skill.get('xp_to_next', 100),
                                        skill.get('level', 0)
                                    )

            # Update achievements
            achievements_container.clear()
            with achievements_container:
                with ui.card().classes('w-full bg-gray-900 p-4'):
                    ui.label('ACHIEVEMENTS').classes('text-sm font-bold text-yellow-400 mb-4')

                    # Recent unlocks
                    recent = sheet.get('achievements', {}).get('recent', [])
                    if recent:
                        ui.label('Recently Unlocked:').classes('text-xs text-gray-500 mb-2')
                        with ui.row().classes('gap-2 flex-wrap mb-4'):
                            for ach in recent:
                                with ui.card().classes(
                                    'bg-gradient-to-br from-yellow-900/50 to-yellow-700/20 p-3'
                                ):
                                    ui.label(ach['name']).classes('text-sm font-bold text-yellow-300')
                                    ui.label(ach['description']).classes('text-xs text-gray-400')
                                    if ach.get('title'):
                                        ui.badge(f'Title: {ach["title"]}').classes('bg-purple-700 mt-1')

                    # Next achievements
                    next_ach = sheet.get('next_achievements', [])
                    if next_ach:
                        ui.label('In Progress:').classes('text-xs text-gray-500 mb-2')
                        with ui.row().classes('gap-2 flex-wrap'):
                            for ach in next_ach:
                                with ui.card().classes('bg-gray-800 p-3 opacity-70'):
                                    ui.label(ach['name']).classes('text-sm text-gray-300')
                                    ui.label(ach['description']).classes('text-xs text-gray-500')
                                    ui.label(f'Progress: {ach.get("progress", "?")}').classes(
                                        'text-xs text-blue-400')

        # Initial load and setup refresh
        ui.timer(0.1, refresh_data, once=True)  # Async initial load
        fairy_select.on_value_change(lambda _: ui.timer(0.1, refresh_data, once=True))
        ui.timer(5.0, refresh_data)  # Refresh every 5 seconds


# ════════════════════════════════════════════════════════════════════════════

# MAIN

# ════════════════════════════════════════════════════════════════════════════

def find_available_port(start_port: int = 8080, max_attempts: int = 10) -> int:

    """Find an available port starting from start_port."""

    import socket

    for port in range(start_port, start_port + max_attempts):

        try:

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:

                s.bind(('127.0.0.1', port))

                return port

        except OSError:

            continue

    return start_port  # Fall back to original


# ════════════════════════════════════════════════════════════════════════════
# FAIRY BROWSER - View all fairies organized by plane
# ════════════════════════════════════════════════════════════════════════════

# Plane metadata
PLANES_META = {
    "P00": {"name": "Autonomic", "color": "red", "icon": "favorite", "desc": "Reflexes, heartbeat, hardware"},
    "P10": {"name": "Memory", "color": "blue", "icon": "storage", "desc": "Storage, SRM, Akashic Records"},
    "P20": {"name": "Somatic", "color": "green", "icon": "healing", "desc": "Body, chemistry, circulation"},
    "P30": {"name": "Cognition", "color": "purple", "icon": "psychology", "desc": "Thinking, reasoning, goals"},
    "P40": {"name": "Sensory", "color": "orange", "icon": "visibility", "desc": "Perception, GUI, MCP"},
    "P50": {"name": "Persona", "color": "pink", "icon": "person", "desc": "Identity, avatars, expression"},
    "P60": {"name": "Executive", "color": "yellow", "icon": "star", "desc": "High-level control, consciousness"},
}


@ui.page('/tools/fairies')
def fairy_browser_page():
    """
    Fairy Browser - View all fairies organized by plane.

    Shows:
    - Plane tabs with fairy counts
    - Fairy cards with expandable character sheets
    - Live status if fairy is running
    - Skills and achievements
    """

    # Dark theme
    ui.query('body').style('background-color: #0a0a0f')

    # State
    selected_plane = {'value': 'all'}
    fairy_data_cache = {'data': None}

    def load_fairies() -> dict:
        """Load fairy data organized by plane."""
        try:
            from collections import defaultdict
            import glob
            from pathlib import Path

            project_root = Path(__file__).parent.parent.parent
            fairies_by_plane = defaultdict(list)

            # Scan each plane directory
            for plane_code in PLANES_META.keys():
                matches = list(project_root.glob(f"{plane_code}_*"))

                for plane_path in matches:
                    if not plane_path.is_dir():
                        continue

                    # Find Python files with fairy patterns
                    for py_file in plane_path.rglob("*.py"):
                        try:
                            # Skip backup/archive directories (only check path WITHIN the plane)
                            relative_path = str(py_file.relative_to(plane_path)).lower()
                            if any(skip in relative_path for skip in [
                                'backup', 'archive', 'patches', 'claude_office',
                                'sandbox', 'snapshots', '_before', '_fixed'
                            ]):
                                continue

                            content = py_file.read_text(encoding='utf-8', errors='ignore')
                            if 'ACTOR_NAME' in content and ('MyFairy' in content or 'MyOrganFairy' in content or 'Fairy' in content):
                                import re

                                # Extract actor name
                                match = re.search(r'ACTOR_NAME\s*=\s*["\']([^"\']+)["\']', content)
                                if not match:
                                    continue

                                actor_name = match.group(1)

                                # Skip test/mock/template fairies
                                if 'test' in actor_name.lower() or 'mock' in actor_name.lower():
                                    continue

                                # Skip template placeholders
                                if '{' in actor_name or 'generated_' in actor_name.lower():
                                    continue

                                # Skip base template fairies (they're not real fairies)
                                if actor_name in ('MyFairy', 'BaseFairy', 'organ.template.clone'):
                                    continue

                                fairy_info = {
                                    "name": actor_name,
                                    "plane": plane_code,
                                    "file": str(py_file.relative_to(project_root)),
                                }

                                # Extract purpose
                                purpose_match = re.search(r'PURPOSE\s*=\s*["\']([^"\']+)["\']', content)
                                if purpose_match:
                                    fairy_info["purpose"] = purpose_match.group(1)[:100]
                                else:
                                    # Try multiline
                                    purpose_match = re.search(r'PURPOSE\s*=\s*"""([^"]+)"""', content, re.DOTALL)
                                    if purpose_match:
                                        fairy_info["purpose"] = purpose_match.group(1).strip()[:100]

                                # Extract channel
                                channel_match = re.search(r'ACTOR_CHANNEL\s*=\s*["\']([^"\']+)["\']', content)
                                if channel_match:
                                    fairy_info["channel"] = channel_match.group(1)

                                # Extract version
                                version_match = re.search(r'ACTOR_VERSION\s*=\s*["\']([^"\']+)["\']', content)
                                if version_match:
                                    fairy_info["version"] = version_match.group(1)

                                fairies_by_plane[plane_code].append(fairy_info)
                        except Exception:
                            pass

            # De-duplicate by name within each plane
            for plane in fairies_by_plane:
                seen = set()
                unique = []
                for f in fairies_by_plane[plane]:
                    if f['name'] not in seen:
                        seen.add(f['name'])
                        unique.append(f)
                fairies_by_plane[plane] = sorted(unique, key=lambda x: x['name'])

            return dict(fairies_by_plane)

        except Exception as e:
            return {"error": str(e)}

    def get_live_fairy_status(fairy_name: str) -> dict:
        """Check if fairy is running and get status."""
        try:
            from fairies.P10_Memory.Akashic_Records_Physical.Organ_Templates.Organ_Template_0_1_0 import _CITIZEN_OBJECTS
            if fairy_name in _CITIZEN_OBJECTS:
                fairy = _CITIZEN_OBJECTS[fairy_name]
                return {
                    "running": True,
                    "health": getattr(fairy, '_health_status', 'unknown'),
                }
        except Exception:
            pass
        return {"running": False}

    def get_fairy_skills(fairy_name: str) -> dict:
        """Get fairy skill profile."""
        try:
            from fairies.P30_Cognition.cognition.skill_system import get_skill_profile
            profile = get_skill_profile(fairy_name)
            return profile.get_character_sheet()
        except Exception:
            return {}

    with ui.column().classes('w-full max-w-7xl mx-auto p-4'):
        # Header
        with ui.row().classes('w-full items-center justify-between mb-6'):
            ui.label('FAIRY BROWSER').classes('text-3xl font-bold text-blue-400')
            with ui.row().classes('gap-2'):
                ui.button('Back to Tools', on_click=lambda: ui.navigate.to('/tools')).classes(
                    'bg-gray-700 hover:bg-gray-600')
                refresh_btn = ui.button('Refresh', icon='refresh').classes(
                    'bg-blue-600 hover:bg-blue-500')

        # Plane tabs
        plane_tabs = ui.column().classes('w-full mb-6')

        # Main content area
        content_area = ui.column().classes('w-full')

        def create_fairy_card(fairy: dict, plane_meta: dict):
            """Create a card for a single fairy."""
            live_status = get_live_fairy_status(fairy['name'])

            with ui.card().classes('bg-gray-900 border border-gray-700 hover:border-gray-500 transition-colors'):
                with ui.expansion(
                    fairy['name'],
                    icon=plane_meta['icon']
                ).classes('w-full'):
                    # Summary row visible when collapsed
                    with ui.row().classes('items-center gap-2'):
                        # Status indicator
                        if live_status['running']:
                            ui.badge('LIVE', color='green').classes('text-xs')
                        else:
                            ui.badge('OFFLINE', color='gray').classes('text-xs')

                        # Channel
                        if fairy.get('channel'):
                            ui.badge(fairy['channel'], color='blue').classes('text-xs')

                    # Expanded content
                    with ui.column().classes('w-full mt-4 gap-2'):
                        # Purpose
                        if fairy.get('purpose'):
                            ui.label(fairy['purpose']).classes('text-sm text-gray-400 italic')

                        # File location
                        ui.label(f'File: {fairy.get("file", "Unknown")}').classes('text-xs text-gray-500 font-mono')

                        # Version
                        if fairy.get('version'):
                            ui.label(f'v{fairy["version"]}').classes('text-xs text-gray-500')

                        # Live status details
                        if live_status['running']:
                            with ui.row().classes('gap-2 mt-2'):
                                ui.label('Health:').classes('text-xs text-gray-400')
                                health = live_status.get('health', 'unknown')
                                color = 'green' if health in ['healthy', 'ok', 'good'] else 'yellow'
                                ui.badge(health, color=color).classes('text-xs')

                        # Skills button
                        async def show_skills(name=fairy['name']):
                            skills = get_fairy_skills(name)
                            if skills:
                                with ui.dialog() as dialog, ui.card().classes('w-96 bg-gray-800'):
                                    ui.label(f'{name} Skills').classes('text-xl font-bold text-purple-400')
                                    ui.label(f'Level {skills.get("level", 1)} - "{skills.get("title", "Apprentice")}"').classes('text-sm text-gray-400')
                                    ui.label(f'Total XP: {skills.get("total_xp", 0):,}').classes('text-xs text-gray-500')

                                    top_skills = skills.get('top_skills', [])
                                    if top_skills:
                                        ui.label('Top Skills:').classes('text-sm text-gray-400 mt-2')
                                        for skill in top_skills[:5]:
                                            ui.label(f'• {skill["name"]}: Lv.{skill.get("level", 0)}').classes('text-xs text-gray-500')

                                    ui.button('Close', on_click=dialog.close).classes('mt-4')
                                dialog.open()

                        ui.button('View Skills', on_click=show_skills, icon='sports_esports').classes(
                            'text-xs mt-2').props('flat dense')

        def refresh_display():
            """Refresh the fairy display."""
            # Load data
            if fairy_data_cache['data'] is None:
                fairy_data_cache['data'] = load_fairies()

            data = fairy_data_cache['data']

            if 'error' in data:
                content_area.clear()
                with content_area:
                    ui.label(f'Error: {data["error"]}').classes('text-red-400')
                return

            # Update plane tabs
            plane_tabs.clear()
            with plane_tabs:
                with ui.row().classes('w-full gap-2 flex-wrap'):
                    # All planes button
                    total_count = sum(len(fairies) for fairies in data.values())
                    all_classes = 'bg-gray-700' if selected_plane['value'] != 'all' else 'bg-blue-600'
                    ui.button(f'All ({total_count})', on_click=lambda: select_plane('all')).classes(all_classes)

                    # Individual plane buttons
                    for plane_code, meta in PLANES_META.items():
                        count = len(data.get(plane_code, []))
                        if count > 0:
                            is_selected = selected_plane['value'] == plane_code
                            btn_class = f'bg-{meta["color"]}-600' if is_selected else 'bg-gray-700'
                            ui.button(
                                f'{meta["name"]} ({count})',
                                icon=meta['icon'],
                                on_click=lambda p=plane_code: select_plane(p)
                            ).classes(btn_class + ' hover:opacity-80')

            # Update content area
            content_area.clear()
            with content_area:
                planes_to_show = [selected_plane['value']] if selected_plane['value'] != 'all' else list(PLANES_META.keys())

                for plane_code in planes_to_show:
                    fairies = data.get(plane_code, [])
                    if not fairies:
                        continue

                    meta = PLANES_META.get(plane_code, {"name": "Unknown", "color": "gray", "icon": "help", "desc": ""})

                    # Plane section
                    with ui.card().classes(f'w-full bg-gray-800/50 border-l-4 border-{meta["color"]}-500 mb-4'):
                        with ui.row().classes('items-center gap-2 mb-2'):
                            ui.icon(meta['icon']).classes(f'text-{meta["color"]}-400')
                            ui.label(f'{plane_code}: {meta["name"]}').classes(f'text-xl font-bold text-{meta["color"]}-400')
                            ui.badge(f'{len(fairies)} fairies').classes('text-xs')

                        ui.label(meta['desc']).classes('text-sm text-gray-500 mb-4')

                        # Fairy grid
                        with ui.row().classes('w-full gap-4 flex-wrap'):
                            for fairy in fairies:
                                with ui.element('div').classes('w-80'):
                                    create_fairy_card(fairy, meta)

        def select_plane(plane: str):
            """Select a plane to view."""
            selected_plane['value'] = plane
            refresh_display()

        def do_refresh():
            """Force refresh data."""
            fairy_data_cache['data'] = None
            refresh_display()

        refresh_btn.on('click', do_refresh)

        # Initial load
        refresh_display()


# ==============================================================================
# COGNITIVE API ROUTES - For hooks and external access
# ==============================================================================

def _setup_cognitive_api():
    """Setup cognitive API endpoints for hooks to access cognitive fairies."""
    from starlette.responses import JSONResponse
    import json

    try:
        from fairies.P40_Sensory.web.cognitive_api import handle_cognitive_api
        api_available = True
    except ImportError:
        api_available = False
        print("[WebDashboard] Cognitive API module not found - endpoints disabled")

    @app.get('/api/cognitive/{action}')
    async def cognitive_get(action: str, request):
        """Handle GET requests to cognitive API."""
        if not api_available:
            return JSONResponse({"error": "Cognitive API not available"}, status_code=503)

        # Convert query params to dict
        params = dict(request.query_params)

        try:
            result = handle_cognitive_api(action, params)
            return JSONResponse(result)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.post('/api/cognitive/{action}')
    async def cognitive_post(action: str, request):
        """Handle POST requests to cognitive API."""
        if not api_available:
            return JSONResponse({"error": "Cognitive API not available"}, status_code=503)

        try:
            body = await request.body()
            params = json.loads(body) if body else {}
        except:
            params = {}

        try:
            result = handle_cognitive_api(action, params)
            return JSONResponse(result)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    @app.get('/api/health')
    async def api_health():
        """Health check for API."""
        return JSONResponse({
            "status": "ok",
            "cognitive_api": api_available,
            "system_running": system.get_status().get("running", False)
        })

    print("[WebDashboard] Cognitive API routes registered at /api/cognitive/*")

# Register cognitive API routes
_setup_cognitive_api()


def run_server(host: str = '0.0.0.0', port: int = 8080, reload: bool = False):

    """Run the Akashic Foundation server."""

    # Check if port is available, find alternate if not

    import socket

    try:

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:

            s.bind(('127.0.0.1', port))

    except OSError:

        old_port = port

        port = find_available_port(port + 1)

        print(f"[WebDashboard] Port {old_port} in use, using {port} instead")

    print(f"""

    ╔══════════════════════════════════════════════════════════════╗

    ║          AKASHIC FOUNDATION - Web Portal                    ║

    ║                                                              ║

    ║   Local:   http://localhost:{port}                           ║

    ║   Network: http://0.0.0.0:{port}                             ║

    ║                                                              ║

    ║   Ready for akashicfoundation.com                           ║

    ╚══════════════════════════════════════════════════════════════╝

    """)

    # Try to connect to postal system for fairy messages

    # This is optional - dashboard works without it

    if system.get_status()["running"]:

        print("[WebDashboard] Main system running, connecting postal listeners...")

        setup_postal_listeners()

    else:
        print("[WebDashboard] Main system not running - will auto-boot after server starts")

        # AUTO-BOOT: Use app.on_startup to boot AFTER uvicorn is ready
        @app.on_startup
        async def auto_boot_system():
            import asyncio
            await asyncio.sleep(1)  # Let server fully initialize
            print("[WebDashboard] Auto-booting server...")
            # CRITICAL: Run blocking boot in thread pool to not block event loop
            boot_result = await asyncio.to_thread(system.boot)
            if boot_result.get('success'):
                print(f"[WebDashboard] [OK] Auto-boot successful: {boot_result.get('message', '')}")
                await asyncio.sleep(2)  # Wait for fairy system
                setup_postal_listeners()
            else:
                print(f"[WebDashboard] [FAIL] Auto-boot failed: {boot_result.get('message', 'Unknown error')}")

    # Mount static files for gallery images
    media_images_dir = PROJECT_ROOT / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "system" / "media" / "images"
    if media_images_dir.exists():
        app.add_static_files('/gallery-images', str(media_images_dir))
        print(f"[WebDashboard] Mounted gallery images from {media_images_dir}")

    # Also mount legacy visual cards images
    legacy_images_dir = PROJECT_ROOT / "P10_Memory" / "SRM_Clusters" / "media" / "images"
    if legacy_images_dir.exists():
        app.add_static_files('/legacy-images', str(legacy_images_dir))
        print(f"[WebDashboard] Mounted legacy images from {legacy_images_dir}")

    # Fix for uvicorn logging when stdout is redirected by the server
    import sys
    if not hasattr(sys.stdout, 'isatty'):
        sys.stdout.isatty = lambda: False
    if not hasattr(sys.stderr, 'isatty'):
        sys.stderr.isatty = lambda: False

    ui.run(
        host=host,
        port=port,
        title=SITE_TITLE,
        favicon='',
        reload=reload,
        dark=True,

        show=True  # Auto-open browser

    )

if __name__ in {"__main__", "__mp_main__"}:
    run_server()


# ════════════════════════════════════════════════════════════════════════════
# EMBEDDED MODE LAUNCHER - For running dashboard inside the server
# ════════════════════════════════════════════════════════════════════════════

_embedded_thread = None

def start_embedded_dashboard(port: int = 8080, open_browser: bool = True) -> threading.Thread:
    """
    Start the dashboard as an embedded thread inside the server.

    This is THE correct way to run the dashboard when you want:
    - Single process (no subprocess spawning)
    - Shared singletons with the server
    - Direct postal hub access

    Call this from server.py after setting AKASHIC_EMBEDDED_DASHBOARD=1

    Args:
        port: Port to run on (default 8080)
        open_browser: Whether to auto-open browser

    Returns:
        The thread running the dashboard
    """
    global _embedded_thread

    import threading

    # Set embedded mode environment variable
    os.environ["AKASHIC_EMBEDDED_DASHBOARD"] = "1"
    global _EMBEDDED_DASHBOARD
    _EMBEDDED_DASHBOARD = True

    def run_dashboard():
        print(f"[Dashboard] Starting EMBEDDED dashboard on port {port}...")
        try:
            # Override show parameter based on open_browser
            ui.run(
                host="0.0.0.0",
                port=port,
                title=SITE_TITLE,
                favicon='',
                reload=False,  # No hot reload in embedded mode
                dark=True,
                show=open_browser
            )
        except Exception as e:
            print(f"[Dashboard] Error: {e}")

    _embedded_thread = threading.Thread(
        target=run_dashboard,
        name="EmbeddedDashboard",
        daemon=True
    )
    _embedded_thread.start()

    print(f"[Dashboard] [OK] Embedded dashboard thread started on port {port}")
    return _embedded_thread


def is_dashboard_running() -> bool:
    """Check if embedded dashboard is running."""
    global _embedded_thread
    return _embedded_thread is not None and _embedded_thread.is_alive()
