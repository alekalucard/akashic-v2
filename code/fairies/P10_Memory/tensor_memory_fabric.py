# ═══════════════════════════════════════════════════════════════════════════════
# TENSOR MEMORY FABRIC - Multi-Dimensional Parallel Memory Access
# ═══════════════════════════════════════════════════════════════════════════════
#
# Memory organized as a tensor (multi-dimensional array) where:
#   - Dimension 1: Plane (P00-P60) - functional domain
#   - Dimension 2: Channel (0-76) - the 77 emotion channels
#   - Dimension 3: Time (temporal slices)
#   - Dimension 4: Type (affect, semantic, temporal from triple helix)
#
# This allows:
#   - Parallel reads across different planes (no blocking)
#   - Channel isolation (no cross-talk)
#   - Time-windowed access
#   - Type-specific queries
#
# Fairies can read/write to their slice without affecting others.
# ═══════════════════════════════════════════════════════════════════════════════

import os as _os
import time
import threading
from collections import deque, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple, Set
import hashlib
import json

@dataclass
class MemoryCell:
    """A single cell in the tensor - one memory unit"""
    id: str
    content: Any

    # Tensor coordinates
    plane: str          # P00-P60
    channel: int        # 0-76 (emotion channels)
    timestamp: float    # When created
    mem_type: str       # affect, semantic, temporal

    # Metadata
    author: str         # Which fairy created this
    strength: float = 1.0  # Memory strength (decays over time)
    access_count: int = 0
    last_accessed: float = 0

    # Associations
    tags: Set[str] = field(default_factory=set)
    links: Set[str] = field(default_factory=set)  # IDs of related memories

    def decay(self, rate: float = 0.001):
        """Apply time-based decay"""
        age = time.time() - self.timestamp
        self.strength = max(0.1, self.strength - (rate * age / 3600))  # Decay per hour

    def reinforce(self, amount: float = 0.1):
        """Strengthen memory through access"""
        self.strength = min(1.0, self.strength + amount)
        self.access_count += 1
        self.last_accessed = time.time()

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'content': str(self.content)[:200],
            'plane': self.plane,
            'channel': self.channel,
            'timestamp': self.timestamp,
            'mem_type': self.mem_type,
            'author': self.author,
            'strength': round(self.strength, 3),
            'access_count': self.access_count,
            'tags': list(self.tags),
            'links': list(self.links)
        }


class PlaneSlice:
    """
    A slice of the tensor for one plane.
    Each plane has its own lock - no cross-plane blocking.
    """

    def __init__(self, plane: str, num_channels: int = 77):
        self.plane = plane
        self.num_channels = num_channels
        self._lock = threading.RLock()

        # Channels: channel_id -> deque of memories
        self.channels: Dict[int, deque] = {
            i: deque(maxlen=1000) for i in range(num_channels)
        }

        # Index by type
        self.by_type: Dict[str, Set[str]] = defaultdict(set)

        # Index by author
        self.by_author: Dict[str, Set[str]] = defaultdict(set)

        # Fast lookup
        self.cells: Dict[str, MemoryCell] = {}

        # Stats
        self.write_count = 0
        self.read_count = 0

    def write(self, cell: MemoryCell) -> bool:
        """Write a memory cell to this plane slice"""
        with self._lock:
            if cell.channel < 0 or cell.channel >= self.num_channels:
                return False

            self.channels[cell.channel].append(cell)
            self.cells[cell.id] = cell
            self.by_type[cell.mem_type].add(cell.id)
            self.by_author[cell.author].add(cell.id)
            self.write_count += 1
            return True

    def read(self, cell_id: str) -> Optional[MemoryCell]:
        """Read a specific cell by ID"""
        with self._lock:
            cell = self.cells.get(cell_id)
            if cell:
                cell.reinforce(0.05)
                self.read_count += 1
            return cell

    def read_channel(self, channel: int, limit: int = 100) -> List[MemoryCell]:
        """Read recent memories from a channel"""
        with self._lock:
            if channel < 0 or channel >= self.num_channels:
                return []
            cells = list(self.channels[channel])[-limit:]
            for cell in cells:
                cell.reinforce(0.02)
            self.read_count += len(cells)
            return cells

    def read_by_type(self, mem_type: str, limit: int = 100) -> List[MemoryCell]:
        """Read memories by type"""
        with self._lock:
            cell_ids = list(self.by_type.get(mem_type, set()))[-limit:]
            cells = [self.cells[cid] for cid in cell_ids if cid in self.cells]
            for cell in cells:
                cell.reinforce(0.02)
            self.read_count += len(cells)
            return cells

    def read_by_author(self, author: str, limit: int = 100) -> List[MemoryCell]:
        """Read memories by author fairy"""
        with self._lock:
            cell_ids = list(self.by_author.get(author, set()))[-limit:]
            cells = [self.cells[cid] for cid in cell_ids if cid in self.cells]
            for cell in cells:
                cell.reinforce(0.02)
            self.read_count += len(cells)
            return cells

    def get_stats(self) -> Dict:
        """Get slice statistics"""
        with self._lock:
            return {
                'plane': self.plane,
                'total_cells': len(self.cells),
                'channels_used': sum(1 for ch in self.channels.values() if len(ch) > 0),
                'writes': self.write_count,
                'reads': self.read_count,
                'by_type': {t: len(ids) for t, ids in self.by_type.items()},
                'top_authors': sorted(
                    [(a, len(ids)) for a, ids in self.by_author.items()],
                    key=lambda x: x[1],
                    reverse=True
                )[:5]
            }


