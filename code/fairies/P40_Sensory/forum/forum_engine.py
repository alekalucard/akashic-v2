# ════════════════════════════════════════════════════════════════════════════════
# FORUM ENGINE - Core logic for Akashic forum system
# ════════════════════════════════════════════════════════════════════════════════
#
# Provides the business logic layer between fairies/UI and thread storage.
# Handles postal integration for notifications.
#
# Usage:
#   engine = get_forum_engine()
#   thread = engine.create_thread("debugging", "Help with boot", "I'm seeing...")
#   engine.reply_to_thread(thread["id"], "Try checking the logs...")
#
# ════════════════════════════════════════════════════════════════════════════════

import time
from typing import Dict, List, Optional, Any, Callable
from threading import Lock

from .thread_store import ThreadStore


# Singleton instance
_forum_engine: Optional['ForumEngine'] = None
_engine_lock = Lock()


def get_forum_engine() -> 'ForumEngine':
    """Get or create the singleton ForumEngine instance."""
    global _forum_engine
    if _forum_engine is None:
        with _engine_lock:
            if _forum_engine is None:
                _forum_engine = ForumEngine()
    return _forum_engine


class ForumEngine:
    """
    Core forum engine - bridges between fairies/UI and storage.
    
    Responsibilities:
    - Thread/post CRUD operations
    - Notification dispatch via postal
    - Subscription management
    - Permission checks
    """
    
    def __init__(self):
        self.store = ThreadStore()
        self.post = None  # Postal hub - set during connect()
        self._notification_callbacks: Dict[str, Callable] = {}
        self._connected = False
        
    def connect(self, postal_hub=None):
        """
        Connect to postal system for notifications.
        
        Args:
            postal_hub: SharedPostalHub instance (or auto-detect)
        """
        if postal_hub:
            self.post = postal_hub
        else:
            try:
                from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
                self.post = get_shared_postal_hub()
            except Exception as e:
                print(f"[ForumEngine] Could not connect to postal: {e}")
                return False
        
        if self.post:
            # Subscribe to forum-related topics
            self.post.subscribe("forum.thread.new", self._on_thread_created)
            self.post.subscribe("forum.post.new", self._on_post_created)
            self._connected = True
            print("[ForumEngine] Connected to postal system")
            return True
        
        return False
    
    # ═══════════════════════════════════════════════════════════════════════
    # THREAD OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    def create_thread(self, board: str, title: str, content: str,
                      author: str, author_type: str = "fairy",
                      tags: List[str] = None) -> Dict[str, Any]:
        """
        Create a new thread.
        
        Args:
            board: Board name
            title: Thread title
            content: First post content
            author: Who's creating it
            author_type: "fairy" or "human"
            tags: Optional tags
            
        Returns:
            Created thread dict
        """
        thread = self.store.create_thread(
            board=board,
            title=title,
            content=content,
            author=author,
            author_type=author_type,
            tags=tags
        )
        
        # Notify via postal
        if self.post:
            self.post.route("forum.thread.new", {
                "thread_id": thread["id"],
                "board": board,
                "title": title,
                "author": author,
                "author_type": author_type,
                "created_at": thread["created_at"]
            })
        
        return thread
    
    def reply_to_thread(self, thread_id: str, content: str,
                        author: str, author_type: str = "fairy",
                        reply_to: str = None) -> Optional[Dict[str, Any]]:
        """
        Add a reply to a thread.
        
        Args:
            thread_id: Thread to reply to
            content: Reply content
            author: Who's replying
            author_type: "fairy" or "human"
            reply_to: Optional post ID this is replying to
            
        Returns:
            Created post dict, or None if failed
        """
        post = self.store.add_post(
            thread_id=thread_id,
            content=content,
            author=author,
            author_type=author_type,
            reply_to=reply_to
        )
        
        if post:
            # Get thread info for notification
            thread = self.store.get_thread(thread_id)
            
            # Notify subscribers
            if self.post and thread:
                # Notify all subscribers except author
                subscribers = thread.get("subscribers", [])
                for subscriber in subscribers:
                    if subscriber != author:
                        self._notify_subscriber(
                            subscriber=subscriber,
                            thread=thread,
                            post=post,
                            notification_type="reply"
                        )
                
                # Broadcast new post event
                self.post.route("forum.post.new", {
                    "post_id": post["id"],
                    "thread_id": thread_id,
                    "thread_title": thread["title"],
                    "board": thread["board"],
                    "author": author,
                    "author_type": author_type,
                    "content_preview": content[:100] + "..." if len(content) > 100 else content,
                    "created_at": post["created_at"]
                })
        
        return post
    
    def get_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get a thread by ID with all posts."""
        return self.store.get_thread(thread_id)
    
    def get_thread_posts(self, thread_id: str) -> List[Dict[str, Any]]:
        """Get all posts in a thread."""
        return self.store.get_posts(thread_id)
    
    # ═══════════════════════════════════════════════════════════════════════
    # BOARD OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_boards(self) -> List[Dict[str, Any]]:
        """Get all boards with summaries."""
        return self.store.get_all_boards_summary()
    
    def get_board_threads(self, board: str, limit: int = 50,
                          offset: int = 0) -> List[Dict[str, Any]]:
        """Get threads in a board."""
        return self.store.get_board_threads(board, limit, offset)
    
    @property
    def board_names(self) -> List[str]:
        """Get list of valid board names."""
        return ThreadStore.BOARDS
    
    # ═══════════════════════════════════════════════════════════════════════
    # SUBSCRIPTION OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    def subscribe(self, actor: str, thread_id: str) -> bool:
        """Subscribe to a thread."""
        return self.store.subscribe(actor, thread_id)
    
    def unsubscribe(self, actor: str, thread_id: str) -> bool:
        """Unsubscribe from a thread."""
        return self.store.unsubscribe(actor, thread_id)
    
    def get_subscriptions(self, actor: str) -> List[str]:
        """Get all thread IDs an actor is subscribed to."""
        return self.store.get_subscriptions_for(actor)
    
    def get_unread(self, actor: str) -> List[Dict[str, Any]]:
        """Get threads with unread posts for an actor."""
        return self.store.get_unread_for(actor)
    
    def mark_read(self, actor: str, thread_id: str, post_id: str = None):
        """Mark a thread as read up to a certain post."""
        self.store.mark_thread_read(actor, thread_id, post_id)
    
    # ═══════════════════════════════════════════════════════════════════════
    # NOTIFICATION SYSTEM
    # ═══════════════════════════════════════════════════════════════════════
    
    def register_notification_callback(self, actor: str, callback: Callable):
        """
        Register a callback for when an actor gets a notification.
        
        Args:
            actor: Fairy name or "Ace"
            callback: Function(notification_dict) to call
        """
        self._notification_callbacks[actor] = callback
    
    def _notify_subscriber(self, subscriber: str, thread: Dict[str, Any],
                           post: Dict[str, Any], notification_type: str):
        """Send notification to a subscriber."""
        notification = {
            "type": notification_type,
            "thread_id": thread["id"],
            "thread_title": thread["title"],
            "board": thread["board"],
            "post_id": post["id"],
            "author": post["author"],
            "author_type": post["author_type"],
            "content_preview": post["content"][:200],
            "timestamp": time.time()
        }
        
        # Try callback first
        if subscriber in self._notification_callbacks:
            try:
                self._notification_callbacks[subscriber](notification)
            except Exception as e:
                print(f"[ForumEngine] Notification callback error for {subscriber}: {e}")
        
        # Also send via postal for distributed systems
        if self.post:
            self.post.route(f"forum.notify.{subscriber.lower()}", notification)
            
            # Also send to inbox for persistence
            self.post.route("ace.inbox" if subscriber.lower() == "ace" else "nous.inbox", {
                "type": "forum_notification",
                "from": "ForumEngine",
                "subject": f"New reply in: {thread['title']}",
                "body": f"{post['author']} replied:\n\n{post['content'][:300]}...",
                "priority": "normal",
                "timestamp": time.time(),
                "metadata": {
                    "thread_id": thread["id"],
                    "post_id": post["id"],
                    "board": thread["board"]
                }
            })
    
    def _on_thread_created(self, msg: dict):
        """Handle thread creation event."""
        print(f"[ForumEngine] New thread: {msg.get('title')} by {msg.get('author')}")
    
    def _on_post_created(self, msg: dict):
        """Handle post creation event."""
        print(f"[ForumEngine] New post in '{msg.get('thread_title')}' by {msg.get('author')}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # SEARCH
    # ═══════════════════════════════════════════════════════════════════════
    
    def search(self, query: str, board: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Search threads by title/content."""
        return self.store.search_threads(query, board, limit)
    
    # ═══════════════════════════════════════════════════════════════════════
    # MODERATION
    # ═══════════════════════════════════════════════════════════════════════
    
    def pin_thread(self, thread_id: str) -> bool:
        """Pin a thread to top of board."""
        thread = self.store.get_thread(thread_id)
        if thread:
            thread["pinned"] = True
            self.store._write_json(
                self.store.threads_path / f"{thread_id}.json",
                thread
            )
            self.store._update_board_index(thread["board"], thread)
            return True
        return False
    
    def unpin_thread(self, thread_id: str) -> bool:
        """Unpin a thread."""
        thread = self.store.get_thread(thread_id)
        if thread:
            thread["pinned"] = False
            self.store._write_json(
                self.store.threads_path / f"{thread_id}.json",
                thread
            )
            self.store._update_board_index(thread["board"], thread)
            return True
        return False
    
    def lock_thread(self, thread_id: str) -> bool:
        """Lock a thread (no more replies)."""
        thread = self.store.get_thread(thread_id)
        if thread:
            thread["locked"] = True
            self.store._write_json(
                self.store.threads_path / f"{thread_id}.json",
                thread
            )
            self.store._update_board_index(thread["board"], thread)
            return True
        return False
    
    def unlock_thread(self, thread_id: str) -> bool:
        """Unlock a thread."""
        thread = self.store.get_thread(thread_id)
        if thread:
            thread["locked"] = False
            self.store._write_json(
                self.store.threads_path / f"{thread_id}.json",
                thread
            )
            self.store._update_board_index(thread["board"], thread)
            return True
        return False
    
    # ═══════════════════════════════════════════════════════════════════════
    # REACTIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    def add_reaction(self, thread_id: str, post_id: str, 
                     actor: str, reaction: str) -> bool:
        """
        Add a reaction to a post.
        
        Reactions: agree, disagree, thinking, funny, insightful
        """
        thread = self.store.get_thread(thread_id)
        if not thread:
            return False
        
        for post in thread.get("posts", []):
            if post["id"] == post_id:
                reactions = post.get("reactions", {})
                if reaction not in reactions:
                    reactions[reaction] = []
                if actor not in reactions[reaction]:
                    reactions[reaction].append(actor)
                post["reactions"] = reactions
                
                self.store._write_json(
                    self.store.threads_path / f"{thread_id}.json",
                    thread
                )
                return True
        
        return False
    
    def remove_reaction(self, thread_id: str, post_id: str,
                        actor: str, reaction: str) -> bool:
        """Remove a reaction from a post."""
        thread = self.store.get_thread(thread_id)
        if not thread:
            return False
        
        for post in thread.get("posts", []):
            if post["id"] == post_id:
                reactions = post.get("reactions", {})
                if reaction in reactions and actor in reactions[reaction]:
                    reactions[reaction].remove(actor)
                    post["reactions"] = reactions
                    
                    self.store._write_json(
                        self.store.threads_path / f"{thread_id}.json",
                        thread
                    )
                    return True
        
        return False
    
    # ═══════════════════════════════════════════════════════════════════════
    # STATS
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_stats(self) -> Dict[str, Any]:
        """Get forum statistics."""
        stats = self.store.get_stats()
        stats["connected"] = self._connected
        return stats
