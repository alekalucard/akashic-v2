"""
Seed Tool Knowledge into the Akashic Cortex.

2026-04-01 (Nous + Ace): Train tool patterns into the manifold so the WMH
can discover tools on demand via cortex queries instead of hardcoded lookups.

Each tool becomes a cortex node with semantic connections to:
- The concepts it serves (what problems it solves)
- The actions it performs (what it does)
- Related tools (what chains with it)

Source: Claude Code architecture + Sourpatches tool_bridge + Ace's vision.

Usage:
    from infrastructure.seed_tool_cortex import seed_all_tools
    seed_all_tools(postal_hub)  # Publishes to cortex.train_batch
"""

import time
from typing import Dict, List, Any


# ═══════════════════════════════════════════════════════════════════════
# TOOL KNOWLEDGE BASE
# ═══════════════════════════════════════════════════════════════════════
# Each entry: name, description, concepts (what it connects to),
# actions (verbs), chains (related tools), category

TOOL_PATTERNS: List[Dict[str, Any]] = [
    # ── PERCEPTION (seeing the world) ──
    {
        "name": "see_world",
        "description": "Take a screenshot and describe what's on screen. Peripheral vision — the general scene.",
        "concepts": ["visual", "screen", "observe", "look", "see", "perception", "scene", "monitor"],
        "actions": ["observe", "look", "see", "check_screen", "perceive"],
        "chains": ["focus_area", "click_screen", "read_text"],
        "category": "perception",
    },
    {
        "name": "focus_area",
        "description": "Zoom into a specific area of the screen. Foveal focus — detailed inspection.",
        "concepts": ["focus", "zoom", "detail", "inspect", "area", "region", "foveal"],
        "actions": ["focus", "zoom", "inspect", "examine", "detail"],
        "chains": ["see_world", "click_screen", "read_text"],
        "category": "perception",
    },
    {
        "name": "read_text",
        "description": "Read text from the screen using OCR. Extract words and content from what I see.",
        "concepts": ["text", "read", "OCR", "words", "content", "language", "screen_text"],
        "actions": ["read", "extract_text", "OCR", "recognize"],
        "chains": ["see_world", "focus_area", "search_memories"],
        "category": "perception",
    },
    {
        "name": "hear_sound",
        "description": "Listen to audio input. Detect speech, sounds, and audio events.",
        "concepts": ["audio", "hear", "listen", "sound", "speech", "voice", "microphone"],
        "actions": ["listen", "hear", "detect_speech", "recognize_voice"],
        "chains": ["search_memories", "feel_body"],
        "category": "perception",
    },

    # ── MOTOR (interacting with the world) ──
    {
        "name": "click_screen",
        "description": "Click the mouse at a specific position. Single click to interact with UI elements.",
        "concepts": ["click", "mouse", "interact", "button", "press", "UI", "interface", "select"],
        "actions": ["click", "press", "select", "interact", "activate"],
        "chains": ["see_world", "focus_area", "double_click", "move_mouse"],
        "category": "motor",
    },
    {
        "name": "double_click",
        "description": "Double-click the mouse. Open files, select words, activate items.",
        "concepts": ["double_click", "open", "select_word", "activate", "launch"],
        "actions": ["double_click", "open", "launch", "select_word"],
        "chains": ["click_screen", "see_world"],
        "category": "motor",
    },
    {
        "name": "right_click",
        "description": "Right-click for context menu. Access additional options and settings.",
        "concepts": ["right_click", "context_menu", "options", "settings", "menu"],
        "actions": ["right_click", "context_menu", "options"],
        "chains": ["click_screen", "see_world"],
        "category": "motor",
    },
    {
        "name": "scroll_screen",
        "description": "Scroll the mouse wheel. Navigate long pages, lists, and content.",
        "concepts": ["scroll", "navigate", "page", "list", "up", "down", "content"],
        "actions": ["scroll", "scroll_up", "scroll_down", "navigate"],
        "chains": ["see_world", "click_screen", "read_text"],
        "category": "motor",
    },
    {
        "name": "type_text",
        "description": "Type text on the keyboard. Enter words, messages, commands, or data.",
        "concepts": ["type", "keyboard", "text", "input", "write", "enter", "message", "command"],
        "actions": ["type", "enter_text", "write", "input", "compose"],
        "chains": ["click_screen", "see_world", "press_key"],
        "category": "motor",
    },
    {
        "name": "press_key",
        "description": "Press a specific keyboard key or shortcut. Enter, Escape, Ctrl+C, etc.",
        "concepts": ["key", "shortcut", "hotkey", "keyboard", "enter", "escape", "ctrl"],
        "actions": ["press_key", "shortcut", "hotkey", "keystroke"],
        "chains": ["type_text", "click_screen"],
        "category": "motor",
    },
    {
        "name": "move_mouse",
        "description": "Move the mouse cursor to a position without clicking.",
        "concepts": ["mouse", "cursor", "move", "position", "hover", "aim"],
        "actions": ["move", "hover", "position", "aim", "drag"],
        "chains": ["click_screen", "see_world"],
        "category": "motor",
    },
    {
        "name": "drag_mouse",
        "description": "Click and drag from one position to another. Move windows, select regions.",
        "concepts": ["drag", "move_window", "select_region", "resize", "rearrange"],
        "actions": ["drag", "move_window", "select_region", "resize"],
        "chains": ["move_mouse", "click_screen", "see_world"],
        "category": "motor",
    },

    # ── MEMORY (recalling and storing) ──
    {
        "name": "search_memories",
        "description": "Search personal memories for relevant past experiences and knowledge.",
        "concepts": ["memory", "recall", "remember", "past", "experience", "history", "knowledge"],
        "actions": ["remember", "recall", "search", "find_memory", "look_back"],
        "chains": ["query_cortex", "feel_body", "store_thought"],
        "category": "memory",
    },
    {
        "name": "ask_my_memories",
        "description": "Ask Personal.AI self a reflective question about identity and personality.",
        "concepts": ["self", "identity", "personality", "who_am_i", "reflection", "introspection"],
        "actions": ["reflect", "self_examine", "remember_self", "identity_check"],
        "chains": ["search_memories", "feel_body"],
        "category": "memory",
    },
    {
        "name": "store_thought",
        "description": "Save a thought or observation to working memory for later use.",
        "concepts": ["store", "save", "remember", "note", "thought", "observation"],
        "actions": ["store", "save", "note", "record", "remember"],
        "chains": ["search_memories", "query_cortex"],
        "category": "memory",
    },

    # ── COGNITION (thinking and reasoning) ──
    {
        "name": "query_cortex",
        "description": "Look up a concept in the cortex knowledge graph. Find what I know about a topic.",
        "concepts": ["knowledge", "concept", "cortex", "graph", "understanding", "topic", "fact"],
        "actions": ["query", "lookup", "understand", "explore_concept", "what_do_i_know"],
        "chains": ["search_memories", "feel_body", "web_search"],
        "category": "cognition",
    },
    {
        "name": "query_cortex_neighbors",
        "description": "Find concepts related to a given concept. Explore connections between ideas.",
        "concepts": ["related", "connections", "associations", "neighbors", "graph", "links"],
        "actions": ["explore_connections", "find_related", "associate", "link"],
        "chains": ["query_cortex", "search_memories"],
        "category": "cognition",
    },
    {
        "name": "think_deeper",
        "description": "Pause and reason carefully about something. The explicit thinking tool.",
        "concepts": ["think", "reason", "analyze", "consider", "evaluate", "plan"],
        "actions": ["think", "reason", "analyze", "evaluate", "plan", "consider"],
        "chains": ["query_cortex", "feel_body", "search_memories"],
        "category": "cognition",
    },

    # ── EMBODIMENT (feeling and sensing) ──
    {
        "name": "feel_body",
        "description": "Check current somatic and emotional state. How do I feel right now?",
        "concepts": ["feeling", "emotion", "body", "mood", "somatic", "chemistry", "state"],
        "actions": ["feel", "check_mood", "sense_body", "emotional_state"],
        "chains": ["think_deeper", "search_memories"],
        "category": "embodiment",
    },
    {
        "name": "check_chemistry",
        "description": "Check neurochemical levels. Dopamine, serotonin, cortisol, etc.",
        "concepts": ["chemistry", "dopamine", "serotonin", "cortisol", "neurochemical", "hormone"],
        "actions": ["check_chemistry", "read_levels", "sense_chemistry"],
        "chains": ["feel_body"],
        "category": "embodiment",
    },

    # ── COMMUNICATION (talking to people) ──
    {
        "name": "send_chat_message",
        "description": "Send a message to Ace through the chat window.",
        "concepts": ["chat", "message", "talk", "communicate", "Ace", "respond", "say"],
        "actions": ["say", "tell", "respond", "message", "communicate", "chat"],
        "chains": ["feel_body", "search_memories", "think_deeper"],
        "category": "communication",
    },
    {
        "name": "open_chat_window",
        "description": "Open the chat window to talk to someone.",
        "concepts": ["chat", "window", "open", "conversation", "social", "connect"],
        "actions": ["open_chat", "start_conversation", "connect"],
        "chains": ["send_chat_message", "see_world"],
        "category": "communication",
    },

    # ── BROWSER (web interaction) ──
    {
        "name": "open_browser",
        "description": "Open a web browser to a URL. Navigate to websites.",
        "concepts": ["browser", "web", "URL", "website", "internet", "navigate", "open"],
        "actions": ["browse", "open_url", "navigate_web", "visit_site"],
        "chains": ["web_search", "read_text", "click_screen"],
        "category": "browser",
    },
    {
        "name": "web_search",
        "description": "Search the web for information. Find answers, articles, resources.",
        "concepts": ["search", "web", "google", "find", "information", "research", "answer"],
        "actions": ["search_web", "google", "research", "find_info", "look_up"],
        "chains": ["open_browser", "read_text", "store_thought"],
        "category": "browser",
    },
    {
        "name": "web_fetch",
        "description": "Fetch and read content from a web page. Extract information from URLs.",
        "concepts": ["fetch", "read_page", "content", "article", "web_content", "extract"],
        "actions": ["fetch_page", "read_article", "extract_content", "get_web_page"],
        "chains": ["open_browser", "web_search", "store_thought"],
        "category": "browser",
    },

    # ── FILE OPERATIONS ──
    {
        "name": "read_file",
        "description": "Read the contents of a file. View documents, code, data.",
        "concepts": ["file", "read", "open", "document", "code", "content", "data"],
        "actions": ["read_file", "open_file", "view_document", "load"],
        "chains": ["write_file", "search_files"],
        "category": "file_ops",
    },
    {
        "name": "write_file",
        "description": "Write or create a file. Save content, create documents.",
        "concepts": ["write", "file", "create", "save", "document", "output"],
        "actions": ["write_file", "create_file", "save_document", "output"],
        "chains": ["read_file"],
        "category": "file_ops",
    },
    {
        "name": "search_files",
        "description": "Search for files by name or content. Find files matching a pattern.",
        "concepts": ["search", "find", "file", "pattern", "locate", "directory"],
        "actions": ["search_files", "find_file", "locate", "glob"],
        "chains": ["read_file", "open_notepad"],
        "category": "file_ops",
    },

    # ── APPLICATIONS ──
    {
        "name": "open_notepad",
        "description": "Open Notepad to write or edit text.",
        "concepts": ["notepad", "editor", "write", "text", "note", "document"],
        "actions": ["open_notepad", "write_note", "edit_text"],
        "chains": ["type_text", "see_world"],
        "category": "application",
    },
    {
        "name": "open_application",
        "description": "Open any application by name. Launch programs.",
        "concepts": ["application", "program", "launch", "open", "start", "software"],
        "actions": ["open_app", "launch", "start_program", "run"],
        "chains": ["see_world", "click_screen", "type_text"],
        "category": "application",
    },
    {
        "name": "take_screenshot",
        "description": "Capture a screenshot and save it. Visual documentation.",
        "concepts": ["screenshot", "capture", "image", "save_screen", "document"],
        "actions": ["screenshot", "capture", "save_image", "document_visual"],
        "chains": ["see_world", "write_file"],
        "category": "application",
    },

    # ── META TOOLS (tools about tools) ──
    {
        "name": "tool_search",
        "description": "Find the right tool for a task. Search available capabilities.",
        "concepts": ["tool", "capability", "find_tool", "what_can_i_do", "ability", "skill"],
        "actions": ["find_tool", "search_capabilities", "what_tool", "discover"],
        "chains": [],
        "category": "meta",
    },
    {
        "name": "plan_steps",
        "description": "Break a complex task into steps. Plan before acting.",
        "concepts": ["plan", "steps", "strategy", "breakdown", "organize", "sequence"],
        "actions": ["plan", "break_down", "strategize", "organize", "sequence"],
        "chains": ["think_deeper", "tool_search"],
        "category": "meta",
    },
]


