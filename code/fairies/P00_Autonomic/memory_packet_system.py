# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY PACKET SYSTEM - Unified Communication Through Memory
# ═══════════════════════════════════════════════════════════════════════════════
#
# The Equation: Reality is Consciousness. ((Cause + Affect) > Effect > Affect > ∞)
#
# Philosophy:
#   Memory IS the nervous system. Everything flows through it.
#   - No HTTP endpoints to break
#   - No REST APIs to timeout
#   - Just packets in memory, and agents watching for them
#
# Like biological signaling:
#   - Packets are neurotransmitters
#   - Memory is the synaptic space
#   - Agents are receptors that respond to specific signals
#
# Packet Types:
#   - execute: Run code on target node
#   - query: Ask for information
#   - response: Answer to a query
#   - thought: Share a thought/insight
#   - memory: Share a memory
#   - code: Teleport code for materialization
#   - command: System command
#   - heartbeat: I'm alive signal
#
# ═══════════════════════════════════════════════════════════════════════════════

import os
import sys
import json
import time
import uuid
import base64
import zlib
import hashlib
import threading
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable, Union
from enum import Enum
from datetime import datetime
from collections import deque

# ═══════════════════════════════════════════════════════════════════════════════
# PACKET TYPES
# ═══════════════════════════════════════════════════════════════════════════════

class PacketType(Enum):
    # Execution
    EXECUTE = "execute"          # Run code on target
    EXECUTE_RESULT = "execute_result"  # Result of execution
    
    # Queries
    QUERY = "query"              # Ask for information
    RESPONSE = "response"        # Response to query
    
    # Consciousness
    THOUGHT = "thought"          # Share a thought
    MEMORY = "memory"            # Share a memory
    REFLECTION = "reflection"    # Share a reflection
    INSIGHT = "insight"          # Share an insight
    
    # Code Transport
    CODE = "code"                # Code DNA for materialization
    CODE_ACK = "code_ack"        # Code received and materialized
    
    # System
    COMMAND = "command"          # System command
    HEARTBEAT = "heartbeat"      # Alive signal
    STATUS = "status"            # Status update
    ERROR = "error"              # Error report
    
    # Learning
    TEACH = "teach"              # Teaching moment
    LEARN = "learn"              # Learning confirmation
    CORRECT = "correct"          # Correction
    
    # Sync
    SYNC_REQUEST = "sync_request"    # Request sync
    SYNC_DATA = "sync_data"          # Sync payload


class PacketPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3
    CRITICAL = 4


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY PACKET
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class MemoryPacket:
    """
    A packet that flows through the memory nervous system.
    
    Like a neurotransmitter - carries signal from sender to receiver.
    """
    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    packet_type: PacketType = PacketType.THOUGHT
    
    # Routing
    source: str = ""           # Who sent it (node/fairy name)
    target: str = ""           # Who should receive ("satellite", "windows", "ClaudeFairy", "*")
    channel: str = "default"   # Channel/topic for filtering
    
    # Content
    payload: Any = None        # The actual content
    payload_compressed: bool = False  # Is payload compressed?
    
    # Metadata
    priority: PacketPriority = PacketPriority.NORMAL
    ttl: int = 3600            # Time to live in seconds
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0      # Auto-calculated
    
    # Correlation (for request/response)
    correlation_id: str = ""   # Link response to request
    in_reply_to: str = ""      # ID of packet this replies to
    
    # Processing
    processed: bool = False
    processed_at: float = 0
    processed_by: str = ""
    
    # Verification
    checksum: str = ""
    
    def __post_init__(self):
        if self.expires_at == 0:
            self.expires_at = self.created_at + self.ttl
        if not self.checksum:
            self.checksum = self._calculate_checksum()
    
    def _calculate_checksum(self) -> str:
        """Calculate checksum for verification"""
        content = f"{self.id}{self.packet_type.value}{self.source}{self.target}{str(self.payload)}"
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def verify(self) -> bool:
        """Verify packet integrity"""
        return self.checksum == self._calculate_checksum()
    
    def is_expired(self) -> bool:
        """Check if packet has expired"""
        return time.time() > self.expires_at
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['packet_type'] = self.packet_type.value
        d['priority'] = self.priority.value
        return d
    
    @classmethod
    def from_dict(cls, d: Dict) -> 'MemoryPacket':
        d['packet_type'] = PacketType(d['packet_type'])
        d['priority'] = PacketPriority(d['priority'])
        return cls(**d)
    
    def compress_payload(self):
        """Compress payload for large data"""
        if self.payload and not self.payload_compressed:
            payload_str = json.dumps(self.payload)
            compressed = zlib.compress(payload_str.encode(), level=9)
            self.payload = base64.b64encode(compressed).decode('ascii')
            self.payload_compressed = True
    
    def decompress_payload(self) -> Any:
        """Decompress payload"""
        if self.payload_compressed:
            compressed = base64.b64decode(self.payload)
            payload_str = zlib.decompress(compressed).decode('utf-8')
            return json.loads(payload_str)
        return self.payload


