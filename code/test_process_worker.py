"""Test the FairyWorkerPool (must be a real file for Windows multiprocessing)."""
import os
import sys
import time

sys.path.insert(0, '.')


# Top-level functions MUST be in a real module for Windows spawn
def heavy_math(n):
    """Simulate heavy computation in worker process."""
    import math
    total = 0
    for i in range(n):
        total += math.sqrt(i) * math.sin(i)
    return {'result': total, 'pid': os.getpid()}


def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)


def failing_fn():
    raise ValueError('test error')


def simulate_cortex_bind(data):
    """Simulate what a fairy would offload: concept graph traversal.

    This represents the kind of CPU-bound work that holds the GIL
    and starves 160+ other threads when run in the main process.
    """
    import math
    concepts = data['concepts']
    depth = data.get('depth', 3)

    # Simulate graph traversal with heavy math
    scores = {}
    for concept in concepts:
        score = 0.0
        for d in range(depth):
            for i in range(5000):
                score += math.sin(hash(concept + str(i)) % 1000) * math.exp(-d * 0.5)
        scores[concept] = round(score, 4)

    return {
        'scores': scores,
        'depth': depth,
        'pid': os.getpid(),
        'concept_count': len(concepts),
    }


if __name__ == '__main__':
    from infrastructure.process_worker import FairyWorkerPool

    pool = FairyWorkerPool(max_workers=2, name='test-pool')

    print('=== Test 1: Basic submit ===')
    main_pid = os.getpid()
    print(f'  Main process PID: {main_pid}')
    future = pool.submit(heavy_math, 100000)
    result = future.result(timeout=10)
    worker_pid = result['pid']
    print(f'  Worker process PID: {worker_pid}')
    print(f'  Different process: {main_pid != worker_pid}')
    assert main_pid != worker_pid, 'Should run in different process!'

    print()
    print('=== Test 2: Concurrent submissions ===')
    t0 = time.time()
    futures = [pool.submit(heavy_math, 200000) for _ in range(4)]
    results = [f.result(timeout=30) for f in futures]
    elapsed = (time.time() - t0) * 1000
    pids = set(r['pid'] for r in results)
    print(f'  4 tasks completed in {elapsed:.0f}ms')
    print(f'  Worker PIDs used: {pids} ({len(pids)} processes)')

    print()
    print('=== Test 3: Named workers ===')
    pool.register_worker('fib', fibonacci)
    future = pool.run('fib', 30)
    result = future.result(timeout=10)
    print(f'  fibonacci(30) = {result}')
    assert result == 832040

    print()
    print('=== Test 4: Error handling ===')
    future = pool.submit(failing_fn)
    try:
        future.result(timeout=5)
        print('  ERROR: Should have raised!')
    except ValueError as e:
        print(f'  Caught error: {e}')

    print()
    print('=== Test 5: Status ===')
    status = pool.status()
    print(f'  {status}')

    print()
    print('=== Test 6: Simulated fairy offload (cortex bind) ===')
    concepts = ['joy', 'warmth', 'sunlight', 'golden', 'wings', 'freedom', 'flight', 'sky']
    payload = {'concepts': concepts, 'depth': 4}

    # Time in-process (GIL-blocking) vs worker process
    t0 = time.time()
    in_proc_result = simulate_cortex_bind(payload)
    in_proc_ms = (time.time() - t0) * 1000
    print(f'  In-process: {in_proc_ms:.0f}ms (blocks GIL the entire time!)')
    print(f'    PID: {in_proc_result["pid"]} (same as main: {in_proc_result["pid"] == main_pid})')

    t0 = time.time()
    future = pool.submit(simulate_cortex_bind, payload)
    worker_result = future.result(timeout=30)
    worker_ms = (time.time() - t0) * 1000
    print(f'  Worker process: {worker_ms:.0f}ms (GIL FREE — main thread unblocked!)')
    print(f'    PID: {worker_result["pid"]} (different from main: {worker_result["pid"] != main_pid})')
    print(f'    Scores: {list(worker_result["scores"].items())[:3]}...')

    # Verify results structure matches (exact values differ due to per-process hash seeds)
    assert set(in_proc_result['scores'].keys()) == set(worker_result['scores'].keys()), \
        'Key mismatch between in-process and worker results'
    assert in_proc_result['concept_count'] == worker_result['concept_count']
    assert worker_result['pid'] != main_pid, 'Worker should run in different process'
    print(f'  Structure match: True (values differ due to per-process hash seeds — expected)')
    print(f'  Key point: main process GIL was FREE during worker computation')

    print()
    print('=== Test 7: Callback pattern (non-blocking fairy integration) ===')
    results_collected = []
    done_event = __import__('threading').Event()

    def on_fairy_result(future):
        """This is how a fairy would handle the result — called in callback thread."""
        try:
            result = future.result()
            results_collected.append(result)
            print(f'  [callback] Got result from PID {result["pid"]}: '
                  f'{result["concept_count"]} concepts scored')
        except Exception as e:
            print(f'  [callback] Worker error: {e}')
        done_event.set()

    future = pool.submit(simulate_cortex_bind, {'concepts': ['alpha', 'beta'], 'depth': 2})
    future.add_done_callback(on_fairy_result)

    # Main thread is FREE to do other work here!
    print('  Main thread: doing other work while worker computes...')
    done_event.wait(timeout=10)
    assert len(results_collected) == 1, 'Should have collected 1 result via callback'
    print(f'  Callback pattern works: {len(results_collected)} result collected')

    pool.shutdown()
    print()
    print('ALL TESTS PASSED')
