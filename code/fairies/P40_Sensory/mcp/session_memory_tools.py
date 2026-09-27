"""
Session Memory Tools - MCP tool registration for session persistence

Provides tools for saving Claude App sessions to the Akashic memory system
for persistent recall across sessions.

Tools:
    - save_app_session: Save a session to memory
    - recall_sessions: List recent saved sessions
    - get_session: Retrieve a specific session by hash
"""

import sys
import json
from pathlib import Path

# Add memory path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "P10_Memory" / "tools"))


def register_session_memory_tools(mcp):
    """
    Register session memory tools with the MCP server.
    
    Args:
        mcp: The FastMCP instance
    """
    
    # Import the core functions
    try:
        from save_app_session import (
            save_app_session as _save_session,
            recall_recent_sessions as _recall_recent,
            recall_session_by_hash as _recall_by_hash
        )
    except ImportError as e:
        sys.stderr.write(f"[SessionMemory] Import error: {e}\n")
        return
    
    @mcp.tool()
    def save_app_session(
        content: str,
        title: str = "",
        tags: str = "",
        session_type: str = "app_chat"
    ) -> str:
        """
        Save a Claude App session to the Akashic memory system.
        
        This saves to THREE locations:
        1. SRM_Intake - for collision chamber processing
        2. Claude's Office - for direct recall
        3. Archive - for long-term storage
        
        Args:
            content: The full session content/transcript
            title: Optional title for the session  
            tags: Comma-separated tags (e.g., "evolution,somatic,boot")
            session_type: Type of session (default: app_chat)
        
        Returns:
            JSON with save status and paths
        """
        try:
            result = _save_session(content, title, tags, session_type)
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e), "status": "failed"})
    
    @mcp.tool()
    def recall_sessions(n: int = 10) -> str:
        """
        Recall the N most recent saved sessions from Claude's office.
        
        Returns list of session summaries (without full content).
        
        Args:
            n: Number of recent sessions to retrieve (default: 10)
        
        Returns:
            JSON list of session summaries
        """
        try:
            sessions = _recall_recent(n)
            return json.dumps(sessions, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @mcp.tool()
    def get_session(content_hash: str) -> str:
        """
        Retrieve a specific session by its content hash.
        
        Returns the full session including content.
        
        Args:
            content_hash: The hash of the session to retrieve
        
        Returns:
            JSON with full session record
        """
        try:
            session = _recall_by_hash(content_hash)
            if session:
                return json.dumps(session, indent=2)
            else:
                return json.dumps({"error": f"Session not found: {content_hash}"})
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    sys.stderr.write("[SessionMemory] [OK] Session memory tools registered\n")


if __name__ == "__main__":
    # Test imports
    from save_app_session import save_app_session, recall_recent_sessions
    print("Imports OK")
    
    # Test save
    result = save_app_session(
        content="Test session content",
        title="Test",
        tags="test"
    )
    print(f"Save result: {result}")
