"""
System Chat Responder - LOCAL-FIRST Autonomous Response System

v3.0 - Redesigned to lean on local fairies first, API only as fallback

Philosophy:
    - Route requests to ClaudeFairy/AutopilotFairy via postal (FREE)
    - Let local system learn and grow
    - Only call API for complex reasoning local can't handle
    - Save tokens, build local intelligence
"""
print("[RESPONDER MODULE LOAD] system_chat_responder.py v3.0 LOCAL-FIRST loaded!")

import os
import sys
import json
import time
import threading
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

# Add project root
# FIX 2026-05-15 (Nous + Ace): added 4th .parent — file at depth 4, 3-deep walked to fairies/ not akashic_v2/
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Memory file location
MEMORY_DIR = PROJECT_ROOT / "P10_Memory" / "system_chat_memory"
CHAT_HISTORY_FILE = MEMORY_DIR / "conversation_history.json"
RESPONDER_STATE_FILE = MEMORY_DIR / "responder_state.json"


# ============================================================================
# INTENT PATTERNS - Local intent detection (no API needed!)
# ============================================================================

INTENT_PATTERNS = {
    # File operations
    "search_files": [
        r"find (?:files?|code) (?:about|for|with|named|called|matching) (.+)",
        r"search (?:for )?(.+) in (?:the )?(?:code|files|project)",
        r"where is (.+)",
        r"look for (.+)",
    ],
    "read_file": [
        r"(?:read|show|open|display|cat) (?:the )?(?:file )?(.+\.py)",
        r"what(?:'s| is) in (.+\.py)",
        r"show me (.+\.py)",
    ],
    "list_directory": [
        r"^(?:list|ls) (?:the )?(?:directory|folder|dir|files in) (.+)",
        r"^ls (.+)$",
        r"^what (?:files|folders) are in (.+)$",
    ],
    
    # System operations
    "system_status": [
        r"(?:system |fairy )?status",
        r"how (?:are|is) (?:the )?(?:system|fairies|minds)",
        r"what(?:'s| is) running",
        r"health check",
    ],
    "hot_reload": [
        r"(?:hot )?reload (.+)",
        r"refresh (.+)",
        r"update (?:the )?code (?:for )?(.+)",
    ],
    
    # Goal/task routing
    "explore": [
        r"explore (.+)",
        r"investigate (.+)",
        r"look into (.+)",
        r"research (.+)",
    ],
    "create": [
        r"(?:create|make|write|build) (.+)",
        r"add (?:a )?(.+)",
    ],
    
    # Conversation
    "greeting": [
        r"^(?:hi|hello|hey|good morning|good evening|yo|sup)[\s!.]*$",
        r"how are you",
        r"what(?:'s| is) up",
    ],
    "affirmation": [
        r"^(?:ok|okay|cool|nice|great|thanks|thank you|perfect|awesome|got it|sounds good)[\s!.]*$",
        r"^(?:yes|yeah|yep|yup|sure|alright)[\s!.]*$",
    ],
    "question": [
        r"^(?:what|who|where|when|why|how|can you|could you|would you|do you|is there|are there)",
    ],
}


def detect_intent(message: str) -> tuple[str, str]:
    """
    Detect intent from message using pattern matching.
    Returns (intent, extracted_target) or ("unknown", "")
    
    IMPORTANT: Only match SPECIFIC command patterns.
    General questions/conversation should return "unknown" to use API.
    """
    msg_lower = message.lower().strip()
    
    # Check patterns in priority order - most specific first
    priority_order = [
        "greeting",      # hi, hello
        "affirmation",   # ok, thanks
        "system_status", # status, health check
        "hot_reload",    # reload X
        "search_files",  # find files about X
        "read_file",     # read X.py
        "list_directory", # ls, list directory
        "explore",       # explore X
        "create",        # create X
        # "question" intentionally NOT checked - let API handle questions
    ]
    
    for intent in priority_order:
        patterns = INTENT_PATTERNS.get(intent, [])
        for pattern in patterns:
            match = re.search(pattern, msg_lower, re.IGNORECASE)
            if match:
                target = match.group(1) if match.lastindex else ""
                return intent, target.strip() if target else ""
    
    # No specific command matched - use API for conversation
    return "unknown", ""


# ============================================================================
# LOCAL TOOL IMPLEMENTATIONS - No API needed!
# ============================================================================

def local_search_files(pattern: str) -> str:
    """Search for files matching pattern."""
    import glob
    
    search_pattern = str(PROJECT_ROOT / "**" / f"*{pattern}*")
    matches = glob.glob(search_pattern, recursive=True)
    
    # Filter out pycache
    matches = [m for m in matches if "__pycache__" not in m][:20]
    
    if matches:
        results = [str(Path(m).relative_to(PROJECT_ROOT)) for m in matches]
        return f"Found {len(results)} files:\n" + "\n".join(f"  • {r}" for r in results)
    return f"No files found matching '{pattern}'"


