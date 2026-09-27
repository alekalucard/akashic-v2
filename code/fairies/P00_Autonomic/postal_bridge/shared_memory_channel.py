# ════════════════════════════════════════════════════════════════════════════════
# SHARED MEMORY CHANNEL - Zero-copy state sharing
# ════════════════════════════════════════════════════════════════════════════════
#
# Unlike sockets or SQLite, shared memory provides:
# - Sub-millisecond reads (direct memory access)
# - No IPC overhead for reading
# - State always available (no connection needed)
#
# The server writes current state to shared memory periodically.
# MCP reads state directly without any network round-trip.
#
# Uses Python 3.8+ multiprocessing.shared_memory which works on Windows.
#
# ════════════════════════════════════════════════════════════════════════════════

import json
import time
import struct
import threading
from typing import Optional, Dict, Any
from pathlib import Path

# Try to use shared_memory, fall back to file-based if not available
try:
    from multiprocessing.shared_memory import SharedMemory
    HAS_SHARED_MEMORY = True
except ImportError:
    HAS_SHARED_MEMORY = False
    print("[SharedMemoryChannel] multiprocessing.shared_memory not available, using file fallback")


# Shared memory name
MEMORY_NAME = "akashic_state"
MEMORY_SIZE = 1024 * 64  # 64KB for state JSON

# Fallback file location
STATE_FILE = Path.home() / ".akashic" / "state.json"

# Singleton
_shared_memory: Optional['SharedMemoryChannel'] = None
_memory_lock = threading.Lock()


def get_shared_memory() -> 'SharedMemoryChannel':
    """Get or create the singleton shared memory channel."""
    global _shared_memory
    if _shared_memory is None:
        with _memory_lock:
            if _shared_memory is None:
                _shared_memory = SharedMemoryChannel()
    return _shared_memory


