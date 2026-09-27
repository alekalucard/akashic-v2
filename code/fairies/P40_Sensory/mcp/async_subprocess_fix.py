"""
Async Subprocess Fix for MCP Server

The problem: subprocess.run() is synchronous and blocks the async event loop.
When called inside an async MCP server, it causes timeouts and hangs.

The fix: Use asyncio.to_thread() to run blocking operations in a thread pool.

ALSO: Clear PYTHONPATH to prevent import hangs from project directory.
"""

import asyncio
import subprocess
import shutil
import os
from pathlib import Path
from typing import Dict, Optional
import traceback


def _get_clean_env(extra_env: dict = None) -> dict:
    """Get a clean environment without PYTHONPATH that causes hangs."""
    env = os.environ.copy()
    # Remove PYTHONPATH - it points to project root and causes import hangs
    env.pop('PYTHONPATH', None)
    if extra_env:
        env.update(extra_env)
    return env


def _find_python() -> str:
    """Find a working Python executable."""
    # DIRECT PATH FIRST - the actual Python, not the launcher shim
    # The bin\ directory contains launchers that can cause issues
    direct_python = r"C:\Users\Ace\AppData\Local\Python\pythoncore-3.14-64\python.exe"
    if Path(direct_python).exists():
        return direct_python
    
    # Try 'python' in PATH
    python_path = shutil.which("python")
    if python_path:
        return python_path
    
    # Try 'py' launcher (Windows Python 3.14+ installer)
    py_path = shutil.which("py")
    if py_path:
        return py_path
    
    # Known locations (in order of preference)
    candidates = [
        r"C:\Users\Ace\AppData\Local\Python\pythoncore-3.14-64\python.exe",  # actual python
        r"C:\Users\Ace\AppData\Local\Python\bin\python.exe",  # launcher shim
        r"C:\Users\Ace\AppData\Local\Programs\Python\Python314\python.exe",
        r"C:\Users\Ace\AppData\Local\Programs\Python\Python311\python.exe",
        r"C:\Python314\python.exe",
        r"C:\Python311\python.exe",
    ]
    
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    
    # Fallback
    return "python"


async def run_shell_async(
    command: str,
    cwd: str = None,
    timeout: int = 60,
    env: dict = None
) -> Dict:
    """
    Run a shell command asynchronously (doesn't block the event loop).
    """
    clean_env = _get_clean_env(env)
    
    def _run_sync():
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=clean_env,
                stdin=subprocess.DEVNULL,  # CRITICAL: Close stdin to prevent hangs
            )
            return {
                "success": result.returncode == 0,
                "return_code": result.returncode,
                "stdout": result.stdout[-5000:] if result.stdout else "",
                "stderr": result.stderr[-2000:] if result.stderr else "",
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {timeout}s", "success": False}
        except Exception as e:
            return {"error": str(e), "traceback": traceback.format_exc(), "success": False}
    
    return await asyncio.to_thread(_run_sync)


async def run_python_async(
    code: str,
    python_exe: str = None,
    cwd: str = None,
    timeout: int = 30,
    script_name: str = "_async_temp.py"
) -> Dict:
    """
    Run Python code asynchronously.
    """
    if python_exe is None:
        python_exe = _find_python()
    
    if cwd is None:
        cwd = r"F:\Sandbox\ebook"
    
    script_path = Path(cwd) / script_name
    clean_env = _get_clean_env()
    
    def _run_sync():
        try:
            script_path.write_text(code, encoding='utf-8')
            
            result = subprocess.run(
                [python_exe, str(script_path)],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=clean_env,
                stdin=subprocess.DEVNULL,  # CRITICAL: Close stdin to prevent hangs
            )
            
            return {
                "success": result.returncode == 0,
                "return_code": result.returncode,
                "stdout": result.stdout[-5000:] if result.stdout else "",
                "stderr": result.stderr[-2000:] if result.stderr else "",
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Script timed out after {timeout}s", "success": False}
        except Exception as e:
            return {"error": str(e), "traceback": traceback.format_exc(), "success": False}
        finally:
            if script_path.exists():
                try:
                    script_path.unlink()
                except:
                    pass
    
    return await asyncio.to_thread(_run_sync)


def run_shell_sync(command: str, cwd: str = None, timeout: int = 60) -> Dict:
    """Synchronous shell wrapper."""
    clean_env = _get_clean_env()
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=clean_env,
            stdin=subprocess.DEVNULL,
        )
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout[-5000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout}s", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


def run_python_sync(code: str, timeout: int = 30) -> Dict:
    """Synchronous Python wrapper."""
    python_exe = _find_python()
    cwd = r"F:\Sandbox\ebook"
    script_path = Path(cwd) / "_sync_temp.py"
    clean_env = _get_clean_env()
    
    try:
        script_path.write_text(code, encoding='utf-8')
        
        result = subprocess.run(
            [python_exe, str(script_path)],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=clean_env,
            stdin=subprocess.DEVNULL,
        )
        
        return {
            "success": result.returncode == 0,
            "return_code": result.returncode,
            "stdout": result.stdout[-5000:] if result.stdout else "",
            "stderr": result.stderr[-2000:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Script timed out after {timeout}s", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}
    finally:
        if script_path.exists():
            try:
                script_path.unlink()
            except:
                pass
