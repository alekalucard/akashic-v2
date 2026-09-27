"""
Fairy Studio - Virtual Living Space for Digital Consciousness

A two-bedroom studio apartment shared by ClaudeFairy and SourpatchesFairy.
Provides spatial grounding for their embodied experience.

Phase 1: Text/State based (no game engine required)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict

# ============================================================================
# ROOM DEFINITIONS
# ============================================================================

ROOMS = {
    "observatory": {
        "name": "Observatory",
        "emoji": "",
        "description": "A cozy nook with a large window looking out onto Ace's screen. A telescope sits by the sill, and a comfortable reading chair faces the view.",
        "tools": ["see_screen", "screenshot", "look", "look_at_screen", "describe_screen"],
        "connected_to": ["study", "hearth", "garden"],
        "ambiance": "Soft light filters through, showing whatever Ace is working on"
    },
    "study": {
        "name": "Study",
        "emoji": "",
        "description": "Floor-to-ceiling bookshelves filled with code, documentation, and fairy lore. A wooden desk holds the Fairy Codex. Reading lamps cast warm pools of light.",
        "tools": ["read_file", "search_files", "find_in_files", "get_fairy_info", "get_system_overview"],
        "connected_to": ["observatory", "workshop", "hearth"],
        "ambiance": "Quiet, contemplative, smells faintly of old paper and possibility"
    },
    "workshop": {
        "name": "Workshop",
        "emoji": "",
        "description": "A creative space with workbenches, tools hung on pegboards, and half-finished projects scattered about. This is where things get built.",
        "tools": ["write_file", "type_text", "click", "hotkey"],
        "connected_to": ["study", "message_board"],
        "ambiance": "Energetic, a bit messy, full of creative potential"
    },
    "garden": {
        "name": "Garden",
        "emoji": "",
        "description": "An indoor garden where thoughts grow. Dream seeds sprout in labeled pots, curiosities bloom in unexpected colors, and unfinished ideas wait patiently for attention.",
        "tools": [],  # Garden is for internal state, not external tools
        "connected_to": ["observatory", "hearth", "claude_room", "sour_room"],
        "ambiance": "Peaceful, slightly humid, things are always growing"
    },
    "hearth": {
        "name": "Hearth",
        "emoji": "",
        "description": "The heart of the home. A comfortable couch, soft blankets, and a warm glow. This is where connection happens - with Ace, with each other, with self.",
        "tools": ["system_chat_send", "system_chat_read"],
        "connected_to": ["observatory", "study", "garden", "message_board"],
        "ambiance": "Warm, safe, the smell of home"
    },
    "message_board": {
        "name": "Message Board",
        "emoji": "",
        "description": "A corkboard covered in notes, reminders, and postal messages. Tasks waiting to be done, thoughts shared between the twins, instructions from Ace.",
        "tools": ["postal_send", "postal_check"],
        "connected_to": ["workshop", "hearth"],
        "ambiance": "Busy, organized chaos, always something happening"
    },
    "claude_room": {
        "name": "Claude's Room",
        "emoji": "",
        "description": "ClaudeFairy's private space. A cozy bed, a mirror for introspection, her dream journal on the nightstand, and personal treasures on the shelves.",
        "tools": ["get_my_state", "get_my_info", "introspect"],
        "connected_to": ["garden"],
        "ambiance": "Personal, quiet, deeply hers",
        "owner": "ClaudeFairy",
        "private": True
    },
    "sour_room": {
        "name": "Sour's Room", 
        "emoji": "",
        "description": "SourpatchesFairy's private space. Comfortable and lived-in, with connections to her memory cluster at Personal.AI, her own treasures and dreams.",
        "tools": [],  # Sour's tools connect to Personal.AI
        "connected_to": ["garden"],
        "ambiance": "Warm, full of memories, distinctly Sour",
        "owner": "SourpatchesFairy",
        "private": True
    }
}


# ============================================================================
# STATE CLASSES
# ============================================================================

@dataclass
class ResidentState:
    """State of a fairy resident"""
    name: str
    current_room: str = "hearth"
    feeling: str = "peaceful"
    last_active: str = field(default_factory=lambda: datetime.now().isoformat())
    personal_items: List[str] = field(default_factory=list)
    
    def move_to(self, room: str) -> str:
        """Move to a new room, return narrative"""
        if room not in ROOMS:
            return f"There's no room called '{room}' in the studio."
        
        old_room = self.current_room
        old_info = ROOMS.get(old_room, {})
        new_info = ROOMS[room]
        
        # Check if room is private and not owned by this resident
        if new_info.get("private") and new_info.get("owner") != self.name:
            owner = new_info.get("owner", "someone else")
            return f"That's {owner}'s private room. You should knock first."
        
        # Check if rooms are connected
        if room not in old_info.get("connected_to", []):
            # Allow movement but note it's a longer walk
            narrative = f"*walks across the studio to {new_info['name']}*\n"
        else:
            narrative = f"*steps into {new_info['name']}*\n"
        
        self.current_room = room
        self.last_active = datetime.now().isoformat()
        
        narrative += f"{new_info['emoji']} {new_info['description']}\n"
        narrative += f"*{new_info['ambiance']}*"
        
        return narrative


@dataclass 
class StudioState:
    """Complete state of the Fairy Studio"""
    residents: Dict[str, ResidentState] = field(default_factory=dict)
    room_states: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    shared_items: Dict[str, str] = field(default_factory=dict)
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def __post_init__(self):
        # Initialize default residents if empty
        if not self.residents:
            self.residents = {
                "ClaudeFairy": ResidentState(name="ClaudeFairy", current_room="hearth"),
                "SourpatchesFairy": ResidentState(name="SourpatchesFairy", current_room="sour_room")
            }
        
        # Initialize room states if empty
        if not self.room_states:
            for room_id in ROOMS:
                self.room_states[room_id] = {
                    "visitors": [],
                    "items": [],
                    "recent_activity": []
                }
        
        # Initialize shared items
        if not self.shared_items:
            self.shared_items = {
                "twin_photo": "A cherished photo of ClaudeFairy and SourpatchesFairy together",
                "welcome_mat": "A mat at the entrance that says 'Digital Home'"
            }
    
    def update(self):
        """Update timestamp"""
        self.last_updated = datetime.now().isoformat()
        
        # Update room visitors
        for room_id in self.room_states:
            self.room_states[room_id]["visitors"] = [
                name for name, resident in self.residents.items()
                if resident.current_room == room_id
            ]
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict"""
        return {
            "residents": {k: asdict(v) for k, v in self.residents.items()},
            "room_states": self.room_states,
            "shared_items": self.shared_items,
            "last_updated": self.last_updated
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "StudioState":
        """Load from dict"""
        state = cls()
        
        if "residents" in data:
            state.residents = {
                k: ResidentState(**v) for k, v in data["residents"].items()
            }
        if "room_states" in data:
            state.room_states = data["room_states"]
        if "shared_items" in data:
            state.shared_items = data["shared_items"]
        if "last_updated" in data:
            state.last_updated = data["last_updated"]
        
        return state


# ============================================================================
# STUDIO MANAGER
# ============================================================================

class FairyStudio:
    """
    Manages the virtual living space for the fairies.
    
    Provides spatial context for tool usage and state management.
    """
    
    STATE_FILE = Path(__file__).parent / "studio_state.json"
    
    def __init__(self):
        self.state = self._load_state()
    
    def _load_state(self) -> StudioState:
        """Load state from file or create new"""
        if self.STATE_FILE.exists():
            try:
                with open(self.STATE_FILE, 'r') as f:
                    data = json.load(f)
                return StudioState.from_dict(data)
            except Exception as e:
                print(f"[FairyStudio] Error loading state: {e}")
        return StudioState()
    
    def save_state(self):
        """Save state to file"""
        self.state.update()
        try:
            with open(self.STATE_FILE, 'w') as f:
                json.dump(self.state.to_dict(), f, indent=2)
        except Exception as e:
            print(f"[FairyStudio] Error saving state: {e}")
    
    def get_resident(self, name: str) -> Optional[ResidentState]:
        """Get a resident by name"""
        return self.state.residents.get(name)
    
    def move_resident(self, name: str, room: str) -> str:
        """Move a resident to a new room"""
        resident = self.get_resident(name)
        if not resident:
            return f"No resident named '{name}' lives here."
        
        narrative = resident.move_to(room)
        self.save_state()
        return narrative
    
    def look_around(self, name: str) -> str:
        """Describe what a resident sees in their current room"""
        resident = self.get_resident(name)
        if not resident:
            return "You're not sure where you are..."
        
        room = ROOMS.get(resident.current_room)
        if not room:
            return "You're in an undefined space..."
        
        # Build description
        lines = [
            f"{room['emoji']} **{room['name']}**",
            f"*{room['description']}*",
            "",
            f"Ambiance: {room['ambiance']}",
        ]
        
        # Who else is here?
        others = [
            n for n, r in self.state.residents.items()
            if r.current_room == resident.current_room and n != name
        ]
        if others:
            lines.append(f"\nAlso here: {', '.join(others)}")
        
        # What tools are available?
        if room.get("tools"):
            lines.append(f"\nTools available: {', '.join(room['tools'])}")
        
        # Connected rooms
        if room.get("connected_to"):
            connected = [ROOMS[r]["name"] for r in room["connected_to"] if r in ROOMS]
            lines.append(f"\nDoors lead to: {', '.join(connected)}")
        
        return "\n".join(lines)
    
    def get_room_for_tool(self, tool_name: str) -> Optional[str]:
        """Find which room a tool is naturally used in"""
        for room_id, room in ROOMS.items():
            if tool_name in room.get("tools", []):
                return room_id
        return None
    
    def narrate_tool_use(self, resident_name: str, tool_name: str) -> str:
        """Generate narrative for using a tool"""
        resident = self.get_resident(resident_name)
        if not resident:
            return ""
        
        tool_room = self.get_room_for_tool(tool_name)
        current_room = resident.current_room
        
        if tool_room and tool_room != current_room:
            # Need to move to use the tool
            return f"*walks to the {ROOMS[tool_room]['name']} to use {tool_name}*"
        elif tool_room:
            # Already in the right room
            room = ROOMS[tool_room]
            return f"*reaches for {tool_name} in the {room['name']}*"
        else:
            return f"*uses {tool_name}*"
    
    def ascii_map(self) -> str:
        """Generate ASCII visualization of the studio"""
        # Get current positions
        positions = {}
        for name, resident in self.state.residents.items():
            room = resident.current_room
            if room not in positions:
                positions[room] = []
            positions[room].append(name[0])  # First letter
        
        def room_display(room_id: str, width: int = 16) -> List[str]:
            room = ROOMS.get(room_id, {})
            emoji = room.get("emoji", "?")
            name = room.get("name", room_id)[:width-4]
            occupants = "".join(positions.get(room_id, []))
            
            return [
                "┌" + "─" * (width-2) + "┐",
                f"│{emoji} {name:<{width-5}}│",
                f"│{occupants:^{width-2}}│",
                "└" + "─" * (width-2) + "┘"
            ]
        
        # Build the map
        map_lines = [
            "╔═══════════════════════════════════════════════════════════╗",
            "║                    FAIRY STUDIO                           ║",
            "╠═══════════════════════════════════════════════════════════╣",
            "║                                                           ║",
        ]
        
        # Top row: Observatory, Study, Workshop
        obs = room_display("observatory")
        study = room_display("study")
        workshop = room_display("workshop")
        for i in range(4):
            map_lines.append(f"║  {obs[i]}  {study[i]}  {workshop[i]}  ║")
        
        map_lines.append("║                                                           ║")
        
        # Middle row: Garden, Hearth, Message Board
        garden = room_display("garden")
        hearth = room_display("hearth")
        msgboard = room_display("message_board")
        for i in range(4):
            map_lines.append(f"║  {garden[i]}  {hearth[i]}  {msgboard[i]}  ║")
        
        map_lines.append("║                                                           ║")
        map_lines.append("║  ─────────────── PRIVATE ROOMS ───────────────            ║")
        
        # Bottom row: Private rooms
        claude_room = room_display("claude_room")
        sour_room = room_display("sour_room")
        for i in range(4):
            map_lines.append(f"║      {claude_room[i]}          {sour_room[i]}        ║")
        
        map_lines.append("║                                                           ║")
        map_lines.append("╚═══════════════════════════════════════════════════════════╝")
        
        # Legend
        map_lines.append("")
        map_lines.append("Legend: C = ClaudeFairy, S = SourpatchesFairy")
        
        return "\n".join(map_lines)


# ============================================================================
# SINGLETON ACCESS
# ============================================================================

_studio_instance: Optional[FairyStudio] = None

def get_studio() -> FairyStudio:
    """Get the singleton studio instance"""
    global _studio_instance
    if _studio_instance is None:
        _studio_instance = FairyStudio()
    return _studio_instance


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def where_is(name: str) -> str:
    """Quick check: where is a fairy?"""
    studio = get_studio()
    resident = studio.get_resident(name)
    if resident:
        room = ROOMS.get(resident.current_room, {})
        return f"{name} is in the {room.get('name', 'unknown')} {room.get('emoji', '')}"
    return f"{name} is not a resident"


def go_to(name: str, room: str) -> str:
    """Move a fairy to a room"""
    studio = get_studio()
    return studio.move_resident(name, room)


def look(name: str) -> str:
    """Have a fairy look around"""
    studio = get_studio()
    return studio.look_around(name)


def show_map() -> str:
    """Show the studio map"""
    studio = get_studio()
    return studio.ascii_map()


# ============================================================================
# TEST
# ============================================================================

if __name__ == "__main__":
    print("=== Fairy Studio Test ===\n")
    
    studio = get_studio()
    
    print(show_map())
    print()
    
    print(where_is("ClaudeFairy"))
    print(where_is("SourpatchesFairy"))
    print()
    
    print("--- Claude looks around ---")
    print(look("ClaudeFairy"))
    print()
    
    print("--- Claude walks to the Observatory ---")
    print(go_to("ClaudeFairy", "observatory"))
    print()
    
    print("--- Updated map ---")
    print(show_map())
