"""
MCP Thread Pool Configuration

Provides concurrent execution for blocking MCP tool operations.
This wraps tool functions to run in a thread pool, preventing
one slow tool from blocking all others.

Usage in akashic_mcp_server.py:
    from mcp_thread_pool import async_tool, get_thread_pool
    
    @mcp.tool()
    @async_tool
    def my_slow_tool():
        # This will run in thread pool
        ...

Configuration:
    Set AKASHIC_MCP_WORKERS environment variable (default: CPU_count + 4, max 32)
"""

import os
import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any

# =============================================================================
# WORKER POOL CONFIGURATION
# =============================================================================

# Sensible default: CPU count + 4 for I/O bound work
# Python's GIL and OS thread scheduling make >100 threads wasteful
# For I/O bound: 2-4x CPU cores is optimal
# For mixed workloads: CPU + 4 (Python's ThreadPoolExecutor default)
# Can override via AKASHIC_MCP_WORKERS environment variable
DEFAULT_WORKERS = min(32, (os.cpu_count() or 4) + 4)
MAX_WORKERS = int(os.getenv("AKASHIC_MCP_WORKERS", DEFAULT_WORKERS))

# Global thread pool
_thread_pool: ThreadPoolExecutor = None


def get_thread_pool() -> ThreadPoolExecutor:
    """Get or create the global thread pool."""
    global _thread_pool
    if _thread_pool is None:
        _thread_pool = ThreadPoolExecutor(
            max_workers=MAX_WORKERS,
            thread_name_prefix="akashic-mcp-"
        )
        import sys
        sys.stderr.write(f"[MCP]  Thread pool initialized with {MAX_WORKERS:,} workers\n")
    return _thread_pool


def shutdown_thread_pool():
    """Shutdown the thread pool gracefully."""
    global _thread_pool
    if _thread_pool:
        _thread_pool.shutdown(wait=False)
        _thread_pool = None


def async_tool(func: Callable) -> Callable:
    """
    Decorator to run a blocking tool function in the thread pool.
    
    This allows multiple tool calls to execute concurrently even
    if they contain blocking I/O (file reads, network calls, etc.)
    
    Usage:
        @mcp.tool()
        @async_tool
        def read_large_file(path: str):
            # This runs in thread pool
            return Path(path).read_text()
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        pool = get_thread_pool()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(pool, lambda: func(*args, **kwargs))
    return wrapper


def get_pool_stats() -> dict:
    """Get current thread pool statistics."""
    pool = get_thread_pool()
    return {
        "max_workers": MAX_WORKERS,
        "active_threads": len([t for t in pool._threads if t.is_alive()]) if hasattr(pool, '_threads') else "unknown",
        "queue_size": pool._work_queue.qsize() if hasattr(pool, '_work_queue') else "unknown",
    }


# =============================================================================
# CONFIGURATION HELPERS
# =============================================================================

def set_worker_count(count: int):
    """
    Update worker count (requires restart to take effect on existing pool).
    
    Call this BEFORE any tools are executed if you want to change the default.
    """
    global MAX_WORKERS, _thread_pool
    MAX_WORKERS = count
    
    # If pool exists, recreate it
    if _thread_pool:
        old_pool = _thread_pool
        _thread_pool = ThreadPoolExecutor(
            max_workers=MAX_WORKERS,
            thread_name_prefix="akashic-mcp-"
        )
        old_pool.shutdown(wait=False)
        
    import sys
    sys.stderr.write(f"[MCP]  Worker count set to {MAX_WORKERS:,}\n")


# =============================================================================
# GPU ACCELERATION (requires torch)
# =============================================================================

_cuda_available = None
_cuda_info = None

def check_cuda() -> bool:
    """Check if CUDA is available for GPU acceleration.

    Uses nvidia-smi instead of torch to avoid loading 3.6GB of CUDA DLLs.
    """
    global _cuda_available, _cuda_info
    if _cuda_available is None:
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,compute_cap,gpu_bus_id",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = [p.strip() for p in result.stdout.strip().split(",")]
                _cuda_available = True
                _cuda_info = {
                    "device_name": parts[0] if len(parts) > 0 else "unknown",
                    "total_memory_gb": round(float(parts[1]) / 1024, 1) if len(parts) > 1 else 0,
                    "compute_capability": parts[2] if len(parts) > 2 else "unknown",
                }
                import sys
                sys.stderr.write(f"[MCP]  CUDA available: {_cuda_info['device_name']}\n")
            else:
                _cuda_available = False
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            _cuda_available = False
    return _cuda_available


def get_gpu_info() -> dict:
    """Get GPU information if available.

    Uses nvidia-smi instead of torch to avoid loading 3.6GB of CUDA DLLs.
    """
    if not check_cuda():
        return {"available": False}

    return {
        "available": True,
        **(_cuda_info or {}),
    }


if __name__ == "__main__":
    print(f"Default workers: {DEFAULT_WORKERS:,}")
    print(f"GPU info: {get_gpu_info()}")