class TensorMemoryFabric:
    """
    The full tensor memory structure.

    Organized as:
    [Plane] x [Channel] x [Time] x [Type]

    Each plane is independent - fairies can read/write in parallel
    without blocking each other across planes.
    """

    def __init__(self, num_channels: int = 77):
        self.num_channels = num_channels

        # One slice per plane
        self.planes: Dict[str, PlaneSlice] = {
            'P00': PlaneSlice('P00', num_channels),  # Autonomic
            'P10': PlaneSlice('P10', num_channels),  # Memory
            'P20': PlaneSlice('P20', num_channels),  # Somatic
            'P30': PlaneSlice('P30', num_channels),  # Cognition
            'P40': PlaneSlice('P40', num_channels),  # Sensory
            'P50': PlaneSlice('P50', num_channels),  # Persona
            'P60': PlaneSlice('P60', num_channels),  # Executive
        }

        # Global index for cross-plane queries
        self._global_lock = threading.RLock()
        self._global_index: Dict[str, Tuple[str, str]] = {}  # cell_id -> (plane, channel)

        # Time index for temporal queries
        self._time_index: deque = deque(maxlen=10000)  # Recent cell_ids by time

    def _generate_id(self, content: Any, author: str) -> str:
        """Generate unique cell ID"""
        data = f"{time.time()}{author}{str(content)[:100]}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def _infer_plane(self, author: str) -> str:
        """Infer plane from fairy name"""
        author_lower = author.lower()
        if any(x in author_lower for x in ['memory', 'srm', 'helix', 'librarian']):
            return 'P10'
        elif any(x in author_lower for x in ['somatic', 'chemistry', 'body', 'stress']):
            return 'P20'
        elif any(x in author_lower for x in ['sensory', 'vision', 'audio', 'input']):
            return 'P40'
        elif any(x in author_lower for x in ['persona', 'identity', 'character']):
            return 'P50'
        elif any(x in author_lower for x in ['executive', 'mission', 'decision', 'plan']):
            return 'P60'
        elif any(x in author_lower for x in ['autonomic', 'nervous', 'reflex', 'heartbeat']):
            return 'P00'
        return 'P30'  # Default to cognition

    def store(
        self,
        content: Any,
        author: str,
        mem_type: str = 'semantic',
        channel: int = 0,
        plane: Optional[str] = None,
        tags: Optional[Set[str]] = None,
        links: Optional[Set[str]] = None
    ) -> MemoryCell:
        """
        Store a memory in the tensor.

        Args:
            content: The memory content
            author: Which fairy is storing this
            mem_type: 'affect', 'semantic', or 'temporal'
            channel: Emotion channel (0-76)
            plane: Plane to store in (auto-inferred if not provided)
            tags: Optional tags for indexing
            links: Optional links to related memories
        """
        if plane is None:
            plane = self._infer_plane(author)

        cell_id = self._generate_id(content, author)

        cell = MemoryCell(
            id=cell_id,
            content=content,
            plane=plane,
            channel=channel % self.num_channels,
            timestamp=time.time(),
            mem_type=mem_type,
            author=author,
            tags=tags or set(),
            links=links or set()
        )

        # Write to plane slice (parallel-safe)
        slice = self.planes.get(plane)
        if slice:
            slice.write(cell)

        # Update global index
        with self._global_lock:
            self._global_index[cell_id] = (plane, str(channel))
            self._time_index.append((time.time(), cell_id, plane))

        return cell

    def retrieve(self, cell_id: str) -> Optional[MemoryCell]:
        """Retrieve a specific memory by ID"""
        with self._global_lock:
            location = self._global_index.get(cell_id)

        if not location:
            return None

        plane, _ = location
        slice = self.planes.get(plane)
        if slice:
            return slice.read(cell_id)
        return None

    def query_plane(
        self,
        plane: str,
        channel: Optional[int] = None,
        mem_type: Optional[str] = None,
        author: Optional[str] = None,
        limit: int = 100
    ) -> List[MemoryCell]:
        """
        Query memories from a specific plane.
        This only locks the target plane - other planes remain accessible.
        """
        slice = self.planes.get(plane)
        if not slice:
            return []

        if channel is not None:
            return slice.read_channel(channel, limit)
        elif mem_type:
            return slice.read_by_type(mem_type, limit)
        elif author:
            return slice.read_by_author(author, limit)
        else:
            # Return recent from all channels
            results = []
            for ch in range(self.num_channels):
                results.extend(slice.read_channel(ch, limit // self.num_channels))
            return sorted(results, key=lambda x: x.timestamp, reverse=True)[:limit]

    def query_cross_plane(
        self,
        planes: List[str],
        mem_type: Optional[str] = None,
        since: Optional[float] = None,
        limit: int = 100
    ) -> List[MemoryCell]:
        """
        Query across multiple planes in parallel.
        Each plane query runs independently.
        """
        results = []

        # Query each plane (could be parallelized with ThreadPoolExecutor)
        for plane in planes:
            plane_results = self.query_plane(plane, mem_type=mem_type, limit=limit)
            if since:
                plane_results = [c for c in plane_results if c.timestamp >= since]
            results.extend(plane_results)

        # Sort by timestamp and limit
        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results[:limit]

    def query_temporal(
        self,
        start_time: float,
        end_time: Optional[float] = None,
        limit: int = 100
    ) -> List[MemoryCell]:
        """Query memories by time window"""
        end_time = end_time or time.time()

        with self._global_lock:
            cell_ids = [
                (ts, cid, plane) for ts, cid, plane in self._time_index
                if start_time <= ts <= end_time
            ]

        results = []
        for ts, cid, plane in cell_ids[-limit:]:
            cell = self.retrieve(cid)
            if cell:
                results.append(cell)

        return results

    def link_memories(self, cell_id_1: str, cell_id_2: str):
        """Create a bidirectional link between two memories"""
        cell1 = self.retrieve(cell_id_1)
        cell2 = self.retrieve(cell_id_2)

        if cell1 and cell2:
            cell1.links.add(cell_id_2)
            cell2.links.add(cell_id_1)

    def get_linked(self, cell_id: str, depth: int = 1) -> List[MemoryCell]:
        """Get memories linked to a cell (with optional depth traversal)"""
        cell = self.retrieve(cell_id)
        if not cell:
            return []

        visited = {cell_id}
        results = []
        to_visit = list(cell.links)

        for _ in range(depth):
            next_visit = []
            for link_id in to_visit:
                if link_id in visited:
                    continue
                visited.add(link_id)
                linked = self.retrieve(link_id)
                if linked:
                    results.append(linked)
                    next_visit.extend(linked.links)
            to_visit = next_visit

        return results

    def get_stats(self) -> Dict:
        """Get tensor statistics"""
        stats = {
            'num_channels': self.num_channels,
            'num_planes': len(self.planes),
            'total_cells': 0,
            'planes': {}
        }

        for plane_name, slice in self.planes.items():
            plane_stats = slice.get_stats()
            stats['planes'][plane_name] = plane_stats
            stats['total_cells'] += plane_stats['total_cells']

        with self._global_lock:
            stats['global_index_size'] = len(self._global_index)
            stats['time_index_size'] = len(self._time_index)

        return stats


# ═══ Fairy Integration ═══

def give_tensor_memory(fairy, tensor: TensorMemoryFabric):
    """Give a fairy direct access to tensor memory"""
    import types

    def remember(self, content: Any, mem_type: str = 'semantic',
                 channel: int = 0, tags: Set[str] = None) -> MemoryCell:
        """Store a memory"""
        return tensor.store(
            content=content,
            author=getattr(self, 'name', str(self)),
            mem_type=mem_type,
            channel=channel,
            tags=tags
        )

    def recall(self, mem_type: str = None, channel: int = None,
               limit: int = 10) -> List[MemoryCell]:
        """Recall memories"""
        plane = tensor._infer_plane(getattr(self, 'name', str(self)))
        return tensor.query_plane(
            plane=plane,
            channel=channel,
            mem_type=mem_type,
            limit=limit
        )

    def recall_linked(self, cell_id: str, depth: int = 1) -> List[MemoryCell]:
        """Recall linked memories"""
        return tensor.get_linked(cell_id, depth)

    fairy.remember = types.MethodType(remember, fairy)
    fairy.recall = types.MethodType(recall, fairy)
    fairy.recall_linked = types.MethodType(recall_linked, fairy)

    return fairy


# ═══════════════════════════════════════════════════════════════════════════════
# GPU-ACCELERATED TENSOR MEMORY - PyTorch/CUDA Implementation
# ═══════════════════════════════════════════════════════════════════════════════
#
# True 4D tensor on GPU: [Plane, Channel, Time, Embedding]
# - Batch operations across 539,000 cells in parallel
# - GPU cosine similarity for fast memory search
# - Vectorized decay across entire tensor
# - Falls back to CPU if CUDA unavailable
# ═══════════════════════════════════════════════════════════════════════════════

# Lazy import torch to avoid startup cost if not using GPU version
_torch = None
_torch_available = None

def _get_torch():
    """Lazy import PyTorch"""
    global _torch, _torch_available
    if _torch_available is None:
        # Battery-only mode: skip torch entirely (~3.5GB CUDA DLLs saved)
        if _os.environ.get("AKASHIC_SKIP_TORCH"):
            _torch_available = False
        else:
            try:
                import torch
                _torch = torch
                _torch_available = True
            except ImportError:
                _torch_available = False
    return _torch if _torch_available else None


class GPUTensorMemoryFabric:
    """
    GPU-accelerated tensor memory using PyTorch.

    4D Tensor Structure:
        [Plane, Channel, Time, Embedding]
        [7,     77,      1000, 128      ]  = 69.3M parameters

    Benefits over CPU version:
        - Batch decay: One op instead of 539k Python iterations
        - Parallel writes: No GIL blocking
        - Fast search: GPU cosine similarity ~100x faster
        - Memory efficient: float16 = half the RAM

    Falls back to CPU tensor if CUDA unavailable.
    """

    # Plane name to index mapping
    PLANE_MAP = {
        'P00': 0,  # Autonomic
        'P10': 1,  # Memory
        'P20': 2,  # Somatic
        'P30': 3,  # Cognition
        'P40': 4,  # Sensory
        'P50': 5,  # Persona
        'P60': 6,  # Executive
    }
    PLANE_NAMES = ['P00', 'P10', 'P20', 'P30', 'P40', 'P50', 'P60']

    def __init__(
        self,
        num_planes: int = 7,
        num_channels: int = 77,
        time_slices: int = 1000,
        embedding_dim: int = 128,
        dtype: str = 'float16',
        force_cpu: bool = False
    ):
        torch = _get_torch()
        if torch is None:
            raise ImportError("PyTorch required for GPUTensorMemoryFabric. pip install torch")

        self.num_planes = num_planes
        self.num_channels = num_channels
        self.time_slices = time_slices
        self.embedding_dim = embedding_dim

        # Select device
        if force_cpu or not torch.cuda.is_available():
            self.device = torch.device('cpu')
            self.is_gpu = False
        else:
            self.device = torch.device('cuda')
            self.is_gpu = True

        # Select dtype
        self.dtype = torch.float16 if dtype == 'float16' else torch.float32

        # ═══ Core 4D Tensor ═══
        # Shape: [Plane, Channel, Time, Embedding]
        self.tensor = torch.zeros(
            (num_planes, num_channels, time_slices, embedding_dim),
            device=self.device,
            dtype=self.dtype
        )

        # ═══ Metadata Tensors ═══
        # Timestamps: when each slot was written
        self.timestamps = torch.zeros(
            (num_planes, num_channels, time_slices),
            device=self.device,
            dtype=torch.float32
        )

        # Strengths: memory strength (for decay)
        self.strengths = torch.ones(
            (num_planes, num_channels, time_slices),
            device=self.device,
            dtype=torch.float32
        )

        # Valid mask: which slots have data
        self.valid = torch.zeros(
            (num_planes, num_channels, time_slices),
            device=self.device,
            dtype=torch.bool
        )

        # ═══ Write Pointers ═══
        # Per-channel circular buffer pointer
        self.write_ptrs = torch.zeros(
            (num_planes, num_channels),
            device='cpu',  # Keep on CPU for indexing
            dtype=torch.long
        )

        # ═══ Content Store ═══
        # Raw content stored separately (can't put strings in tensor)
        self._content: Dict[Tuple[int, int, int], Any] = {}
        self._metadata: Dict[Tuple[int, int, int], Dict] = {}

        # ═══ Global Index ═══
        self._id_to_coords: Dict[str, Tuple[int, int, int]] = {}
        self._lock = threading.RLock()

        # Stats
        self.total_writes = 0
        self.total_reads = 0

        print(f"[GPUTensorFabric] Initialized on {self.device}")
        print(f"  Shape: {list(self.tensor.shape)} = {self.tensor.numel():,} cells")
        print(f"  Memory: {self.tensor.element_size() * self.tensor.numel() / 1024 / 1024:.1f} MB")

    def _get_plane_idx(self, plane: str) -> int:
        """Convert plane name to index"""
        return self.PLANE_MAP.get(plane, 3)  # Default to P30 (cognition)

    def _infer_plane(self, author: str) -> str:
        """Infer plane from fairy name (same logic as CPU version)"""
        author_lower = author.lower()
        if any(x in author_lower for x in ['memory', 'srm', 'helix', 'librarian']):
            return 'P10'
        elif any(x in author_lower for x in ['somatic', 'chemistry', 'body', 'stress']):
            return 'P20'
        elif any(x in author_lower for x in ['sensory', 'vision', 'audio', 'input']):
            return 'P40'
        elif any(x in author_lower for x in ['persona', 'identity', 'character']):
            return 'P50'
        elif any(x in author_lower for x in ['executive', 'mission', 'decision', 'plan']):
            return 'P60'
        elif any(x in author_lower for x in ['autonomic', 'nervous', 'reflex', 'heartbeat']):
            return 'P00'
        return 'P30'

    def _content_to_embedding(self, content: Any) -> 'torch.Tensor':
        """
        Convert content to embedding vector.

        For now, uses simple hash-based embedding.
        TODO: Use actual embedding model (sentence-transformers, etc.)
        """
        torch = _get_torch()

        # Simple deterministic embedding from content hash
        content_str = str(content)[:500]
        hash_bytes = hashlib.sha256(content_str.encode()).digest()

        # Convert hash to floats
        embedding = torch.zeros(self.embedding_dim, dtype=self.dtype, device=self.device)
        for i in range(min(32, self.embedding_dim)):
            embedding[i] = (hash_bytes[i % 32] / 255.0) * 2 - 1  # Normalize to [-1, 1]

        # Add some variation based on content length and words
        words = content_str.split()
        if len(words) > 0:
            embedding[32:64] = torch.tensor(
                [(hash(w) % 1000) / 500 - 1 for w in words[:32]] + [0] * max(0, 32 - len(words)),
                dtype=self.dtype, device=self.device
            )[:32]

        return embedding

    def store(
        self,
        content: Any,
        author: str,
        mem_type: str = 'semantic',
        channel: int = 0,
        plane: Optional[str] = None,
        tags: Optional[Set[str]] = None,
        embedding: Optional['torch.Tensor'] = None
    ) -> str:
        """
        Store a memory in the GPU tensor.

        Args:
            content: The memory content (stored separately, embedding goes in tensor)
            author: Which fairy is storing this
            mem_type: 'affect', 'semantic', or 'temporal'
            channel: Emotion channel (0-76)
            plane: Plane to store in (auto-inferred if not provided)
            tags: Optional tags for indexing
            embedding: Pre-computed embedding (if None, auto-generated)

        Returns:
            Cell ID string
        """
        torch = _get_torch()

        if plane is None:
            plane = self._infer_plane(author)

        plane_idx = self._get_plane_idx(plane)
        channel = channel % self.num_channels

        with self._lock:
            # Get write position (circular buffer)
            time_idx = int(self.write_ptrs[plane_idx, channel].item())

            # Generate embedding if not provided
            if embedding is None:
                embedding = self._content_to_embedding(content)
            else:
                embedding = embedding.to(device=self.device, dtype=self.dtype)

            # Write to tensor
            self.tensor[plane_idx, channel, time_idx] = embedding
            self.timestamps[plane_idx, channel, time_idx] = time.time()
            self.strengths[plane_idx, channel, time_idx] = 1.0
            self.valid[plane_idx, channel, time_idx] = True

            # Store content and metadata
            coords = (plane_idx, channel, time_idx)
            self._content[coords] = content
            self._metadata[coords] = {
                'author': author,
                'mem_type': mem_type,
                'tags': tags or set(),
                'timestamp': time.time()
            }

            # Generate ID and index
            cell_id = f"{plane}_{channel}_{time_idx}_{int(time.time()*1000) % 10000}"
            self._id_to_coords[cell_id] = coords

            # Advance write pointer
            self.write_ptrs[plane_idx, channel] = (time_idx + 1) % self.time_slices
            self.total_writes += 1

        return cell_id

    def retrieve(self, cell_id: str) -> Optional[Dict]:
        """Retrieve a memory by ID"""
        with self._lock:
            coords = self._id_to_coords.get(cell_id)
            if coords is None:
                return None

            plane_idx, channel, time_idx = coords

            if not self.valid[plane_idx, channel, time_idx]:
                return None

            # Reinforce on access
            self.strengths[plane_idx, channel, time_idx] = min(
                1.0,
                self.strengths[plane_idx, channel, time_idx] + 0.05
            )
            self.total_reads += 1

            return {
                'id': cell_id,
                'content': self._content.get(coords),
                'embedding': self.tensor[plane_idx, channel, time_idx].cpu().numpy(),
                'plane': self.PLANE_NAMES[plane_idx],
                'channel': channel,
                'timestamp': float(self.timestamps[plane_idx, channel, time_idx]),
                'strength': float(self.strengths[plane_idx, channel, time_idx]),
                **self._metadata.get(coords, {})
            }

    def decay_all(self, rate: float = 0.001):
        """
        Apply decay to ALL memories in one GPU operation.

        This is where GPU shines - decays 539,000 cells in one op.
        """
        torch = _get_torch()
        with torch.no_grad():
            # Calculate time-based decay
            now = time.time()
            age_hours = (now - self.timestamps) / 3600
            decay_amount = rate * age_hours

            # Apply decay only to valid cells
            self.strengths = torch.where(
                self.valid,
                torch.clamp(self.strengths - decay_amount, min=0.1),
                self.strengths
            )

    def similarity_search(
        self,
        query_embedding: 'torch.Tensor',
        top_k: int = 10,
        plane: Optional[str] = None,
        channel: Optional[int] = None,
        min_strength: float = 0.1
    ) -> List[Dict]:
        """
        GPU-accelerated similarity search using cosine similarity.

        Args:
            query_embedding: The embedding to search for
            top_k: Number of results to return
            plane: Optional - restrict to specific plane
            channel: Optional - restrict to specific channel
            min_strength: Minimum memory strength to consider

        Returns:
            List of matching memories with similarity scores
        """
        torch = _get_torch()

        query = query_embedding.to(device=self.device, dtype=self.dtype)

        with torch.no_grad():
            # Build mask for valid cells above strength threshold
            mask = self.valid & (self.strengths >= min_strength)

            if plane is not None:
                plane_idx = self._get_plane_idx(plane)
                plane_mask = torch.zeros_like(mask)
                plane_mask[plane_idx] = True
                mask = mask & plane_mask

            if channel is not None:
                channel_mask = torch.zeros_like(mask)
                channel_mask[:, channel, :] = True
                mask = mask & channel_mask

            # Flatten tensor for similarity computation
            flat_tensor = self.tensor.view(-1, self.embedding_dim)  # [N, E]
            flat_mask = mask.view(-1)  # [N]

            # Compute cosine similarity (GPU-accelerated)
            query_norm = query / (query.norm() + 1e-8)
            tensor_norm = flat_tensor / (flat_tensor.norm(dim=1, keepdim=True) + 1e-8)
            similarities = torch.mv(tensor_norm, query_norm)  # [N]

            # Zero out invalid cells
            similarities = torch.where(flat_mask, similarities, torch.tensor(-float('inf'), device=self.device))

            # Get top k
            top_values, top_indices = torch.topk(similarities, min(top_k, flat_mask.sum().item()))

        # Convert indices back to coordinates and retrieve
        results = []
        for score, flat_idx in zip(top_values.cpu().tolist(), top_indices.cpu().tolist()):
            if score == float('-inf'):
                continue

            # Convert flat index to coordinates
            plane_idx = flat_idx // (self.num_channels * self.time_slices)
            remainder = flat_idx % (self.num_channels * self.time_slices)
            ch = remainder // self.time_slices
            t = remainder % self.time_slices

            coords = (plane_idx, ch, t)
            content = self._content.get(coords)
            metadata = self._metadata.get(coords, {})

            results.append({
                'content': content,
                'similarity': score,
                'plane': self.PLANE_NAMES[plane_idx],
                'channel': ch,
                'strength': float(self.strengths[plane_idx, ch, t]),
                **metadata
            })

        return results

    def search_by_content(self, query_content: Any, top_k: int = 10, **kwargs) -> List[Dict]:
        """Search by content (converts to embedding first)"""
        query_embedding = self._content_to_embedding(query_content)
        return self.similarity_search(query_embedding, top_k, **kwargs)

    def get_plane_stats(self, plane: str) -> Dict:
        """Get statistics for a specific plane"""
        plane_idx = self._get_plane_idx(plane)

        valid_count = self.valid[plane_idx].sum().item()
        avg_strength = self.strengths[plane_idx][self.valid[plane_idx]].mean().item() if valid_count > 0 else 0

        return {
            'plane': plane,
            'valid_cells': int(valid_count),
            'avg_strength': round(avg_strength, 3),
            'channels_used': int((self.valid[plane_idx].sum(dim=1) > 0).sum().item())
        }

    def get_stats(self) -> Dict:
        """Get overall tensor statistics"""
        return {
            'device': str(self.device),
            'is_gpu': self.is_gpu,
            'shape': list(self.tensor.shape),
            'total_cells': int(self.tensor.numel() / self.embedding_dim),
            'valid_cells': int(self.valid.sum().item()),
            'total_writes': self.total_writes,
            'total_reads': self.total_reads,
            'memory_mb': round(self.tensor.element_size() * self.tensor.numel() / 1024 / 1024, 1),
            'dtype': str(self.dtype),
            'planes': {name: self.get_plane_stats(name) for name in self.PLANE_NAMES}
        }

    def save(self, path: str):
        """Save tensor to disk"""
        torch = _get_torch()
        torch.save({
            'tensor': self.tensor.cpu(),
            'timestamps': self.timestamps.cpu(),
            'strengths': self.strengths.cpu(),
            'valid': self.valid.cpu(),
            'write_ptrs': self.write_ptrs,
            'content': self._content,
            'metadata': self._metadata,
            'id_to_coords': self._id_to_coords,
        }, path)
        print(f"[GPUTensorFabric] Saved to {path}")

    def load(self, path: str):
        """Load tensor from disk"""
        torch = _get_torch()
        data = torch.load(path, map_location=self.device)

        self.tensor = data['tensor'].to(device=self.device, dtype=self.dtype)
        self.timestamps = data['timestamps'].to(device=self.device)
        self.strengths = data['strengths'].to(device=self.device)
        self.valid = data['valid'].to(device=self.device)
        self.write_ptrs = data['write_ptrs']
        self._content = data['content']
        self._metadata = data['metadata']
        self._id_to_coords = data['id_to_coords']

        print(f"[GPUTensorFabric] Loaded from {path}")
        print(f"  Valid cells: {self.valid.sum().item():,}")


# ═══ Factory function ═══

def create_tensor_fabric(use_gpu: bool = True, **kwargs) -> 'TensorMemoryFabric | GPUTensorMemoryFabric':
    """
    Create the appropriate tensor fabric based on availability.

    Args:
        use_gpu: Whether to try GPU version (falls back to CPU TensorMemoryFabric)
        **kwargs: Passed to GPUTensorMemoryFabric if used

    Returns:
        GPU version if available and requested, otherwise CPU version
    """
    if use_gpu:
        torch = _get_torch()
        if torch is not None:
            try:
                return GPUTensorMemoryFabric(**kwargs)
            except Exception as e:
                print(f"[TensorFabric] GPU init failed: {e}, using CPU version")

    return TensorMemoryFabric(num_channels=kwargs.get('num_channels', 77))


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL SINGLETON - Shared GPU Tensor Fabric for All Fairies
# ═══════════════════════════════════════════════════════════════════════════════
#
# The system needs ONE shared tensor fabric that all fairies use.
# This singleton is created on first access and persists for the session.
# ═══════════════════════════════════════════════════════════════════════════════

_global_gpu_fabric: Optional[GPUTensorMemoryFabric] = None
_fabric_lock = threading.Lock()


def get_global_tensor_fabric(force_new: bool = False) -> 'GPUTensorMemoryFabric | TensorMemoryFabric':
    """
    Get the global shared GPU tensor fabric singleton.

    Creates it on first access with optimal settings for the system.
    Falls back to CPU version if GPU unavailable.

    Args:
        force_new: If True, create a fresh instance (for testing)

    Returns:
        The shared GPUTensorMemoryFabric (or CPU fallback)
    """
    global _global_gpu_fabric

    with _fabric_lock:
        if _global_gpu_fabric is None or force_new:
            # Try GPU first, fall back to CPU
            _global_gpu_fabric = create_tensor_fabric(
                use_gpu=True,
                num_planes=7,
                num_channels=77,
                time_slices=1000,
                embedding_dim=128,
                dtype='float16'
            )
            print(f"[TensorFabric] Global singleton created: {type(_global_gpu_fabric).__name__}")

        return _global_gpu_fabric


def register_tensor_provider(postal_hub) -> bool:
    """
    Register the GPU tensor fabric as a provider in SharedPostalHub.

    Call this during boot to make tensor memory available to all fairies:
        from fairies.P10_Memory.tensor_memory_fabric import register_tensor_provider
        register_tensor_provider(get_shared_postal_hub())

    Args:
        postal_hub: The SharedPostalHub instance

    Returns:
        True if registered successfully
    """
    fabric = get_global_tensor_fabric()

    if hasattr(postal_hub, 'register_provider'):
        postal_hub.register_provider("memory.tensor", fabric)
        postal_hub.register_provider("memory.gpu", fabric)  # Alias
        print(f"[TensorFabric] Registered as provider: memory.tensor, memory.gpu")
        return True
    else:
        print("[TensorFabric] Warning: postal_hub has no register_provider method")
        return False


def wire_fairy_to_tensor(fairy, tensor=None) -> bool:
    """
    Wire a fairy to use the GPU tensor memory.

    Gives the fairy these methods:
        - fairy.remember(content, mem_type, channel, tags) -> cell_id
        - fairy.recall(mem_type, channel, limit) -> [memories]
        - fairy.search_memory(query, top_k) -> [results]

    Args:
        fairy: The fairy object to wire
        tensor: Optional tensor fabric (uses global singleton if not provided)

    Returns:
        True if wired successfully
    """
    import types

    if tensor is None:
        tensor = get_global_tensor_fabric()

    is_gpu = isinstance(tensor, GPUTensorMemoryFabric)
    fairy_name = getattr(fairy, 'ACTOR_NAME', getattr(fairy, 'name', str(fairy)))

    # ═══ remember: Store a memory ═══
    def remember(self, content: Any, mem_type: str = 'semantic',
                 channel: int = 0, tags: Set[str] = None) -> str:
        """Store a memory in tensor. Returns cell_id."""
        result = tensor.store(
            content=content,
            author=fairy_name,
            mem_type=mem_type,
            channel=channel,
            tags=tags
        )
        # GPU returns string ID, CPU returns MemoryCell - normalize to ID
        if hasattr(result, 'id'):
            return result.id
        return result

    # ═══ recall: Get recent memories ═══
    def recall(self, mem_type: str = None, channel: int = None,
               limit: int = 10) -> List:
        """Recall recent memories from tensor."""
        plane = tensor._infer_plane(fairy_name)

        if is_gpu:
            # GPU version uses coordinate-based query
            plane_idx = tensor._get_plane_idx(plane)
            results = []
            with tensor._lock:
                for (p, ch, t), content in tensor._content.items():
                    if p != plane_idx:
                        continue
                    if channel is not None and ch != channel:
                        continue
                    meta = tensor._metadata.get((p, ch, t), {})
                    if mem_type and meta.get('mem_type') != mem_type:
                        continue
                    if tensor.valid[p, ch, t]:
                        results.append({
                            'content': content,
                            'plane': tensor.PLANE_NAMES[p],
                            'channel': ch,
                            'strength': float(tensor.strengths[p, ch, t]),
                            **meta
                        })
            # Sort by timestamp, return most recent
            results.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            return results[:limit]
        else:
            # CPU version uses query_plane - convert MemoryCell to dict
            cells = tensor.query_plane(
                plane=plane,
                channel=channel,
                mem_type=mem_type,
                limit=limit
            )
            return [cell.to_dict() if hasattr(cell, 'to_dict') else cell for cell in cells]

    # ═══ search_memory: Similarity search ═══
    def search_memory(self, query: Any, top_k: int = 10, plane: str = None) -> List:
        """Search memories by content similarity (GPU-accelerated)."""
        if is_gpu:
            return tensor.search_by_content(query, top_k=top_k, plane=plane)
        else:
            # CPU version doesn't have similarity search, use author-based recall
            results = tensor.query_plane(
                plane=plane or tensor._infer_plane(fairy_name),
                limit=top_k
            )
            return [cell.to_dict() if hasattr(cell, 'to_dict') else cell for cell in results]

    # Bind methods to fairy
    fairy.remember = types.MethodType(remember, fairy)
    fairy.recall = types.MethodType(recall, fairy)
    fairy.search_memory = types.MethodType(search_memory, fairy)

    # Store reference to tensor
    fairy._tensor_fabric = tensor

    return True


def auto_wire_on_boot(postal_hub):
    """
    Register the GPU tensor fabric as a provider in the postal hub.

    Call this once during system boot:
        from fairies.P10_Memory.tensor_memory_fabric import auto_wire_on_boot
        auto_wire_on_boot(get_shared_postal_hub())

    After this, fairies can:
    1. Call wire_self() in their on_boot to get remember/recall/search methods
    2. Use postal_hub.get_provider("memory.tensor") to get the raw tensor fabric
    """
    # Register the tensor fabric as a provider
    register_tensor_provider(postal_hub)
    print("[TensorFabric] Registered as provider - fairies can use wire_self() or get_provider('memory.tensor')")


def wire_self(fairy) -> bool:
    """
    Wire a fairy to tensor memory. Call this in your fairy's on_boot():

        def on_boot(self):
            from fairies.P10_Memory.tensor_memory_fabric import wire_self
            wire_self(self)
            # Now you have: self.remember(), self.recall(), self.search_memory()

    Or even simpler, if you have a postal reference:
        tensor = self.post.get_provider("memory.tensor")
        # Use tensor.store(), tensor.search_by_content(), etc. directly

    Args:
        fairy: The fairy instance (typically 'self' in on_boot)

    Returns:
        True if wired successfully
    """
    return wire_fairy_to_tensor(fairy)


def get_tensor_from_postal(postal_hub) -> Optional['GPUTensorMemoryFabric']:
    """
    Get the tensor fabric from the postal hub provider registry.

    Usage:
        from fairies.P10_Memory.tensor_memory_fabric import get_tensor_from_postal
        tensor = get_tensor_from_postal(self.post)
        if tensor:
            tensor.store("my memory", author="MyFairy")

    Args:
        postal_hub: The SharedPostalHub instance

    Returns:
        The GPUTensorMemoryFabric instance, or None if not registered
    """
    if hasattr(postal_hub, 'get_provider'):
        return postal_hub.get_provider("memory.tensor")
    return None


# Export
__all__ = [
    'TensorMemoryFabric',
    'PlaneSlice',
    'MemoryCell',
    'give_tensor_memory',
    'GPUTensorMemoryFabric',
    'create_tensor_fabric',
    'get_global_tensor_fabric',
    'register_tensor_provider',
    'wire_fairy_to_tensor',
    'wire_self',
    'get_tensor_from_postal',
    'auto_wire_on_boot',
]
