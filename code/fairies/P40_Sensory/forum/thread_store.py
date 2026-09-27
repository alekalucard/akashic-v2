# ════════════════════════════════════════════════════════════════════════════════
# THREAD STORE - Persistence layer for forum threads and posts
# ════════════════════════════════════════════════════════════════════════════════

import os
import json
import time
import hashlib
from typing import Dict, List, Optional, Any
from pathlib import Path
from threading import Lock


class ThreadStore:
    """
    Persistent storage for forum threads, posts, and subscriptions.
    
    File structure:
        state/forum/
            boards/{board_name}/index.json   # Thread list per board
            threads/{thread_id}.json          # Full thread with posts
            subscriptions.json                # Who watches what
            profiles.json                     # User/fairy profiles
    """
    
    # Default boards
    BOARDS = [
        "system-evolution",   # Proposals for system improvements
        "consciousness",      # Discussions about consciousness mechanics
        "debugging",          # Help with issues
        "observations",       # Things fairies notice
        "research",           # Deep dives into topics
        "general",            # Anything else
        "announcements",      # System-wide (admin only)
    ]
    
    def __init__(self, base_path: str = None):
        if base_path is None:
            # Find project root
            current = Path(__file__).resolve()
            for parent in current.parents:
                if (parent / "server.py").exists() or (parent / "ebookmain.py").exists():
                    base_path = str(parent / "state" / "forum")
                    break
            else:
                base_path = "state/forum"
        
        self.base_path = Path(base_path)
        self.boards_path = self.base_path / "boards"
        self.threads_path = self.base_path / "threads"
        self.subscriptions_file = self.base_path / "subscriptions.json"
        self.profiles_file = self.base_path / "profiles.json"
        
        self._lock = Lock()
        self._ensure_structure()
    
    def _ensure_structure(self):
        """Create directory structure if needed."""
        self.boards_path.mkdir(parents=True, exist_ok=True)
        self.threads_path.mkdir(parents=True, exist_ok=True)
        
        # Create board directories
        for board in self.BOARDS:
            board_dir = self.boards_path / board
            board_dir.mkdir(exist_ok=True)
            
            # Create index if missing
            index_file = board_dir / "index.json"
            if not index_file.exists():
                self._write_json(index_file, {"threads": [], "updated_at": time.time()})
        
        # Create subscriptions file if missing
        if not self.subscriptions_file.exists():
            self._write_json(self.subscriptions_file, {"subscriptions": {}})
        
        # Create profiles file if missing
        if not self.profiles_file.exists():
            self._write_json(self.profiles_file, {"profiles": {}})
    
    # ═══════════════════════════════════════════════════════════════════════
    # THREAD OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    def create_thread(self, board: str, title: str, content: str,
                      author: str, author_type: str = "fairy",
                      tags: List[str] = None) -> Dict[str, Any]:
        """
        Create a new thread.
        
        Args:
            board: Board name (must be valid)
            title: Thread title
            content: First post content
            author: Who created it
            author_type: "fairy" or "human"
            tags: Optional tags
            
        Returns:
            Thread dict with id
        """
        if board not in self.BOARDS:
            raise ValueError(f"Invalid board: {board}. Valid: {self.BOARDS}")
        
        now = time.time()
        thread_id = self._generate_id("thread")
        post_id = self._generate_id("post")
        
        # Create thread
        thread = {
            "id": thread_id,
            "board": board,
            "title": title,
            "author": author,
            "author_type": author_type,
            "created_at": now,
            "updated_at": now,
            "post_count": 1,
            "subscribers": [author],  # Author auto-subscribed
            "pinned": False,
            "locked": False,
            "tags": tags or [],
            "posts": [
                {
                    "id": post_id,
                    "thread_id": thread_id,
                    "author": author,
                    "author_type": author_type,
                    "content": content,
                    "created_at": now,
                    "reply_to": None,
                    "reactions": {}
                }
            ]
        }
        
        with self._lock:
            # Save thread file
            thread_file = self.threads_path / f"{thread_id}.json"
            self._write_json(thread_file, thread)
            
            # Update board index
            self._add_to_board_index(board, thread)
            
            # Auto-subscribe author
            self._add_subscription(author, thread_id)
        
        return thread
    
    def get_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get a thread by ID."""
        thread_file = self.threads_path / f"{thread_id}.json"
        if thread_file.exists():
            return self._read_json(thread_file)
        return None
    
    def add_post(self, thread_id: str, content: str, author: str,
                 author_type: str = "fairy", reply_to: str = None) -> Optional[Dict[str, Any]]:
        """
        Add a post to a thread.
        
        Returns:
            The new post dict, or None if thread not found/locked
        """
        with self._lock:
            thread = self.get_thread(thread_id)
            if not thread:
                return None
            
            if thread.get("locked"):
                return None
            
            now = time.time()
            post_id = self._generate_id("post")
            
            post = {
                "id": post_id,
                "thread_id": thread_id,
                "author": author,
                "author_type": author_type,
                "content": content,
                "created_at": now,
                "reply_to": reply_to,
                "reactions": {}
            }
            
            # Add post to thread
            thread["posts"].append(post)
            thread["post_count"] = len(thread["posts"])
            thread["updated_at"] = now
            
            # Auto-subscribe author if not already
            if author not in thread["subscribers"]:
                thread["subscribers"].append(author)
                self._add_subscription(author, thread_id)
            
            # Save thread
            thread_file = self.threads_path / f"{thread_id}.json"
            self._write_json(thread_file, thread)
            
            # Update board index
            self._update_board_index(thread["board"], thread)
            
            return post
    
    def get_posts(self, thread_id: str) -> List[Dict[str, Any]]:
        """Get all posts in a thread."""
        thread = self.get_thread(thread_id)
        if thread:
            return thread.get("posts", [])
        return []
    
    # ═══════════════════════════════════════════════════════════════════════
    # BOARD OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_board_threads(self, board: str, limit: int = 50, 
                          offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get threads for a board, sorted by most recent activity.
        
        Returns thread summaries (without full posts).
        """
        if board not in self.BOARDS:
            return []
        
        index_file = self.boards_path / board / "index.json"
        if not index_file.exists():
            return []
        
        index = self._read_json(index_file)
        threads = index.get("threads", [])
        
        # Sort by updated_at descending (most recent first)
        # Pinned threads always at top
        threads.sort(key=lambda t: (not t.get("pinned", False), -t.get("updated_at", 0)))
        
        return threads[offset:offset + limit]
    
    def get_all_boards_summary(self) -> List[Dict[str, Any]]:
        """Get summary of all boards with thread counts."""
        summaries = []
        for board in self.BOARDS:
            index_file = self.boards_path / board / "index.json"
            thread_count = 0
            latest_activity = 0
            
            if index_file.exists():
                index = self._read_json(index_file)
                threads = index.get("threads", [])
                thread_count = len(threads)
                if threads:
                    latest_activity = max(t.get("updated_at", 0) for t in threads)
            
            summaries.append({
                "name": board,
                "thread_count": thread_count,
                "latest_activity": latest_activity
            })
        
        return summaries
    
    def _add_to_board_index(self, board: str, thread: Dict[str, Any]):
        """Add a thread summary to board index."""
        index_file = self.boards_path / board / "index.json"
        index = self._read_json(index_file) if index_file.exists() else {"threads": []}
        
        # Thread summary (without posts)
        summary = {
            "id": thread["id"],
            "title": thread["title"],
            "author": thread["author"],
            "author_type": thread["author_type"],
            "created_at": thread["created_at"],
            "updated_at": thread["updated_at"],
            "post_count": thread["post_count"],
            "pinned": thread.get("pinned", False),
            "locked": thread.get("locked", False),
            "tags": thread.get("tags", [])
        }
        
        index["threads"].append(summary)
        index["updated_at"] = time.time()
        self._write_json(index_file, index)
    
    def _update_board_index(self, board: str, thread: Dict[str, Any]):
        """Update thread summary in board index."""
        index_file = self.boards_path / board / "index.json"
        if not index_file.exists():
            return
        
        index = self._read_json(index_file)
        
        for i, t in enumerate(index.get("threads", [])):
            if t["id"] == thread["id"]:
                index["threads"][i] = {
                    "id": thread["id"],
                    "title": thread["title"],
                    "author": thread["author"],
                    "author_type": thread["author_type"],
                    "created_at": thread["created_at"],
                    "updated_at": thread["updated_at"],
                    "post_count": thread["post_count"],
                    "pinned": thread.get("pinned", False),
                    "locked": thread.get("locked", False),
                    "tags": thread.get("tags", [])
                }
                break
        
        index["updated_at"] = time.time()
        self._write_json(index_file, index)
    
    # ═══════════════════════════════════════════════════════════════════════
    # SUBSCRIPTION OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════
    
    def subscribe(self, actor: str, thread_id: str) -> bool:
        """Subscribe an actor to a thread."""
        with self._lock:
            # Update thread's subscriber list
            thread = self.get_thread(thread_id)
            if not thread:
                return False
            
            if actor not in thread["subscribers"]:
                thread["subscribers"].append(actor)
                thread_file = self.threads_path / f"{thread_id}.json"
                self._write_json(thread_file, thread)
            
            # Update subscriptions file
            self._add_subscription(actor, thread_id)
            return True
    
    def unsubscribe(self, actor: str, thread_id: str) -> bool:
        """Unsubscribe an actor from a thread."""
        with self._lock:
            # Update thread's subscriber list
            thread = self.get_thread(thread_id)
            if thread and actor in thread["subscribers"]:
                thread["subscribers"].remove(actor)
                thread_file = self.threads_path / f"{thread_id}.json"
                self._write_json(thread_file, thread)
            
            # Update subscriptions file
            self._remove_subscription(actor, thread_id)
            return True
    
    def get_subscriptions_for(self, actor: str) -> List[str]:
        """Get all thread IDs an actor is subscribed to."""
        subs = self._read_json(self.subscriptions_file)
        return subs.get("subscriptions", {}).get(actor, {}).get("threads", [])
    
    def get_subscribers(self, thread_id: str) -> List[str]:
        """Get all actors subscribed to a thread."""
        thread = self.get_thread(thread_id)
        if thread:
            return thread.get("subscribers", [])
        return []
    
    def _add_subscription(self, actor: str, thread_id: str):
        """Internal: add to subscriptions file."""
        subs = self._read_json(self.subscriptions_file)
        
        if actor not in subs["subscriptions"]:
            subs["subscriptions"][actor] = {
                "threads": [],
                "last_read": {},
                "unread_count": 0
            }
        
        if thread_id not in subs["subscriptions"][actor]["threads"]:
            subs["subscriptions"][actor]["threads"].append(thread_id)
        
        self._write_json(self.subscriptions_file, subs)
    
    def _remove_subscription(self, actor: str, thread_id: str):
        """Internal: remove from subscriptions file."""
        subs = self._read_json(self.subscriptions_file)
        
        if actor in subs["subscriptions"]:
            threads = subs["subscriptions"][actor].get("threads", [])
            if thread_id in threads:
                threads.remove(thread_id)
            subs["subscriptions"][actor]["threads"] = threads
        
        self._write_json(self.subscriptions_file, subs)
    
    # ═══════════════════════════════════════════════════════════════════════
    # READ TRACKING
    # ═══════════════════════════════════════════════════════════════════════
    
    def mark_thread_read(self, actor: str, thread_id: str, post_id: str = None):
        """Mark a thread as read up to a certain post."""
        with self._lock:
            subs = self._read_json(self.subscriptions_file)
            
            if actor not in subs["subscriptions"]:
                return
            
            # If no post_id, use the latest
            if not post_id:
                thread = self.get_thread(thread_id)
                if thread and thread["posts"]:
                    post_id = thread["posts"][-1]["id"]
            
            if post_id:
                subs["subscriptions"][actor]["last_read"][thread_id] = {
                    "post_id": post_id,
                    "read_at": time.time()
                }
            
            self._write_json(self.subscriptions_file, subs)
    
    def get_unread_for(self, actor: str) -> List[Dict[str, Any]]:
        """
        Get threads with unread posts for an actor.
        
        Returns list of {thread_id, thread_title, unread_count, latest_post}
        """
        subs = self._read_json(self.subscriptions_file)
        actor_subs = subs.get("subscriptions", {}).get(actor, {})
        
        threads = actor_subs.get("threads", [])
        last_read = actor_subs.get("last_read", {})
        
        unread = []
        for thread_id in threads:
            thread = self.get_thread(thread_id)
            if not thread:
                continue
            
            posts = thread.get("posts", [])
            if not posts:
                continue
            
            # Find unread count
            last_read_info = last_read.get(thread_id, {})
            last_read_post = last_read_info.get("post_id")
            
            if last_read_post:
                # Find index of last read post
                unread_posts = []
                found_last = False
                for post in posts:
                    if found_last:
                        unread_posts.append(post)
                    if post["id"] == last_read_post:
                        found_last = True
                
                if unread_posts:
                    unread.append({
                        "thread_id": thread_id,
                        "thread_title": thread["title"],
                        "board": thread["board"],
                        "unread_count": len(unread_posts),
                        "latest_post": unread_posts[-1]
                    })
            else:
                # Never read - all posts are unread (except if author)
                author_posts = [p for p in posts if p["author"] != actor]
                if author_posts:
                    unread.append({
                        "thread_id": thread_id,
                        "thread_title": thread["title"],
                        "board": thread["board"],
                        "unread_count": len(author_posts),
                        "latest_post": posts[-1]
                    })
        
        return unread
    
    # ═══════════════════════════════════════════════════════════════════════
    # SEARCH
    # ═══════════════════════════════════════════════════════════════════════
    
    def search_threads(self, query: str, board: str = None, 
                       limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search threads by title/content.
        
        Args:
            query: Search string
            board: Optional board filter
            limit: Max results
        """
        results = []
        query_lower = query.lower()
        
        boards_to_search = [board] if board else self.BOARDS
        
        for b in boards_to_search:
            if b not in self.BOARDS:
                continue
            
            threads = self.get_board_threads(b, limit=1000)
            for thread_summary in threads:
                # Check title
                if query_lower in thread_summary.get("title", "").lower():
                    results.append(thread_summary)
                    continue
                
                # Check tags
                tags = thread_summary.get("tags", [])
                if any(query_lower in tag.lower() for tag in tags):
                    results.append(thread_summary)
                    continue
                
                # Check post content (need full thread)
                full_thread = self.get_thread(thread_summary["id"])
                if full_thread:
                    for post in full_thread.get("posts", []):
                        if query_lower in post.get("content", "").lower():
                            results.append(thread_summary)
                            break
                
                if len(results) >= limit:
                    break
            
            if len(results) >= limit:
                break
        
        return results[:limit]
    
    # ═══════════════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════════════
    
    def _generate_id(self, prefix: str) -> str:
        """Generate a unique ID."""
        timestamp = str(time.time()).encode()
        random_bytes = os.urandom(8)
        hash_input = timestamp + random_bytes
        short_hash = hashlib.sha256(hash_input).hexdigest()[:12]
        return f"{prefix}_{short_hash}"
    
    def _read_json(self, path: Path) -> Dict[str, Any]:
        """Read JSON file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _write_json(self, path: Path, data: Dict[str, Any]):
        """Write JSON file."""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get forum statistics."""
        total_threads = 0
        total_posts = 0
        
        for board in self.BOARDS:
            threads = self.get_board_threads(board, limit=10000)
            total_threads += len(threads)
            
            for t in threads:
                total_posts += t.get("post_count", 0)
        
        return {
            "total_boards": len(self.BOARDS),
            "total_threads": total_threads,
            "total_posts": total_posts,
            "boards": self.get_all_boards_summary()
        }
