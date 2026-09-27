"""
Test GPU Memory Fabric Operations
==================================

Tests:
1. GPU tensor creation and device detection
2. Memory store and retrieve
3. GPU similarity search
4. Batch decay operations
5. Fairy wiring (remember/recall/search methods)

Run: python test_gpu_memory.py
"""

import sys
import time
from pathlib import Path

# Setup paths
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "postal_core" / "python"))


def test_gpu_memory():
    """Test GPU memory fabric operations."""
    print("=" * 60)
    print("GPU TENSOR MEMORY FABRIC TEST")
    print("=" * 60)

    # 1. Create memory fabric
    print("\n[1] Creating GPU Tensor Memory Fabric...")
    from memory import get_global_tensor_fabric, GPUTensorMemoryFabric

    fabric = get_global_tensor_fabric(force_new=True)
    stats = fabric.get_stats()

    print(f"    Device: {stats['device']}")
    print(f"    GPU: {stats['is_gpu']}")
    print(f"    Shape: {stats['shape']}")
    print(f"    Memory: {stats['memory_mb']:.1f} MB")

    is_gpu = isinstance(fabric, GPUTensorMemoryFabric)
    print(f"    Type: {'GPUTensorMemoryFabric' if is_gpu else 'TensorMemoryFabric (CPU)'}")

    # 2. Store memories
    print("\n[2] Storing test memories...")
    test_memories = [
        ("The system is booting up", "AutonomicFairy", "semantic", 0),
        ("User asked about weather", "SensoryFairy", "temporal", 5),
        ("Feeling slightly anxious about task", "SomaticFairy", "affect", 12),
        ("Learned that Python uses GIL", "MemoryFairy", "semantic", 30),
        ("Completed task successfully", "ExecutiveFairy", "temporal", 60),
    ]

    stored_ids = []
    for content, author, mem_type, channel in test_memories:
        cell_id = fabric.store(
            content=content,
            author=author,
            mem_type=mem_type,
            channel=channel,
        )
        stored_ids.append(cell_id)
        print(f"    Stored: '{content[:30]}...' -> {cell_id}")

    print(f"    Total stored: {len(stored_ids)}")

    # 3. Retrieve memories
    print("\n[3] Retrieving memories by ID...")
    for cell_id in stored_ids[:2]:
        cell = fabric.retrieve(cell_id)
        if cell:
            print(f"    {cell_id}: '{cell['content'][:30]}...' (strength: {cell['strength']:.2f})")
        else:
            print(f"    {cell_id}: NOT FOUND")

    # 4. Similarity search (GPU-accelerated)
    print("\n[4] GPU Similarity Search...")
    if is_gpu:
        query = "Tell me about the system starting"
        results = fabric.search_by_content(query, top_k=3)
        print(f"    Query: '{query}'")
        print(f"    Results:")
        for r in results:
            print(f"      - [{r['similarity']:.3f}] '{r['content'][:40]}...' (plane: {r['plane']})")
    else:
        print("    Skipped (CPU version doesn't support similarity search)")

    # 5. Batch decay
    print("\n[5] Batch Memory Decay (GPU operation)...")
    if is_gpu:
        import torch
        # Manually set some old timestamps for testing
        with torch.no_grad():
            # Make one memory "old" (1 hour ago)
            fabric.timestamps[0, 0, 0] = time.time() - 3600
            fabric.valid[0, 0, 0] = True
            fabric.strengths[0, 0, 0] = 1.0

        original_strength = float(fabric.strengths[0, 0, 0])
        fabric.decay_all(rate=0.1)  # High rate for testing
        new_strength = float(fabric.strengths[0, 0, 0])

        print(f"    Decay applied to all {stats['shape'][0] * stats['shape'][1] * stats['shape'][2]:,} cells")
        print(f"    Example: {original_strength:.3f} -> {new_strength:.3f}")
    else:
        print("    Skipped (CPU version)")

    # 6. Fairy wiring test
    print("\n[6] Fairy Wiring Test...")
    from memory import wire_fairy_to_tensor

    class MockFairy:
        name = "TestFairy"
        ACTOR_NAME = "TestFairy"

    fairy = MockFairy()
    wire_fairy_to_tensor(fairy, fabric)

    # Test remember
    cell_id = fairy.remember("Test memory from wired fairy", mem_type="semantic", channel=7)
    print(f"    fairy.remember() -> {cell_id}")

    # Test recall
    memories = fairy.recall(limit=3)
    print(f"    fairy.recall() -> {len(memories)} memories")

    # Test search
    if is_gpu:
        results = fairy.search_memory("test memory", top_k=2)
        print(f"    fairy.search_memory() -> {len(results)} results")
    else:
        print("    fairy.search_memory() -> (CPU fallback)")

    # 7. Final stats
    print("\n[7] Final Statistics...")
    final_stats = fabric.get_stats()
    print(f"    Valid cells: {final_stats['valid_cells']}")
    print(f"    Total writes: {final_stats['total_writes']}")
    print(f"    Total reads: {final_stats['total_reads']}")
    print(f"    Planes: {list(final_stats['planes'].keys())}")

    print("\n" + "=" * 60)
    print("GPU MEMORY FABRIC TEST COMPLETE")
    print("=" * 60)

    return True


def benchmark_gpu_similarity():
    """Benchmark GPU similarity search speed."""
    print("\n" + "=" * 60)
    print("GPU SIMILARITY SEARCH BENCHMARK")
    print("=" * 60)

    from memory import get_global_tensor_fabric, GPUTensorMemoryFabric

    fabric = get_global_tensor_fabric()

    if not isinstance(fabric, GPUTensorMemoryFabric):
        print("GPU not available - skipping benchmark")
        return

    # Store 1000 test memories
    print("\n[1] Storing 1000 test memories...")
    start = time.time()
    for i in range(1000):
        fabric.store(
            content=f"Test memory number {i} with some additional content",
            author="BenchmarkFairy",
            mem_type="semantic",
            channel=i % 77,
        )
    store_time = time.time() - start
    print(f"    Store time: {store_time:.2f}s ({1000/store_time:.0f} memories/sec)")

    # Benchmark similarity search
    print("\n[2] Running 100 similarity searches...")
    import torch

    query_embedding = fabric._content_to_embedding("Find something about memory")

    # Warmup
    for _ in range(10):
        fabric.similarity_search(query_embedding, top_k=10)

    # Timed run
    torch.cuda.synchronize() if fabric.is_gpu else None
    start = time.time()
    for _ in range(100):
        results = fabric.similarity_search(query_embedding, top_k=10)
    torch.cuda.synchronize() if fabric.is_gpu else None
    search_time = time.time() - start

    print(f"    Total time: {search_time*1000:.1f}ms for 100 searches")
    print(f"    Per search: {search_time*10:.2f}ms")
    print(f"    Throughput: {100/search_time:.0f} searches/sec")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_gpu_memory()
    benchmark_gpu_similarity()
