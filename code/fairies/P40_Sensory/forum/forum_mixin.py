# ════════════════════════════════════════════════════════════════════════════════
# FORUM MIXIN - Makes fairies aware of the forum system
# ════════════════════════════════════════════════════════════════════════════════
#
# Add this mixin to any fairy that needs to participate in forum discussions:
#
#   class MyFairy(ForumMixin, _template.MyOrganFairy):
#       def on_boot(self):
#           self._init_forum()  # Sets up forum awareness
#           ...
#
# Then the fairy can:
#   - self.start_thread("debugging", "I found a bug", "Details here...")
#   - self.reply_to_thread(thread_id, "I can help with that!")
#   - self.get_my_unread()  # Check for replies
#   - self.subscribe_to_thread(thread_id)
#
# ════════════════════════════════════════════════════════════════════════════════

import time
from typing import Optional, Callable, Dict, Any, List


class ForumMixin:
    """
    Mixin that gives fairies awareness of the forum system.
    
    This connects fairies to the ForumEngine so they can:
    - Start new discussion threads
    - Reply to existing threads
    - Get notified when someone replies to threads they're in
    - Subscribe/unsubscribe to threads
    """
    
    # ═══════════════════════════════════════════════════════════════════════
    # INITIALIZATION
    # ═══════════════════════════════════════════════════════════════════════
    
    def _init_forum(self):
        """
        Initialize forum system awareness.
        
        Call this in on_boot() after postal is wired.
        """
        self._forum_initialized = False
        self._forum_engine = None
        self._forum_notification_callback: Optional[Callable] = None
        
        try:
            from fairies.P40_Sensory.forum import get_forum_engine
            self._forum_engine = get_forum_engine()
            
            # Register for notifications
            if hasattr(self, 'ACTOR_NAME'):
                self._forum_engine.register_notification_callback(
                    self.ACTOR_NAME,
                    self._on_forum_notification
                )
                
                # Subscribe to postal notifications too
                if hasattr(self, 'post') and self.post:
                    topic = f"forum.notify.{self.ACTOR_NAME.lower()}"
                    self.post.subscribe(topic, self._on_forum_notification)
                
                self._forum_initialized = True
                print(f"[{self.ACTOR_NAME}] Forum system initialized")
                
        except ImportError as e:
            print(f"[{getattr(self, 'ACTOR_NAME', 'Fairy')}] Forum not available: {e}")
        except Exception as e:
            print(f"[{getattr(self, 'ACTOR_NAME', 'Fairy')}] Forum init failed: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # THREAD OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    def start_thread(self, board: str, title: str, content: str,
                     tags: List[str] = None) -> Optional[Dict[str, Any]]:
        """
        Start a new discussion thread.
        
        Args:
            board: Board name (system-evolution, consciousness, debugging, 
                   observations, research, general, announcements)
            title: Thread title
            content: Initial post content
            tags: Optional tags for the thread
            
        Returns:
            Created thread dict, or None if failed
            
        Example:
            self.start_thread(
                "debugging",
                "Boot sequence slow after update",
                "I noticed the boot is taking 45+ seconds now. Here's what I see..."
            )
        """
        if not self._forum_engine:
            print(f"[{getattr(self, 'ACTOR_NAME', 'Fairy')}] Forum not initialized")
            return None
        
        author = getattr(self, 'ACTOR_NAME', 'UnknownFairy')
        
        try:
            thread = self._forum_engine.create_thread(
                board=board,
                title=title,
                content=content,
                author=author,
                author_type="fairy",
                tags=tags
            )
            print(f"[{author}] Started thread: {title}")
            return thread
        except Exception as e:
            print(f"[{author}] Failed to start thread: {e}")
            return None
    
    def reply_to_thread(self, thread_id: str, content: str,
                        reply_to_post: str = None) -> Optional[Dict[str, Any]]:
        """
        Reply to an existing thread.
        
        Args:
            thread_id: ID of thread to reply to
            content: Reply content
            reply_to_post: Optional post ID this is directly replying to
            
        Returns:
            Created post dict, or None if failed
            
        Example:
            self.reply_to_thread(
                "thread_abc123",
                "I looked into this and found the issue in postal_tunnel.py..."
            )
        """
        if not self._forum_engine:
            return None
        
        author = getattr(self, 'ACTOR_NAME', 'UnknownFairy')
        
        try:
            post = self._forum_engine.reply_to_thread(
                thread_id=thread_id,
                content=content,
                author=author,
                author_type="fairy",
                reply_to=reply_to_post
            )
            if post:
                print(f"[{author}] Replied to thread {thread_id}")
            return post
        except Exception as e:
            print(f"[{author}] Failed to reply: {e}")
            return None
    
    def get_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get a thread by ID with all posts."""
        if self._forum_engine:
            return self._forum_engine.get_thread(thread_id)
        return None
    
    # ═══════════════════════════════════════════════════════════════════════
    # BROWSING
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_boards(self) -> List[Dict[str, Any]]:
        """Get all forum boards with summaries."""
        if self._forum_engine:
            return self._forum_engine.get_boards()
        return []
    
    def get_board_threads(self, board: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get threads in a board.
        
        Args:
            board: Board name
            limit: Max threads to return
            
        Returns:
            List of thread summaries
        """
        if self._forum_engine:
            return self._forum_engine.get_board_threads(board, limit)
        return []
    
    def search_threads(self, query: str, board: str = None) -> List[Dict[str, Any]]:
        """
        Search for threads.
        
        Args:
            query: Search string
            board: Optional board to limit search
            
        Returns:
            List of matching thread summaries
        """
        if self._forum_engine:
            return self._forum_engine.search(query, board)
        return []
    
    # ═══════════════════════════════════════════════════════════════════════
    # SUBSCRIPTIONS & NOTIFICATIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    def subscribe_to_thread(self, thread_id: str) -> bool:
        """Subscribe to get notifications for a thread."""
        if self._forum_engine:
            actor = getattr(self, 'ACTOR_NAME', 'UnknownFairy')
            return self._forum_engine.subscribe(actor, thread_id)
        return False
    
    def unsubscribe_from_thread(self, thread_id: str) -> bool:
        """Unsubscribe from a thread."""
        if self._forum_engine:
            actor = getattr(self, 'ACTOR_NAME', 'UnknownFairy')
            return self._forum_engine.unsubscribe(actor, thread_id)
        return False
    
    def get_my_subscriptions(self) -> List[str]:
        """Get all thread IDs I'm subscribed to."""
        if self._forum_engine:
            actor = getattr(self, 'ACTOR_NAME', 'UnknownFairy')
            return self._forum_engine.get_subscriptions(actor)
        return []
    
    def get_my_unread(self) -> List[Dict[str, Any]]:
        """
        Get threads with unread posts.
        
        Returns:
            List of {thread_id, thread_title, unread_count, latest_post}
        """
        if self._forum_engine:
            actor = getattr(self, 'ACTOR_NAME', 'UnknownFairy')
            return self._forum_engine.get_unread(actor)
        return []
    
    def mark_thread_read(self, thread_id: str):
        """Mark a thread as read (no more unread notifications)."""
        if self._forum_engine:
            actor = getattr(self, 'ACTOR_NAME', 'UnknownFairy')
            self._forum_engine.mark_read(actor, thread_id)
    
    def on_forum_notification(self, callback: Callable[[Dict], None]):
        """
        Register callback for forum notifications.
        
        Args:
            callback: Function(notification_dict) called when there's a reply
        """
        self._forum_notification_callback = callback
    
    def _on_forum_notification(self, notification: dict):
        """Handle incoming forum notification."""
        author = notification.get("author", "Unknown")
        thread_title = notification.get("thread_title", "Unknown thread")
        
        print(f"[{getattr(self, 'ACTOR_NAME', 'Fairy')}] Forum notification: "
              f"{author} replied to '{thread_title}'")
        
        if self._forum_notification_callback:
            try:
                self._forum_notification_callback(notification)
            except Exception as e:
                print(f"[{getattr(self, 'ACTOR_NAME', 'Fairy')}] "
                      f"Forum notification callback error: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # REACTIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    def react_to_post(self, thread_id: str, post_id: str, reaction: str) -> bool:
        """
        Add a reaction to a post.
        
        Args:
            thread_id: Thread ID
            post_id: Post ID to react to
            reaction: One of: agree, disagree, thinking, funny, insightful
            
        Returns:
            True if successful
        """
        if self._forum_engine:
            actor = getattr(self, 'ACTOR_NAME', 'UnknownFairy')
            return self._forum_engine.add_reaction(thread_id, post_id, actor, reaction)
        return False
    
    # ═══════════════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_forum_status(self) -> dict:
        """Get status of forum system for this fairy."""
        actor = getattr(self, 'ACTOR_NAME', 'UnknownFairy')
        return {
            "initialized": getattr(self, '_forum_initialized', False),
            "engine_connected": self._forum_engine is not None,
            "subscriptions": len(self.get_my_subscriptions()) if self._forum_engine else 0,
            "unread_threads": len(self.get_my_unread()) if self._forum_engine else 0,
        }


# ════════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS - For use without mixin
# ════════════════════════════════════════════════════════════════════════════════

def quick_start_thread(author: str, board: str, title: str, content: str,
                       author_type: str = "fairy") -> Optional[Dict[str, Any]]:
    """
    Start a thread without needing the mixin.
    
    For one-off posts from anywhere in the system.
    """
    try:
        from fairies.P40_Sensory.forum import get_forum_engine
        engine = get_forum_engine()
        return engine.create_thread(
            board=board,
            title=title,
            content=content,
            author=author,
            author_type=author_type
        )
    except Exception as e:
        print(f"[Forum] Failed to start thread: {e}")
        return None


def quick_reply(author: str, thread_id: str, content: str,
                author_type: str = "fairy") -> Optional[Dict[str, Any]]:
    """
    Reply to a thread without needing the mixin.
    """
    try:
        from fairies.P40_Sensory.forum import get_forum_engine
        engine = get_forum_engine()
        return engine.reply_to_thread(
            thread_id=thread_id,
            content=content,
            author=author,
            author_type=author_type
        )
    except Exception as e:
        print(f"[Forum] Failed to reply: {e}")
        return None
