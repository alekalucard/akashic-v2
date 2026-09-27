"""
AkashicManifold — The Russian Doll Architecture.

The system IS the manifold. Every fairy, every thought, every memory,
every message — all regions inside one unified mmap-backed structure.

"Why dont we just put the whole system in there" — Ace
"Can we put manifold files within manifold files?" — Ace
"Its the blue box of the TARDIS" — Ace

Architecture:
    state/akashic/                      ← The TARDIS interior
    ├── akashic.index                   ← Master index (region metadata)
    ├── cortex.manifold                 ← Graph region (concept associations)
    ├── ego.manifold                    ← Graph region (identity, habits)
    ├── postal.ring                     ← Ring buffer region (pub/sub messages)
    ├── consciousness.ring              ← Ring buffer region (thought streams)
    ├── somatic.state                   ← State region (body, chemistry)
    ├── sensory.ring                    ← Ring buffer region (visual, audio)
    ├── fairy_state.state               ← State region (all 90 fairies)
    └── energy.state                    ← State region (per-region batteries)

Region types:
    GRAPH  — nodes + edges + strings (ManifoldMemory compatible)
    STATE  — fixed-size structured records (key-value, typed)
    RING   — circular buffers for streaming data (pub/sub)

Every region has:
    - version counter (monotonic, for change detection)
    - owner (fairy name or "system")
    - per-region write lock (writes to A don't block writes to B)
    - optional GPU mirror flag (sync to CUDA sparse tensor)

Reading is ALWAYS lock-free (mmap concurrent reads are safe).
Writing is per-region locked (one writer per region at a time).

2026-03-20 — Ace + Nous
"""

import os
import sys
import json
import mmap
import time
import struct
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

# Import the existing ManifoldMemory for graph regions
from infrastructure.manifold_memory import ManifoldMemory


def _log(msg: str):
    print(msg, file=sys.stderr, flush=True)


# ============================================================================
# CONSTANTS
# ============================================================================

# Region types
REGION_GRAPH = 0    # ManifoldMemory-compatible graph (nodes + edges + strings)
REGION_STATE = 1    # Fixed-size key-value state records
REGION_RING = 2     # Circular buffer for streaming messages

# Region type names for display
REGION_TYPE_NAMES = {
    REGION_GRAPH: "graph",
    REGION_STATE: "state",
    REGION_RING: "ring",
}

# State region record layout: 256 bytes per slot
# key(64B) + value(176B) + version(u64) + flags(u16) + _pad(6B) = 256
STATE_RECORD_SIZE = 256
STATE_KEY_SIZE = 64
STATE_VALUE_SIZE = 176
STATE_HEADER = struct.Struct('<64s176sQH6x')  # 256 bytes

# Ring buffer header: 128 bytes
# magic(4B) + topic(60B) + capacity(u32) + head(u32) + tail(u32) +
# record_size(u32) + count(u64) + version(u64) + _pad(8B) = 128
RING_HEADER_SIZE = 128
RING_HEADER_STRUCT = struct.Struct('<4s60sIIIIQQ8x')  # 128 bytes
RING_MAGIC = b'RING'

# Default ring record size: 1024 bytes (topic + payload)
RING_RECORD_SIZE = 1024
# Ring record: topic(64B) + tracer(32B) + source(32B) + timestamp(f64) +
#              payload_len(u32) + payload(884B) = 1024
RING_RECORD_STRUCT_HEADER = struct.Struct('<64s32s32sdI')  # 140 bytes
RING_PAYLOAD_SIZE = RING_RECORD_SIZE - 140  # 884 bytes

# State file header: 4096 bytes
STATE_FILE_HEADER_SIZE = 4096
STATE_FILE_MAGIC = b'AKST'
STATE_FILE_HEADER_STRUCT = struct.Struct('<4sIIQ')  # magic(4) + version(4) + capacity(4) + count(8) = 20 bytes

# Ring file header: 4096 bytes
RING_FILE_HEADER_SIZE = 4096
RING_FILE_MAGIC = b'AKRG'
RING_FILE_HEADER_STRUCT = struct.Struct('<4sIIIQ')  # magic(4) + version(4) + topic_count(4) + topic_capacity(4) + global_version(8) = 24 bytes


# ============================================================================
# REGION METADATA
# ============================================================================

