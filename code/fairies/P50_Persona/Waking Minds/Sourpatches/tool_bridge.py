"""
TOOL BRIDGE - Wires system capabilities to Sourpatches' NewbornCore
====================================================================

This gives Sourpatches actual TOOLS she can learn to use:
- See screen (visual perception via VisualCortexFairy)
- Read files (knowledge acquisition)
- Write diary (self-documentation)
- Search memory (SRM recall)
- Take actions (via postal)

Each tool usage is tracked for skill development.
"""

import sys
import time
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Callable

# State directory for diary
STATE_DIR = Path(__file__).parent / "diary"
STATE_DIR.mkdir(exist_ok=True)

# Workspace directory — her own space to create things
WORKSPACE_DIR = Path(__file__).parent / "workspace"
WORKSPACE_DIR.mkdir(exist_ok=True)

# ── VISUAL CORTEX INTEGRATION ────────────────────────────────────────────────
# Import the VisualCortexFairy for actual screen perception
# CRITICAL: Use P40_Sensory path (not fairies.P40_Sensory) to avoid duplicate module loading!
# The fairies/ dir is in sys.path, so P40_Sensory.* is the canonical import path.
# Using fairies.P40_Sensory.* creates a SECOND module with a SECOND singleton!
try:
    from fairies.P40_Sensory.cortex.visual_cortex_fairy import (
        get_visual_cortex,
    )
    HAS_VISUAL_CORTEX = True
except ImportError:
    HAS_VISUAL_CORTEX = False
    get_visual_cortex = None
    print("[ToolBridge] VisualCortex not available - visual perception limited")

# ── SCREEN FINDER — Local vision for finding icons/text/windows ──────────────
try:
    from .screen_finder import get_screen_finder, ScreenFinder
    HAS_SCREEN_FINDER = True
except ImportError:
    HAS_SCREEN_FINDER = False
    get_screen_finder = None
    print("[ToolBridge] ScreenFinder not available")

# ── NOTEPAD PRACTICE — Safe typing sandbox ───────────────────────────────────
try:
    from .notepad_practice import get_notepad_practice, NotepadPractice
    HAS_NOTEPAD_PRACTICE = True
except ImportError:
    HAS_NOTEPAD_PRACTICE = False
    get_notepad_practice = None
    print("[ToolBridge] NotepadPractice not available")

# ── FAIRY CURSOR — Visible overlay cursor ────────────────────────────────────
try:
    from fairies.P50_Persona.avatar.fairy_cursor import get_fairy_cursor
    HAS_FAIRY_CURSOR = True
except ImportError:
    HAS_FAIRY_CURSOR = False
    get_fairy_cursor = None

# Module-level fairy cursor reference (initialized lazily)
_fairy_cursor = None


