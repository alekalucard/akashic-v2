# ════════════════════════════════════════════════════════════════════════════════
# SQLITE CHANNEL - Bulletproof message queue
# ════════════════════════════════════════════════════════════════════════════════
#
# Unlike sockets, SQLite:
# - Never drops connections
# - Handles concurrent access automatically
# - Survives process crashes
# - Is cross-platform and in Python's stdlib
#
# This channel ALWAYS works. It's the foundation of the multi-channel bridge.
#
# ════════════════════════════════════════════════════════════════════════════════

import sqlite3
import json
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from contextlib import contextmanager


# Database location - user home for cross-process visibility
QUEUE_DB = Path.home() / ".akashic" / "postal_queue.db"

# Singleton
_sqlite_channel: Optional['SQLiteChannel'] = None
_channel_lock = threading.Lock()


def get_sqlite_channel() -> 'SQLiteChannel':
    """Get or create the singleton SQLite channel."""
    global _sqlite_channel
    if _sqlite_channel is None:
        with _channel_lock:
            if _sqlite_channel is None:
                _sqlite_channel = SQLiteChannel()
    return _sqlite_channel


@dataclass
class QueuedMessage:
    """A message in the queue."""
    id: int
    direction: str  # 'mcp_to_main' or 'main_to_mcp'
    topic: str
    payload: Dict[str, Any]
    created_at: float
    processed: bool = False