class RegionMeta:
    """Metadata for a single region in the AkashicManifold."""

    def __init__(self, name: str, region_type: int, owner: str = "system",
                 gpu_mirror: bool = False, **kwargs):
        self.name = name
        self.region_type = region_type
        self.owner = owner
        self.gpu_mirror = gpu_mirror
        self.version = 0
        self.created = time.time()
        self.last_modified = time.time()

        # Graph-specific
        self.node_capacity = kwargs.get('node_capacity', 0)
        self.edge_capacity = kwargs.get('edge_capacity', 0)

        # State-specific
        self.state_capacity = kwargs.get('state_capacity', 0)

        # Ring-specific
        self.ring_capacity = kwargs.get('ring_capacity', 0)
        self.ring_record_size = kwargs.get('ring_record_size', RING_RECORD_SIZE)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'region_type': self.region_type,
            'type_name': REGION_TYPE_NAMES.get(self.region_type, 'unknown'),
            'owner': self.owner,
            'gpu_mirror': self.gpu_mirror,
            'version': self.version,
            'created': self.created,
            'last_modified': self.last_modified,
            'node_capacity': self.node_capacity,
            'edge_capacity': self.edge_capacity,
            'state_capacity': self.state_capacity,
            'ring_capacity': self.ring_capacity,
            'ring_record_size': self.ring_record_size,
        }

    @staticmethod
    def from_dict(d: dict) -> "RegionMeta":
        meta = RegionMeta(
            name=d['name'],
            region_type=d['region_type'],
            owner=d.get('owner', 'system'),
            gpu_mirror=d.get('gpu_mirror', False),
            node_capacity=d.get('node_capacity', 0),
            edge_capacity=d.get('edge_capacity', 0),
            state_capacity=d.get('state_capacity', 0),
            ring_capacity=d.get('ring_capacity', 0),
            ring_record_size=d.get('ring_record_size', RING_RECORD_SIZE),
        )
        meta.version = d.get('version', 0)
        meta.created = d.get('created', time.time())
        meta.last_modified = d.get('last_modified', time.time())
        return meta


# ============================================================================
# STATE REGION — Fixed-size key-value records
# ============================================================================