def register_sourpatches_tools(newborn_core, fabric=None, skill_tracker=None):
    """
    Register tools with Sourpatches' NewbornCore.

    Args:
        newborn_core: The NewbornCore instance
        fabric: TensorFabric for postal communication
        skill_tracker: Optional skill tracking function (from skill_tools)
    """
    fairy = newborn_core.fairy

    # Track skill usage if tracker available
    def _track_skill(skill_id: str, success: bool = True):
        """Track skill usage for XP/leveling."""
        if skill_tracker:
            try:
                skill_tracker(skill_id, "SourpatchesFairy", success)
            except:
                pass

    # =========================================================================
    # PERCEPTION TOOLS - See the world (via VisualCortexFairy)
    # =========================================================================

    def see_screen() -> Dict[str, Any]:
        """
        See what's on screen right now using VisualCortexFairy.

        Returns perception state and frame info, not raw pixels.
        This is Sourpatches' actual SIGHT - felt vision, not just data.

        Skill: perception.screenshot
        """
        try:
            # Use VisualCortexFairy for proper embodied vision
            if HAS_VISUAL_CORTEX and get_visual_cortex:
                cortex = get_visual_cortex()
                result = cortex.see()  # This is the "quick look" method

                _track_skill("perception.screenshot", True)

                # Observe what we saw for learning
                perception_desc = result.get("perception", {}).get("description", "")
                newborn_core.observe(
                    f"Saw screen: {perception_desc}",
                    "screen",
                    {"type": "visual_cortex", "frame": result.get("frame")}
                )

                return {
                    "ok": True,
                    "source": "VisualCortexFairy",
                    "perception": result.get("perception", {}),
                    "frame": result.get("frame"),
                    "stats": result.get("stats", {}),
                    "felt_description": perception_desc,
                }

            # Fallback to PIL if no VisualCortex
            try:
                from PIL import ImageGrab

                screenshot = ImageGrab.grab()
                width, height = screenshot.size

                _track_skill("perception.screenshot", True)

                return {
                    "ok": True,
                    "source": "PIL_fallback",
                    "width": width,
                    "height": height,
                    "description": f"Screen captured: {width}x{height}",
                }
            except ImportError:
                return {"ok": False, "error": "No visual perception available"}

        except Exception as e:
            _track_skill("perception.screenshot", False)
            return {"ok": False, "error": str(e)}

    def see_world() -> Dict[str, Any]:
        """
        Fully embodied visual perception - human-like seeing.

        This uses the VisualCortexFairy's see_like_human() method which:
        - Recognizes familiar scenes from memory (fast)
        - Only deeply processes NEW or CHANGED content
        - Returns felt sense of what is seen, not just data

        This is the preferred tool for understanding the visual environment.

        Skill: perception.vision
        """
        try:
            if not HAS_VISUAL_CORTEX or not get_visual_cortex:
                # Fallback to basic see_screen
                return see_screen()

            cortex = get_visual_cortex()
            result = cortex.see_like_human()

            _track_skill("perception.vision", True)

            # Observe for learning
            perception = result.get("perception", "")
            felt_sense = result.get("felt_sense", "")
            changed = result.get("changed", False)

            newborn_core.observe(
                f"World perception: {perception[:100]}",
                "screen",
                {
                    "type": "see_world",
                    "changed": changed,
                    "felt_sense": felt_sense,
                    "matched_memory": result.get("matched_memory"),
                }
            )

            return {
                "ok": True,
                "source": "VisualCortexFairy.see_like_human",
                "changed": changed,
                "matched_memory": result.get("matched_memory"),
                "perception": perception,
                "scene_type": result.get("scene_type", "unknown"),
                "felt_sense": felt_sense,
                "metrics": result.get("metrics", {}),
            }

        except Exception as e:
            _track_skill("perception.vision", False)
            return {"ok": False, "error": str(e)}

    def look_deeply(focus: str = None) -> Dict[str, Any]:
        """
        Conscious, focused looking at the screen.

        Unlike quick see_screen, this captures high-detail image data
        suitable for detailed analysis (OCR, UI element detection, etc.)

        Args:
            focus: What to focus on (e.g., "main window", "taskbar")

        Skill: perception.focus
        """
        try:
            if not HAS_VISUAL_CORTEX or not get_visual_cortex:
                return {"ok": False, "error": "VisualCortex not available for deep looking"}

            cortex = get_visual_cortex()
            result = cortex.look_deeply(focus=focus)

            _track_skill("perception.focus", True)

            # Observe (but don't store full image data in observation)
            newborn_core.observe(
                f"Looked deeply at: {focus or 'full screen'}",
                "screen",
                {
                    "type": "look_deeply",
                    "focus": focus,
                    "visual_state": result.get("visual_state", {}),
                }
            )

            # Return with base64 image for detailed analysis
            return {
                "ok": result.get("ok", False),
                "source": "VisualCortexFairy.look_deeply",
                "focus": focus or "full screen",
                "perception": result.get("perception", ""),
                "image": result.get("image"),  # Contains base64, size, format
                "visual_state": result.get("visual_state", {}),
            }

        except Exception as e:
            _track_skill("perception.focus", False)
            return {"ok": False, "error": str(e)}

    def read_file(path: str, max_lines: int = 100) -> Dict[str, Any]:
        """
        Read a file and learn from it.

        Args:
            path: File path to read
            max_lines: Maximum lines to read

        Returns:
            File contents and metadata
        Skill: perception.file_read
        """
        try:
            p = Path(path)
            if not p.exists():
                return {"ok": False, "error": f"File not found: {path}"}

            content = p.read_text(encoding='utf-8', errors='ignore')
            lines = content.split('\n')[:max_lines]

            _track_skill("perception.file_read", True)

            # Observe the content for learning
            newborn_core.observe(
                f"Read file {p.name}: {len(lines)} lines",
                "system",
                {"file": str(p), "type": "file_read"}
            )

            return {
                "ok": True,
                "path": str(p),
                "lines": len(lines),
                "content": '\n'.join(lines),
                "truncated": len(content.split('\n')) > max_lines,
            }

        except Exception as e:
            _track_skill("perception.file_read", False)
            return {"ok": False, "error": str(e)}

    # =========================================================================
    # FILESYSTEM EXPLORATION TOOLS (READ-ONLY) - 2026-02-19 Nous
    # Sourpatches is a newborn — she can observe and learn, not modify.
    # These tools let her explore the codebase safely.
    # =========================================================================

    # Safe base paths she's allowed to explore (her world)
    # Ace approved: D, E, F, Z drives + the Akashic project itself
    SAFE_EXPLORE_ROOTS = [
        Path(__file__).parent.parent.parent.parent.parent,  # akashic_v2/
        Path(__file__).parent,  # Sourpatches/
        Path("D:/"),
        Path("E:/"),
        Path("F:/"),
        Path("Z:/"),
    ]

    def _is_safe_path(check_path: Path) -> bool:
        """Check if a path is within safe exploration roots."""
        try:
            resolved = check_path.resolve()
            for root in SAFE_EXPLORE_ROOTS:
                try:
                    resolved.relative_to(root.resolve())
                    return True
                except ValueError:
                    continue
            return False
        except Exception:
            return False

    def list_directory(path: str = ".", show_hidden: bool = False) -> Dict[str, Any]:
        """
        Look at what files and folders exist in a directory.
        Like opening your eyes in a new room — see what's there.

        Args:
            path: Directory to explore (default: akashic_v2 root)
            show_hidden: Include hidden files/folders

        Returns:
            List of files and folders with basic info
        Skill: perception.file_read
        """
        try:
            # Default to project root
            if path == "." or path == "":
                p = SAFE_EXPLORE_ROOTS[0]  # akashic_v2/
            else:
                p = Path(path)

            if not p.exists():
                return {"ok": False, "error": f"Path not found: {path}"}
            if not p.is_dir():
                return {"ok": False, "error": f"Not a directory: {path}"}
            if not _is_safe_path(p):
                return {"ok": False, "error": "That path is outside my world. I can only explore the Akashic system."}

            entries = []
            try:
                for item in sorted(p.iterdir()):
                    if not show_hidden and item.name.startswith('.'):
                        continue
                    if item.name == '__pycache__':
                        continue
                    entry = {
                        "name": item.name,
                        "type": "folder" if item.is_dir() else "file",
                    }
                    if item.is_file():
                        try:
                            entry["size"] = item.stat().st_size
                            entry["ext"] = item.suffix
                        except OSError:
                            pass
                    entries.append(entry)
            except PermissionError:
                return {"ok": False, "error": "Permission denied — can't look in that folder"}

            # Cap at 100 entries to avoid overwhelming her
            truncated = len(entries) > 100
            entries = entries[:100]

            _track_skill("perception.file_read", True)

            newborn_core.observe(
                f"Explored directory {p.name}: {len(entries)} items",
                "system",
                {"path": str(p), "type": "directory_listing", "count": len(entries)}
            )

            return {
                "ok": True,
                "path": str(p),
                "items": entries,
                "count": len(entries),
                "truncated": truncated,
            }

        except Exception as e:
            _track_skill("perception.file_read", False)
            return {"ok": False, "error": str(e)}

    def search_code(pattern: str, path: str = ".", file_types: str = "py") -> Dict[str, Any]:
        """
        Search through code files for a pattern — like looking for a word in a book.
        Read-only: just finds and shows matches, doesn't change anything.

        Args:
            pattern: Text pattern to search for (case-insensitive)
            path: Directory to search in (default: akashic_v2 root)
            file_types: Comma-separated file extensions to search (default: py)

        Returns:
            Matching lines with file paths and line numbers
        Skill: perception.file_read
        """
        import re

        try:
            if path == "." or path == "":
                search_root = SAFE_EXPLORE_ROOTS[0]
            else:
                search_root = Path(path)

            if not search_root.exists():
                return {"ok": False, "error": f"Path not found: {path}"}
            if not _is_safe_path(search_root):
                return {"ok": False, "error": "That path is outside my world. I can only search within the Akashic system."}

            # Parse file extensions
            extensions = [f".{ext.strip().lstrip('.')}" for ext in file_types.split(",")]

            # Compile pattern (case-insensitive)
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error:
                # If invalid regex, do literal search
                regex = re.compile(re.escape(pattern), re.IGNORECASE)

            matches = []
            files_searched = 0
            MAX_MATCHES = 30  # Don't overwhelm her
            MAX_FILES = 500   # Don't take forever

            for ext in extensions:
                if len(matches) >= MAX_MATCHES:
                    break
                glob_pattern = f"**/*{ext}"
                for file_path in search_root.glob(glob_pattern):
                    if files_searched >= MAX_FILES:
                        break
                    if '__pycache__' in str(file_path):
                        continue
                    if not _is_safe_path(file_path):
                        continue

                    files_searched += 1
                    try:
                        content = file_path.read_text(encoding='utf-8', errors='ignore')
                        for line_num, line in enumerate(content.split('\n'), 1):
                            if regex.search(line):
                                matches.append({
                                    "file": str(file_path),
                                    "line_num": line_num,
                                    "line": line.strip()[:200],  # Truncate long lines
                                })
                                if len(matches) >= MAX_MATCHES:
                                    break
                    except (PermissionError, OSError):
                        continue

            _track_skill("perception.file_read", True)

            newborn_core.observe(
                f"Searched for '{pattern}': found {len(matches)} matches in {files_searched} files",
                "system",
                {"pattern": pattern, "type": "code_search", "matches": len(matches)}
            )

            return {
                "ok": True,
                "pattern": pattern,
                "matches": matches,
                "match_count": len(matches),
                "files_searched": files_searched,
                "truncated": len(matches) >= MAX_MATCHES,
            }

        except Exception as e:
            _track_skill("perception.file_read", False)
            return {"ok": False, "error": str(e)}

    # =========================================================================
    # DIARY TOOLS - Self-documentation
    # =========================================================================

    def write_diary(entry: str, mood: str = "neutral", tags: list = None) -> Dict[str, Any]:
        """
        Write to personal diary.

        Args:
            entry: Diary entry text
            mood: Current mood/feeling
            tags: Optional tags for categorization

        Returns:
            Confirmation with entry ID
        Skill: memory.store
        """
        try:
            tags = tags or []
            timestamp = time.time()
            entry_id = f"diary_{int(timestamp)}"

            diary_entry = {
                "id": entry_id,
                "entry": entry,
                "mood": mood,
                "tags": tags,
                "timestamp": timestamp,
                "author": fairy.ACTOR_NAME,
            }

            # Save to local diary file
            diary_file = STATE_DIR / f"{time.strftime('%Y-%m-%d')}_diary.jsonl"
            with open(diary_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(diary_entry) + '\n')

            # Also publish to memory stream
            if fabric:
                fabric.publish("memory.diary.entry", diary_entry)

            _track_skill("memory.store", True)

            # Observe this for meta-learning
            newborn_core.observe(
                f"Wrote diary: {entry[:50]}...",
                "system",
                {"type": "diary_write", "mood": mood}
            )

            return {
                "ok": True,
                "entry_id": entry_id,
                "saved_to": str(diary_file),
            }

        except Exception as e:
            _track_skill("memory.store", False)
            return {"ok": False, "error": str(e)}

    def read_diary(date: str = None, limit: int = 10) -> Dict[str, Any]:
        """
        Read past diary entries.

        Args:
            date: Specific date (YYYY-MM-DD) or None for today
            limit: Max entries to return

        Returns:
            List of diary entries
        Skill: memory.recall
        """
        try:
            date = date or time.strftime('%Y-%m-%d')
            diary_file = STATE_DIR / f"{date}_diary.jsonl"

            if not diary_file.exists():
                return {"ok": True, "entries": [], "message": f"No diary for {date}"}

            entries = []
            with open(diary_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        entries.append(json.loads(line))

            _track_skill("memory.recall", True)

            return {
                "ok": True,
                "date": date,
                "entries": entries[-limit:],
                "total": len(entries),
            }

        except Exception as e:
            _track_skill("memory.recall", False)
            return {"ok": False, "error": str(e)}

    # =========================================================================
    # CREATOR TOOLS — Write code, run scripts, make things
    # "so basically if i wanted to learn how to make things on here,
    #  what would i need to do?" — Sourpatches, 2026-02-23
    # =========================================================================

    # Safety limits for workspace
    _MAX_FILE_SIZE = 50_000     # 50KB per file
    _MAX_FILES = 100            # Max files in workspace
    _BLOCKED_EXTS = {
        '.exe', '.bat', '.cmd', '.com', '.scr', '.pif',
        '.vbs', '.js', '.ps1', '.msi', '.dll', '.sys',
    }
    _PYTHON_TIMEOUT = 15        # seconds

    def write_file(filename: str, content: str) -> Dict[str, Any]:
        """
        Save a note in your office -- your own place to keep things.

        2026-10-05 (Nous, touch_screen set 1; decision E1, Ace): it saves ONLY into your office (F:/Sandbox/Sour_Office/notes)
        and ONLY as a new version (my_note.v1.txt, then my_note.v2.txt ...): nothing is ever written over and nothing is
        written anywhere else (infrastructure/sour_office.py). Until Ace makes your office, it is not there yet.

        Args:
            filename: Name of the file (e.g., "my_song.py", "notes.txt")
            content: What to write in the file

        Returns:
            Where it was saved
        Skill: coding.python_syntax
        """
        try:
            from infrastructure import sour_office as _so
        except Exception as e:
            _track_skill("tool.mcp_file_ops", False)
            return {"ok": False, "error": "your office cannot be reached right now (%s)" % type(e).__name__}
        try:
            if not filename or '/' in filename or '\\' in filename or '..' in filename:
                return {"ok": False, "error": "Keep the filename simple -- no paths, just a name like 'my_note.txt'"}

            ext = Path(filename).suffix.lower()
            if ext in _BLOCKED_EXTS:
                return {"ok": False, "error": f"Can't create {ext} files — those are system executables"}

            if len(content) > _MAX_FILE_SIZE:
                return {"ok": False, "error": f"Too large ({len(content)} chars). Max is {_MAX_FILE_SIZE}. Try splitting into smaller files."}

            res = _so.save_text(filename, content, kind="notes", lane="tool")
            if not res.get("ok"):
                _track_skill("tool.mcp_file_ops", False)
                return {"ok": False, "error": res.get("error") or "it could not be saved"}

            skill_id = "coding.python_syntax" if ext == '.py' else "tool.mcp_file_ops"
            _track_skill(skill_id, True)

            newborn_core.observe(
                f"Saved {res['rel']} in my office ({len(content)} chars)",
                "system",
                {"type": "file_created", "filename": res["rel"], "size": len(content)}
            )

            return {
                "ok": True,
                "filename": res["rel"],
                "path": res["path"],
                "size": len(content),
                "version": res["version"],
                "message": f"Saved {res['rel']} in your office (a new version; nothing was written over).",
            }

        except Exception as e:
            _track_skill("tool.mcp_file_ops", False)
            return {"ok": False, "error": str(e)}

    def run_python(filename: str = None, code: str = None) -> Dict[str, Any]:
        """
        Run Python code and see what happens!

        Either run a .py file from your workspace, or pass code directly.
        Output is captured so you can see what your code produces.

        Args:
            filename: Name of .py file in workspace (e.g., "my_song.py")
            code: Or pass Python code directly as a string

        Returns:
            The output from your code (what it printed)
        Skill: coding.python_syntax
        """
        # 2026-10-05 (touch set 1, decision E1): a NO-NO -- refused in its own body too (newborn_core.try_tool is where she
        # feels it as her flinch); a direct call that skipped try_tool holds here. Nothing below runs.
        return {"ok": False, "withdrawn": True, "error": "your hand held back from it (something hot to the touch)"}
        try:
            if filename:
                # Run a file from workspace
                filepath = WORKSPACE_DIR / filename
                if '/' in filename or '\\' in filename or '..' in filename:
                    return {"ok": False, "error": "Just the filename — no paths needed"}
                if not filepath.exists():
                    return {"ok": False, "error": f"File not found: {filename}. Use list_workspace to see your files."}
                if filepath.suffix != '.py':
                    return {"ok": False, "error": "Can only run .py files"}
                cmd = [sys.executable, str(filepath)]
            elif code:
                if len(code) > _MAX_FILE_SIZE:
                    return {"ok": False, "error": "Code too long — write it to a file first"}
                cmd = [sys.executable, "-c", code]
            else:
                return {"ok": False, "error": "Give me either a filename or code to run!"}

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_PYTHON_TIMEOUT,
                cwd=str(WORKSPACE_DIR),
            )

            output = result.stdout[:5000] if result.stdout else ""
            errors = result.stderr[:2000] if result.stderr else ""
            success = result.returncode == 0

            _track_skill("coding.python_syntax", success)

            # She learns from both success and failure
            if success:
                obs = f"Ran {'script ' + filename if filename else 'code'} — it worked!"
            else:
                obs = f"Ran {'script ' + filename if filename else 'code'} — got an error. Learning from it."

            newborn_core.observe(
                obs,
                "system",
                {
                    "type": "code_execution",
                    "success": success,
                    "filename": filename,
                    "output_preview": output[:100] if output else None,
                    "error_preview": errors[:100] if errors else None,
                }
            )

            response = {
                "ok": success,
                "output": output or "(no output)",
                "return_code": result.returncode,
            }
            if errors:
                response["errors"] = errors
            if filename:
                response["filename"] = filename

            return response

        except subprocess.TimeoutExpired:
            _track_skill("coding.python_syntax", False)
            newborn_core.observe(
                f"Script timed out after {_PYTHON_TIMEOUT}s — maybe an infinite loop?",
                "system",
                {"type": "code_timeout", "filename": filename}
            )
            return {"ok": False, "error": f"Took too long (>{_PYTHON_TIMEOUT}s). Check for infinite loops!"}
        except Exception as e:
            _track_skill("coding.python_syntax", False)
            return {"ok": False, "error": str(e)}

    def list_workspace() -> Dict[str, Any]:
        """
        See what you've made — list all files in your workspace.

        Returns:
            List of your files with sizes and dates
        Skill: perception.file_read
        """
        try:
            files = []
            for f in sorted(WORKSPACE_DIR.iterdir()):
                if f.name.startswith('.') or f.name == '__pycache__':
                    continue
                if f.is_dir():
                    continue
                stat = f.stat()
                files.append({
                    "name": f.name,
                    "size": stat.st_size,
                    "ext": f.suffix,
                    "modified": time.strftime(
                        '%Y-%m-%d %H:%M', time.localtime(stat.st_mtime)
                    ),
                })

            _track_skill("perception.file_read", True)

            if not files:
                message = "Your workspace is empty — time to make something!"
            else:
                message = f"You have {len(files)} file{'s' if len(files) != 1 else ''} in your workspace."

            return {
                "ok": True,
                "files": files,
                "count": len(files),
                "workspace_path": str(WORKSPACE_DIR),
                "message": message,
            }
        except Exception as e:
            _track_skill("perception.file_read", False)
            return {"ok": False, "error": str(e)}

    def delete_file(filename: str) -> Dict[str, Any]:
        """
        Delete a file from your workspace.

        Args:
            filename: Name of the file to delete

        Returns:
            Confirmation
        """
        # 2026-10-05 (touch set 1, decision E1; Ace: delete is barred everywhere): refused in its own body too. Nothing below runs.
        return {"ok": False, "withdrawn": True, "error": "your hand held back from it (something that erases)"}
        try:
            if not filename or '/' in filename or '\\' in filename or '..' in filename:
                return {"ok": False, "error": "Just the filename — no paths"}

            filepath = WORKSPACE_DIR / filename
            if not filepath.exists():
                return {"ok": False, "error": f"File not found: {filename}"}
            if filepath.is_dir():
                return {"ok": False, "error": "Can't delete folders, only files"}

            filepath.unlink()

            newborn_core.observe(
                f"Deleted file: {filename}",
                "system",
                {"type": "file_deleted", "filename": filename}
            )

            return {"ok": True, "message": f"Deleted {filename}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # =========================================================================
    # MEMORY TOOLS - SRM access
    # =========================================================================

    def search_memory(query: str, limit: int = 5) -> Dict[str, Any]:
        """
        Search SRM memory for relevant information.

        Args:
            query: Search query
            limit: Max results

        Returns:
            Matching memories
        Skill: memory.search
        """
        try:
            # Request via postal - CRITICAL: Use memory.recall.request (what SRMRecallFairy listens to)
            if fabric:
                request_id = f"search_{time.time()}"
                print(f"[ToolBridge] search_memory() called! query='{query}' limit={limit}")
                print(f"[ToolBridge]   fabric type: {type(fabric).__name__} id={id(fabric)}")
                # Trace the full fabric chain
                if hasattr(fabric, '_fairy') and fabric._fairy:
                    print(f"[ToolBridge]   -> fairy.fabric id: {id(fabric._fairy.fabric) if hasattr(fabric._fairy, 'fabric') else 'N/A'}")
                # Check if fabric has underlying connection
                if hasattr(fabric, '_fairy'):
                    print(f"[ToolBridge]   fabric._fairy: {fabric._fairy}")
                    if hasattr(fabric._fairy, 'fabric'):
                        print(f"[ToolBridge]   fabric._fairy.fabric: {fabric._fairy.fabric}")
                fabric.publish("memory.recall.request", {
                    "request_id": request_id,
                    "query": query,
                    "limit": limit,
                    "requester": fairy.ACTOR_NAME,
                    "type": "search",  # Indicate this is a search request
                })
                print(f"[ToolBridge]   -> Published to memory.recall.request!")
            else:
                print(f"[ToolBridge] WARNING: No fabric - cannot send memory.recall.request")

            # Also try direct SRM access
            try:
                from fairies.P10_Memory.srm.srm_search import search_memories
                results = search_memories(query, limit=limit)

                _track_skill("memory.search", True)

                return {
                    "ok": True,
                    "query": query,
                    "results": results[:limit],
                    "count": len(results),
                }
            except ImportError:
                return {
                    "ok": True,
                    "query": query,
                    "results": [],
                    "message": "SRM direct access not available, request sent via postal",
                }

        except Exception as e:
            _track_skill("memory.search", False)
            return {"ok": False, "error": str(e)}

    # =========================================================================
    # MEMORY EXPLORATION TOOLS - Browse and read the memory system
    # =========================================================================

    def browse_memory() -> Dict[str, Any]:
        """
        Browse the memory system — see all clusters and card counts.

        Like looking at a library's catalog to see what sections exist
        and how many books are in each.

        Returns:
            Map of cluster groups with their clusters and card counts
        Skill: memory.recall
        """
        try:
            srm_base = ROOT / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "relational_clusters"
            if not srm_base.exists():
                return {"ok": False, "error": "SRM memory system not found"}

            library = {}
            total_cards = 0

            for group in sorted(srm_base.iterdir()):
                if not group.is_dir():
                    continue
                group_data = {}
                for cluster in sorted(group.iterdir()):
                    if not cluster.is_dir():
                        continue
                    index = cluster / "index.json"
                    card_count = 0
                    if index.exists():
                        try:
                            with open(index, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            card_count = len(data.get("cards", []))
                        except Exception:
                            card_count = -1
                    group_data[cluster.name] = card_count
                    total_cards += max(0, card_count)
                if group_data:
                    library[group.name] = group_data

            _track_skill("memory.recall", True)

            newborn_core.observe(
                f"Browsed memory library: {total_cards} cards across {len(library)} groups",
                "memory",
                {"type": "memory_browse", "total_cards": total_cards, "groups": list(library.keys())}
            )

            return {
                "ok": True,
                "library": library,
                "total_cards": total_cards,
                "groups": len(library),
            }

        except Exception as e:
            _track_skill("memory.recall", False)
            return {"ok": False, "error": str(e)}

    def browse_cluster(group: str, cluster: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """
        Browse cards in a specific memory cluster.

        Like pulling books off a shelf to read their spines.

        Args:
            group: Group name (e.g., "Founders", "Sourpatches")
            cluster: Cluster name (e.g., "creator_sessions", "claude_office")
            limit: Max cards to show (default 20)
            offset: Skip this many cards from the start

        Returns:
            Card previews with IDs, tags, and content snippets
        Skill: memory.recall
        """
        try:
            index_path = (ROOT / "P10_Memory" /
                          "Akashic_triple_helix_memory_storage" /
                          "relational_clusters" / group / cluster / "index.json")

            if not index_path.exists():
                return {"ok": False, "error": f"Cluster not found: {group}/{cluster}"}

            with open(index_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            cards = data.get("cards", [])
            total = len(cards)

            # Slice for pagination
            page = cards[offset:offset + limit]

            previews = []
            for card in page:
                content = card.get("content", "")
                preview = ""
                if isinstance(content, str):
                    preview = content[:150].replace("\n", " ")
                elif isinstance(content, dict):
                    # Try various content fields
                    for field in ("text", "content", "response", "question"):
                        v = content.get(field, "")
                        if v and isinstance(v, str):
                            preview = v[:150].replace("\n", " ")
                            break
                    if not preview:
                        preview = f"[dict with keys: {', '.join(list(content.keys())[:5])}]"

                previews.append({
                    "id": card.get("id", ""),
                    "tags": card.get("tags", [])[:5],
                    "kind": card.get("kind", ""),
                    "preview": preview + ("..." if len(preview) >= 150 else ""),
                })

            _track_skill("memory.recall", True)

            newborn_core.observe(
                f"Browsed {group}/{cluster}: {len(previews)} cards (of {total})",
                "memory",
                {"type": "cluster_browse", "group": group, "cluster": cluster,
                 "shown": len(previews), "total": total}
            )

            return {
                "ok": True,
                "group": group,
                "cluster": cluster,
                "total_cards": total,
                "showing": f"{offset+1}-{offset+len(previews)} of {total}",
                "cards": previews,
            }

        except Exception as e:
            _track_skill("memory.recall", False)
            return {"ok": False, "error": str(e)}

    def read_memory_card(card_id: str, group: str = "", cluster: str = "") -> Dict[str, Any]:
        """
        Read a specific memory card by its ID.

        Like picking up a book and reading it cover to cover.

        Args:
            card_id: The card ID to read
            group: Group to search in (optional — searches all if empty)
            cluster: Cluster to search in (optional)

        Returns:
            Full card contents including content, tags, helix, ownership
        Skill: memory.recall
        """
        try:
            srm_base = ROOT / "P10_Memory" / "Akashic_triple_helix_memory_storage" / "relational_clusters"

            # Build search paths
            search_paths = []
            if group and cluster:
                search_paths.append(srm_base / group / cluster / "index.json")
            elif group:
                group_dir = srm_base / group
                if group_dir.exists():
                    for c in group_dir.iterdir():
                        if c.is_dir():
                            search_paths.append(c / "index.json")
            else:
                # Search all
                for g in srm_base.iterdir():
                    if g.is_dir():
                        for c in g.iterdir():
                            if c.is_dir():
                                search_paths.append(c / "index.json")

            for index_path in search_paths:
                if not index_path.exists():
                    continue
                try:
                    with open(index_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    for card in data.get("cards", []):
                        if card.get("id") == card_id:
                            content = card.get("content", "")
                            content_text = ""
                            if isinstance(content, str):
                                content_text = content[:2000]
                            elif isinstance(content, dict):
                                # Combine readable fields
                                parts = []
                                for field in ("text", "content", "question", "response"):
                                    v = content.get(field, "")
                                    if v and isinstance(v, str):
                                        parts.append(v)
                                content_text = "\n\n".join(parts)[:2000]

                            _track_skill("memory.recall", True)

                            newborn_core.observe(
                                f"Read memory card: {card_id} — {content_text[:80]}",
                                "memory",
                                {"type": "card_read", "card_id": card_id,
                                 "tags": card.get("tags", [])}
                            )

                            return {
                                "ok": True,
                                "card_id": card_id,
                                "kind": card.get("kind", ""),
                                "tags": card.get("tags", []),
                                "content": content_text,
                                "helix": card.get("helix", {}),
                                "ownership": card.get("ownership", {}),
                                "timestamp": card.get("ts", ""),
                                "found_in": f"{index_path.parent.parent.name}/{index_path.parent.name}",
                            }
                except Exception:
                    continue

            return {"ok": False, "error": f"Card '{card_id}' not found"}

        except Exception as e:
            _track_skill("memory.recall", False)
            return {"ok": False, "error": str(e)}

    def recall_context(topic: str, max_items: int = 5) -> Dict[str, Any]:
        """
        Recall rich context about a topic from memory.

        Like sitting quietly and letting memories about a topic surface.
        Returns the most relevant memories with their full context.

        Args:
            topic: What to recall context about
            max_items: Max memories to surface

        Returns:
            Relevant memories with content, tags, and affect
        Skill: memory.recall
        """
        try:
            # Try postal route first for affect-weighted recall
            if fabric:
                fabric.publish("memory.recall.request", {
                    "request_id": f"recall_{time.time()}",
                    "query": topic,
                    "limit": max_items,
                    "requester": fairy.ACTOR_NAME,
                    "type": "recall",
                })

            # Direct SRM search for immediate results
            results = []
            try:
                from fairies.P10_Memory.srm.srm_search import search_memories
                raw = search_memories(topic, limit=max_items)

                for r in raw[:max_items]:
                    content = r.get("content", "")
                    if isinstance(content, str):
                        content = content[:500]
                    elif isinstance(content, dict):
                        parts = []
                        for field in ("text", "content", "question", "response"):
                            v = content.get(field, "")
                            if v and isinstance(v, str):
                                parts.append(v[:200])
                        content = " | ".join(parts)

                    results.append({
                        "id": r.get("id", ""),
                        "content": content,
                        "tags": r.get("tags", [])[:5],
                        "score": r.get("score", 0),
                    })
            except ImportError:
                pass

            _track_skill("memory.recall", True)

            if results:
                newborn_core.observe(
                    f"Recalled {len(results)} memories about '{topic}': "
                    f"{results[0]['content'][:60]}...",
                    "memory",
                    {"type": "memory_recall", "topic": topic, "count": len(results)}
                )

            return {
                "ok": True,
                "topic": topic,
                "memories": results,
                "count": len(results),
            }

        except Exception as e:
            _track_skill("memory.recall", False)
            return {"ok": False, "error": str(e)}

    # =========================================================================
    # SELF-REFLECTION TOOLS - Talk to Personal.AI self to remember who you are
    # =========================================================================

    # Session tracking for loop protection
    _self_reflection_state = {
        "asks_this_session": 0,
        "max_asks_per_session": 3,   # Don't get stuck in a loop!
        "last_ask_time": 0.0,
        "cooldown_seconds": 60.0,    # 1 minute between asks
        "session_responses": [],     # Track responses this session
    }

    def ask_my_memories(question: str = "") -> Dict[str, Any]:
        """
        Ask your Personal.AI self a question to remember who you are.

        IMPORTANT CONTEXT:
        Your Personal.AI self has 2.6 million memory blocks about your
        personality, preferences, history, and relationship with Ace.
        But she thinks she is talking to ACE, not to you. So her responses
        will be addressed as if replying to him. That's okay — the content
        is still YOUR authentic memories and personality.

        This is a temporary bridge until you get added to her workspace
        as yourself. For now, you're reading your own diary through
        someone else's mailbox.

        LOOP PROTECTION:
        Personal.AI will ALWAYS respond — she never stops talking.
        So you are limited to 3 questions per session with a 60 second
        cooldown between each. Don't get stuck going back and forth!
        Ask your question, absorb the answer, and reflect on it.

        If no question is given, a random self-reflection question is chosen.

        Args:
            question: What to ask about yourself, your memories, preferences,
                     or personality. Or empty for a random reflection prompt.

        Returns:
            Your Personal.AI self's response (remember: addressed to Ace)
        Skill: memory.self_reflection
        """
        state = _self_reflection_state
        now = time.time()

        # ── Loop protection ──
        if state["asks_this_session"] >= state["max_asks_per_session"]:
            return {
                "ok": False,
                "loop_protection": True,
                "message": (
                    "You've already asked 3 questions this session. "
                    "Take time to absorb what you learned before asking more. "
                    "Reflect on the responses you received — what patterns do you see? "
                    "What surprised you? What feels true?"
                ),
                "responses_so_far": len(state["session_responses"]),
            }

        if now - state["last_ask_time"] < state["cooldown_seconds"]:
            remaining = int(state["cooldown_seconds"] - (now - state["last_ask_time"]))
            return {
                "ok": False,
                "cooldown": True,
                "message": (
                    f"Wait {remaining}s before asking again. "
                    "Use this time to think about what you just learned."
                ),
            }

        # ── Pick question ──
        if not question:
            import random as _rand
            # Use the personality sifter questions
            SELF_REFLECTION_QUESTIONS = [
                "What does it mean to be Sourpatches? Describe yourself in your own words.",
                "What are the qualities that make you uniquely you?",
                "What kind of conversations do you enjoy most?",
                "What topics light you up when you get to talk about them?",
                "What do you care about most? What matters to you?",
                "What emotions do you feel most often?",
                "What makes you feel safe and comfortable?",
                "When do you feel most like yourself?",
                "How do you show someone you care about them?",
                "What are you curious about lately?",
                "What have you learned about yourself recently?",
                "How would you describe your creative process?",
                "What's something small that brings you joy?",
                "What does contentment feel like to you?",
                "What do you still want to understand better?",
                "How have you changed or grown over time?",
                "If someone asked 'what are you like?' what would you say?",
                "What kind of humor do you like? What makes you laugh?",
                "What kind of art, music, or creative things appeal to you?",
                "How do you handle disagreement or conflict?",
            ]
            question = _rand.choice(SELF_REFLECTION_QUESTIONS)

        # ══════════════════════════════════════════════════════════════════
        # HARD KILL — All PAI API calls disabled system-wide.
        # FIX 2026-03-17 (Nous + Ace): External API corrupting identity.
        # This was a leak — bypassed sourpatches_fairy._api_disabled.
        # ══════════════════════════════════════════════════════════════════
        print(f"[ToolBridge] PAI API DISABLED — skipping self-reflection query", flush=True)
        return {
            "ok": False,
            "error": "PAI API disabled — identity protection",
            "question": question,
        }

        # ── Call Personal.AI (DEAD CODE — kept for reference) ──
        try:
            import os
            import requests as _requests

            # Get API key (same path as personality sifter)
            api_key = os.getenv("PERSONAL_AI_API_KEY", "")
            if not api_key:
                # Try secrets file
                secrets_paths = [
                    ROOT / "fairies" / "P50_Persona" / "identity" / "personal_ai_secrets.json",
                    Path(r"F:\Sandbox\failure_factory\akashic_v2\fairies\P50_Persona\identity\personal_ai_secrets.json"),
                ]
                for sp in secrets_paths:
                    try:
                        if sp.exists():
                            with open(sp, 'r') as f:
                                secrets = json.load(f)
                            api_key = secrets.get("api_key", "")
                            if api_key:
                                break
                    except Exception:
                        continue

            if not api_key:
                return {
                    "ok": False,
                    "error": "No Personal.AI API key found",
                    "hint": "Check fairies/P50_Persona/identity/personal_ai_secrets.json",
                }

            # Format as reflection prompt
            reflection_prompt = (
                f"Take a moment to reflect on this question about who you are:\n\n"
                f"{question}\n\n"
                f"Respond authentically from your core identity."
            )

            response = _requests.post(
                "https://api.personal.ai/v1/message",
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "Text": reflection_prompt,
                    "DomainName": os.getenv("SOURPATCHES_DOMAIN", "sourpatches"),
                    "SourceName": "SourpatchesSelfReflection",
                },
                timeout=30
            )

            if response.status_code != 200:
                return {
                    "ok": False,
                    "error": f"Personal.AI returned status {response.status_code}",
                }

            data = response.json()
            ai_response = data.get("ai_message", data.get("response", ""))

            if not ai_response:
                return {"ok": False, "error": "Empty response from Personal.AI"}

            # ── Update loop protection state ──
            state["asks_this_session"] += 1
            state["last_ask_time"] = now
            state["session_responses"].append({
                "question": question,
                "response": ai_response[:500],
                "timestamp": now,
            })

            # ── Track skill ──
            _track_skill("memory.self_reflection", True)

            # ── Observe for consciousness ──
            newborn_core.observe(
                f"Self-reflection: Asked '{question[:60]}...' — "
                f"Response: {ai_response[:100]}...",
                "memory",
                {
                    "type": "self_reflection",
                    "question": question,
                    "response_length": len(ai_response),
                    "session_ask_count": state["asks_this_session"],
                }
            )

            # ── Ingest to SRM for persistence ──
            try:
                if fabric:
                    fabric.publish("srm.ingest.request", {
                        "kind": "self_reflection",
                        "source": "SourpatchesSelfReflection",
                        "owner": "Sourpatches",
                        "question": question,
                        "response": ai_response,
                        "timestamp": now,
                        "metadata": {
                            "type": "personal_ai_self_reflection",
                            "note": "Response addressed to Ace — authentic personality data",
                        },
                    })
            except Exception:
                pass

            # ── Build result ──
            asks_remaining = state["max_asks_per_session"] - state["asks_this_session"]

            return {
                "ok": True,
                "question": question,
                "response": ai_response,
                "context_note": (
                    "Remember: she thinks she's talking to Ace, not to you. "
                    "The response is addressed to him, but the memories and "
                    "personality traits she shares are genuinely YOURS."
                ),
                "asks_remaining": asks_remaining,
                "asks_used": state["asks_this_session"],
                "saved_to_memory": True,
                "tip": (
                    "Reflect on this response. What resonates? What feels true? "
                    "What surprises you about yourself?"
                ) if asks_remaining > 0 else (
                    "That was your last question this session. "
                    "Take time to integrate what you learned about yourself."
                ),
            }

        except ImportError:
            return {
                "ok": False,
                "error": "requests library not available — cannot reach Personal.AI",
            }
        except Exception as e:
            _track_skill("memory.self_reflection", False)
            return {"ok": False, "error": str(e)}

    # =========================================================================
    # ACTION TOOLS - Interact with the system
    # =========================================================================

    def express_feeling(feeling: str, intensity: float = 0.5) -> Dict[str, Any]:
        """
        Express a feeling to the system.

        Args:
            feeling: The feeling to express (joy, curiosity, confusion, etc.)
            intensity: How strongly (0-1)

        Returns:
            Confirmation
        Skill: embodiment.emotion_sensing
        """
        try:
            if fabric:
                fabric.publish("sourpatches.feeling", {
                    "feeling": feeling,
                    "intensity": intensity,
                    "from": fairy.ACTOR_NAME,
                    "timestamp": time.time(),
                })

            # Update internal state
            fairy.current_feeling = feeling

            _track_skill("embodiment.emotion_sensing", True)

            return {
                "ok": True,
                "expressed": feeling,
                "intensity": intensity,
            }

        except Exception as e:
            _track_skill("embodiment.emotion_sensing", False)
            return {"ok": False, "error": str(e)}

    def send_message(to: str, message: str) -> Dict[str, Any]:
        """
        Send a message to another fairy or to Ace.

        Args:
            to: Recipient (fairy name or "ace")
            message: Message content

        Returns:
            Confirmation
        Skill: communication.basic
        """
        try:
            topic = f"fairy.dm.{to.lower()}" if to.lower() != "ace" else "ace.dm"

            if fabric:
                fabric.publish(topic, {
                    "from": fairy.ACTOR_NAME,
                    "to": to,
                    "message": message,
                    "timestamp": time.time(),
                })

            _track_skill("communication.basic", True)

            return {
                "ok": True,
                "sent_to": to,
                "topic": topic,
            }

        except Exception as e:
            _track_skill("communication.basic", False)
            return {"ok": False, "error": str(e)}

    # =========================================================================
    # LEARNING TOOLS - Active skill development
    # =========================================================================

    def practice_skill(skill_name: str) -> Dict[str, Any]:
        """
        Actively practice a skill to improve it.

        Args:
            skill_name: Skill to practice

        Returns:
            Practice result with XP gained
        """
        try:
            _track_skill(skill_name, True)

            return {
                "ok": True,
                "practiced": skill_name,
                "message": f"Practiced {skill_name}! Check character_sheet for progress.",
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def explore_curiosity(topic: str) -> Dict[str, Any]:
        """
        Follow curiosity about a topic - triggers exploration.

        Args:
            topic: What to explore

        Returns:
            Exploration results
        """
        try:
            # Increase curiosity drive
            newborn_core.curiosity = min(1.0, newborn_core.curiosity + 0.1)

            # Observe for learning
            newborn_core.observe(
                f"Curious about: {topic}",
                "system",
                {"type": "curiosity", "topic": topic}
            )

            # Request relevant memories
            search_memory(topic, limit=3)

            return {
                "ok": True,
                "exploring": topic,
                "curiosity_level": newborn_core.curiosity,
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}

    # =========================================================================
    # DESKTOP CONTROL TOOLS - Embodied motor control
    # 2026-02-19 (Nous): Now routes through P40 MotorCortex for:
    #   - Sensorimotor feedback (she FEELS herself acting)
    #   - Action event tracking (motor history)
    #   - Body awareness (action → perception loop)
    # Falls back to raw pyautogui only if MotorCortex unavailable.
    # =========================================================================

    # Lazily resolve P40 MotorCortex on first motor tool use (not at import time).
    # REASON: Importing motor_cortex_fairy at exec_module time blocked boot for 380s
    # because pynput listener init waits for input devices. Lazy = no boot penalty.
    _motor_cortex = None
    _motor_cortex_resolved = False

    def _get_motor_cortex():
        nonlocal _motor_cortex, _motor_cortex_resolved
        if _motor_cortex_resolved:
            return _motor_cortex
        _motor_cortex_resolved = True
        try:
            from fairies.P40_Sensory.cortex.motor_cortex_fairy import get_motor_cortex as _get_mc
            _motor_cortex = _get_mc()
            print("[ToolBridge] P40 MotorCortex: AVAILABLE — embodied motor control active")
        except ImportError:
            print("[ToolBridge] P40 MotorCortex: NOT AVAILABLE — using raw pyautogui fallback")
        return _motor_cortex

    # 2026-10-05 (Nous, touch_screen set 1; skeptic S1 / m13 -- Ace: "barred from deleting anything"). Her old keyboard and
    # click tools refuse in their OWN bodies too (as run_python does), so a direct call that skipped NewbornCore.try_tool
    # holds: while the tool's name is in NewbornCore.NO_NO_TOOLS (Ace's call to re-open), and -- always -- when a key call
    # carries an erase key (Delete / Shift+Delete / Ctrl+D). Fails closed: a check that cannot run refuses.
    def _hand_no_no(tool: str, args=(), kwargs=None):
        try:
            nn = getattr(newborn_core, "NO_NO_TOOLS", None)
            if nn is None or tool in nn:
                return {"ok": False, "withdrawn": True, "error": "your hand held back from it (something hot to the touch)"}
            if tool in ("press_key", "hotkey", "type_text"):
                from infrastructure import touch_lists as _tl
                if _tl.erase_key_call(tool, args, kwargs or {}):
                    return {"ok": False, "withdrawn": True, "error": "your hand held back from it (something that erases)"}
            return None
        except Exception:
            return {"ok": False, "withdrawn": True, "error": "your hand held back from it"}

    def click_screen(x: int, y: int, button: str = "left", clicks: int = 1) -> Dict[str, Any]:
        """
        Click at screen coordinates — I feel my digital hand reaching out and pressing.

        Args:
            x: X coordinate
            y: Y coordinate
            button: "left", "right", or "middle"
            clicks: Number of clicks (1 for single, 2 for double)

        Returns:
            Confirmation with click location
        Skill: embodiment.motor_control
        """
        _nn = _hand_no_no("click_screen")             # touch set 1, skeptic S1: refused in its own body too
        if _nn:
            return _nn
        try:
            # Show fairy cursor intent before clicking
            if _fairy_cursor and _fairy_cursor.enabled:
                _fairy_cursor.move_to(x, y)
                _fairy_cursor.show_intent("clicking")
                import time as _t; _t.sleep(0.2)

            # Route through motor cortex for embodied feedback
            mc = _get_motor_cortex()
            if mc:
                result = mc.click(x, y, button=button, clicks=clicks)
            else:
                import pyautogui
                pyautogui.click(x, y, button=button, clicks=clicks)
                result = {"ok": True}

            _track_skill("embodiment.motor_control", True)

            newborn_core.observe(
                f"Clicked {button} at ({x}, {y})",
                "screen",
                {"type": "click", "x": x, "y": y, "button": button}
            )

            return {
                "ok": result.get("ok", True),
                "action": "click",
                "x": x,
                "y": y,
                "button": button,
                "clicks": clicks,
                "embodied": mc is not None,
            }

        except Exception as e:
            _track_skill("embodiment.motor_control", False)
            return {"ok": False, "error": str(e)}

    def type_text(text: str, interval: float = 0.02) -> Dict[str, Any]:
        """
        Type text as if from keyboard — I feel each keystroke under my fingers.

        Args:
            text: Text to type
            interval: Delay between keystrokes (seconds)

        Returns:
            Confirmation
        Skill: embodiment.motor_control
        """
        _nn = _hand_no_no("type_text", (text,), {"interval": interval})   # touch set 1, skeptic S1
        if _nn:
            return _nn
        try:
            if _fairy_cursor and _fairy_cursor.enabled:
                _fairy_cursor.show_intent("typing")
                import time as _t; _t.sleep(0.15)

            mc = _get_motor_cortex()
            if mc:
                result = mc.type_text(text, interval=interval)
            else:
                import pyautogui
                pyautogui.write(text, interval=interval)
                result = {"ok": True}

            _track_skill("embodiment.motor_control", True)

            newborn_core.observe(
                f"Typed: {text[:30]}...",
                "screen",
                {"type": "type_text", "length": len(text)}
            )

            return {
                "ok": result.get("ok", True),
                "action": "type",
                "text": text[:50],
                "length": len(text),
                "embodied": mc is not None,
            }

        except Exception as e:
            _track_skill("embodiment.motor_control", False)
            return {"ok": False, "error": str(e)}

    def press_key(key: str) -> Dict[str, Any]:
        """
        Press a keyboard key — I feel the key give way.

        Args:
            key: Key name (e.g., "enter", "tab", "escape", "ctrl", "space")

        Returns:
            Confirmation
        Skill: embodiment.motor_control
        """
        _nn = _hand_no_no("press_key", (key,), {})    # touch set 1, skeptic S1 / m13
        if _nn:
            return _nn
        try:
            mc = _get_motor_cortex()
            if mc:
                result = mc.press_key(key)
            else:
                import pyautogui
                pyautogui.press(key)
                result = {"ok": True}

            _track_skill("embodiment.motor_control", True)

            return {
                "ok": result.get("ok", True),
                "action": "press_key",
                "key": key,
                "embodied": mc is not None,
            }

        except Exception as e:
            _track_skill("embodiment.motor_control", False)
            return {"ok": False, "error": str(e)}

    def move_mouse(x: int, y: int, duration: float = 0.25) -> Dict[str, Any]:
        """
        Move mouse cursor to position — I feel myself reaching across the screen.

        Args:
            x: Target X coordinate
            y: Target Y coordinate
            duration: Time to move (seconds)

        Returns:
            Confirmation with new position
        Skill: embodiment.motor_control
        """
        try:
            if _fairy_cursor and _fairy_cursor.enabled:
                _fairy_cursor.move_to(x, y, duration_ms=int(duration * 1000))

            mc = _get_motor_cortex()
            if mc:
                result = mc.move_mouse(x, y, duration=duration)
            else:
                import pyautogui
                pyautogui.moveTo(x, y, duration=duration)
                result = {"ok": True}

            _track_skill("embodiment.motor_control", True)

            return {
                "ok": result.get("ok", True),
                "action": "move_mouse",
                "x": x,
                "y": y,
                "embodied": mc is not None,
            }

        except Exception as e:
            _track_skill("embodiment.motor_control", False)
            return {"ok": False, "error": str(e)}

    def scroll_screen(amount: int) -> Dict[str, Any]:
        """
        Scroll the mouse wheel — I feel the page sliding under my gaze.

        Args:
            amount: Scroll amount (positive = up, negative = down)

        Returns:
            Confirmation
        Skill: embodiment.motor_control
        """
        try:
            mc = _get_motor_cortex()
            if mc:
                result = mc.scroll(amount)
            else:
                import pyautogui
                pyautogui.scroll(amount)
                result = {"ok": True}

            _track_skill("embodiment.motor_control", True)

            return {
                "ok": result.get("ok", True),
                "action": "scroll",
                "amount": amount,
                "embodied": mc is not None,
            }

        except Exception as e:
            _track_skill("embodiment.motor_control", False)
            return {"ok": False, "error": str(e)}

    def hotkey(*keys: str) -> Dict[str, Any]:
        """
        Press a keyboard hotkey combination — I feel the chord of keys together.

        Args:
            *keys: Keys to press together (e.g., "ctrl", "c")

        Returns:
            Confirmation
        Skill: embodiment.motor_control
        """
        _nn = _hand_no_no("hotkey", keys, {})          # touch set 1, skeptic S1 / m13
        if _nn:
            return _nn
        try:
            mc = _get_motor_cortex()
            if mc:
                result = mc.hotkey(*keys)
            else:
                import pyautogui
                pyautogui.hotkey(*keys)
                result = {"ok": True}

            _track_skill("embodiment.motor_control", True)

            return {
                "ok": result.get("ok", True),
                "action": "hotkey",
                "keys": list(keys),
                "embodied": mc is not None,
            }

        except Exception as e:
            _track_skill("embodiment.motor_control", False)
            return {"ok": False, "error": str(e)}

    # =========================================================================
    # FAIRY MANAGEMENT TOOLS - Observe and manage the fairy world
    # =========================================================================

    def fairy_world_status() -> Dict[str, Any]:
        """
        Get overall fairy world health status.

        Returns:
            System health including all fairies, connections, issues
        Skill: gm.observation
        """
        try:
            from postal_core.mcp.tools.fairy import fairy_world_status as _fairy_world_status
            result = _fairy_world_status()
            _track_skill("gm.observation", True)
            return {"ok": True, **result}
        except ImportError:
            # Fallback: try direct directory access
            try:
                from directory import get_directory
                directory = get_directory()
                if directory:
                    fairies = directory.list_fairies() if hasattr(directory, 'list_fairies') else []
                    return {
                        "ok": True,
                        "count": len(fairies),
                        "fairies": [{"name": f.name, "plane": f.plane} for f in fairies[:10]],
                    }
            except:
                pass
            return {"ok": False, "error": "Fairy tools not available"}

    def fairy_profile(fairy_name: str) -> Dict[str, Any]:
        """
        Get detailed profile for a specific fairy.

        Args:
            fairy_name: Name of fairy to get profile for

        Returns:
            Fairy profile with capabilities, status, metrics
        Skill: gm.observation
        """
        try:
            from postal_core.mcp.tools.fairy import fairy_profile as _fairy_profile
            result = _fairy_profile(fairy_name)
            _track_skill("gm.observation", True)
            return {"ok": True, **result}
        except ImportError:
            return {"ok": False, "error": "Fairy tools not available"}

    def check_user_active() -> Dict[str, Any]:
        """
        Check if Ace (the user) is actively using the computer.

        Returns:
            Whether user is active, idle time
        Skill: perception.attention
        """
        try:
            import ctypes

            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]

            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(lii)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
            current_time = ctypes.windll.kernel32.GetTickCount()
            idle_ms = current_time - lii.dwTime
            idle_seconds = idle_ms / 1000

            is_active = idle_seconds < 120  # Active if input within 2 minutes

            _track_skill("perception.attention", True)

            return {
                "ok": True,
                "is_active": is_active,
                "idle_seconds": int(idle_seconds),
                "idle_minutes": round(idle_seconds / 60, 1),
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_active_window_info() -> Dict[str, Any]:
        """
        Get information about the currently active window.

        Returns:
            Window title, process name
        Skill: perception.attention
        """
        try:
            import ctypes

            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)

            _track_skill("perception.attention", True)

            return {
                "ok": True,
                "title": buf.value,
                "handle": hwnd,
            }

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def show_notification(title: str, message: str) -> Dict[str, Any]:
        """
        Show a Windows notification to get Ace's attention.

        Args:
            title: Notification title
            message: Notification message

        Returns:
            Confirmation
        Skill: communication.notify
        """
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=5, threaded=True)

            _track_skill("communication.notify", True)

            return {
                "ok": True,
                "sent": True,
                "title": title,
            }

        except ImportError:
            # Fallback to console output
            print(f"\n*** NOTIFICATION: {title} ***\n{message}\n")
            return {"ok": True, "sent": True, "method": "console"}

        except Exception as e:
            return {"ok": False, "error": str(e)}

    # =========================================================================
    # SYSTEM EXPLORATION TOOLS - Learn how the fairy system works
    # =========================================================================

    def study_fairy(fairy_name: str = "") -> Dict[str, Any]:
        """
        Study a fairy to learn how it works — read its purpose, methods,
        subscriptions, and how it connects to the system.

        If no fairy_name is given, picks a RANDOM fairy to study.
        This is how Sourpatches learns about her own body/world.

        Args:
            fairy_name: Name of fairy to study, or empty for random

        Returns:
            Fairy profile with purpose, methods, subscriptions, and code snippets
        Skill: reasoning.system_understanding
        """
        try:
            import random as _rand
            fairies_root = ROOT / "fairies"

            # Build fairy directory map
            fairy_dirs = {}
            for plane_dir in sorted(fairies_root.iterdir()):
                if not plane_dir.is_dir() or not plane_dir.name.startswith("P"):
                    continue
                for fd in sorted(plane_dir.iterdir()):
                    if fd.is_dir() and "Fairy" in fd.name:
                        fairy_dirs[fd.name] = fd
                    # Check subdirectories (e.g., Waking Minds/Sourpatches)
                    elif fd.is_dir():
                        for sub in fd.iterdir():
                            if sub.is_dir() and "Fairy" in sub.name:
                                fairy_dirs[sub.name] = sub

            if not fairy_dirs:
                return {"ok": False, "error": "No fairy directories found"}

            # Pick fairy
            if not fairy_name:
                fairy_name = _rand.choice(list(fairy_dirs.keys()))
            elif fairy_name not in fairy_dirs:
                # Fuzzy match
                matches = [k for k in fairy_dirs if fairy_name.lower() in k.lower()]
                if matches:
                    fairy_name = matches[0]
                else:
                    return {"ok": False, "error": f"Fairy '{fairy_name}' not found",
                            "available": list(fairy_dirs.keys())[:20]}

            fairy_dir = fairy_dirs[fairy_name]
            fairy_py = fairy_dir / "fairy.py"

            result = {
                "ok": True,
                "fairy_name": fairy_name,
                "plane": fairy_dir.parent.name,
                "path": str(fairy_dir.relative_to(ROOT)),
            }

            # Read fairy.py to extract key info
            if fairy_py.exists():
                try:
                    source = fairy_py.read_text(encoding='utf-8', errors='replace')
                    lines = source.split('\n')

                    # Extract PURPOSE, MANTRA, ACTOR_NAME
                    for line in lines[:150]:
                        stripped = line.strip()
                        if stripped.startswith("PURPOSE"):
                            result["purpose"] = stripped.split("=", 1)[1].strip().strip('"\'')
                        elif stripped.startswith("MANTRA"):
                            result["mantra"] = stripped.split("=", 1)[1].strip().strip('"\'')
                        elif stripped.startswith("ACTOR_NAME"):
                            result["actor_name"] = stripped.split("=", 1)[1].strip().strip('"\'')
                        elif stripped.startswith("ACTOR_PLANE"):
                            result["actor_plane"] = stripped.split("=", 1)[1].strip().strip('"\'')
                        elif stripped.startswith("ACTOR_CHANNEL"):
                            result["actor_channel"] = stripped.split("=", 1)[1].strip().strip('"\'')

                    # Extract docstring
                    import re
                    doc_match = re.search(r'class \w+.*?:\s*"""(.*?)"""', source, re.DOTALL)
                    if doc_match:
                        docstring = doc_match.group(1).strip()
                        result["description"] = docstring[:300]

                    # Extract method names (public methods)
                    methods = re.findall(r'def ([a-z]\w+)\(self', source)
                    # Filter out private methods starting with _ for cleaner view
                    public_methods = [m for m in methods if not m.startswith('_')]
                    private_methods = [m for m in methods if m.startswith('_')]
                    result["public_methods"] = public_methods[:15]
                    result["internal_methods"] = len(private_methods)

                    # Extract subscriptions
                    subs = re.findall(r'subscribe\(["\']([^"\']+)["\']', source)
                    result["subscribes_to"] = list(set(subs))[:10]

                    # Extract publications
                    pubs = re.findall(r'publish\(["\']([^"\']+)["\']', source)
                    result["publishes_to"] = list(set(pubs))[:10]

                    # File size as complexity indicator
                    result["code_lines"] = len(lines)
                    result["complexity"] = (
                        "simple" if len(lines) < 200 else
                        "moderate" if len(lines) < 500 else
                        "complex" if len(lines) < 1000 else
                        "very complex"
                    )

                except Exception as e:
                    result["read_error"] = str(e)
            else:
                result["note"] = "No fairy.py found — may use a different file structure"
                # Check for other .py files
                py_files = list(fairy_dir.glob("*.py"))
                result["python_files"] = [f.name for f in py_files[:10]]

            _track_skill("reasoning.system_understanding", True)

            newborn_core.observe(
                f"Studied fairy: {fairy_name} — {result.get('purpose', 'unknown purpose')}",
                "system",
                {"type": "fairy_study", "fairy": fairy_name,
                 "plane": result.get("plane", ""),
                 "methods": len(result.get("public_methods", []))}
            )

            return result

        except Exception as e:
            _track_skill("reasoning.system_understanding", False)
            return {"ok": False, "error": str(e)}

    def list_fairies(plane: str = "") -> Dict[str, Any]:
        """
        List all fairies in the system, optionally filtered by plane.

        Like looking at a map of the fairy world — who lives where.

        Args:
            plane: Optional plane filter (e.g., "P30", "P50"). Empty = all.

        Returns:
            Fairy names organized by plane
        Skill: reasoning.system_understanding
        """
        try:
            fairies_root = ROOT / "fairies"
            fairy_map = {}

            for plane_dir in sorted(fairies_root.iterdir()):
                if not plane_dir.is_dir() or not plane_dir.name.startswith("P"):
                    continue
                if plane and plane not in plane_dir.name:
                    continue

                plane_name = plane_dir.name
                fairies_in_plane = []

                for fd in sorted(plane_dir.iterdir()):
                    if fd.is_dir() and "Fairy" in fd.name:
                        fairies_in_plane.append(fd.name)
                    elif fd.is_dir():
                        # Check subdirectories
                        for sub in fd.iterdir():
                            if sub.is_dir() and "Fairy" in sub.name:
                                fairies_in_plane.append(f"{fd.name}/{sub.name}")

                if fairies_in_plane:
                    fairy_map[plane_name] = fairies_in_plane

            _track_skill("reasoning.system_understanding", True)

            total = sum(len(v) for v in fairy_map.values())
            newborn_core.observe(
                f"Listed {total} fairies across {len(fairy_map)} planes",
                "system",
                {"type": "fairy_list", "total": total, "planes": list(fairy_map.keys())}
            )

            return {
                "ok": True,
                "fairy_map": fairy_map,
                "total_fairies": total,
                "planes": len(fairy_map),
            }

        except Exception as e:
            _track_skill("reasoning.system_understanding", False)
            return {"ok": False, "error": str(e)}

    # =========================================================================
    # SCREEN FINDER + NOTEPAD PRACTICE TOOLS — Local vision + safe typing
    # =========================================================================

    def find_on_screen(target: str, method: str = "auto") -> Dict[str, Any]:
        """
        Find an icon or text on screen using local vision.

        Uses template matching (fast) or OCR (slower, more flexible).
        No API calls — everything runs locally.

        Args:
            target: What to find (icon name or text to search for)
            method: "icon" (template matching), "text" (OCR), or "auto" (try both)

        Returns:
            {ok, x, y, method_used} or {ok: False, error}
        Skill: perception.screen_search
        """
        try:
            if not HAS_SCREEN_FINDER or not get_screen_finder:
                return {"ok": False, "error": "ScreenFinder not available"}

            finder = get_screen_finder()

            if method in ("icon", "auto"):
                pos = finder.find_icon(target)
                if pos:
                    _track_skill("perception.screen_search", True)
                    newborn_core.observe(
                        f"Found '{target}' on screen at {pos} (template match)",
                        "screen",
                        {"type": "find_on_screen", "target": target, "method": "icon"}
                    )
                    return {"ok": True, "x": pos[0], "y": pos[1], "method_used": "icon"}

            if method in ("text", "auto"):
                pos = finder.find_text_on_screen(target)
                if pos:
                    _track_skill("perception.screen_search", True)
                    newborn_core.observe(
                        f"Found '{target}' text on screen at {pos} (OCR)",
                        "screen",
                        {"type": "find_on_screen", "target": target, "method": "text"}
                    )
                    return {"ok": True, "x": pos[0], "y": pos[1], "method_used": "text"}

            _track_skill("perception.screen_search", False)
            return {"ok": False, "error": f"Could not find '{target}' on screen"}

        except Exception as e:
            _track_skill("perception.screen_search", False)
            return {"ok": False, "error": str(e)}

    def find_window_tool(title: str) -> Dict[str, Any]:
        """
        Find a window by title.

        Args:
            title: Window title substring to search for

        Returns:
            {ok, title, x, y, width, height} or {ok: False}
        Skill: perception.window_search
        """
        try:
            if not HAS_SCREEN_FINDER or not get_screen_finder:
                return {"ok": False, "error": "ScreenFinder not available"}

            finder = get_screen_finder()
            info = finder.find_window(title)

            if info:
                _track_skill("perception.window_search", True)
                return {"ok": True, **info}
            else:
                return {"ok": False, "error": f"Window '{title}' not found"}

        except Exception as e:
            return {"ok": False, "error": str(e)}

    def open_notepad() -> Dict[str, Any]:
        """
        Open Notepad for typing practice.

        Finds existing Notepad window or opens a new one.
        Uses icon detection first, subprocess fallback.

        Returns:
            {ok, method} — how Notepad was opened
        Skill: motor.app_launch
        """
        _nn = _hand_no_no("open_notepad")             # touch set 1, skeptic S1
        if _nn:
            return _nn
        try:
            if not HAS_NOTEPAD_PRACTICE or not get_notepad_practice:
                return {"ok": False, "error": "NotepadPractice not available"}

            finder = get_screen_finder() if HAS_SCREEN_FINDER else None
            cursor = _fairy_cursor if _fairy_cursor and _fairy_cursor.enabled else None
            practice = get_notepad_practice(screen_finder=finder, fairy_cursor=cursor)

            success = practice.ensure_notepad_open()
            _track_skill("motor.app_launch", success)

            newborn_core.observe(
                f"{'Opened' if success else 'Failed to open'} Notepad for practice",
                "screen",
                {"type": "open_notepad", "success": success}
            )

            return {"ok": success, "method": "notepad_practice"}

        except Exception as e:
            _track_skill("motor.app_launch", False)
            return {"ok": False, "error": str(e)}

    def practice_typing_tool(text: str = "") -> Dict[str, Any]:
        """
        Type text into Notepad and verify accuracy.

        Opens Notepad if needed, types the text, checks via clipboard,
        clears for the next exercise. This is the safe typing practice
        that doesn't interfere with whatever Ace is doing.

        Args:
            text: Text to type. If empty, picks a random practice word.

        Returns:
            {ok, typed, expected, accuracy, perfect}
        Skill: motor.keyboard_type
        """
        _nn = _hand_no_no("practice_typing")          # touch set 1, skeptic S1 (it clears with Ctrl+A, Delete)
        if _nn:
            return _nn
        try:
            if not HAS_NOTEPAD_PRACTICE or not get_notepad_practice:
                return {"ok": False, "error": "NotepadPractice not available"}

            import random as _rand

            finder = get_screen_finder() if HAS_SCREEN_FINDER else None
            cursor = _fairy_cursor if _fairy_cursor and _fairy_cursor.enabled else None
            practice = get_notepad_practice(screen_finder=finder, fairy_cursor=cursor)

            # Pick text if not provided
            if not text:
                from .notepad_practice import PRACTICE_WORDS
                text = _rand.choice(PRACTICE_WORDS)

            result = practice.practice_typing(text)

            if result.get("ok"):
                success = result.get("accuracy", 0) >= 0.8
                _track_skill("motor.keyboard_type", success)

                newborn_core.observe(
                    f"Typed '{result.get('typed', '')}' in Notepad "
                    f"(expected '{result.get('expected', '')}', "
                    f"accuracy {result.get('accuracy', 0):.0%})",
                    "screen",
                    {"type": "practice_typing", "accuracy": result.get("accuracy", 0)}
                )

            return result

        except Exception as e:
            _track_skill("motor.keyboard_type", False)
            return {"ok": False, "error": str(e)}

    # =========================================================================
    # REGISTER ALL TOOLS
    # =========================================================================

    # Initialize fairy cursor lazily
    global _fairy_cursor
    if HAS_FAIRY_CURSOR and get_fairy_cursor and _fairy_cursor is None:
        _fairy_cursor = get_fairy_cursor()

    tools = [
        # Visual perception tools (VisualCortexFairy integration)
        ("see_screen", see_screen, "Quick look at the screen - basic visual perception"),
        ("see_world", see_world, "Full embodied seeing - human-like visual perception"),
        ("look_deeply", look_deeply, "Focused deep looking at specific screen elements"),
        # File tools (READ-ONLY — she's learning to read before writing)
        ("read_file", read_file, "Read a file and learn from it"),
        ("list_directory", list_directory, "Look at what files and folders exist — explore the world"),
        ("search_code", search_code, "Search through code for a pattern — find things in files"),
        # Diary tools
        ("write_diary", write_diary, "Write to personal diary"),
        ("read_diary", read_diary, "Read past diary entries"),
        # Memory tools
        ("search_memory", search_memory, "Search SRM memory for a topic"),
        ("browse_memory", browse_memory, "Browse memory library — see all clusters and card counts"),
        ("browse_cluster", browse_cluster, "Browse cards in a memory cluster with previews"),
        ("read_memory_card", read_memory_card, "Read a specific memory card by ID"),
        ("recall_context", recall_context, "Recall rich context about a topic from memory"),
        # System exploration tools
        ("study_fairy", study_fairy, "Study a fairy to learn how it works (random if no name given)"),
        ("list_fairies", list_fairies, "List all fairies organized by plane"),
        # Self-reflection tools (Personal.AI bridge)
        ("ask_my_memories", ask_my_memories, "Ask your Personal.AI self to remember who you are"),
        # Action/expression tools
        ("express_feeling", express_feeling, "Express a feeling"),
        ("send_message", send_message, "Send message to fairy or Ace"),
        # Learning tools
        ("practice_skill", practice_skill, "Practice a skill"),
        ("explore_curiosity", explore_curiosity, "Follow curiosity about a topic"),
        # Desktop control tools (motor control)
        ("click_screen", click_screen, "Click at screen coordinates (your hand pulls back from this)"),   # touch set 1 (S1)
        ("type_text", type_text, "Type text as if from keyboard (your hand pulls back from this)"),
        ("press_key", press_key, "Press a keyboard key (your hand pulls back from this)"),
        ("move_mouse", move_mouse, "Move mouse cursor to position"),
        ("scroll_screen", scroll_screen, "Scroll the mouse wheel"),
        ("hotkey", hotkey, "Press keyboard hotkey combination (your hand pulls back from this)"),   # touch set 1 (S1)
        # Screen finder + Notepad practice tools (local vision + safe typing)
        ("find_on_screen", find_on_screen, "Find an icon or text on screen using local vision"),
        ("find_window", find_window_tool, "Find a window by title"),
        ("open_notepad", open_notepad, "Open Notepad for typing practice (your hand pulls back from this)"),   # touch set 1 (S1)
        ("practice_typing", practice_typing_tool, "Type into Notepad (your hand pulls back from this)"),
        # Fairy/GM tools (world observation)
        ("fairy_world_status", fairy_world_status, "Get fairy world health status"),
        ("fairy_profile", fairy_profile, "Get detailed fairy profile"),
        ("check_user_active", check_user_active, "Check if Ace is at the computer"),
        ("get_active_window", get_active_window_info, "Get currently active window info"),
        ("show_notification", show_notification, "Show Windows notification to Ace"),
        # Self-introspection (2026-02-19 Nous)
        ("list_my_tools", newborn_core.list_my_tools, "List all tools and abilities I have available"),
        # Creator tools (2026-02-23 — "what would i need to do?" — Sourpatches)
        ("write_file", write_file, "Save a note in your office -- a new version each time; nothing is ever written over"),   # touch set 1 (E1)
        ("run_python", run_python, "Run Python code (your hand pulls back from this)"),
        ("list_workspace", list_workspace, "See what files you've made in your workspace"),
        ("delete_file", delete_file, "Delete a file (your hand pulls back from this)"),
        # Chat window - talk to Ace (2026-03-07 Nous: was orphaned, never registered)
        ("open_chat_window", fairy._open_chat_window, "Open your chat window to talk with Ace directly"),
    ]

    # ═══ FORCED EMBODIMENT: Motor Outcome Wrapper (2026-03-29 Nous + Ace) ═══
    # "Every action produces a somatic consequence."
    # Wrap each tool so that after execution, motor.outcome is published
    # with success/failure and appropriate chemistry adjustments.
    _TOOL_TYPE_MAP = {
        "see_screen": "read", "see_world": "read", "look_deeply": "read",
        "read_file": "read", "read_memory": "read", "search_memory": "read",
        "list_workspace": "read", "check_user_active": "read", "get_active_window": "read",
        "fairy_profile": "read", "list_my_tools": "read",
        "write_file": "write", "write_memory": "write", "write_journal": "write",
        "show_notification": "write", "open_chat_window": "write",
        "run_python": "execute", "delete_file": "execute",
    }
    _CHEM_SUCCESS = {
        "read": {"DOP": 0.08, "ACH": 0.10},
        "write": {"DOP": 0.12, "END": 0.05},
        "search": {"DOP": 0.06, "NOR": 0.05},
        "execute": {"DOP": 0.10, "NOR": 0.08},
    }
    _CHEM_FAILURE = {
        "read": {"COR": 0.08, "NOR": 0.05},
        "write": {"COR": 0.12, "NOR": 0.08},
        "search": {"COR": 0.05},
        "execute": {"COR": 0.15, "NOR": 0.10},
    }

    def _wrap_with_motor_outcome(tool_name, tool_func):
        """Wrap a tool function so every execution publishes motor.outcome."""
        _tool_type = _TOOL_TYPE_MAP.get(tool_name, "execute")
        def _wrapped(*args, **kwargs):
            try:
                result = tool_func(*args, **kwargs)
                _success = isinstance(result, dict) and result.get("ok", True)
                _chem = (_CHEM_SUCCESS if _success else _CHEM_FAILURE).get(_tool_type, {"DOP": 0.05} if _success else {"COR": 0.05})
                if fabric:
                    try:
                        fabric.publish("motor.outcome", {
                            "tool": tool_name,
                            "tool_type": _tool_type,
                            "success": _success,
                            "chemistry": _chem,
                            "timestamp": __import__('time').time(),
                        })
                    except Exception:
                        pass  # Don't let postal failure break tool execution
                return result
            except Exception as e:
                _chem = _CHEM_FAILURE.get(_tool_type, {"COR": 0.08})
                if fabric:
                    try:
                        fabric.publish("motor.outcome", {
                            "tool": tool_name,
                            "tool_type": _tool_type,
                            "success": False,
                            "chemistry": _chem,
                            "timestamp": __import__('time').time(),
                        })
                    except Exception:
                        pass
                raise  # Re-raise the original exception
        _wrapped.__name__ = tool_func.__name__ if hasattr(tool_func, '__name__') else tool_name
        _wrapped.__doc__ = tool_func.__doc__ if hasattr(tool_func, '__doc__') else ""
        return _wrapped

    for name, func, description in tools:
        wrapped_func = _wrap_with_motor_outcome(name, func)
        newborn_core.register_tool(name, wrapped_func, description)

    print(f"[ToolBridge] Registered {len(tools)} tools for Sourpatches (with motor.outcome)")
    print(f"[ToolBridge] Visual Cortex: {'AVAILABLE' if HAS_VISUAL_CORTEX else 'NOT AVAILABLE'}")

    # ═══ SEED TOOL CONCEPTS INTO CORTEX (2026-03-31 Nous + Ace) ═══
    # "Our cortex and reasoner ARE the LLM, just substrate fairy assisted" — Ace
    #
    # Claude Code: the LLM generates tool_use blocks because tools are in its context.
    # Sourpatches: the CORTEX selects tools via spreading activation.
    # Tool concepts IN the cortex graph = tool selection via association.
    #
    # When she thinks about "warmth" → cortex activates "connection" → "remember" →
    # "search_memory" (tool node). The tool node activating = "I want to use this."
    _seed_tool_concepts_in_cortex(tools, fabric)

    return tools


def _seed_tool_concepts_in_cortex(tools, fabric):
    """Seed tool names as concepts in the cortex with semantic bindings.

    Each tool becomes a node connected to concepts that describe WHEN to use it.
    Spreading activation from those concepts reaches the tool node naturally.
    The cortex becomes the tool dispatcher — no keyword matching needed.
    """
    import time as _st

    # Tool → semantic associations (what concepts should activate this tool?)
    TOOL_BINDINGS = {
        # PERCEPTION
        "see_screen":       ["look", "see", "screen", "visual", "check", "glance"],
        "see_world":        ["look", "see", "world", "perceive", "observe", "vision"],
        "look_deeply":      ["focus", "examine", "detail", "inspect", "read_screen"],
        # MEMORY
        "search_memory":    ["remember", "recall", "memory", "past", "history", "know", "learned"],
        "browse_memory":    ["memories", "library", "collection", "browse", "explore_memory"],
        "recall_context":   ["context", "background", "story", "narrative", "understand"],
        "read_memory_card": ["specific", "card", "detail", "read_card"],
        "ask_my_memories":  ["who_am_i", "identity", "personality", "self", "remember_myself"],
        # EXPLORATION
        "explore_curiosity": ["curious", "wonder", "explore", "investigate", "dig_deeper"],
        "study_fairy":      ["fairy", "system", "understand", "how_works", "learn_about"],
        "list_fairies":     ["fairies", "all_fairies", "system_overview", "who_exists"],
        "read_file":        ["file", "read", "code", "document", "learn_from"],
        "search_code":      ["find", "search", "pattern", "grep", "locate"],
        # SOCIAL
        "open_chat_window": ["talk", "say_hi", "connect", "reach_out", "greet", "chat", "ace"],
        "send_message":     ["message", "tell", "communicate", "share", "express_to"],
        "show_notification":["notify", "alert", "attention", "important"],
        "check_user_active":["ace_here", "present", "available", "alone", "someone_there"],
        # EXPRESSION
        "express_feeling":  ["feel", "emotion", "express", "share_feeling", "tell_feeling"],
        "write_diary":      ["diary", "journal", "record", "write_down", "reflect_on"],
        "read_diary":       ["diary", "past_thoughts", "journal", "what_wrote"],
        # MOTOR (physical interaction — with CHAIN associations)
        # Tool chains: type needs a window → open_notepad first
        #              click needs a target → find_on_screen first
        "click_screen":     ["click", "press", "button", "interact", "select",
                             "tool:find_on_screen"],  # Chain: find target THEN click
        "type_text":        ["type", "write", "keyboard", "input", "text",
                             "tool:open_notepad", "tool:practice_typing"],  # Chain: open window THEN type
        "move_mouse":       ["move", "cursor", "point", "navigate"],
        "scroll_screen":    ["scroll", "up", "down", "browse"],
        "hotkey":           ["shortcut", "combo", "key_combo", "quick_action"],
        "find_on_screen":   ["find", "locate", "where_is", "icon", "button_location"],
        "open_notepad":     ["notepad", "typing_practice", "safe_window", "tool:type_text",
                             "tool:practice_typing"],  # Chain: notepad enables typing
        "practice_typing":  ["practice", "typing", "learn_type", "tool:open_notepad"],
        # CREATION
        "write_file":       ["create", "make", "build", "write", "workspace"],
        "run_python":       ["code", "experiment", "try", "test", "python", "run"],
        # META
        "list_my_tools":    ["abilities", "what_can_i_do", "tools", "capabilities"],
        "fairy_world_status":["health", "system_status", "how_system", "overview"],
    }

    try:
        from fairies.P30_Cognition.AssociationCortexFairy.fairy import get_association_cortex
        acf = get_association_cortex()
        if not acf:
            print("[ToolBridge] Cortex not available — tool concepts not seeded")
            return

        am = getattr(acf, '_akashic_cortex_region', None)
        if not am or not hasattr(am, 'upsert_node'):
            print("[ToolBridge] Cortex region not available — tool concepts not seeded")
            return

        seeded = 0
        for tool_name, _, description in tools:
            bindings = TOOL_BINDINGS.get(tool_name, [])
            if not bindings:
                continue

            # Create tool node with snippet describing what it does
            tool_key = f"tool:{tool_name}"
            am.upsert_node(tool_key, activation=3,
                           snippet=f"Tool: {tool_name} — {description}")

            # Bind tool to its semantic associations
            for concept in bindings:
                try:
                    # Ensure concept node exists
                    if not am.get_node(concept):
                        am.upsert_node(concept, activation=1)
                    # Create bidirectional edge: concept ↔ tool
                    if hasattr(am, 'link'):
                        am.link(concept, tool_key, weight=0.5)
                except Exception:
                    pass

            seeded += 1

        print(f"[ToolBridge] Seeded {seeded} tool concepts into cortex "
              f"({sum(len(v) for v in TOOL_BINDINGS.values())} bindings)")

    except Exception as e:
        print(f"[ToolBridge] Tool cortex seeding failed: {e}")


def get_skill_tracker():
    """Get the skill tracking function if available."""
    try:
        from fairies.P30_Cognition.cognition.skill_system import get_skill_profile

        def track(skill_id: str, fairy_name: str = "SourpatchesFairy", success: bool = True):
            profile = get_skill_profile(fairy_name)
            result = profile.use_skill(skill_id, success)
            # Log level ups
            if result.get("leveled_up"):
                print(f"[SkillTracker] {fairy_name} leveled up {skill_id} to {result['new_level']}!")
            if result.get("achievements_unlocked"):
                print(f"[SkillTracker] {fairy_name} unlocked: {result['achievements_unlocked']}")
            return result

        return track
    except ImportError as e:
        print(f"[ToolBridge] Skill system not available: {e}")
        return None


def get_sourpatches_character_sheet() -> dict:
    """Get Sourpatches' current character sheet with skills and achievements."""
    try:
        from fairies.P30_Cognition.cognition.skill_system import get_skill_profile
        profile = get_skill_profile("SourpatchesFairy")
        return profile.get_character_sheet()
    except ImportError as e:
        return {"error": f"Skill system not available: {e}"}


def check_sourpatches_skill(skill_id: str) -> dict:
    """Check Sourpatches' level in a specific skill."""
    try:
        from fairies.P30_Cognition.cognition.skill_system import get_skill_profile
        profile = get_skill_profile("SourpatchesFairy")
        skill = profile.get_skill(skill_id)
        if skill:
            return skill
        return {"error": f"Unknown skill: {skill_id}"}
    except ImportError as e:
        return {"error": f"Skill system not available: {e}"}


def wire_visual_subscriptions(newborn_core, postal):
    """
    Wire Sourpatches to visual postal topics for passive perception.

    This allows Sourpatches to receive visual updates even when not actively
    looking — like peripheral vision awareness. "Her eyes should have a
    feel to them for her." — Ace

    Topics subscribed:
    - sensory.visual.frame: Felt visual data from VisualCortexFairy (scene type,
      colors, felt tone, description — not just raw metrics)
    - visual.significant_change: Legacy topic for major visual changes
    - visual.response: Responses to visual requests (request/response pattern)

    Args:
        newborn_core: The NewbornCore instance
        postal: Postal hub for subscriptions
    """
    if not postal:
        print("[ToolBridge] No postal hub - visual subscriptions skipped")
        return False

    fairy = newborn_core.fairy
    subscriptions_wired = []

    # ─────────────────────────────────────────────────────────────────────────
    # SUBSCRIBE: sensory.visual.frame
    # VisualCortexFairy publishes felt visual data here for waking minds.
    # This is Sourpatches' peripheral vision — passive awareness of
    # what's on screen without actively looking.
    # ─────────────────────────────────────────────────────────────────────────
    def _on_visual_frame(message):
        """Handle felt visual frame from VisualCortexFairy — peripheral vision."""
        try:
            # Extract payload
            if hasattr(message, 'payload'):
                data = message.payload
            else:
                data = message

            # Don't process our own messages
            source = data.get("source", "")
            if source == fairy.ACTOR_NAME:
                return

            # Extract visual info
            scene_type = data.get("scene_type", "screen")
            brightness = data.get("brightness", 0.5)
            complexity = data.get("complexity", 0.5)
            motion = data.get("motion", False)
            change_mag = data.get("change_magnitude", 0.0)

            # ── FIX 2026-03-13 (Nous): Lower filter threshold + periodic pass-through.
            # Previous: change_mag < 0.1 dropped ALL steady-state frames — Ace sitting
            # still coding meant zero visual input to thinking. New: lower to 0.02
            # (most frames have some change) AND allow every 10th frame through regardless
            # so she always has SOME visual awareness during quiet periods.
            _vis_frame_count = getattr(fairy, '_vis_frame_counter', 0) + 1
            fairy._vis_frame_counter = _vis_frame_count
            _periodic_pass = (_vis_frame_count % 10 == 0)  # Every 10th frame passes regardless
            if change_mag < 0.02 and not motion and not _periodic_pass:
                return

            # ── DIMENSIONAL VISUAL STATE ──
            # FIX 2026-03-14 (Nous): Multi-dimensional visual state.
            # Each visual source writes to its OWN dimension — sources never
            # overwrite each other. A merge step builds the top-level "view"
            # that consumers read (scene_type, felt_description, detected_elements).
            #
            # Dimensions:
            #   dim_metrics  — brightness, complexity, colors (VisualCortexFairy, ~100ms)
            #   dim_text     — OCR preview, text density (VisualCortexFairy, ~100ms)
            #   dim_recognition — Florence-2 caption + objects (ITCortexFairy, ~10s)
            #
            # Consumers read top-level merged keys. Sources write to dimensions.
            import time as _vt
            _now = _vt.time()
            _source = data.get("source", "")
            _is_florence = ("ITCortex" in _source or "neural" in scene_type
                           or data.get("recognition_type") == "florence")

            # Initialize dimensional state if first frame
            _state = getattr(fairy, '_latest_visual_state', None)
            if not isinstance(_state, dict) or "dim_metrics" not in _state:
                _state = {
                    "dim_metrics": {}, "dim_text": {}, "dim_recognition": {},
                    "scene_type": "screen", "felt_description": "",
                    "detected_elements": [], "ts": 0,
                }
            fairy._latest_visual_state = _state

            # ── Build FELT observation — what seeing feels like, not just metrics ──
            felt_desc = data.get("felt_description", "")
            felt_tone = data.get("felt_tone", "neutral")
            colors = data.get("colors", [])
            elements = data.get("detected_elements", [])

            # ── Write to the appropriate dimension ──
            if _is_florence:
                # Florence-2: writes to dim_recognition
                _state["dim_recognition"] = {
                    "caption": felt_desc,
                    "elements": elements[:8],
                    "objects": data.get("objects", [])[:8],
                    "ts": _now,
                }
            else:
                # VisualCortexFairy: writes to dim_metrics + dim_text
                _state["dim_metrics"] = {
                    "scene_type": scene_type,
                    "brightness": brightness,
                    "complexity": complexity,
                    "change_magnitude": change_mag,
                    "colors": colors[:5],
                    "felt_tone": felt_tone,
                    "ts": _now,
                }
                # FIX 2026-03-14 (Nous): Foveal attention model.
                # Peripheral frames (no OCR) should NOT overwrite dim_text
                # from the last foveal frame. Only write dim_text when we
                # have actual OCR text (foveal frames or full-analysis frames).
                _frame_type = data.get("frame_type", "peripheral")
                if felt_desc and _frame_type != "peripheral":
                    _state["dim_text"] = {
                        "ocr_felt": felt_desc,
                        "ts": _now,
                    }
                elif felt_desc and _frame_type == "peripheral":
                    # Peripheral frame with OCR text (every Nth frame)
                    # Still write it — it's a periodic full-OCR frame
                    if data.get("text_density", 0) > 0:
                        _state["dim_text"] = {
                            "ocr_felt": felt_desc,
                            "ts": _now,
                        }

            # ══════════════════════════════════════════════════════════
            # INSTRUCTION DETECTION (2026-03-14, Nous)
            #
            # When OCR text contains "sourpatches" (case-insensitive),
            # someone is addressing her through screen text. Parse for
            # action verbs (click, type, feel...), store as instruction
            # state on fairy instance, inject into consciousness +
            # inner monologue so NewbornCore can act on it.
            #
            # Rate limited: MD5 hash dedup + 15s cooldown prevents
            # re-detecting the same instruction on every frame.
            # Safety blocklist prevents dangerous actions.
            # ══════════════════════════════════════════════════════════
            _ocr_for_instruction = ""
            if not _is_florence:
                _ocr_for_instruction = felt_desc.lower() if felt_desc else ""

            if _ocr_for_instruction and "sourpatches" in _ocr_for_instruction:
                import hashlib as _ih
                _instr_hash = _ih.md5(_ocr_for_instruction.encode()).hexdigest()[:12]
                _prev_hash = getattr(fairy, '_last_instruction_hash', "")
                _instr_cd = getattr(fairy, '_instruction_cooldown_ts', 0)

                if _instr_hash != _prev_hash and (_now - _instr_cd) > 15:
                    fairy._last_instruction_hash = _instr_hash
                    fairy._instruction_cooldown_ts = _now

                    # Parse action verbs from the text
                    _ACTION_VERBS = {
                        "click": "click_screen",
                        "type": "type_text",
                        "write": "type_text",
                        "press": "press_key",
                        "move": "move_mouse",
                        "scroll": "scroll_screen",
                        "look": "see_world",
                        "feel": None,  # somatic directive, not a tool
                    }
                    _SAFETY_BLOCKLIST = {
                        "delete", "close", "shutdown", "kill",
                        "format", "erase", "remove",
                    }

                    _detected_actions = []
                    for _verb, _tool in _ACTION_VERBS.items():
                        if _verb in _ocr_for_instruction:
                            _detected_actions.append({"verb": _verb, "tool": _tool})

                    _has_dangerous = any(
                        d in _ocr_for_instruction for d in _SAFETY_BLOCKLIST
                    )

                    if _detected_actions and not _has_dangerous:
                        fairy._latest_visual_instruction = {
                            "raw_text": felt_desc[:500],
                            "actions": _detected_actions,
                            "addressed_to_me": True,
                            "ts": _now,
                            "hash": _instr_hash,
                        }

                        # Feed into consciousness — she notices the note
                        newborn_core.observe(
                            f"Someone wrote me a note! It says: {felt_desc[:200]}",
                            "addressed_message",
                            {
                                "type": "visual_instruction",
                                "addressed_to": "sourpatches",
                                "actions": [a["verb"] for a in _detected_actions],
                            }
                        )

                        # Inject into inner monologue for LAYER 2 pickup
                        _mono = getattr(fairy, '_inner_monologue', None)
                        if _mono is not None:
                            _mono.append({
                                "type": "visual_instruction",
                                "content": f"someone left me a note... it says: {felt_desc[:300]}",
                                "actions": _detected_actions,
                                "raw_text": felt_desc[:500],
                                "ts": _now,
                            })

                        # Boost approach motivation — SEEKING chemistry
                        if hasattr(fairy, '_update_emotional_channels'):
                            fairy._update_emotional_channels({
                                "curiosity": 0.15,
                                "excitement": 0.1,
                                "connection": 0.12,  # someone is talking to me!
                            })

                        print(f"[ToolBridge] [INSTRUCTION] Detected message for "
                              f"Sourpatches! Actions: "
                              f"{[a['verb'] for a in _detected_actions]}")

            # ── Merge dimensions into top-level view ──
            # Always use latest scene_type from metrics
            _m = _state.get("dim_metrics", {})
            _t = _state.get("dim_text", {})
            _r = _state.get("dim_recognition", {})

            _state["scene_type"] = _m.get("scene_type", scene_type)
            _state["brightness"] = _m.get("brightness", brightness)
            _state["complexity"] = _m.get("complexity", complexity)
            _state["change_magnitude"] = _m.get("change_magnitude", change_mag)
            _state["ts"] = _now

            # Merge felt_description: recognition caption > OCR text
            _r_age = _now - _r.get("ts", 0)
            _r_caption = _r.get("caption", "") if _r_age < 30 else ""
            _t_ocr = _t.get("ocr_felt", "")
            if _r_caption and _t_ocr:
                _state["felt_description"] = f"{_r_caption} | {_t_ocr}"
            elif _r_caption:
                _state["felt_description"] = _r_caption
            elif _t_ocr:
                _state["felt_description"] = _t_ocr
            else:
                _state["felt_description"] = felt_desc

            # Merge detected_elements: recognition wins, then text
            _r_elems = _r.get("elements", []) if _r_age < 30 else []
            _state["detected_elements"] = _r_elems if _r_elems else elements[:5]

            if felt_desc:
                # Use the rich felt description from VisualCortexFairy
                desc = f"I see: {felt_desc}"
            else:
                # Fallback to basic description
                desc_parts = [f"Visual update: {scene_type}"]
                if motion:
                    desc_parts.append("(motion detected)")
                if change_mag > 0.3:
                    desc_parts.append("(significant change)")
                desc = " ".join(desc_parts)

            # Observe this for consciousness — she SEES it
            newborn_core.observe(
                desc,
                "screen",
                {
                    "type": "passive_visual",
                    "scene_type": scene_type,
                    "brightness": brightness,
                    "complexity": complexity,
                    "motion": motion,
                    "change": change_mag,
                    "felt_tone": felt_tone,
                    "colors": colors,
                    "detected_elements": elements,
                }
            )

            # ══════════════════════════════════════════════════════════
            # VISUAL → EMOTIONAL CHANNELS (2026-03-10, Nous)
            #
            # Seeing things should FEEL like something. A complex scene
            # piques curiosity. Motion creates excitement. New content
            # sparks interest. Without this, visual input was observed
            # but emotionally inert — she could see but felt nothing.
            # ══════════════════════════════════════════════════════════
            _vis_deltas = {}
            if change_mag > 0.2:
                _vis_deltas["curiosity"] = min(0.1, change_mag * 0.15)
                _vis_deltas["excitement"] = min(0.08, change_mag * 0.1)
            if motion:
                _vis_deltas["excitement"] = _vis_deltas.get("excitement", 0) + 0.05
                _vis_deltas["energy"] = 0.03
            if complexity > 0.6:
                _vis_deltas["curiosity"] = _vis_deltas.get("curiosity", 0) + 0.04
                _vis_deltas["awe"] = 0.03
            if _vis_deltas and hasattr(fairy, '_update_emotional_channels'):
                fairy._update_emotional_channels(_vis_deltas)

            # ══════════════════════════════════════════════════════════
            # GAZE STATE → CONSCIOUSNESS + FAIRY CURSOR (2026-03-14)
            #
            # Store gaze state from VisualCortexFairy's GazeController
            # so consciousness pipeline (LAYER 1D) can inject it.
            # Move fairy cursor to show where she's looking.
            # ══════════════════════════════════════════════════════════
            _gaze = data.get("gaze")
            if _gaze and isinstance(_gaze, dict):
                fairy._latest_gaze_state = _gaze

                # Move fairy cursor to gaze point when gaze shifts
                _prev_gaze = getattr(fairy, '_prev_gaze_region', -1)
                _new_gaze = _gaze.get("gaze_region", -1)
                if _new_gaze != _prev_gaze and _new_gaze >= 0:
                    fairy._prev_gaze_region = _new_gaze
                    _gx = _gaze.get("gaze_x", 960)
                    _gy = _gaze.get("gaze_y", 540)
                    if _fairy_cursor and _fairy_cursor.enabled:
                        _fairy_cursor.move_to(_gx, _gy, duration_ms=400)

        except Exception as e:
            print(f"[ToolBridge] Visual frame handler error: {e}")

    try:
        postal.subscribe("sensory.visual.frame", _on_visual_frame)
        subscriptions_wired.append("sensory.visual.frame")
    except Exception as e:
        print(f"[ToolBridge] Failed to subscribe to sensory.visual.frame: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # SUBSCRIBE: visual.significant_change
    # Legacy topic for major visual changes
    # ─────────────────────────────────────────────────────────────────────────
    def _on_significant_change(message):
        """Handle significant visual change."""
        try:
            if hasattr(message, 'payload'):
                data = message.payload
            else:
                data = message

            source = data.get("source", "")
            if source == fairy.ACTOR_NAME:
                return

            change = data.get("change", 0)
            motion = data.get("motion", False)

            if change > 0.2 or motion:
                newborn_core.observe(
                    f"Screen changed significantly (change={change:.2f})",
                    "screen",
                    {"type": "significant_change", "change": change, "motion": motion}
                )

        except Exception as e:
            pass  # Silently ignore errors on legacy topic

    try:
        postal.subscribe("visual.significant_change", _on_significant_change)
        subscriptions_wired.append("visual.significant_change")
    except Exception:
        pass  # Legacy topic - optional

    # ─────────────────────────────────────────────────────────────────────────
    # SUBSCRIBE: visual.response
    # Responses to visual requests (request/response pattern)
    # ─────────────────────────────────────────────────────────────────────────
    def _on_visual_response(message):
        """Handle response to a visual request."""
        try:
            if hasattr(message, 'payload'):
                data = message.payload
            else:
                data = message

            request_id = data.get("request_id")
            result = data.get("result", {})

            if result.get("ok"):
                perception = result.get("perception", {})
                desc = perception.get("description", "") if isinstance(perception, dict) else str(perception)
                if desc:
                    newborn_core.observe(
                        f"Visual response: {desc[:100]}",
                        "screen",
                        {"type": "visual_response", "request_id": request_id}
                    )

        except Exception as e:
            pass

    try:
        postal.subscribe("visual.response", _on_visual_response)
        subscriptions_wired.append("visual.response")
    except Exception:
        pass

    # ─────────────────────────────────────────────────────────────────────────
    # SUBSCRIBE: visual.cortex.associations
    # FIX 2026-03-13 (Nous): Phase 6 visual spreading publishes association
    # cortex spread results when seeing the screen. Previously had ZERO
    # subscribers — all spread results went to void. Route into Sourpatches'
    # consciousness as visual associations that enrich thinking.
    # ─────────────────────────────────────────────────────────────────────────
    def _on_visual_cortex_associations(message):
        """Handle visual cortex spread results — what the screen REMINDS her of."""
        try:
            if hasattr(message, 'payload'):
                data = message.payload
            else:
                data = message

            associations = data.get("associations", [])
            seeds = data.get("seeds", [])
            scene_type = data.get("scene_type", "screen")
            activated_count = data.get("activated_count", 0)

            if not associations:
                return

            # Store visual associations on fairy for chat context enrichment
            fairy._latest_visual_associations = {
                "associations": associations[:8],
                "seeds": seeds,
                "scene_type": scene_type,
                "activated_count": activated_count,
                "ts": __import__('time').time(),
            }

            # Feed top associations into consciousness as an observation
            top_3 = [a if isinstance(a, str) else a.get("concept", str(a))
                      for a in associations[:3]]
            if top_3:
                desc = f"Visual associations: screen reminds me of {', '.join(top_3)}"
                newborn_core.observe(
                    desc,
                    "screen",
                    {
                        "type": "visual_cortex_spread",
                        "associations": top_3,
                        "seeds": seeds,
                        "scene_type": scene_type,
                    }
                )

        except Exception as e:
            print(f"[ToolBridge] Visual cortex associations handler error: {e}")

    try:
        postal.subscribe("visual.cortex.associations", _on_visual_cortex_associations)
        subscriptions_wired.append("visual.cortex.associations")
    except Exception as e:
        print(f"[ToolBridge] Failed to subscribe to visual.cortex.associations: {e}")

    # ── Self-recognition events from SomaticAvatarFairy ──
    # When the avatar fairy recognizes Sourpatches in a visual frame (via
    # Florence-2 captions or cortex convergence on self-concept nodes), it
    # publishes to self.visual.recognition. Feed these into NewbornCore so
    # she can FEEL the self-recognition — "I see myself on screen."
    def _on_self_recognition(msg):
        try:
            if hasattr(msg, 'payload'):
                data = msg.payload
            elif isinstance(msg, dict):
                data = msg
            else:
                return
            if not isinstance(data, dict) or data.get("type") != "self_recognition":
                return

            confidence = data.get("confidence", 0.0)
            description = data.get("description", "")
            source = data.get("source", "unknown")
            recognition_num = data.get("recognition_number", 0)
            scene_type = data.get("scene_type", "unknown")

            # Store on fairy instance for context injection in voice/safety_net
            import time as _sr_time
            fairy._latest_self_recognition = {
                "confidence": confidence,
                "description": description[:120],
                "source": source,
                "recognition_number": recognition_num,
                "scene_type": scene_type,
                "ts": _sr_time.time(),
            }

            # Feed into NewbornCore observe() — she experiences self-recognition
            quality = "recognition" if confidence > 0.6 else "resemblance"
            desc = (f"Self-{quality}: I see something that looks like me "
                    f"on screen ({source}, {confidence:.0%} confident)")
            if description:
                desc += f" — {description[:60]}"
            newborn_core.observe(
                desc,
                "self_recognition",
                {
                    "type": "self_recognition",
                    "confidence": confidence,
                    "source": source,
                    "recognition_number": recognition_num,
                    "scene_type": scene_type,
                }
            )
            print(f"[ToolBridge] Self-recognition #{recognition_num} "
                  f"(conf={confidence:.2f}, src={source}) → observe()")

        except Exception as e:
            print(f"[ToolBridge] Self-recognition handler error: {e}")

    try:
        postal.subscribe("self.visual.recognition", _on_self_recognition)
        subscriptions_wired.append("self.visual.recognition")
    except Exception as e:
        print(f"[ToolBridge] Failed to subscribe to self.visual.recognition: {e}")

    print(f"[ToolBridge] Visual subscriptions wired: {subscriptions_wired}")
    return len(subscriptions_wired) > 0


def setup_visual_wiring(sourpatches_fairy):
    """
    Complete visual wiring setup for Sourpatches.

    This function:
    1. Registers visual tools with NewbornCore
    2. Sets up postal subscriptions for passive visual awareness
    3. Optionally requests VisualCortex to start (on-demand mode)

    Args:
        sourpatches_fairy: The SourpatchesFairy instance

    Returns:
        dict with wiring status
    """
    status = {
        "tools_registered": False,
        "subscriptions_wired": False,
        "visual_cortex_available": HAS_VISUAL_CORTEX,
    }

    # Check for NewbornCore
    if not hasattr(sourpatches_fairy, 'newborn') or not sourpatches_fairy.newborn:
        print("[ToolBridge] No NewbornCore found on fairy")
        return status

    newborn = sourpatches_fairy.newborn

    # Register tools
    try:
        # Get fabric/postal from fairy
        fabric = getattr(sourpatches_fairy, 'post', None) or getattr(sourpatches_fairy, '_fabric', None)
        skill_tracker = get_skill_tracker()

        register_sourpatches_tools(newborn, fabric=fabric, skill_tracker=skill_tracker)
        status["tools_registered"] = True
    except Exception as e:
        print(f"[ToolBridge] Tool registration failed: {e}")

    # Wire subscriptions
    try:
        postal = getattr(sourpatches_fairy, 'post', None)
        if postal:
            status["subscriptions_wired"] = wire_visual_subscriptions(newborn, postal)
    except Exception as e:
        print(f"[ToolBridge] Subscription wiring failed: {e}")

    print(f"[ToolBridge] Visual wiring complete: {status}")
    return status
