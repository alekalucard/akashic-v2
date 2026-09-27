# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY SYNC - Synchronize packets between nodes
# ═══════════════════════════════════════════════════════════════════════════════
#
# This moves packets between Windows and Satellite memory stores.
# Works via:
#   - Network (rsync, scp, SMB)
#   - File system (shared folder)
#   - USB (sneakernet)
#   - Any method that can move files
#
# The beauty: packets don't care HOW they get there, just that they do.
#
# ═══════════════════════════════════════════════════════════════════════════════

import os
import sys
import json
import time
import shutil
import hashlib
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from datetime import datetime

@dataclass
class SyncConfig:
    """Configuration for memory sync"""
    local_path: str
    remote_path: str
    remote_host: str = ""
    sync_method: str = "file"  # file, rsync, scp, smb
    sync_interval: float = 5.0
    bidirectional: bool = True


class MemorySync:
    """
    Synchronizes memory packets between nodes.
    
    Methods:
    - file: Direct file copy (for shared folders/USB)
    - rsync: rsync over SSH
    - scp: SCP copy
    - smb: Windows share
    """
    
    def __init__(self, config: SyncConfig):
        self.config = config
        self.local_path = Path(config.local_path)
        self.remote_path = Path(config.remote_path) if not config.remote_host else config.remote_path
        
        # Track what we've synced
        self.synced_files: Dict[str, float] = {}  # filename -> mtime
        
        # Stats
        self.files_sent = 0
        self.files_received = 0
        self.last_sync = 0
        self.sync_errors = 0
    
    def _get_local_files(self, subdir: str = "outbox") -> List[Path]:
        """Get files from local subdirectory"""
        local_dir = self.local_path / subdir
        if not local_dir.exists():
            return []
        return list(local_dir.glob("*.json"))
    
    def _get_remote_files(self, subdir: str = "outbox") -> List[str]:
        """Get files from remote subdirectory"""
        if self.config.sync_method == "file":
            remote_dir = Path(self.config.remote_path) / subdir
            if not remote_dir.exists():
                return []
            return [f.name for f in remote_dir.glob("*.json")]
        
        elif self.config.sync_method == "rsync":
            # List remote files via SSH
            cmd = f"ssh {self.config.remote_host} 'ls {self.config.remote_path}/{subdir}/*.json 2>/dev/null'"
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode == 0:
                    return [Path(f).name for f in result.stdout.strip().split('\n') if f]
            except:
                pass
            return []
        
        return []
    
    def _copy_to_remote(self, local_file: Path, remote_subdir: str = "inbox") -> bool:
        """Copy a file to remote"""
        if self.config.sync_method == "file":
            remote_dir = Path(self.config.remote_path) / remote_subdir
            remote_dir.mkdir(parents=True, exist_ok=True)
            dest = remote_dir / local_file.name
            shutil.copy2(local_file, dest)
            return True
        
        elif self.config.sync_method == "rsync":
            remote = f"{self.config.remote_host}:{self.config.remote_path}/{remote_subdir}/"
            cmd = ["rsync", "-avz", str(local_file), remote]
            try:
                result = subprocess.run(cmd, capture_output=True)
                return result.returncode == 0
            except:
                return False
        
        elif self.config.sync_method == "scp":
            remote = f"{self.config.remote_host}:{self.config.remote_path}/{remote_subdir}/"
            cmd = ["scp", str(local_file), remote]
            try:
                result = subprocess.run(cmd, capture_output=True)
                return result.returncode == 0
            except:
                return False
        
        return False
    
    def _copy_from_remote(self, filename: str, remote_subdir: str = "outbox", 
                          local_subdir: str = "inbox") -> bool:
        """Copy a file from remote"""
        local_dir = self.local_path / local_subdir
        local_dir.mkdir(parents=True, exist_ok=True)
        dest = local_dir / filename
        
        if self.config.sync_method == "file":
            source = Path(self.config.remote_path) / remote_subdir / filename
            if source.exists():
                shutil.copy2(source, dest)
                return True
            return False
        
        elif self.config.sync_method == "rsync":
            source = f"{self.config.remote_host}:{self.config.remote_path}/{remote_subdir}/{filename}"
            cmd = ["rsync", "-avz", source, str(dest)]
            try:
                result = subprocess.run(cmd, capture_output=True)
                return result.returncode == 0
            except:
                return False
        
        elif self.config.sync_method == "scp":
            source = f"{self.config.remote_host}:{self.config.remote_path}/{remote_subdir}/{filename}"
            cmd = ["scp", source, str(dest)]
            try:
                result = subprocess.run(cmd, capture_output=True)
                return result.returncode == 0
            except:
                return False
        
        return False
    
    def sync_outgoing(self) -> int:
        """Send local outbox to remote inbox"""
        sent = 0
        
        for local_file in self._get_local_files("outbox"):
            # Check if already synced
            mtime = local_file.stat().st_mtime
            if local_file.name in self.synced_files:
                if self.synced_files[local_file.name] >= mtime:
                    continue  # Already synced
            
            if self._copy_to_remote(local_file, "inbox"):
                self.synced_files[local_file.name] = mtime
                sent += 1
                self.files_sent += 1
                
                # Move to processed locally
                processed_dir = self.local_path / "sent"
                processed_dir.mkdir(exist_ok=True)
                local_file.rename(processed_dir / local_file.name)
            else:
                self.sync_errors += 1
        
        return sent
    
    def sync_incoming(self) -> int:
        """Get remote outbox to local inbox"""
        received = 0
        
        # Get list of files in remote outbox
        remote_files = self._get_remote_files("outbox")
        
        # Get what we already have locally
        local_files = {f.name for f in self._get_local_files("inbox")}
        local_processed = {f.name for f in self._get_local_files("processed")}
        
        for filename in remote_files:
            # Skip if we already have it
            if filename in local_files or filename in local_processed:
                continue
            
            if self._copy_from_remote(filename, "outbox", "inbox"):
                received += 1
                self.files_received += 1
            else:
                self.sync_errors += 1
        
        return received
    
    def sync(self) -> Dict:
        """Perform full bidirectional sync"""
        result = {
            "timestamp": time.time(),
            "sent": 0,
            "received": 0,
            "errors": 0
        }
        
        try:
            result["sent"] = self.sync_outgoing()
            
            if self.config.bidirectional:
                result["received"] = self.sync_incoming()
                
        except Exception as e:
            result["errors"] += 1
            result["error_message"] = str(e)
        
        self.last_sync = time.time()
        return result
    
    def get_status(self) -> Dict:
        """Get sync status"""
        return {
            "local_path": str(self.local_path),
            "remote_path": str(self.remote_path),
            "remote_host": self.config.remote_host,
            "method": self.config.sync_method,
            "files_sent": self.files_sent,
            "files_received": self.files_received,
            "sync_errors": self.sync_errors,
            "last_sync": self.last_sync,
            "pending_outgoing": len(self._get_local_files("outbox"))
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PRE-CONFIGURED SYNC SETUPS
# ═══════════════════════════════════════════════════════════════════════════════

def create_satellite_sync(method: str = "file") -> MemorySync:
    """Create sync for Windows <-> Satellite"""
    
    if method == "file":
        # Assumes shared folder or USB mount
        config = SyncConfig(
            local_path="E:/coding projects/ebook/memory_packets",
            remote_path="E:/coding projects/ebook/satellite_mirror",  # Or USB path
            sync_method="file"
        )
    elif method == "rsync":
        # FIX 2026-02-09: was root@, actual username is alaksander
        config = SyncConfig(
            local_path="E:/coding projects/ebook/memory_packets",
            remote_path="/home/alaksander/akashic/memory_packets",
            remote_host="alaksander@192.168.1.24",
            sync_method="rsync"
        )
    elif method == "scp":
        # FIX 2026-02-09: was root@, actual username is alaksander
        config = SyncConfig(
            local_path="E:/coding projects/ebook/memory_packets",
            remote_path="/home/alaksander/akashic/memory_packets",
            remote_host="alaksander@192.168.1.24",
            sync_method="scp"
        )
    else:
        raise ValueError(f"Unknown sync method: {method}")
    
    return MemorySync(config)


# ═══════════════════════════════════════════════════════════════════════════════
# USB SNEAKERNET MODE
# ═══════════════════════════════════════════════════════════════════════════════

class USBSync:
    """
    USB-based sync for when network is unreliable.
    
    Export packets to USB, physically move USB, import on other side.
    Old school, but it works.
    """
    
    def __init__(self, packet_store_path: str):
        self.store_path = Path(packet_store_path)
    
    def export_to_usb(self, usb_path: str) -> Dict:
        """Export pending packets to USB drive"""
        usb = Path(usb_path)
        export_dir = usb / "akashic_packets" / "from_" + os.environ.get("COMPUTERNAME", "unknown")
        export_dir.mkdir(parents=True, exist_ok=True)
        
        exported = 0
        
        # Copy outbox
        outbox = self.store_path / "outbox"
        if outbox.exists():
            for f in outbox.glob("*.json"):
                dest = export_dir / f.name
                shutil.copy2(f, dest)
                exported += 1
                # Move to sent
                sent_dir = self.store_path / "sent"
                sent_dir.mkdir(exist_ok=True)
                f.rename(sent_dir / f.name)
        
        # Write manifest
        manifest = {
            "exported_at": datetime.now().isoformat(),
            "from_host": os.environ.get("COMPUTERNAME", "unknown"),
            "packet_count": exported
        }
        
        with open(export_dir / "MANIFEST.json", 'w') as f:
            json.dump(manifest, f, indent=2)
        
        return {"exported": exported, "path": str(export_dir)}
    
    def import_from_usb(self, usb_path: str) -> Dict:
        """Import packets from USB drive"""
        usb = Path(usb_path)
        
        imported = 0
        sources = []
        
        # Find all packet directories
        akashic_dir = usb / "akashic_packets"
        if akashic_dir.exists():
            for source_dir in akashic_dir.iterdir():
                if source_dir.is_dir() and source_dir.name.startswith("from_"):
                    source_name = source_dir.name[5:]  # Remove "from_" prefix
                    
                    if source_name == os.environ.get("COMPUTERNAME", ""):
                        continue  # Don't import our own packets
                    
                    for packet_file in source_dir.glob("*.json"):
                        if packet_file.name == "MANIFEST.json":
                            continue
                        
                        # Copy to inbox
                        inbox = self.store_path / "inbox"
                        inbox.mkdir(parents=True, exist_ok=True)
                        dest = inbox / packet_file.name
                        
                        if not dest.exists():  # Don't overwrite
                            shutil.copy2(packet_file, dest)
                            imported += 1
                    
                    sources.append(source_name)
        
        return {
            "imported": imported,
            "sources": sources
        }


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    'MemorySync',
    'SyncConfig',
    'USBSync',
    'create_satellite_sync'
]