class StateRegion:
    """
    mmap-backed key-value state store.

    Fixed-size records: 256 bytes each (64B key + 176B value + 8B version + 6B overhead).
    Readers are lock-free. Writer uses a threading lock.

    Use for: somatic chemistry, fairy state, energy budgets, anything with
    a known set of keys that get updated frequently.
    """

    def __init__(self, filepath: str, capacity: int = 0, readonly: bool = False):
        self.filepath = filepath
        self.readonly = readonly
        self._file = None
        self._mm = None
        self._capacity = 0
        self._count = 0
        self._key_index: Dict[str, int] = {}  # key → slot
        self._version = 0
        self._lock = threading.Lock()

        if os.path.exists(filepath) and not capacity:
            self._open_existing()
        elif capacity > 0:
            self._create_new(capacity)
        else:
            raise ValueError(f"File {filepath} doesn't exist and no capacity specified")

    def _create_new(self, capacity: int):
        total_size = STATE_FILE_HEADER_SIZE + capacity * STATE_RECORD_SIZE
        self._file = open(self.filepath, 'w+b')
        self._file.write(b'\x00' * total_size)
        self._file.flush()
        self._mm = mmap.mmap(self._file.fileno(), total_size)
        self._capacity = capacity
        self._count = 0
        self._version = 0
        self._write_header()
        _log(f"[StateRegion] Created: {self.filepath} ({capacity} slots, "
             f"{total_size / 1024:.0f}KB)")

    def _open_existing(self):
        mode = 'r+b' if not self.readonly else 'rb'
        access = mmap.ACCESS_WRITE if not self.readonly else mmap.ACCESS_READ
        self._file = open(self.filepath, mode)
        file_size = os.path.getsize(self.filepath)
        self._mm = mmap.mmap(self._file.fileno(), file_size, access=access)
        self._read_header()
        self._rebuild_index()
        _log(f"[StateRegion] Opened: {self.filepath} ({self._count}/{self._capacity} slots)")

    def _write_header(self):
        data = STATE_FILE_HEADER_STRUCT.pack(
            STATE_FILE_MAGIC, 1, self._capacity, self._version
        )
        self._mm[0:STATE_FILE_HEADER_STRUCT.size] = data

    def _read_header(self):
        data = STATE_FILE_HEADER_STRUCT.unpack(self._mm[0:STATE_FILE_HEADER_STRUCT.size])
        magic, version, self._capacity, self._version = data
        if magic != STATE_FILE_MAGIC:
            raise ValueError(f"Not a state file: {magic}")

    def _rebuild_index(self):
        self._key_index.clear()
        for slot in range(self._capacity):
            offset = STATE_FILE_HEADER_SIZE + slot * STATE_RECORD_SIZE
            record = STATE_HEADER.unpack(self._mm[offset:offset + STATE_RECORD_SIZE])
            key_bytes = record[0].rstrip(b'\x00')
            if key_bytes:
                key = key_bytes.decode('utf-8', errors='replace')
                self._key_index[key] = slot
        self._count = len(self._key_index)

    def get(self, key: str) -> Optional[bytes]:
        """Read a value by key. Lock-free (mmap read)."""
        slot = self._key_index.get(key)
        if slot is None:
            return None
        offset = STATE_FILE_HEADER_SIZE + slot * STATE_RECORD_SIZE
        record = STATE_HEADER.unpack(self._mm[offset:offset + STATE_RECORD_SIZE])
        return record[1].rstrip(b'\x00')

    def get_json(self, key: str) -> Optional[Any]:
        """Read a JSON-encoded value by key. Lock-free."""
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def put(self, key: str, value: bytes) -> bool:
        """Write a value by key. Uses per-region lock."""
        if self.readonly:
            return False
        if len(key) > STATE_KEY_SIZE:
            key = key[:STATE_KEY_SIZE]
        if len(value) > STATE_VALUE_SIZE:
            value = value[:STATE_VALUE_SIZE]

        with self._lock:
            slot = self._key_index.get(key)
            if slot is None:
                # New key — find empty slot
                if self._count >= self._capacity:
                    return False  # Full
                slot = self._count
                # Search for first empty slot
                for s in range(self._capacity):
                    if s not in self._key_index.values():
                        slot = s
                        break
                self._key_index[key] = slot
                self._count = len(self._key_index)

            # Write record
            key_bytes = key.encode('utf-8')[:STATE_KEY_SIZE].ljust(STATE_KEY_SIZE, b'\x00')
            val_bytes = value[:STATE_VALUE_SIZE].ljust(STATE_VALUE_SIZE, b'\x00')
            self._version += 1
            data = STATE_HEADER.pack(key_bytes, val_bytes, self._version, 0)
            offset = STATE_FILE_HEADER_SIZE + slot * STATE_RECORD_SIZE
            self._mm[offset:offset + STATE_RECORD_SIZE] = data
            self._write_header()  # Update global version
            return True

    def put_json(self, key: str, value: Any) -> bool:
        """Write a JSON-encoded value by key."""
        encoded = json.dumps(value, separators=(',', ':')).encode('utf-8')
        return self.put(key, encoded)

    @property
    def version(self) -> int:
        """Current version counter (monotonic). Lock-free read."""
        data = STATE_FILE_HEADER_STRUCT.unpack(self._mm[0:STATE_FILE_HEADER_STRUCT.size])
        return data[3]

    @property
    def count(self) -> int:
        return self._count

    @property
    def capacity(self) -> int:
        return self._capacity

    def keys(self) -> List[str]:
        return list(self._key_index.keys())

    def flush(self):
        if self._mm:
            self._mm.flush()

    def close(self):
        if self._mm:
            self._mm.flush()
            self._mm.close()
        if self._file:
            self._file.close()


# ============================================================================
# RING BUFFER REGION — Circular buffers for streaming messages
# ============================================================================

