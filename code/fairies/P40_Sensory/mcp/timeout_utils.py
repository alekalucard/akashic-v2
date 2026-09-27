"""
MCP Timeout Wrappers - Prevent tools from hanging forever

Provides decorators and utilities to add timeouts to MCP tools,
so they return errors instead of hanging indefinitely.
"""

import asyncio
import json
import time
from functools import wraps
from typing import Optional, Callable, Any
import sys


# Default timeouts by operation type
TIMEOUTS = {
    "quick": 5.0,      # Simple reads, status checks
    "standard": 30.0,   # Most operations
    "long": 120.0,      # Complex operations, searches
    "dangerous": 300.0  # Only for explicitly long tasks
}


def with_timeout(seconds: float = 30.0, operation_name: str = ""):
    """
    Decorator that adds timeout to async MCP tools.
    
    If the tool takes longer than `seconds`, returns a timeout error
    instead of hanging forever.
    
    Usage:
        @mcp.tool()
        @with_timeout(30.0)
        async def my_tool():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            op_name = operation_name or func.__name__
            start_time = time.time()
            
            try:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
                return result
                
            except asyncio.TimeoutError:
                elapsed = time.time() - start_time
                return json.dumps({
                    "error": "TIMEOUT",
                    "tool": op_name,
                    "elapsed_seconds": round(elapsed, 2),
                    "timeout_seconds": seconds,
                    "message": f"Tool '{op_name}' timed out after {seconds}s",
                    "suggestions": [
                        "Try breaking this into smaller steps",
                        "Check if target resource is accessible",
                        "Try an alternative approach",
                        "If this keeps happening, ask Ace"
                    ]
                }, indent=2)
                
            except Exception as e:
                elapsed = time.time() - start_time
                return json.dumps({
                    "error": "EXCEPTION",
                    "tool": op_name,
                    "elapsed_seconds": round(elapsed, 2),
                    "exception_type": type(e).__name__,
                    "message": str(e),
                    "suggestions": [
                        "Check the error message for clues",
                        "Try a different approach",
                        "Search memory for past solutions"
                    ]
                }, indent=2)
                
        return wrapper
    return decorator


def sync_with_timeout(seconds: float = 30.0, operation_name: str = ""):
    """
    Decorator for sync functions that might hang.
    
    Uses threading to implement timeout for synchronous code.
    """
    import threading
    import queue
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            op_name = operation_name or func.__name__
            result_queue = queue.Queue()
            exception_queue = queue.Queue()
            
            def target():
                try:
                    result = func(*args, **kwargs)
                    result_queue.put(result)
                except Exception as e:
                    exception_queue.put(e)
            
            thread = threading.Thread(target=target, daemon=True)
            start_time = time.time()
            thread.start()
            thread.join(timeout=seconds)
            
            if thread.is_alive():
                # Thread is still running - timeout
                elapsed = time.time() - start_time
                return json.dumps({
                    "error": "TIMEOUT",
                    "tool": op_name,
                    "elapsed_seconds": round(elapsed, 2),
                    "timeout_seconds": seconds,
                    "message": f"Tool '{op_name}' timed out after {seconds}s",
                    "note": "Background thread may still be running",
                    "suggestions": [
                        "Try breaking this into smaller steps",
                        "Check if target resource is accessible",
                        "Try an alternative approach"
                    ]
                }, indent=2)
            
            # Check for exception
            if not exception_queue.empty():
                e = exception_queue.get()
                return json.dumps({
                    "error": "EXCEPTION",
                    "tool": op_name,
                    "exception_type": type(e).__name__,
                    "message": str(e)
                }, indent=2)
            
            # Get result
            if not result_queue.empty():
                return result_queue.get()
            
            return json.dumps({"error": "NO_RESULT", "tool": op_name})
            
        return wrapper
    return decorator


class OperationTracker:
    """
    Track operations to detect loops and hangs.
    
    Maintains history of what's been tried and can detect:
    - Repeated identical operations
    - Slow operations that might hang
    - Patterns that lead to failure
    """
    
    def __init__(self, max_history: int = 100):
        self.history = []
        self.max_history = max_history
        self.slow_operations = {}  # op_name -> avg_time
        
    def record(self, operation: str, args: dict, outcome: str, 
               duration: float, error: Optional[str] = None):
        """Record an operation attempt."""
        entry = {
            "operation": operation,
            "args_hash": hash(json.dumps(args, sort_keys=True, default=str)),
            "args_summary": str(args)[:200],
            "outcome": outcome,
            "duration": duration,
            "error": error,
            "time": time.time()
        }
        
        self.history.append(entry)
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        # Track slow operations
        if operation not in self.slow_operations:
            self.slow_operations[operation] = []
        self.slow_operations[operation].append(duration)
        # Keep last 10
        self.slow_operations[operation] = self.slow_operations[operation][-10:]
    
    def is_repeated(self, operation: str, args: dict, lookback: int = 5) -> bool:
        """Check if this exact operation+args was tried recently."""
        args_hash = hash(json.dumps(args, sort_keys=True, default=str))
        
        recent = self.history[-lookback:] if len(self.history) >= lookback else self.history
        for entry in recent:
            if entry["operation"] == operation and entry["args_hash"] == args_hash:
                return True
        return False
    
    def get_failure_count(self, operation: str, lookback: int = 10) -> int:
        """Count recent failures for an operation."""
        recent = self.history[-lookback:] if len(self.history) >= lookback else self.history
        return sum(1 for e in recent if e["operation"] == operation and e["outcome"] == "failed")
    
    def estimate_duration(self, operation: str) -> Optional[float]:
        """Estimate how long an operation will take based on history."""
        if operation in self.slow_operations and self.slow_operations[operation]:
            return sum(self.slow_operations[operation]) / len(self.slow_operations[operation])
        return None
    
    def detect_loop(self, lookback: int = 6) -> Optional[dict]:
        """Detect if we're in a loop (same operation repeated with failures)."""
        if len(self.history) < lookback:
            return None
        
        recent = self.history[-lookback:]
        
        # Check for repeated same operation with same args
        ops = [(e["operation"], e["args_hash"]) for e in recent]
        unique_ops = set(ops)
        
        if len(unique_ops) <= 2:  # Only 1-2 unique operations in last N
            # Check if they're failing
            failures = sum(1 for e in recent if e["outcome"] == "failed")
            if failures >= lookback // 2:
                return {
                    "loop_detected": True,
                    "repeated_operations": list(unique_ops),
                    "failure_rate": failures / lookback,
                    "suggestion": "You're repeating the same failing approach. Try something different!"
                }
        
        return None
    
    def get_summary(self) -> dict:
        """Get summary of operation history."""
        if not self.history:
            return {"total": 0}
        
        total = len(self.history)
        successes = sum(1 for e in self.history if e["outcome"] == "success")
        failures = sum(1 for e in self.history if e["outcome"] == "failed")
        timeouts = sum(1 for e in self.history if e["outcome"] == "timeout")
        
        return {
            "total": total,
            "successes": successes,
            "failures": failures,
            "timeouts": timeouts,
            "success_rate": round(successes / total, 2) if total > 0 else 0,
            "loop_detected": self.detect_loop() is not None
        }
    
    def save(self, path: str = "state/nous_workspace/operation_tracker.json"):
        """Save tracker state to file."""
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump({
                "history": self.history[-50:],  # Save last 50
                "slow_operations": self.slow_operations,
                "summary": self.get_summary()
            }, f, indent=2)
    
    def load(self, path: str = "state/nous_workspace/operation_tracker.json"):
        """Load tracker state from file."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                self.history = data.get("history", [])
                self.slow_operations = data.get("slow_operations", {})
        except FileNotFoundError:
            pass


# Global tracker instance
_tracker: Optional[OperationTracker] = None

def get_operation_tracker() -> OperationTracker:
    """Get the global operation tracker."""
    global _tracker
    if _tracker is None:
        _tracker = OperationTracker()
        _tracker.load()
    return _tracker


def check_before_operation(operation: str, args: dict) -> Optional[dict]:
    """
    Check if an operation should be attempted.
    
    Returns warning dict if there's a concern, None if OK to proceed.
    """
    tracker = get_operation_tracker()
    
    # Check for repeated operation
    if tracker.is_repeated(operation, args):
        return {
            "warning": "REPEATED_OPERATION",
            "message": f"You just tried '{operation}' with these same arguments",
            "suggestion": "Try a different approach or different arguments"
        }
    
    # Check for high failure rate
    failure_count = tracker.get_failure_count(operation)
    if failure_count >= 3:
        return {
            "warning": "HIGH_FAILURE_RATE",
            "message": f"'{operation}' has failed {failure_count} times recently",
            "suggestion": "Consider an alternative approach"
        }
    
    # Check for loop
    loop = tracker.detect_loop()
    if loop:
        return {
            "warning": "LOOP_DETECTED",
            "message": "You appear to be stuck in a loop",
            "details": loop,
            "suggestion": "Step back and try a completely different approach"
        }
    
    return None


# Export for MCP server
__all__ = [
    'with_timeout', 
    'sync_with_timeout', 
    'TIMEOUTS',
    'OperationTracker',
    'get_operation_tracker',
    'check_before_operation'
]