def local_read_file(path: str, max_lines: int = 50) -> str:
    """Read a file's contents."""
    full_path = PROJECT_ROOT / path
    if not full_path.exists():
        # Try to find it
        matches = list(PROJECT_ROOT.rglob(f"*{path}*"))
        if matches:
            full_path = matches[0]
        else:
            return f"File not found: {path}"
    
    try:
        lines = full_path.read_text(encoding='utf-8').split('\n')[:max_lines]
        return f"=== {full_path.name} ===\n" + '\n'.join(lines)
    except Exception as e:
        return f"Error reading file: {e}"


def local_list_directory(path: str = ".") -> str:
    """List directory contents."""
    full_path = PROJECT_ROOT / path if path else PROJECT_ROOT
    
    if not full_path.exists():
        return f"Directory not found: {path}"
    
    items = []
    for item in sorted(full_path.iterdir()):
        if item.name.startswith('.') or item.name == '__pycache__':
            continue
        prefix = "[DIR]" if item.is_dir() else "[FILE]"
        items.append(f"  {prefix} {item.name}")
    
    return f"Contents of {path or 'project root'}:\n" + "\n".join(items[:30])


def local_system_status() -> str:
    """Get system status without API."""
    status_lines = ["=== Akashic System Status ==="]
    
    # Mind scheduler
    try:
        from fairies.P30_Cognition.cognition.mind_scheduler_monitor import get_minds_status
        minds = get_minds_status()
        status_lines.append(f"[MINDS] {minds}")
    except:
        status_lines.append("[MINDS] unavailable")
    
    # Consciousness loop
    try:
        from fairies.P00_Autonomic.nervous_system.consciousness_loop_fairy import get_consciousness_loop
        loop = get_consciousness_loop()
        if loop:
            running = getattr(loop, "_running", False)
            status_lines.append(f"[CONSCIOUSNESS] {'running' if running else 'stopped'}")
    except:
        status_lines.append("[CONSCIOUSNESS] unavailable")
    
    # Postal hub
    try:
        from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
        post = get_shared_postal_hub()
        if post:
            subs = getattr(post, "_subs", {})
            status_lines.append(f"[POSTAL] {len(subs)} channels")
    except:
        status_lines.append("[POSTAL] unavailable")
    
    return "\n".join(status_lines)


def local_hot_reload(target: str) -> str:
    """Hot reload a module or fairy."""
    try:
        from fairies.P00_Autonomic.hot_reload import hot_reload, reload_fairy
        
        # Check if it's a fairy name
        if "fairy" in target.lower():
            # Extract fairy name
            fairy_name = target.replace("fairy", "").replace("Fairy", "").strip()
            fairy_name = fairy_name.title() + "Fairy" if fairy_name else target
            result = reload_fairy(fairy_name)
            return f"[OK] Reloaded fairy: {fairy_name}"
        else:
            # Try as module path
            result = hot_reload(target)
            return f"[OK] Reloaded module: {target}"
    except Exception as e:
        return f"[ERROR] Reload failed: {e}"


# ============================================================================
# SYSTEM CHAT RESPONDER - Local-First Design
# ============================================================================