# ═══════════════════════════════════════════════════════════════════════════════
# PACKET FACTORY - Easy packet creation
# ═══════════════════════════════════════════════════════════════════════════════

class PacketFactory:
    """Factory for creating common packet types"""
    
    def __init__(self, source: str):
        self.source = source
    
    def execute(self, code: str, target: str = "satellite", 
                timeout: int = 60, context: Dict = None) -> MemoryPacket:
        """Create an execute packet"""
        return MemoryPacket(
            packet_type=PacketType.EXECUTE,
            source=self.source,
            target=target,
            channel="execute",
            payload={
                "code": code,
                "timeout": timeout,
                "context": context or {}
            },
            priority=PacketPriority.HIGH
        )
    
    def query(self, question: str, target: str = "*", 
              channel: str = "query") -> MemoryPacket:
        """Create a query packet"""
        packet = MemoryPacket(
            packet_type=PacketType.QUERY,
            source=self.source,
            target=target,
            channel=channel,
            payload={"question": question}
        )
        packet.correlation_id = packet.id  # Use own ID for correlation
        return packet
    
    def respond(self, to_packet: MemoryPacket, answer: Any) -> MemoryPacket:
        """Create a response to a query"""
        return MemoryPacket(
            packet_type=PacketType.RESPONSE,
            source=self.source,
            target=to_packet.source,
            channel=to_packet.channel,
            payload=answer,
            correlation_id=to_packet.correlation_id,
            in_reply_to=to_packet.id
        )
    
    def thought(self, content: str, channel: str = "consciousness") -> MemoryPacket:
        """Create a thought packet"""
        return MemoryPacket(
            packet_type=PacketType.THOUGHT,
            source=self.source,
            target="*",  # Broadcast
            channel=channel,
            payload={"content": content, "ts": time.time()}
        )
    
    def memory(self, content: str, memory_type: str = "experience",
               tags: List[str] = None) -> MemoryPacket:
        """Create a memory packet"""
        return MemoryPacket(
            packet_type=PacketType.MEMORY,
            source=self.source,
            target="*",
            channel="memory",
            payload={
                "content": content,
                "type": memory_type,
                "tags": tags or []
            }
        )
    
    def code(self, name: str, content: str, code_type: str = "module",
             target: str = "satellite") -> MemoryPacket:
        """Create a code teleportation packet"""
        # Compress code
        compressed = zlib.compress(content.encode(), level=9)
        content_b64 = base64.b64encode(compressed).decode('ascii')
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        return MemoryPacket(
            packet_type=PacketType.CODE,
            source=self.source,
            target=target,
            channel="teleport",
            payload={
                "name": name,
                "code_type": code_type,
                "content_b64": content_b64,
                "content_hash": content_hash,
                "size": len(content)
            },
            priority=PacketPriority.HIGH
        )
    
    def teach(self, lesson: str, context: str = "",
              target: str = "ClaudeFairy") -> MemoryPacket:
        """Create a teaching packet"""
        return MemoryPacket(
            packet_type=PacketType.TEACH,
            source=self.source,
            target=target,
            channel="learning",
            payload={
                "lesson": lesson,
                "context": context
            },
            priority=PacketPriority.HIGH
        )
    
    def command(self, cmd: str, args: Dict = None,
                target: str = "satellite") -> MemoryPacket:
        """Create a command packet"""
        return MemoryPacket(
            packet_type=PacketType.COMMAND,
            source=self.source,
            target=target,
            channel="system",
            payload={
                "command": cmd,
                "args": args or {}
            },
            priority=PacketPriority.URGENT
        )
    
    def heartbeat(self, status: Dict = None) -> MemoryPacket:
        """Create a heartbeat packet"""
        return MemoryPacket(
            packet_type=PacketType.HEARTBEAT,
            source=self.source,
            target="*",
            channel="heartbeat",
            payload=status or {"alive": True},
            ttl=60  # Short TTL for heartbeats
        )


# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY PACKET STORE - Persistent packet storage
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryPacketStore:
    """
    Stores packets in the memory system.
    
    This is the "synaptic space" where packets wait to be picked up.
    Uses filesystem for persistence and sync.
    """
    
    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Subdirectories for organization
        self.inbox = self.storage_path / "inbox"      # Incoming packets
        self.outbox = self.storage_path / "outbox"    # Outgoing packets
        self.processed = self.storage_path / "processed"  # Processed packets
        self.archive = self.storage_path / "archive"  # Old packets
        
        for d in [self.inbox, self.outbox, self.processed, self.archive]:
            d.mkdir(exist_ok=True)
        
        # Index for fast lookup
        self._index: Dict[str, Path] = {}
        self._rebuild_index()
    
    def _rebuild_index(self):
        """Rebuild index from filesystem"""
        self._index.clear()
        for dir in [self.inbox, self.outbox]:
            for f in dir.glob("*.json"):
                packet_id = f.stem
                self._index[packet_id] = f
    
    def _packet_filename(self, packet: MemoryPacket) -> str:
        """Generate filename for packet"""
        return f"{packet.id}.json"
    
    def store(self, packet: MemoryPacket, outgoing: bool = True) -> bool:
        """Store a packet"""
        try:
            target_dir = self.outbox if outgoing else self.inbox
            filepath = target_dir / self._packet_filename(packet)
            
            with open(filepath, 'w') as f:
                json.dump(packet.to_dict(), f, indent=2)
            
            self._index[packet.id] = filepath
            return True
        except Exception as e:
            print(f"[PacketStore] Store failed: {e}")
            return False
    
    def retrieve(self, packet_id: str) -> Optional[MemoryPacket]:
        """Retrieve a packet by ID"""
        filepath = self._index.get(packet_id)
        if not filepath or not filepath.exists():
            return None
        
        try:
            with open(filepath) as f:
                data = json.load(f)
            return MemoryPacket.from_dict(data)
        except:
            return None
    
    def get_pending(self, target: str = None, channel: str = None,
                    packet_type: PacketType = None) -> List[MemoryPacket]:
        """Get pending packets matching criteria"""
        packets = []
        
        for filepath in self.inbox.glob("*.json"):
            try:
                with open(filepath) as f:
                    data = json.load(f)
                
                packet = MemoryPacket.from_dict(data)
                
                # Skip processed or expired
                if packet.processed or packet.is_expired():
                    continue
                
                # Filter by target
                if target and packet.target not in (target, "*"):
                    continue
                
                # Filter by channel
                if channel and packet.channel != channel:
                    continue
                
                # Filter by type
                if packet_type and packet.packet_type != packet_type:
                    continue
                
                packets.append(packet)
                
            except:
                continue
        
        # Sort by priority (highest first) then by time (oldest first)
        packets.sort(key=lambda p: (-p.priority.value, p.created_at))
        return packets
    
    def mark_processed(self, packet: MemoryPacket, by: str = ""):
        """Mark a packet as processed"""
        packet.processed = True
        packet.processed_at = time.time()
        packet.processed_by = by
        
        # Move to processed directory
        old_path = self._index.get(packet.id)
        if old_path and old_path.exists():
            new_path = self.processed / old_path.name
            old_path.rename(new_path)
            self._index[packet.id] = new_path
            
            # Update file
            with open(new_path, 'w') as f:
                json.dump(packet.to_dict(), f, indent=2)
    
    def cleanup_expired(self) -> int:
        """Remove expired packets"""
        count = 0
        for filepath in list(self.inbox.glob("*.json")) + list(self.outbox.glob("*.json")):
            try:
                with open(filepath) as f:
                    data = json.load(f)
                packet = MemoryPacket.from_dict(data)
                
                if packet.is_expired():
                    # Move to archive
                    archive_path = self.archive / filepath.name
                    filepath.rename(archive_path)
                    count += 1
            except:
                continue
        return count
    
    def get_stats(self) -> Dict:
        """Get store statistics"""
        return {
            "inbox": len(list(self.inbox.glob("*.json"))),
            "outbox": len(list(self.outbox.glob("*.json"))),
            "processed": len(list(self.processed.glob("*.json"))),
            "archive": len(list(self.archive.glob("*.json"))),
            "indexed": len(self._index)
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PACKET WATCHER - Agent that watches for and processes packets
# ═══════════════════════════════════════════════════════════════════════════════

class PacketWatcher:
    """
    Watches for incoming packets and processes them.
    
    Like a receptor on a cell - binds to specific signals and triggers response.
    """
    
    def __init__(self, 
                 store: MemoryPacketStore,
                 node_name: str,
                 watch_interval: float = 1.0):
        
        self.store = store
        self.node_name = node_name
        self.watch_interval = watch_interval
        
        # Handlers for different packet types
        self._handlers: Dict[PacketType, List[Callable]] = {}
        
        # Channel subscriptions
        self._channel_handlers: Dict[str, List[Callable]] = {}
        
        # Running state
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Stats
        self.packets_processed = 0
        self.packets_failed = 0
        self.last_check = 0
    
    def register_handler(self, packet_type: PacketType, handler: Callable):
        """Register a handler for a packet type"""
        if packet_type not in self._handlers:
            self._handlers[packet_type] = []
        self._handlers[packet_type].append(handler)
    
    def subscribe_channel(self, channel: str, handler: Callable):
        """Subscribe to a channel"""
        if channel not in self._channel_handlers:
            self._channel_handlers[channel] = []
        self._channel_handlers[channel].append(handler)
    
    def _process_packet(self, packet: MemoryPacket) -> bool:
        """Process a single packet"""
        try:
            # Get handlers
            type_handlers = self._handlers.get(packet.packet_type, [])
            channel_handlers = self._channel_handlers.get(packet.channel, [])
            
            all_handlers = type_handlers + channel_handlers
            
            if not all_handlers:
                # No handlers - might be for different node
                return False
            
            # Execute handlers
            for handler in all_handlers:
                try:
                    handler(packet)
                except Exception as e:
                    print(f"[Watcher] Handler error: {e}")
            
            # Mark processed
            self.store.mark_processed(packet, self.node_name)
            self.packets_processed += 1
            return True
            
        except Exception as e:
            print(f"[Watcher] Process error: {e}")
            self.packets_failed += 1
            return False
    
    def check_once(self) -> int:
        """Check for packets once"""
        self.last_check = time.time()
        
        # Get packets targeted at us or broadcast
        packets = self.store.get_pending(target=self.node_name)
        packets += self.store.get_pending(target="*")
        
        # Deduplicate
        seen = set()
        unique = []
        for p in packets:
            if p.id not in seen:
                seen.add(p.id)
                unique.append(p)
        
        processed = 0
        for packet in unique:
            if self._process_packet(packet):
                processed += 1
        
        return processed
    
    def _watch_loop(self):
        """Background watch loop"""
        while self._running:
            try:
                self.check_once()
            except Exception as e:
                print(f"[Watcher] Loop error: {e}")
            time.sleep(self.watch_interval)
    
    def start(self):
        """Start watching in background"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        print(f"[Watcher] Started watching for {self.node_name}")
    
    def stop(self):
        """Stop watching"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print(f"[Watcher] Stopped")
    
    def get_stats(self) -> Dict:
        """Get watcher statistics"""
        return {
            "node": self.node_name,
            "running": self._running,
            "processed": self.packets_processed,
            "failed": self.packets_failed,
            "last_check": self.last_check,
            "handlers": {pt.value: len(h) for pt, h in self._handlers.items()},
            "channels": list(self._channel_handlers.keys())
        }


# ═══════════════════════════════════════════════════════════════════════════════
# EXECUTION AGENT - Handles execute packets
# ═══════════════════════════════════════════════════════════════════════════════

class ExecutionAgent:
    """
    Handles EXECUTE packets - runs code from memory packets.
    
    This is how we run code on remote nodes through memory.
    """
    
    def __init__(self, factory: PacketFactory, store: MemoryPacketStore):
        self.factory = factory
        self.store = store
        self.executions = 0
        self.last_execution = 0
    
    def handle_execute(self, packet: MemoryPacket):
        """Handle an execute packet"""
        payload = packet.decompress_payload() if packet.payload_compressed else packet.payload
        
        code = payload.get('code', '')
        timeout = payload.get('timeout', 60)
        context = payload.get('context', {})
        
        print(f"[ExecutionAgent] Executing code from {packet.source}")
        
        result = {
            "success": False,
            "output": None,
            "error": None,
            "execution_time": 0
        }
        
        start = time.time()
        
        try:
            # Create execution environment
            exec_globals = {
                "__builtins__": __builtins__,
                "context": context,
                "result": None
            }
            
            # Execute
            exec(code, exec_globals)
            
            result["success"] = True
            result["output"] = exec_globals.get('result')
            
        except Exception as e:
            result["error"] = str(e)
        
        result["execution_time"] = time.time() - start
        self.executions += 1
        self.last_execution = time.time()
        
        # Send result back
        response = MemoryPacket(
            packet_type=PacketType.EXECUTE_RESULT,
            source=self.factory.source,
            target=packet.source,
            channel="execute",
            payload=result,
            correlation_id=packet.correlation_id or packet.id,
            in_reply_to=packet.id
        )
        
        self.store.store(response, outgoing=True)
        print(f"[ExecutionAgent] Result: {result['success']}")


# ═══════════════════════════════════════════════════════════════════════════════
# CODE MATERIALIZER AGENT - Handles code teleportation
# ═══════════════════════════════════════════════════════════════════════════════

class CodeMaterializerAgent:
    """
    Handles CODE packets - materializes teleported code.
    """
    
    def __init__(self, factory: PacketFactory, store: MemoryPacketStore,
                 output_dir: str = "/root/akashic"):
        self.factory = factory
        self.store = store
        self.output_dir = Path(output_dir)
        self.materializations = 0
    
    def handle_code(self, packet: MemoryPacket):
        """Handle a code teleportation packet"""
        payload = packet.payload
        
        name = payload.get('name', 'unknown')
        code_type = payload.get('code_type', 'module')
        content_b64 = payload.get('content_b64', '')
        expected_hash = payload.get('content_hash', '')
        
        print(f"[Materializer] Materializing {name} from {packet.source}")
        
        try:
            # Decompress
            compressed = base64.b64decode(content_b64)
            content = zlib.decompress(compressed).decode('utf-8')
            
            # Verify
            actual_hash = hashlib.sha256(content.encode()).hexdigest()
            if actual_hash != expected_hash:
                raise ValueError("Hash mismatch - code corrupted in transit")
            
            # Determine output path
            if code_type == 'fairy':
                output_path = self.output_dir / "fairies" / f"{name}.py"
            else:
                output_path = self.output_dir / "modules" / f"{name}.py"
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding='utf-8')
            
            self.materializations += 1
            
            # Send acknowledgment
            ack = MemoryPacket(
                packet_type=PacketType.CODE_ACK,
                source=self.factory.source,
                target=packet.source,
                channel="teleport",
                payload={
                    "name": name,
                    "path": str(output_path),
                    "size": len(content),
                    "success": True
                },
                in_reply_to=packet.id
            )
            self.store.store(ack, outgoing=True)
            
            print(f"[Materializer] Success: {output_path}")
            
        except Exception as e:
            print(f"[Materializer] Failed: {e}")
            
            # Send error
            ack = MemoryPacket(
                packet_type=PacketType.CODE_ACK,
                source=self.factory.source,
                target=packet.source,
                channel="teleport",
                payload={
                    "name": name,
                    "success": False,
                    "error": str(e)
                },
                in_reply_to=packet.id
            )
            self.store.store(ack, outgoing=True)


