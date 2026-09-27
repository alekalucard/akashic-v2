"""
Terminal Log Capture - Writes console output to a file Claude can read
"""
import sys
import os
from datetime import datetime
from pathlib import Path

# Log file path
LOG_DIR = Path("F:/Sandbox/ebook/boot_logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "live_console.log"

class TeeWriter:
    """Write to both console and file"""
    def __init__(self, original, log_file):
        self.original = original
        self.log_file = log_file
        self.encoding = getattr(original, 'encoding', 'utf-8')
        
    def write(self, text):
        self.original.write(text)
        try:
            with open(self.log_file, 'a', encoding='utf-8', errors='replace') as f:
                f.write(text)
        except:
            pass
            
    def flush(self):
        self.original.flush()

def install_log_capture():
    """Install the log capture - call early in boot"""
    # Clear previous log
    try:
        LOG_FILE.unlink(missing_ok=True)
        LOG_FILE.write_text(f"=== Boot started at {datetime.now().isoformat()} ===\n")
    except:
        pass
    
    # Install tee writers
    sys.stdout = TeeWriter(sys.__stdout__, LOG_FILE)
    sys.stderr = TeeWriter(sys.__stderr__, LOG_FILE)
    print(f"[LogCapture] Writing to {LOG_FILE}")

# Auto-install when imported
if __name__ != "__main__":
    install_log_capture()