class SharedMemoryChannel:
    """
    Shared memory state channel for ultra-fast reads.
    
    State Structure (in shared memory):
    - Bytes 0-3: Length of JSON (uint32)
    - Bytes 4-7: Timestamp (float32 seconds since epoch, truncated)
    - Bytes 8+: JSON state data
    
    Falls back to file-based state if shared_memory unavailable.
    """
    
    def __init__(self, name: str = MEMORY_NAME, size: int = MEMORY_SIZE):
        self.name = name
        self.size = size
        self._shm: Optional[SharedMemory] = None
        self._is_owner = False
        self._lock = threading.Lock()
        
        # Cache for read performance
        self._cache: Dict[str, Any] = {}
        self._cache_time: float = 0
        self._cache_ttl: float = 0.1  # 100ms cache validity
        
        # Statistics
        self._read_count = 0
        self._write_count = 0
        self._cache_hits = 0
        self._error_count = 0
        
        # Ensure state directory exists for fallback
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    def create(self) -> bool:
        """
        Create the shared memory block (called by server).
        
        Returns True if created successfully.
        """
        if not HAS_SHARED_MEMORY:
            return True  # Fall back to file-based
        
        with self._lock:
            try:
                # Try to create new shared memory
                self._shm = SharedMemory(name=self.name, create=True, size=self.size)
                self._is_owner = True
                
                # Initialize with empty state
                self._write_to_memory({})
                
                print(f"[SharedMemoryChannel] Created shared memory: {self.name} ({self.size} bytes)")
                return True
                
            except FileExistsError:
                # Already exists, attach to it
                try:
                    self._shm = SharedMemory(name=self.name, create=False)
                    self._is_owner = False
                    print(f"[SharedMemoryChannel] Attached to existing: {self.name}")
                    return True
                except Exception as e:
                    print(f"[SharedMemoryChannel] Attach failed: {e}")
                    return False
                    
            except Exception as e:
                print(f"[SharedMemoryChannel] Create failed: {e}")
                return False
    
    def attach(self) -> bool:
        """
        Attach to existing shared memory (called by MCP).
        
        Returns True if attached successfully.
        """
        if not HAS_SHARED_MEMORY:
            return True  # Fall back to file-based
        
        with self._lock:
            if self._shm is not None:
                return True  # Already attached
            
            try:
                self._shm = SharedMemory(name=self.name, create=False)
                self._is_owner = False
                print(f"[SharedMemoryChannel] Attached to: {self.name}")
                return True
                
            except FileNotFoundError:
                # Not created yet, will fall back to file
                return False
                
            except Exception as e:
                print(f"[SharedMemoryChannel] Attach failed: {e}")
                return False
    
    def _write_to_memory(self, state: Dict[str, Any]):
        """Write state to shared memory."""
        json_bytes = json.dumps(state, default=str).encode('utf-8')
        length = len(json_bytes)
        
        if length > self.size - 8:
            # State too large, truncate
            state_str = json.dumps(state, default=str)
            max_len = self.size - 8
            truncated = state_str[:max_len-20] + '..."truncated":true}'
            json_bytes = truncated.encode('utf-8')
            length = len(json_bytes)
        
        # Pack: length (4 bytes) + timestamp (4 bytes) + JSON
        timestamp = int(time.time()) & 0xFFFFFFFF  # Truncate to 32 bits
        header = struct.pack('<II', length, timestamp)
        
        # Write to shared memory
        self._shm.buf[:4] = header[:4]  # Length
        self._shm.buf[4:8] = header[4:8]  # Timestamp
        self._shm.buf[8:8+length] = json_bytes
    
    def _read_from_memory(self) -> Optional[Dict[str, Any]]:
        """Read state from shared memory."""
        try:
            # Read header
            length = struct.unpack('<I', bytes(self._shm.buf[:4]))[0]
            
            if length == 0 or length > self.size - 8:
                return None
            
            # Read JSON
            json_bytes = bytes(self._shm.buf[8:8+length])
            return json.loads(json_bytes.decode('utf-8'))
            
        except Exception as e:
            self._error_count += 1
            return None
    
    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC API - Write (server side)
    # ═══════════════════════════════════════════════════════════════════════
    
    def write_state(self, state: Dict[str, Any]):
        """
        Write current state to shared memory.
        
        Called periodically by the server to publish current state.
        """
        with self._lock:
            try:
                # Always write to file (fallback)
                self._write_to_file(state)
                
                # Write to shared memory if available
                if self._shm is not None:
                    self._write_to_memory(state)
                
                self._write_count += 1
                
            except Exception as e:
                self._error_count += 1
                print(f"[SharedMemoryChannel] Write error: {e}")
    
    def _write_to_file(self, state: Dict[str, Any]):
        """Write state to fallback file."""
        try:
            STATE_FILE.write_text(json.dumps(state, default=str, indent=2))
        except Exception:
            pass
    
    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC API - Read (MCP side)
    # ═══════════════════════════════════════════════════════════════════════
    
    def read_state(self, key: str = None) -> Optional[Any]:
        """
        Read state from shared memory (with caching).
        
        Args:
            key: Optional key to read specific value, or None for full state
            
        Returns:
            State dict or specific value, or None if unavailable
        """
        now = time.time()
        
        # Check cache first
        if now - self._cache_time < self._cache_ttl and self._cache:
            self._cache_hits += 1
            if key:
                return self._cache.get(key)
            return self._cache.copy()
        
        # Read from source
        state = None
        
        with self._lock:
            # Try shared memory first
            if self._shm is not None:
                state = self._read_from_memory()
            
            # Fall back to file
            if state is None:
                state = self._read_from_file()
        
        # Update cache
        if state:
            self._cache = state
            self._cache_time = now
            self._read_count += 1
            
            if key:
                return state.get(key)
            return state.copy()
        
        return None
    
    def _read_from_file(self) -> Optional[Dict[str, Any]]:
        """Read state from fallback file."""
        try:
            if STATE_FILE.exists():
                return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
        return None
    
    def read_heart_rate(self) -> Optional[float]:
        """Quick accessor for heart rate."""
        return self.read_state('heart_rate')
    
    def read_consciousness(self) -> Optional[Dict]:
        """Quick accessor for consciousness state."""
        return self.read_state('consciousness')
    
    def read_fairy_count(self) -> Optional[int]:
        """Quick accessor for active fairy count."""
        return self.read_state('fairies_active')
    
    # ═══════════════════════════════════════════════════════════════════════
    # CLEANUP
    # ═══════════════════════════════════════════════════════════════════════
    
    def close(self):
        """Close and optionally unlink shared memory."""
        with self._lock:
            if self._shm is not None:
                try:
                    self._shm.close()
                    if self._is_owner:
                        self._shm.unlink()
                except Exception:
                    pass
                self._shm = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get channel statistics."""
        return {
            'reads': self._read_count,
            'writes': self._write_count,
            'cache_hits': self._cache_hits,
            'errors': self._error_count,
            'memory_attached': self._shm is not None,
            'is_owner': self._is_owner,
            'using_shared_memory': HAS_SHARED_MEMORY,
        }


class StatePublisher:
    """
    Helper class that periodically publishes state to shared memory.
    
    Run this in the server to keep MCP's state view up to date.
    """
    
    def __init__(self, channel: SharedMemoryChannel = None, interval: float = 0.5):
        self.channel = channel or get_shared_memory()
        self.interval = interval
        self._running = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._state_provider: Optional[callable] = None
    
    def set_state_provider(self, provider: callable):
        """
        Set a function that returns current state dict.
        
        Called periodically to get latest state.
        """
        self._state_provider = provider
    
    def start(self):
        """Start publishing state periodically."""
        if not self.channel.create():
            print("[StatePublisher] Warning: Could not create shared memory")
        
        self._running.set()
        self._thread = threading.Thread(
            target=self._publish_loop,
            daemon=True,
            name="StatePublisher"
        )
        self._thread.start()
    
    def stop(self):
        """Stop publishing."""
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=2.0)
    
    def _publish_loop(self):
        """Background loop that publishes state."""
        while self._running.is_set():
            try:
                if self._state_provider:
                    state = self._state_provider()
                    if state:
                        self.channel.write_state(state)
            except Exception as e:
                print(f"[StatePublisher] Error: {e}")
            
            time.sleep(self.interval)
    
    def publish_now(self, state: Dict[str, Any] = None):
        """Publish state immediately (useful for important updates)."""
        if state is None and self._state_provider:
            state = self._state_provider()
        if state:
            self.channel.write_state(state)