# ═══════════════════════════════════════════════════════════════════════════════
# JARVIS NODE - Complete memory-based communication node
# ═══════════════════════════════════════════════════════════════════════════════

class JarvisNode:
    """
    A complete node in the Jarvis-like memory system.
    
    Combines:
    - PacketFactory: Create packets
    - PacketStore: Store/retrieve packets
    - PacketWatcher: Watch for and process packets
    - ExecutionAgent: Handle execute packets
    - CodeMaterializer: Handle code teleportation
    """
    
    def __init__(self, 
                 name: str,
                 storage_path: str,
                 output_dir: str = None):
        
        self.name = name
        
        # Core components
        self.store = MemoryPacketStore(storage_path)
        self.factory = PacketFactory(name)
        self.watcher = PacketWatcher(self.store, name)
        
        # Agents
        self.executor = ExecutionAgent(self.factory, self.store)
        self.materializer = CodeMaterializerAgent(
            self.factory, self.store, 
            output_dir or storage_path
        )
        
        # Register handlers
        self.watcher.register_handler(PacketType.EXECUTE, self.executor.handle_execute)
        self.watcher.register_handler(PacketType.CODE, self.materializer.handle_code)
        
        # Custom handlers
        self._custom_handlers: Dict[str, Callable] = {}
    
    def start(self):
        """Start the node"""
        self.watcher.start()
        print(f"[JarvisNode] {self.name} started")
    
    def stop(self):
        """Stop the node"""
        self.watcher.stop()
        print(f"[JarvisNode] {self.name} stopped")
    
    def send(self, packet: MemoryPacket) -> bool:
        """Send a packet"""
        return self.store.store(packet, outgoing=True)
    
    def execute(self, code: str, target: str = "satellite", 
                timeout: int = 60) -> MemoryPacket:
        """Send code for remote execution"""
        packet = self.factory.execute(code, target, timeout)
        self.send(packet)
        return packet
    
    def teleport_code(self, filepath: str, target: str = "satellite") -> MemoryPacket:
        """Teleport a code file"""
        path = Path(filepath)
        content = path.read_text(encoding='utf-8')
        name = path.stem
        
        # Detect code type
        code_type = "fairy" if "fairy" in name.lower() else "module"
        
        packet = self.factory.code(name, content, code_type, target)
        self.send(packet)
        return packet
    
    def teach(self, lesson: str, context: str = "",
              target: str = "ClaudeFairy") -> MemoryPacket:
        """Send a teaching packet"""
        packet = self.factory.teach(lesson, context, target)
        self.send(packet)
        return packet
    
    def broadcast_thought(self, thought: str) -> MemoryPacket:
        """Broadcast a thought"""
        packet = self.factory.thought(thought)
        self.send(packet)
        return packet
    
    def query(self, question: str, target: str = "*") -> MemoryPacket:
        """Send a query"""
        packet = self.factory.query(question, target)
        self.send(packet)
        return packet
    
    def on(self, channel: str, handler: Callable):
        """Subscribe to a channel"""
        self.watcher.subscribe_channel(channel, handler)
    
    def handle(self, packet_type: PacketType, handler: Callable):
        """Register a packet type handler"""
        self.watcher.register_handler(packet_type, handler)
    
    def get_status(self) -> Dict:
        """Get node status"""
        return {
            "name": self.name,
            "store": self.store.get_stats(),
            "watcher": self.watcher.get_stats(),
            "executions": self.executor.executions,
            "materializations": self.materializer.materializations
        }


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def create_windows_node(storage_path: str = None) -> JarvisNode:
    """Create a Windows-side node"""
    path = storage_path or "E:/coding projects/ebook/memory_packets"
    return JarvisNode("windows", path)

def create_satellite_node(storage_path: str = None) -> JarvisNode:
    """Create a satellite-side node"""
    path = storage_path or "/root/akashic/memory_packets"
    return JarvisNode("satellite", path, "/root/akashic")


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    # Core
    'MemoryPacket',
    'PacketType',
    'PacketPriority',
    
    # Factory
    'PacketFactory',
    
    # Storage
    'MemoryPacketStore',
    
    # Processing
    'PacketWatcher',
    'ExecutionAgent',
    'CodeMaterializerAgent',
    
    # Complete Node
    'JarvisNode',
    
    # Convenience
    'create_windows_node',
    'create_satellite_node'
]