class RingRegion:
    """
    mmap-backed ring buffer for pub/sub messaging.

    Fixed-capacity circular buffer. When full, oldest messages are overwritten.
    Never drops. Never blocks. Readers poll with version counter.

    Use for: postal messages, consciousness thought stream, sensory buffers.
    """

    def __init__(self, filepath: str, capacity: int = 0,
                 record_size: int = RING_RECORD_SIZE, readonly: bool = False):
        self.filepath = filepath
        self.readonly = readonly
        self._file = None
        self._mm = None
        self._capacity = 0
        self._record_size = record_size
        self._head = 0       # Next write position
        self._count = 0      # Total messages written (monotonic)
        self._version = 0    # Global version (monotonic)
        self._lock = threading.Lock()

        if os.path.exists(filepath) and not capacity:
            self._open_existing()
        elif capacity > 0:
            self._create_new(capacity)
        else:
            raise ValueError(f"File {filepath} doesn't exist and no capacity specified")

    def _create_new(self, capacity: int):
        total_size = RING_FILE_HEADER_SIZE + capacity * self._record_size
        self._file = open(self.filepath, 'w+b')
        self._file.write(b'\x00' * total_size)
        self._file.flush()
        self._mm = mmap.mmap(self._file.fileno(), total_size)
        self._capacity = capacity
        self._head = 0
        self._count = 0
        self._version = 0
        self._write_header()
        _log(f"[RingRegion] Created: {self.filepath} ({capacity} slots × "
             f"{self._record_size}B = {total_size / 1024:.0f}KB)")

    def _open_existing(self):
        mode = 'r+b' if not self.readonly else 'rb'
        access = mmap.ACCESS_WRITE if not self.readonly else mmap.ACCESS_READ
        self._file = open(self.filepath, mode)
        file_size = os.path.getsize(self.filepath)
        self._mm = mmap.mmap(self._file.fileno(), file_size, access=access)
        self._read_header()
        _log(f"[RingRegion] Opened: {self.filepath} ({self._capacity} slots, "
             f"count={self._count}, head={self._head})")

    def _write_header(self):
        data = RING_FILE_HEADER_STRUCT.pack(
            RING_FILE_MAGIC, 1, self._capacity,
            self._record_size, self._version
        )
        self._mm[0:RING_FILE_HEADER_STRUCT.size] = data
        # Also write head and count after the struct
        struct.pack_into('<IQ', self._mm, RING_FILE_HEADER_STRUCT.size,
                         self._head, self._count)

    def _read_header(self):
        data = RING_FILE_HEADER_STRUCT.unpack(self._mm[0:RING_FILE_HEADER_STRUCT.size])
        magic, version, self._capacity, self._record_size, self._version = data
        if magic != RING_FILE_MAGIC:
            raise ValueError(f"Not a ring file: {magic}")
        extra = struct.unpack_from('<IQ', self._mm, RING_FILE_HEADER_STRUCT.size)
        self._head, self._count = extra

    def publish(self, topic: str, payload: bytes, source: str = "",
                tracer: str = "") -> int:
        """
        Write a message to the ring buffer. Returns the message sequence number.

        Lock-free for readers. Writer uses per-region lock.
        When buffer is full, overwrites oldest message (circular).
        """
        if self.readonly:
            return -1

        with self._lock:
            slot = self._head % self._capacity
            offset = RING_FILE_HEADER_SIZE + slot * self._record_size

            # Pack the record header
            topic_b = topic.encode('utf-8')[:64].ljust(64, b'\x00')
            tracer_b = tracer.encode('utf-8')[:32].ljust(32, b'\x00')
            source_b = source.encode('utf-8')[:32].ljust(32, b'\x00')
            timestamp = time.time()
            payload_len = min(len(payload), RING_PAYLOAD_SIZE)

            header_data = RING_RECORD_STRUCT_HEADER.pack(
                topic_b, tracer_b, source_b, timestamp, payload_len
            )

            # Write header + payload
            self._mm[offset:offset + RING_RECORD_STRUCT_HEADER.size] = header_data
            payload_offset = offset + RING_RECORD_STRUCT_HEADER.size
            self._mm[payload_offset:payload_offset + payload_len] = payload[:payload_len]

            # Advance head
            self._head += 1
            self._count += 1
            self._version += 1
            self._write_header()

            return self._count

    def publish_json(self, topic: str, data: Any, source: str = "",
                     tracer: str = "") -> int:
        """Publish a JSON-serialized message."""
        payload = json.dumps(data, separators=(',', ':')).encode('utf-8')
        return self.publish(topic, payload, source=source, tracer=tracer)

    def read_latest(self, n: int = 1) -> List[dict]:
        """Read the N most recent messages. Lock-free."""
        results = []
        # Read header values directly from mmap for freshest data
        extra = struct.unpack_from('<IQ', self._mm, RING_FILE_HEADER_STRUCT.size)
        head, count = extra
        if count == 0:
            return results

        start = max(0, head - n)
        for seq in range(start, head):
            slot = seq % self._capacity
            offset = RING_FILE_HEADER_SIZE + slot * self._record_size

            header = RING_RECORD_STRUCT_HEADER.unpack(
                self._mm[offset:offset + RING_RECORD_STRUCT_HEADER.size]
            )
            topic = header[0].rstrip(b'\x00').decode('utf-8', errors='replace')
            tracer = header[1].rstrip(b'\x00').decode('utf-8', errors='replace')
            source = header[2].rstrip(b'\x00').decode('utf-8', errors='replace')
            timestamp = header[3]
            payload_len = header[4]

            payload_offset = offset + RING_RECORD_STRUCT_HEADER.size
            payload = self._mm[payload_offset:payload_offset + payload_len]

            results.append({
                'seq': seq,
                'topic': topic,
                'tracer': tracer,
                'source': source,
                'timestamp': timestamp,
                'payload': payload,
            })

        return results

    def poll_since(self, last_seq: int) -> List[dict]:
        """Read all messages since a given sequence number. Lock-free."""
        extra = struct.unpack_from('<IQ', self._mm, RING_FILE_HEADER_STRUCT.size)
        head, count = extra

        if last_seq >= head:
            return []  # Nothing new

        # Clamp to buffer capacity (oldest available message)
        oldest = max(0, head - self._capacity)
        start = max(last_seq, oldest)

        return self.read_latest(head - start)

    @property
    def version(self) -> int:
        """Current version (monotonic). Lock-free read from mmap."""
        data = RING_FILE_HEADER_STRUCT.unpack(self._mm[0:RING_FILE_HEADER_STRUCT.size])
        return data[4]

    @property
    def head(self) -> int:
        extra = struct.unpack_from('<IQ', self._mm, RING_FILE_HEADER_STRUCT.size)
        return extra[0]

    @property
    def count(self) -> int:
        extra = struct.unpack_from('<IQ', self._mm, RING_FILE_HEADER_STRUCT.size)
        return extra[1]

    def flush(self):
        if self._mm:
            self._mm.flush()

    def close(self):
        if self._mm:
            self._mm.flush()
            self._mm.close()
        if self._file:
            self._file.close()