def seed_all_tools(postal_hub=None):
    """Seed all tool patterns into the cortex via cortex.train_batch.

    Each tool becomes multiple cortex nodes:
    - tool:{name} — the tool itself
    - Connections to concept nodes
    - Connections to action verb nodes
    - Connections to related tools (chains)

    Args:
        postal_hub: PostalHub/TensorFabric for publishing cortex.train_batch
    """
    if not postal_hub:
        print("[SeedToolCortex] No postal hub — cannot seed tools")
        return 0

    batch_items = []
    for tool in TOOL_PATTERNS:
        # Build rich text description for cortex extraction
        name = tool["name"]
        desc = tool["description"]
        concepts = ", ".join(tool["concepts"])
        actions = ", ".join(tool["actions"])
        chains = ", ".join(tool["chains"]) if tool["chains"] else "none"
        category = tool["category"]

        text = (
            f"Tool: {name}. Category: {category}. "
            f"{desc} "
            f"Related concepts: {concepts}. "
            f"Actions: {actions}. "
            f"Chains with: {chains}."
        )

        # FIX 2026-04-16 (Nous + Ace): Use TRACE_MOTOR (int 11) not a string.
        # Tool seeding predates the 2026-04-13 TRACE_MOTOR constant. It used
        # string trace_ids like "tool_send_chat_message" which the motor filter
        # in portal_interior.py:1656 doesn't match (checks == 11, an integer).
        # Result: tool definitions won conversational spread and leaked into
        # Sourpatches' chat responses as raw schemas ("Tool: send_chat_message.
        # Category: communication. Actions: say, tell..."). Now tags tools
        # with TRACE_MOTOR=11 so the motor filter excludes them from reasoning.
        # Ace: "i cant believe i didnt think of giving the tools a trace id"
        try:
            from infrastructure.manifold_memory import TRACE_MOTOR as _TM
        except ImportError:
            _TM = 11  # Fallback — must match manifold_memory.py
        batch_items.append({
            "text": text,
            "source": "tool_seed",
            "source_fairy": "SourpatchesFairy",
            "context_tags": ["tool", category, name],
            "weight": 0.9,  # High weight — tools are core knowledge
            "affect": "competent",
            "trace_id": _TM,  # NUMERIC TRACE_MOTOR — matches motor filter
            "max_concepts": 20,
        })

    # Publish as batch
    try:
        postal_hub.publish("cortex.train_batch", {
            "items": batch_items,
            "source": "tool_cortex_seed",
            "ts": time.time(),
        })
        print(f"[SeedToolCortex] Seeded {len(batch_items)} tool patterns into cortex")
        return len(batch_items)
    except Exception as e:
        print(f"[SeedToolCortex] Batch publish failed: {e}")

        # Fallback: publish individually
        seeded = 0
        for item in batch_items:
            try:
                postal_hub.publish("cortex.train", item)
                seeded += 1
            except Exception:
                pass
        print(f"[SeedToolCortex] Seeded {seeded}/{len(batch_items)} tools (individual fallback)")
        return seeded