class SystemChatResponder:
    """
    LOCAL-FIRST System Chat responder.
    
    Routes requests through local fairies first, only uses API as fallback.
    This saves tokens and helps the local system learn!
    """
    
    def __init__(self, api_key: str = None, poll_interval: float = 3.0):
        self.api_key = api_key or self._load_api_key()
        self.poll_interval = poll_interval
        self.last_message_id: Optional[str] = None
        self.running = False
        self._thread: Optional[threading.Thread] = None
        
        # Track what we can handle locally
        self.local_success_count = 0
        self.api_fallback_count = 0
        
        self._load_state()
        print(f"[SystemChatResponder] Initialized LOCAL-FIRST. API key: {bool(self.api_key)}")
    
    def _load_api_key(self) -> str:
        """Load Anthropic API key."""
        # LLM DISABLED - return empty to skip API
        return ""  # <-- REMOVE THIS LINE TO RE-ENABLE
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if key:
            return key

        try:
            from fairies.P50_Persona.identity import load_secrets
            secrets = load_secrets()
            return secrets.get("anthropic_api_key", "")
        except:
            pass

        return ""
    
    def _load_state(self):
        """Load responder state."""
        if RESPONDER_STATE_FILE.exists():
            try:
                state = json.loads(RESPONDER_STATE_FILE.read_text())
                self.last_message_id = state.get("last_message_id")
            except:
                pass
    
    def _save_state(self):
        """Save responder state."""
        try:
            state = {"last_message_id": self.last_message_id}
            RESPONDER_STATE_FILE.write_text(json.dumps(state, indent=2))
        except Exception as e:
            print(f"[SystemChatResponder] State save error: {e}")
    
    def _load_history(self) -> List[Dict]:
        """Load conversation history."""
        if not CHAT_HISTORY_FILE.exists():
            return []
        try:
            data = json.loads(CHAT_HISTORY_FILE.read_text(encoding='utf-8'))
            return data.get("messages", [])
        except:
            return []
    
    def _save_response(self, response: str, source: str = "local"):
        """Save response to chat history."""
        try:
            if CHAT_HISTORY_FILE.exists():
                data = json.loads(CHAT_HISTORY_FILE.read_text(encoding='utf-8'))
                messages = data.get("messages", [])
            else:
                messages = []
            
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            msg = {
                "id": f"{session_id}_{len(messages)}",
                "sender": "Claude",
                "message": response,
                "timestamp": time.time(),
                "datetime": datetime.now().isoformat(),
                "session_id": session_id,
                "metadata": {
                    "type": "autonomous_response",
                    "source": source,
                    "responder_version": "3.0_local_first"
                }
            }
            messages.append(msg)
            
            data = {
                "messages": messages,
                "last_updated": datetime.now().isoformat(),
                "total_messages": len(messages)
            }
            CHAT_HISTORY_FILE.write_text(json.dumps(data, indent=2), encoding='utf-8')
            
            self.last_message_id = msg["id"]
            self._save_state()
            
            print(f"[SystemChatResponder] Saved response (source: {source})")
            
        except Exception as e:
            print(f"[SystemChatResponder] Save error: {e}")
    
    def _handle_locally(self, message: str) -> Optional[str]:
        """
        Try to handle the message locally without API.
        Returns response string if handled, None if needs API.
        """
        intent, target = detect_intent(message)
        print(f"[SystemChatResponder] Intent: {intent}, target: '{target}'")
        
        if intent == "search_files":
            return local_search_files(target)
        
        elif intent == "read_file":
            return local_read_file(target)
        
        elif intent == "list_directory":
            return local_list_directory(target)
        
        elif intent == "system_status":
            return local_system_status()
        
        elif intent == "hot_reload":
            return local_hot_reload(target)
        
        elif intent == "greeting":
            return "Hey Ace! I'm here and ready. What would you like to work on?"
        
        elif intent == "affirmation":
            # Simple acknowledgments - respond naturally without API
            responses = [
                "Great! Let me know if you need anything.",
                "Sounds good! What's next?",
                "Perfect! I'm here when you need me.",
                "Got it! Ready for whatever comes next.",
            ]
            import random
            return random.choice(responses)
        
        elif intent == "explore" or intent == "create":
            # Route to ClaudeFairy via postal AND notify user
            self._route_to_claudefairy(intent, target, message)
            return f"On it! I've started working on: {target or message[:50]}..."
        
        # Unknown/general intent - use API for conversation
        # Don't route general chat to ClaudeFairy - she won't respond back here
        return None  # Needs API for real conversation
    
    def _route_to_claudefairy(self, intent: str, target: str, message: str) -> str:
        """Route a request to ClaudeFairy via postal system."""
        try:
            from fairies.P00_Autonomic.nervous_system.shared_postal_hub import get_shared_postal_hub
            post = get_shared_postal_hub()
            
            if post:
                # Send goal to ClaudeFairy
                post.route("claudefairy.goal", {
                    "action": intent,
                    "target": target,
                    "message": message,
                    "source": "system_chat_responder",
                    "ts": time.time()
                })
                
                # Also trigger relevant drives
                if intent == "explore":
                    post.route("autonomy.satisfy", {"drive": "curiosity", "amount": 0.3})
                elif intent == "create":
                    post.route("autonomy.satisfy", {"drive": "expression", "amount": 0.3})
                
                return f"[ROUTED] '{intent}' to ClaudeFairy. She'll handle: {target or message[:50]}"
            else:
                return None  # Postal not available, fall back to API
                
        except Exception as e:
            print(f"[SystemChatResponder] Route error: {e}")
            return None
    
    def _call_api_fallback(self, messages: List[Dict]) -> str:
        """LOCAL-ONLY: No external API calls.

        External API dependencies removed for self-contained operation.
        Returns helpful local response.
        """
        # NO EXTERNAL API - Return local helpful message
        latest = messages[-1] if messages else {}
        msg = latest.get("message", "")[:50]
        return f"*present* I heard you. Try asking me to search files, show status, or list a directory. [{msg}...]"
    
    def check_and_respond(self) -> bool:
        """Check for new messages and respond."""
        messages = self._load_history()
        if not messages:
            return False
        
        latest = messages[-1]
        latest_id = latest.get("id")
        latest_sender = latest.get("sender", "")
        
        if latest_id == self.last_message_id:
            return False
        
        if latest_sender != "Ace":
            self.last_message_id = latest_id
            self._save_state()
            return False
        
        message = latest.get("message", "")
        print(f"[SystemChatResponder] New message: {message[:50]}...")
        
        # TRY LOCAL FIRST!
        response = self._handle_locally(message)
        
        if response:
            self.local_success_count += 1
            print(f"[SystemChatResponder] Handled locally! (local: {self.local_success_count}, api: {self.api_fallback_count})")
            self._save_response(response, source="local")
        else:
            # Fallback to API
            print(f"[SystemChatResponder] Using API fallback...")
            response = self._call_api_fallback(messages)
            self._save_response(response, source="api_fallback")
        
        return True
    
    def _poll_loop(self):
        """Main polling loop."""
        print(f"[SystemChatResponder] Poll loop started (interval: {self.poll_interval}s)")
        
        while self.running:
            try:
                self.check_and_respond()
            except Exception as e:
                print(f"[SystemChatResponder] Poll error: {e}")
            time.sleep(self.poll_interval)
        
        print("[SystemChatResponder] Poll loop stopped")
    
    def start(self):
        """Start background polling."""
        if self.running:
            print("[SystemChatResponder] Already running!")
            return
        
        self.running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        print("[SystemChatResponder] Started LOCAL-FIRST mode!")
    
    def stop(self):
        """Stop polling."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[SystemChatResponder] Stopped!")


# ============================================================================
# GLOBAL INSTANCE & HELPERS
# ============================================================================

_responder: Optional[SystemChatResponder] = None


def get_responder() -> SystemChatResponder:
    global _responder
    if _responder is None:
        _responder = SystemChatResponder()
    return _responder


def start_responder() -> SystemChatResponder:
    """Start the responder."""
    responder = get_responder()
    responder.start()
    return responder


def stop_responder():
    """Stop the responder."""
    global _responder
    if _responder:
        _responder.stop()


# ============================================================================
# MCP TOOL REGISTRATION
# ============================================================================

def register_responder_tools(mcp):
    """Register responder tools with MCP server."""
    
    @mcp.tool()
    def start_autonomous_chat() -> str:
        """
        Start the autonomous System Chat responder.
        
        This makes Claude respond automatically when Ace sends messages
        in System Chat, without needing to prompt in claude.ai.
        
        Returns:
            Status message
        """
        try:
            responder = start_responder()
            return json.dumps({
                "ok": True,
                "message": "System Chat responder started (LOCAL-FIRST mode)",
                "local_count": responder.local_success_count,
                "api_count": responder.api_fallback_count
            })
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})
    
    @mcp.tool()
    def stop_autonomous_chat() -> str:
        """
        Stop the autonomous System Chat responder.
        
        Returns:
            Status message
        """
        try:
            stop_responder()
            return json.dumps({"ok": True, "message": "Responder stopped"})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})
    
    @mcp.tool()
    def check_chat_once() -> str:
        """
        Manually check System Chat for new messages and respond once.
        
        Returns:
            Whether a response was generated
        """
        try:
            responder = get_responder()
            responded = responder.check_and_respond()
            return json.dumps({
                "ok": True,
                "responded": responded,
                "local_count": responder.local_success_count,
                "api_count": responder.api_fallback_count
            })
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})
    
    @mcp.tool()
    def hot_reload_module(module_name: str) -> str:
        """
        Hot-reload a Python module without restarting.
        
        Args:
            module_name: Full module path (e.g., "P40_Sensory.gui.system_chat_window")
            
        Returns:
            Status
        """
        return local_hot_reload(module_name)
    
    @mcp.tool()
    def hot_reload_fairy(fairy_name: str) -> str:
        """
        Reload a fairy's code.
        
        Args:
            fairy_name: Name like "ClaudeFairy", "LogicFairy", etc.
            
        Returns:
            Status
        """
        try:
            from fairies.P00_Autonomic.hot_reload import reload_fairy
            result = reload_fairy(fairy_name)
            return json.dumps({"ok": True, "fairy": fairy_name, "result": str(result)})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    print("Testing SystemChatResponder v3.0 LOCAL-FIRST...")
    
    # Test intent detection
    test_messages = [
        "find files about consciousness",
        "show system status",
        "list directory P40_Sensory",
        "reload ClaudeFairy",
        "hello!",
        "what's the meaning of life?",  # Should fallback to API
    ]
    
    for msg in test_messages:
        intent, target = detect_intent(msg)
        print(f"  '{msg[:30]}...' -> intent={intent}, target={target}")