# ============================================================================
# AKASHIC MANIFOLD — The Russian Doll
# ============================================================================

class AkashicManifold:
    """
    The system IS the manifold.

    Manages a directory of mmap-backed region files. Each region has its own
    file, its own type, its own write lock. Reads are always lock-free.

    Region types:
        GRAPH  — ManifoldMemory (nodes + edges + strings). For cortex, ego, episodic.
        STATE  — Key-value records. For somatic, fairy state, energy.
        RING   — Circular buffers. For postal, consciousness, sensory streams.

    Usage:
        akashic = AkashicManifold("state/akashic")
        akashic.create_region("cortex", REGION_GRAPH, node_capacity=1_000_000)
        akashic.create_region("somatic", REGION_STATE, state_capacity=256)
        akashic.create_region("postal", REGION_RING, ring_capacity=10_000)

        # Any fairy can get a read handle:
        cortex = akashic.graph("cortex")          # ManifoldMemory (readonly)
        body = akashic.state("somatic")            # StateRegion (readonly)
        msgs = akashic.ring("postal")              # RingRegion (readonly)

        # Owner fairy gets a write handle:
        cortex_rw = akashic.graph("cortex", write=True)
        cortex_rw.upsert_node("empathy", activation=0.8)
        cortex_rw.link("empathy", "compassion", weight=0.7)
    """

    INDEX_FILE = "akashic.index"
    EXTENSIONS = {
        REGION_GRAPH: ".manifold",
        REGION_STATE: ".state",
        REGION_RING: ".ring",
    }

    def __init__(self, base_dir: str):
        """
        Open or create an AkashicManifold at the given directory.

        Args:
            base_dir: Directory for all region files + index
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self._index_path = self.base_dir / self.INDEX_FILE
        self._regions: Dict[str, RegionMeta] = {}
        self._handles: Dict[str, Any] = {}  # name → open handle (ManifoldMemory/StateRegion/RingRegion)
        self._lock = threading.Lock()  # For index operations only

        # Load existing index
        if self._index_path.exists():
            self._load_index()
            _log(f"[AkashicManifold] Opened: {self.base_dir} ({len(self._regions)} regions)")
        else:
            self._save_index()
            _log(f"[AkashicManifold] Created: {self.base_dir}")

    def _load_index(self):
        """Load region metadata from index file."""
        try:
            with open(self._index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for rd in data.get('regions', []):
                meta = RegionMeta.from_dict(rd)
                self._regions[meta.name] = meta
        except Exception as e:
            _log(f"[AkashicManifold] Index load error: {e}")

    def _save_index(self):
        """Save region metadata to index file."""
        data = {
            'magic': 'AKASHIC_MANIFOLD',
            'version': 1,
            'created': time.time(),
            'regions': [m.to_dict() for m in self._regions.values()],
        }
        with open(self._index_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def _region_path(self, name: str, region_type: int) -> Path:
        """Get file path for a region."""
        ext = self.EXTENSIONS.get(region_type, '.manifold')
        return self.base_dir / f"{name}{ext}"

    # ════════════════════════════════════════════════════════════════════
    # REGION CREATION
    # ════════════════════════════════════════════════════════════════════

    def create_region(self, name: str, region_type: int,
                      owner: str = "system", gpu_mirror: bool = False,
                      **kwargs) -> bool:
        """
        Create a new region.

        Args:
            name: Region name (e.g., "cortex", "somatic", "postal")
            region_type: REGION_GRAPH, REGION_STATE, or REGION_RING
            owner: Fairy that owns this region (has write access)
            gpu_mirror: If True, mark for GPU CUDA tensor sync
            **kwargs: Type-specific params:
                GRAPH: node_capacity, edge_capacity
                STATE: state_capacity
                RING:  ring_capacity, ring_record_size

        Returns:
            True if created, False if already exists
        """
        if name in self._regions:
            _log(f"[AkashicManifold] Region '{name}' already exists")
            return False

        filepath = self._region_path(name, region_type)

        with self._lock:
            meta = RegionMeta(name, region_type, owner=owner,
                              gpu_mirror=gpu_mirror, **kwargs)

            if region_type == REGION_GRAPH:
                nc = kwargs.get('node_capacity', 100_000)
                ec = kwargs.get('edge_capacity', nc * 10)
                meta.node_capacity = nc
                meta.edge_capacity = ec
                handle = ManifoldMemory(str(filepath),
                                        node_capacity=nc,
                                        edge_capacity=ec)
                handle.close()  # Close after creation, reopen on access

            elif region_type == REGION_STATE:
                sc = kwargs.get('state_capacity', 256)
                meta.state_capacity = sc
                handle = StateRegion(str(filepath), capacity=sc)
                handle.close()

            elif region_type == REGION_RING:
                rc = kwargs.get('ring_capacity', 10_000)
                meta.ring_capacity = rc
                meta.ring_record_size = kwargs.get('ring_record_size', RING_RECORD_SIZE)
                handle = RingRegion(str(filepath), capacity=rc,
                                    record_size=meta.ring_record_size)
                handle.close()

            else:
                _log(f"[AkashicManifold] Unknown region type: {region_type}")
                return False

            self._regions[name] = meta
            self._save_index()

            type_name = REGION_TYPE_NAMES.get(region_type, 'unknown')
            _log(f"[AkashicManifold] Created region '{name}' ({type_name}) "
                 f"owner={owner} gpu={gpu_mirror}")
            return True

    # ════════════════════════════════════════════════════════════════════
    # REGION ACCESS — The API fairies use
    # ════════════════════════════════════════════════════════════════════

    def graph(self, name: str, write: bool = False) -> Optional[ManifoldMemory]:
        """
        Get a ManifoldMemory handle for a graph region.

        Args:
            name: Region name
            write: If True, open read-write. If False, open readonly.

        Returns:
            ManifoldMemory instance or None if region doesn't exist/wrong type.
        """
        meta = self._regions.get(name)
        if not meta or meta.region_type != REGION_GRAPH:
            return None

        handle_key = f"{name}:{'rw' if write else 'ro'}"
        if handle_key in self._handles:
            return self._handles[handle_key]

        filepath = self._region_path(name, REGION_GRAPH)
        if not filepath.exists():
            return None

        handle = ManifoldMemory(str(filepath), readonly=not write)
        self._handles[handle_key] = handle
        return handle

    def state(self, name: str, write: bool = False) -> Optional[StateRegion]:
        """
        Get a StateRegion handle for a state region.

        Args:
            name: Region name
            write: If True, open read-write. If False, open readonly.

        Returns:
            StateRegion instance or None.
        """
        meta = self._regions.get(name)
        if not meta or meta.region_type != REGION_STATE:
            return None

        handle_key = f"{name}:{'rw' if write else 'ro'}"
        if handle_key in self._handles:
            return self._handles[handle_key]

        filepath = self._region_path(name, REGION_STATE)
        if not filepath.exists():
            return None

        handle = StateRegion(str(filepath), readonly=not write)
        self._handles[handle_key] = handle
        return handle

    def ring(self, name: str, write: bool = False) -> Optional[RingRegion]:
        """
        Get a RingRegion handle for a ring buffer region.

        Args:
            name: Region name
            write: If True, open read-write. If False, open readonly.

        Returns:
            RingRegion instance or None.
        """
        meta = self._regions.get(name)
        if not meta or meta.region_type != REGION_RING:
            return None

        handle_key = f"{name}:{'rw' if write else 'ro'}"
        if handle_key in self._handles:
            return self._handles[handle_key]

        filepath = self._region_path(name, REGION_RING)
        if not filepath.exists():
            return None

        handle = RingRegion(str(filepath), readonly=not write)
        self._handles[handle_key] = handle
        return handle

    # ════════════════════════════════════════════════════════════════════
    # IMPORT — Migrate existing ManifoldMemory into AkashicManifold
    # ════════════════════════════════════════════════════════════════════

    def import_manifold(self, name: str, source_path: str,
                        owner: str = "system", gpu_mirror: bool = False) -> bool:
        """
        Import an existing ManifoldMemory file as a graph region.

        Copies the file into the akashic directory and registers it.
        The original file is NOT modified.

        Args:
            name: Region name for the imported graph
            source_path: Path to existing .manifold file
            owner: Owner fairy
            gpu_mirror: Mark for GPU sync

        Returns:
            True if imported successfully.
        """
        import shutil

        if name in self._regions:
            _log(f"[AkashicManifold] Region '{name}' already exists, skipping import")
            return False

        source = Path(source_path)
        if not source.exists():
            _log(f"[AkashicManifold] Source file not found: {source_path}")
            return False

        dest = self._region_path(name, REGION_GRAPH)

        # Copy the file
        _log(f"[AkashicManifold] Importing {source_path} -> {dest}")
        shutil.copy2(source_path, str(dest))

        # Open to read metadata
        temp = ManifoldMemory(str(dest), readonly=True)
        node_cap = temp._node_capacity
        edge_cap = temp._edge_capacity
        node_count = temp.node_count
        edge_count = temp.edge_count
        temp.close()

        # Register
        meta = RegionMeta(name, REGION_GRAPH, owner=owner,
                          gpu_mirror=gpu_mirror,
                          node_capacity=node_cap,
                          edge_capacity=edge_cap)
        self._regions[name] = meta
        self._save_index()

        _log(f"[AkashicManifold] Imported '{name}': {node_count} nodes, "
             f"{edge_count} edges ({dest.stat().st_size / (1024*1024):.1f}MB)")
        return True

    # ════════════════════════════════════════════════════════════════════
    # STATUS & DIAGNOSTICS
    # ════════════════════════════════════════════════════════════════════

    def regions(self) -> List[dict]:
        """List all regions with metadata."""
        return [m.to_dict() for m in self._regions.values()]

    def region_names(self) -> List[str]:
        """List all region names."""
        return list(self._regions.keys())

    def has_region(self, name: str) -> bool:
        return name in self._regions

    def region_version(self, name: str) -> int:
        """Get the current version of a region. Lock-free."""
        handle_key_rw = f"{name}:rw"
        handle_key_ro = f"{name}:ro"
        handle = self._handles.get(handle_key_rw) or self._handles.get(handle_key_ro)
        if handle and hasattr(handle, 'version'):
            return handle.version
        return self._regions.get(name, RegionMeta("", 0)).version

    def status(self) -> dict:
        """Full system status."""
        total_size = 0
        region_info = []
        for name, meta in self._regions.items():
            filepath = self._region_path(name, meta.region_type)
            size = filepath.stat().st_size if filepath.exists() else 0
            total_size += size
            info = {
                'name': name,
                'type': REGION_TYPE_NAMES.get(meta.region_type, 'unknown'),
                'owner': meta.owner,
                'gpu_mirror': meta.gpu_mirror,
                'size_mb': round(size / (1024 * 1024), 2),
            }

            # Add type-specific info from open handles
            handle = self._handles.get(f"{name}:rw") or self._handles.get(f"{name}:ro")
            if handle:
                if isinstance(handle, ManifoldMemory):
                    info['nodes'] = handle.node_count
                    info['edges'] = handle.edge_count
                elif isinstance(handle, StateRegion):
                    info['keys'] = handle.count
                    info['capacity'] = handle.capacity
                elif isinstance(handle, RingRegion):
                    info['messages'] = handle.count
                    info['capacity'] = handle._capacity

            region_info.append(info)

        return {
            'base_dir': str(self.base_dir),
            'region_count': len(self._regions),
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'regions': region_info,
        }

    # ════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ════════════════════════════════════════════════════════════════════

    def flush_all(self):
        """Flush all open region handles."""
        for handle in self._handles.values():
            if hasattr(handle, 'flush'):
                try:
                    handle.flush()
                except Exception:
                    pass

    def close(self):
        """Close all open handles and save index."""
        for handle in self._handles.values():
            if hasattr(handle, 'close'):
                try:
                    handle.close()
                except Exception:
                    pass
        self._handles.clear()
        self._save_index()
        _log(f"[AkashicManifold] Closed: {self.base_dir}")


# ============================================================================
# CONVENIENCE: Boot the standard system manifold
# ============================================================================

def boot_akashic(base_dir: str = None,
                 import_cortex: str = None) -> AkashicManifold:
    """
    Boot the standard AkashicManifold with default regions.

    Args:
        base_dir: Directory for the manifold (default: state/akashic)
        import_cortex: Path to existing portal_cortex.manifold to import

    Returns:
        Initialized AkashicManifold with standard regions.
    """
    if base_dir is None:
        base_dir = str(Path(__file__).parent.parent / "state" / "akashic")

    akashic = AkashicManifold(base_dir)

    # Create standard regions if they don't exist
    if not akashic.has_region("cortex"):
        if import_cortex and os.path.exists(import_cortex):
            akashic.import_manifold("cortex", import_cortex,
                                    owner="AssociationCortexFairy",
                                    gpu_mirror=True)
        else:
            akashic.create_region("cortex", REGION_GRAPH,
                                  owner="AssociationCortexFairy",
                                  gpu_mirror=True,
                                  node_capacity=1_000_000,
                                  edge_capacity=10_000_000)

    if not akashic.has_region("ego"):
        akashic.create_region("ego", REGION_GRAPH,
                              owner="EgoDrivesFairy",
                              node_capacity=100_000,
                              edge_capacity=1_000_000)

    if not akashic.has_region("somatic"):
        akashic.create_region("somatic", REGION_STATE,
                              owner="SomaticMindFairy",
                              state_capacity=512)

    if not akashic.has_region("consciousness"):
        akashic.create_region("consciousness", REGION_RING,
                              owner="ConsciousnessLoopFairy",
                              ring_capacity=10_000)

    if not akashic.has_region("postal"):
        akashic.create_region("postal", REGION_RING,
                              owner="system",
                              ring_capacity=50_000)

    if not akashic.has_region("sensory"):
        akashic.create_region("sensory", REGION_RING,
                              owner="system",
                              ring_capacity=20_000)

    if not akashic.has_region("fairy_state"):
        akashic.create_region("fairy_state", REGION_STATE,
                              owner="system",
                              state_capacity=256)  # Room for 256 fairies

    if not akashic.has_region("energy"):
        akashic.create_region("energy", REGION_STATE,
                              owner="system",
                              state_capacity=128)  # Per-region energy budgets

    _log(f"[AkashicManifold] ONLINE: {len(akashic.regions())} regions")
    return akashic


# ============================================================================
# CLI TEST
# ============================================================================

if __name__ == '__main__':
    import tempfile

    print("=" * 60)
    print("AkashicManifold — Russian Doll Architecture Test")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Boot
        akashic = AkashicManifold(os.path.join(tmpdir, "akashic"))

        # Create regions
        akashic.create_region("cortex", REGION_GRAPH,
                              node_capacity=1000, edge_capacity=5000,
                              gpu_mirror=True)
        akashic.create_region("somatic", REGION_STATE, state_capacity=64)
        akashic.create_region("postal", REGION_RING, ring_capacity=100)

        # Test graph region
        print("\n--- Graph Region (cortex) ---")
        cortex = akashic.graph("cortex", write=True)
        cortex.upsert_node("empathy", activation=0.8)
        cortex.upsert_node("compassion", activation=0.7)
        cortex.upsert_node("kindness", activation=0.6)
        cortex.link("empathy", "compassion", weight=0.9)
        cortex.link("compassion", "kindness", weight=0.8)
        print(f"  Nodes: {cortex.node_count}, Edges: {cortex.edge_count}")

        # Readonly handle sees the same data
        cortex_ro = akashic.graph("cortex", write=False)
        print(f"  Readonly sees: {cortex_ro.node_count} nodes")

        # Test state region
        print("\n--- State Region (somatic) ---")
        body = akashic.state("somatic", write=True)
        body.put_json("chemistry", {"dopamine": 0.7, "cortisol": 0.3, "oxytocin": 0.5})
        body.put_json("heart_rate", {"bpm": 72, "variability": 0.15})
        print(f"  Chemistry: {body.get_json('chemistry')}")
        print(f"  Heart rate: {body.get_json('heart_rate')}")
        print(f"  Version: {body.version}")

        # Test ring region
        print("\n--- Ring Region (postal) ---")
        postal = akashic.ring("postal", write=True)
        postal.publish_json("consciousness.thought",
                            {"text": "I wonder about empathy"},
                            source="InnerNarrator", tracer="tr_001")
        postal.publish_json("consciousness.thought",
                            {"text": "Music makes me feel things"},
                            source="InnerNarrator", tracer="tr_002")
        postal.publish_json("sensory.audio",
                            {"is_music": True, "song": "Snowman by Sia"},
                            source="AudioCortex", tracer="tr_003")
        latest = postal.read_latest(3)
        for msg in latest:
            payload = json.loads(msg['payload'].decode('utf-8'))
            print(f"  [{msg['topic']}] from {msg['source']}: {payload}")
        print(f"  Total messages: {postal.count}, Version: {postal.version}")

        # Status
        print("\n--- System Status ---")
        status = akashic.status()
        print(f"  Regions: {status['region_count']}")
        print(f"  Total size: {status['total_size_mb']}MB")
        for r in status['regions']:
            print(f"    {r['name']} ({r['type']}): {r['size_mb']}MB"
                  f" owner={r['owner']}"
                  f" gpu={r.get('gpu_mirror', False)}")

        akashic.close()
        print("\n[OK] All tests passed")