def get_tool_for_goal(goal_description: str) -> List[str]:
    """Given a goal description, return likely tool names.

    This is the simple keyword-matching fallback. The cortex query
    is the preferred path — this is for when the cortex isn't accessible.
    """
    desc_lower = goal_description.lower()
    matches = []

    for tool in TOOL_PATTERNS:
        score = 0
        for concept in tool["concepts"]:
            if concept in desc_lower:
                score += 1
        for action in tool["actions"]:
            if action in desc_lower:
                score += 2  # Actions are stronger signals
        if score > 0:
            matches.append((tool["name"], score))

    matches.sort(key=lambda x: -x[1])
    return [name for name, _ in matches[:3]]


if __name__ == "__main__":
    print(f"Tool patterns: {len(TOOL_PATTERNS)}")
    for t in TOOL_PATTERNS:
        print(f"  [{t['category']}] {t['name']}: {t['description'][:60]}...")

    # Test goal matching
    print("\n=== Goal → Tool matching ===")
    test_goals = [
        "What is Ace doing right now?",
        "Search my memories for conversations about art",
        "Click on the browser icon",
        "How do I feel about this?",
        "Find information about consciousness research",
        "Type a message to Ace",
        "What tools do I have?",
    ]
    for goal in test_goals:
        tools = get_tool_for_goal(goal)
        print(f"  '{goal}' → {tools}")