class SQLiteChannel:
    """
    SQLite-based message queue for cross-process communication.
    
    This is the PRIMARY channel - it NEVER fails.
    
    Features:
    - Atomic operations with transactions
    - Automatic retry on SQLITE_BUSY
    - Message ordering guaranteed
    - Persistent across restarts
    - Both processes can read/write simultaneously
    """
    
    def __init__(self, db_path: Path = None):
        self.db_path = db_path or QUEUE_DB
        self._local = threading.local()  # Thread-local connections
        self._poll_interval = 0.1  # 100ms between polls
        self._running = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None
        self._subscribers: Dict[str, List[Callable]] = {}
        self._subscriber_lock = threading.Lock()
        
        # Statistics
        self._sent_count = 0
        self._received_count = 0
        self._error_count = 0
        
        self._ensure_db()
    
    def _ensure_db(self):
        """Create database and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS postal_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    direction TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    processed INTEGER DEFAULT 0,
                    processed_at REAL DEFAULT NULL
                )
            """)
            
            # Index for efficient polling
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_queue_poll 
                ON postal_queue (direction, processed, id)
            """)
            
            # Response table for request/response pattern
            conn.execute("""
                CREATE TABLE IF NOT EXISTS postal_responses (
                    request_id TEXT PRIMARY KEY,
                    response TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get thread-local database connection with automatic retry."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,  # Wait up to 30s for locks
                isolation_level='IMMEDIATE',  # Avoid deadlocks
                check_same_thread=False
            )
            self._local.conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        
        yield self._local.conn
    
    # ═══════════════════════════════════════════════════════════════════════
    # SENDING MESSAGES
    # ═══════════════════════════════════════════════════════════════════════
    
    def send(self, direction: str, topic: str, payload: Dict[str, Any]) -> int:
        """
        Queue a message for delivery.
        
        Args:
            direction: 'mcp_to_main' or 'main_to_mcp'
            topic: Postal topic (e.g., 'ace.inbox')
            payload: Message payload (will be JSON serialized)
            
        Returns:
            Message ID
        """
        now = time.time()
        payload_json = json.dumps(payload, default=str)
        
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO postal_queue (direction, topic, payload, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (direction, topic, payload_json, now)
                )
                conn.commit()
                msg_id = cursor.lastrowid
                self._sent_count += 1
                
                # Touch signal file to wake up poller
                self._signal_new_message(direction)
                
                return msg_id
                
        except Exception as e:
            self._error_count += 1
            print(f"[SQLiteChannel] Send error: {e}")
            raise
    
    def send_to_main(self, topic: str, payload: Dict[str, Any]) -> int:
        """Send message from MCP to server."""
        return self.send('mcp_to_main', topic, payload)
    
    def send_to_mcp(self, topic: str, payload: Dict[str, Any]) -> int:
        """Send message from server to MCP."""
        return self.send('main_to_mcp', topic, payload)
    
    def _signal_new_message(self, direction: str):
        """Touch a signal file to wake up the poller."""
        signal_file = self.db_path.parent / f".signal_{direction}"
        try:
            signal_file.touch()
        except Exception:
            pass  # Best effort
    
    # ═══════════════════════════════════════════════════════════════════════
    # RECEIVING MESSAGES
    # ═══════════════════════════════════════════════════════════════════════
    
    def receive(self, direction: str, limit: int = 100) -> List[QueuedMessage]:
        """
        Fetch unprocessed messages for a direction.
        
        Args:
            direction: Which direction to poll
            limit: Max messages to fetch
            
        Returns:
            List of QueuedMessage objects (not yet marked processed)
        """
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT id, direction, topic, payload, created_at, processed
                    FROM postal_queue
                    WHERE direction = ? AND processed = 0
                    ORDER BY id
                    LIMIT ?
                    """,
                    (direction, limit)
                ).fetchall()
                
                messages = []
                for row in rows:
                    try:
                        payload = json.loads(row['payload'])
                    except json.JSONDecodeError:
                        payload = {'raw': row['payload']}
                    
                    messages.append(QueuedMessage(
                        id=row['id'],
                        direction=row['direction'],
                        topic=row['topic'],
                        payload=payload,
                        created_at=row['created_at'],
                        processed=bool(row['processed'])
                    ))
                
                return messages
                
        except Exception as e:
            self._error_count += 1
            print(f"[SQLiteChannel] Receive error: {e}")
            return []
    
    def mark_processed(self, message_ids: List[int]):
        """Mark messages as processed (consumed)."""
        if not message_ids:
            return
        
        now = time.time()
        try:
            with self._get_connection() as conn:
                placeholders = ','.join('?' * len(message_ids))
                conn.execute(
                    f"""
                    UPDATE postal_queue 
                    SET processed = 1, processed_at = ?
                    WHERE id IN ({placeholders})
                    """,
                    [now] + message_ids
                )
                conn.commit()
                self._received_count += len(message_ids)
                
        except Exception as e:
            self._error_count += 1
            print(f"[SQLiteChannel] Mark processed error: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # REQUEST/RESPONSE PATTERN
    # ═══════════════════════════════════════════════════════════════════════
    
    def request(self, direction: str, topic: str, payload: Dict[str, Any],
                timeout: float = 10.0) -> Optional[Dict[str, Any]]:
        """
        Send a request and wait for response.
        
        This is for synchronous queries that need a response.
        Uses a unique request_id to correlate response.
        
        Args:
            direction: Which direction to send
            topic: Postal topic
            payload: Request payload
            timeout: How long to wait for response
            
        Returns:
            Response payload, or None if timeout
        """
        import uuid
        request_id = str(uuid.uuid4())
        
        # Add request_id to payload
        payload_with_id = {**payload, '_request_id': request_id}
        
        # Send request
        self.send(direction, topic, payload_with_id)
        
        # Wait for response
        start = time.time()
        while time.time() - start < timeout:
            response = self._get_response(request_id)
            if response is not None:
                return response
            time.sleep(0.05)  # 50ms poll interval
        
        return None  # Timeout
    
    def respond(self, request_id: str, response: Dict[str, Any]):
        """
        Send a response to a request.
        
        Called by the receiver after processing a request with _request_id.
        """
        now = time.time()
        response_json = json.dumps(response, default=str)
        
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO postal_responses (request_id, response, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (request_id, response_json, now)
                )
                conn.commit()
        except Exception as e:
            print(f"[SQLiteChannel] Respond error: {e}")
    
    def _get_response(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Check if a response is available for a request."""
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT response FROM postal_responses WHERE request_id = ?",
                    (request_id,)
                ).fetchone()

                if row:
                    # Clean up response
                    conn.execute(
                        "DELETE FROM postal_responses WHERE request_id = ?",
                        (request_id,)
                    )
                    conn.commit()
                    return json.loads(row['response'])

        except Exception:
            pass

        return None

    # ═══════════════════════════════════════════════════════════════════════
    # HEARTBEAT / PING - Verify other side is actually alive
    # ═══════════════════════════════════════════════════════════════════════

    def ping(self, timeout: float = 2.0) -> bool:
        """
        Send a ping to the server and wait for pong.

        This VERIFIES the other side is actually running and processing
        messages, not just that files exist.

        Args:
            timeout: How long to wait for pong (default 2s)

        Returns:
            True if pong received, False if timeout/error
        """
        import uuid
        correlation_id = str(uuid.uuid4())

        # Send ping request via SQLite
        payload = {
            "_correlation_id": correlation_id,
            "_command": "ping",
            "_params": {"sent_at": time.time()}
        }

        try:
            self.send('mcp_to_main', 'bridge.request', payload)

            # Wait for response
            start = time.time()
            while time.time() - start < timeout:
                response = self._get_response(correlation_id)
                if response is not None:
                    # Got a pong!
                    if response.get("success") and response.get("result", {}).get("pong"):
                        return True
                    # Got response but not valid pong
                    return False
                time.sleep(0.05)  # 50ms poll

            # Timeout - server not responding
            return False

        except Exception as e:
            print(f"[SQLiteChannel] Ping error: {e}")
            return False

    def get_last_heartbeat(self) -> Optional[float]:
        """
        Check when the server last wrote a heartbeat.

        The bridge server writes heartbeats to shared memory.
        This reads the timestamp to detect staleness.

        Returns:
            Timestamp of last heartbeat, or None if unavailable
        """
        try:
            from .shared_memory_channel import get_shared_memory
            mem = get_shared_memory()
            state = mem.read_state()
            if state:
                return state.get("last_heartbeat")
        except Exception:
            pass
        return None

    def is_other_side_alive(self, max_stale_seconds: float = 5.0) -> bool:
        """
        Quick check if the server appears alive.

        First checks heartbeat timestamp (fast, no IPC).
        Falls back to ping if heartbeat is stale.

        Args:
            max_stale_seconds: How old heartbeat can be before we ping

        Returns:
            True if other side appears alive
        """
        # First check heartbeat (instant)
        last_hb = self.get_last_heartbeat()
        if last_hb and (time.time() - last_hb) < max_stale_seconds:
            return True

        # Heartbeat stale or missing - do actual ping
        return self.ping(timeout=1.5)

    # ═══════════════════════════════════════════════════════════════════════
    # SUBSCRIPTION / POLLING
    # ═══════════════════════════════════════════════════════════════════════
    
    def subscribe(self, topic: str, callback: Callable[[Dict], None]):
        """
        Subscribe to messages on a topic.
        
        Callback will be called when messages arrive.
        Requires start_polling() to be called.
        """
        with self._subscriber_lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(callback)
    
    def start_polling(self, direction: str):
        """
        Start background thread to poll for messages.
        
        Args:
            direction: Which direction to poll ('mcp_to_main' or 'main_to_mcp')
        """
        if self._poll_thread and self._poll_thread.is_alive():
            return
        
        self._running.set()
        self._poll_thread = threading.Thread(
            target=self._poll_loop,
            args=(direction,),
            daemon=True,
            name=f"SQLiteChannel-Poller-{direction}"
        )
        self._poll_thread.start()
    
    def stop_polling(self):
        """Stop the polling thread."""
        self._running.clear()
        if self._poll_thread:
            self._poll_thread.join(timeout=2.0)
    
    def _poll_loop(self, direction: str):
        """Background loop that polls for messages."""
        while self._running.is_set():
            try:
                messages = self.receive(direction, limit=50)
                
                if messages:
                    processed_ids = []
                    
                    for msg in messages:
                        # Check for request/response pattern
                        if '_request_id' in msg.payload:
                            # This is handled by the request() method
                            pass
                        
                        # Dispatch to subscribers
                        self._dispatch_message(msg)
                        processed_ids.append(msg.id)
                    
                    # Mark all as processed
                    if processed_ids:
                        self.mark_processed(processed_ids)
                
                # Wait before next poll
                # Use shorter interval if we found messages (likely more coming)
                interval = 0.02 if messages else self._poll_interval
                time.sleep(interval)
                
            except Exception as e:
                print(f"[SQLiteChannel] Poll error: {e}")
                time.sleep(1.0)  # Backoff on error
    
    def _dispatch_message(self, msg: QueuedMessage):
        """Dispatch message to subscribers."""
        with self._subscriber_lock:
            # Exact topic match
            if msg.topic in self._subscribers:
                for callback in self._subscribers[msg.topic]:
                    try:
                        callback(msg.payload)
                    except Exception as e:
                        print(f"[SQLiteChannel] Callback error for {msg.topic}: {e}")
            
            # Wildcard match (topic.*)
            for topic, callbacks in self._subscribers.items():
                if topic.endswith('.*'):
                    prefix = topic[:-2]
                    if msg.topic.startswith(prefix):
                        for callback in callbacks:
                            try:
                                callback(msg.payload)
                            except Exception as e:
                                print(f"[SQLiteChannel] Callback error for {topic}: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════
    # MAINTENANCE
    # ═══════════════════════════════════════════════════════════════════════
    
    def prune(self, max_age_hours: float = 24.0):
        """
        Remove old processed messages.
        
        Call this periodically to keep database small.
        """
        cutoff = time.time() - (max_age_hours * 3600)
        
        try:
            with self._get_connection() as conn:
                result = conn.execute(
                    """
                    DELETE FROM postal_queue 
                    WHERE processed = 1 AND processed_at < ?
                    """,
                    (cutoff,)
                )
                conn.commit()
                deleted = result.rowcount
                
                # Also clean old responses
                conn.execute(
                    "DELETE FROM postal_responses WHERE created_at < ?",
                    (cutoff,)
                )
                conn.commit()
                
                if deleted > 0:
                    print(f"[SQLiteChannel] Pruned {deleted} old messages")
                    
        except Exception as e:
            print(f"[SQLiteChannel] Prune error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get channel statistics."""
        pending_mcp = 0
        pending_main = 0
        
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT 
                        SUM(CASE WHEN direction = 'mcp_to_main' AND processed = 0 THEN 1 ELSE 0 END) as mcp,
                        SUM(CASE WHEN direction = 'main_to_mcp' AND processed = 0 THEN 1 ELSE 0 END) as main
                    FROM postal_queue
                    """
                ).fetchone()
                
                if row:
                    pending_mcp = row['mcp'] or 0
                    pending_main = row['main'] or 0
                    
        except Exception:
            pass
        
        return {
            'sent': self._sent_count,
            'received': self._received_count,
            'errors': self._error_count,
            'pending_to_main': pending_mcp,
            'pending_to_mcp': pending_main,
            'polling': self._running.is_set(),
            'subscribers': len(self._subscribers),
        }
    
    def close(self):
        """Close the channel."""
        self.stop_polling()
        if hasattr(self._local, 'conn') and self._local.conn:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None
