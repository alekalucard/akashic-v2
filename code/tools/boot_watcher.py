"""
Boot Watcher — real-time boot monitor for Claude Code / Nous.
==============================================================

Tails state/boot_full.log, classifies events by severity, tracks key
milestones (GPU status, fairy failures, guild wiring, performance),
and produces a structured JSON digest when boot completes.

Usage:
    # Start BEFORE or right after running start_nous.bat
    python tools/boot_watcher.py

    # With timeout (default 300s)
    python tools/boot_watcher.py --timeout 300

    # Analyze an existing log (no waiting, instant digest)
    python tools/boot_watcher.py --analyze

Output:
    - Prints key events to stdout in real-time
    - Writes state/boot_digest.json on completion
    - Exits with code 0 (success) or 1 (timeout/error)

Designed to be launched from Claude Code as a background Bash task:
    Bash("python tools/boot_watcher.py --timeout 300", run_in_background=True)
"""
import sys
import os
import json
import time
import re
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ═══ Paths ═══
PROJECT_ROOT = Path(__file__).parent.parent
STATE_DIR = PROJECT_ROOT / "state"
BOOT_FULL_LOG = STATE_DIR / "boot_full.log"
BOOT_SIGNAL = STATE_DIR / "boot_signal.txt"
DIGEST_FILE = STATE_DIR / "boot_digest.json"

# ═══ Severity patterns (same as boot_observer_tools.py) ═══
ERROR_PATTERNS = {
    # CRITICAL (3)
    "FAIRY DEATH": 3, "Traceback": 3, "CRITICAL": 3, "FATAL": 3,
    "crashed": 3, "segfault": 3, "MemoryError": 3,
    # HIGH (2)
    "Error": 2, "ERROR": 2, "Exception": 2, "failed": 2,
    "Attempting to restart": 2, "DEATH DETECTED": 2,
    "AttributeError": 2, "TypeError": 2, "ImportError": 2,
    "KeyError": 2, "ModuleNotFoundError": 2, "NoneType": 2,
    "No fairy_instance": 2,
    # MEDIUM (1)
    "WARNING": 1, "Warning": 1, "timeout": 1, "timed out": 1,
    "Silent for": 1, "not found": 1, "not available": 1,
    "skipping": 1, "DISABLED": 1, "Access is denied": 1,
}

IGNORE_PATTERNS = [
    "SetProcessDpiAwarenessContext", "qt.qpa.window", "Qt's default DPI",
    "QApplication was not created in the main", "ThoughtChainEngine not available",
    "DISABLED per Ace", "sifting DISABLED", "PyCUDA", "UserWarning",
    "Health analysis",      # CognitionLoop health check contains "failed=0" — not an error
    "healthy (failed=0",    # Same — false positive match on "failed"
]

# ═══ Special interest patterns ═══
GPU_PATTERNS = re.compile(
    r"(Rust\s*bridge|cuBLAS|CUDA|GPU|cpu[_\-]?only|tok/s|tokens?\s*per\s*sec|"
    r"rwkv_inference|_native\.cp|\.pyd|device\s*=\s*['\"]?cuda)", re.IGNORECASE
)
GUILD_PATTERNS = re.compile(
    r"(guild\.inference|guild.*request|guild.*response|match=True|No subscribers"
    r"|AkashicInferenceFairy.*[Gg]uild)", re.IGNORECASE
)
PLANE_PATTERN = re.compile(r"\(plane=(P\d{2})")
PLANE_BOOT_PATTERN = re.compile(r"Booting plane\(s\):\s*(P\d{2})")
FAIRY_BOOTED_PATTERN = re.compile(r"\[CASCADE\].*?:\s*BOOTED\s*\((\d+)ms\)", re.IGNORECASE)
FAIRY_SCAN_PATTERN = re.compile(r"(\d+)\s*fairies?\s*(found|across|in filesystem)", re.IGNORECASE)
FAIRY_COUNT_PATTERN = re.compile(r"(\d+)\s*fairies?\s*(booted|online|running|registered|awake)", re.IGNORECASE)
BOOT_COMPLETE_PATTERNS = [
    "BOOT COMPLETE",
    "STAGED BOOT COMPLETE",
    "ALL FAIRIES AWAKE",
]
BOOT_TIME_PATTERN = re.compile(r"(\d+\.?\d*)\s*s", re.IGNORECASE)
TOK_S_PATTERN = re.compile(r"([\d.]+)\s*tok/s", re.IGNORECASE)


class BootWatcher:
    """Watches boot_full.log and produces a structured digest."""

    def __init__(self, timeout: int = 300):
        self.timeout = timeout
        self.start_time = time.time()
        self.boot_start_time = None
        self.file_position = 0
        self.total_lines = 0

        # Tracked events
        self.critical_events = []
        self.errors = []
        self.warnings_count = 0
        self.gpu_events = []
        self.guild_events = []
        self.slow_operations = []
        self.planes_seen = []
        self.fairy_count = 0          # Individual [CASCADE] BOOTED count
        self._fairies_scanned = 0     # FairyScanner total
        self._fairies_reported = 0    # Any "N fairies booted/online" count
        self.boot_duration = None
        self.boot_complete = False

        # Dedup
        self._seen = set()
        self._announced_planes = set()

    def _classify_line(self, line: str) -> int:
        """Score a line's severity (0=normal, 1=warning, 2=error, 3=critical)."""
        if any(ign in line for ign in IGNORE_PATTERNS):
            return 0
        max_score = 0
        for pattern, score in ERROR_PATTERNS.items():
            if pattern in line:
                max_score = max(max_score, score)
        return max_score

    def _check_special(self, line: str, line_num: int):
        """Check for special interest patterns."""
        # GPU status
        if GPU_PATTERNS.search(line):
            event = {"line": line_num, "text": line.strip()[:200]}
            self.gpu_events.append(event)

        # Guild wiring
        if GUILD_PATTERNS.search(line):
            event = {"line": line_num, "text": line.strip()[:200]}
            self.guild_events.append(event)

        # Plane transitions — match [awake] FairyName (plane=PXX
        m = PLANE_PATTERN.search(line)
        if m:
            plane = m.group(1)
            if plane not in self.planes_seen:
                self.planes_seen.append(plane)
        # Also match "Booting plane(s): PXX"
        m = PLANE_BOOT_PATTERN.search(line)
        if m:
            plane = m.group(1)
            if plane not in self.planes_seen:
                self.planes_seen.append(plane)

        # Individual fairy boots: [CASCADE] XFairy: BOOTED (XXms)
        m = FAIRY_BOOTED_PATTERN.search(line)
        if m:
            self.fairy_count += 1

        # Fairy scanner count (total found)
        m = FAIRY_SCAN_PATTERN.search(line)
        if m:
            count = int(m.group(1))
            if count > self._fairies_scanned:
                self._fairies_scanned = count

        # General fairy count patterns
        m = FAIRY_COUNT_PATTERN.search(line)
        if m:
            count = int(m.group(1))
            if count > self._fairies_reported:
                self._fairies_reported = count

        # Boot completion — multiple patterns
        for pat in BOOT_COMPLETE_PATTERNS:
            if pat in line:
                if not self.boot_complete:
                    self.boot_complete = True
                    # Try to parse duration from the line
                    if self.boot_start_time:
                        self.boot_duration = round(time.time() - self.boot_start_time, 1)
                break

        # Slow operations (timing > 10s)
        timing_match = re.search(r"(\d+\.?\d*)\s*(?:ms|seconds?|s\b)", line)
        if timing_match:
            val = float(timing_match.group(1))
            unit = timing_match.group(0)
            if "ms" in unit:
                val /= 1000.0
            if val > 10.0 and not any(p in line for p in BOOT_COMPLETE_PATTERNS):
                self.slow_operations.append({
                    "line": line_num,
                    "seconds": round(val, 1),
                    "text": line.strip()[:150],
                })

    def process_line(self, line: str, line_num: int):
        """Process a single log line."""
        self.total_lines = line_num
        stripped = line.strip()
        if not stripped:
            return

        # Classify severity
        score = self._classify_line(stripped)

        # Track by severity
        if score >= 3:
            dedup = stripped[:80]
            if dedup not in self._seen:
                self._seen.add(dedup)
                self.critical_events.append({
                    "line": line_num,
                    "text": stripped[:200],
                })
                self._print(f"  🔴 CRITICAL: {stripped[:120]}")
        elif score >= 2:
            dedup = stripped[:80]
            if dedup not in self._seen:
                self._seen.add(dedup)
                self.errors.append({
                    "line": line_num,
                    "text": stripped[:200],
                })
                # Only print first 15 errors to avoid spam
                if len(self.errors) <= 15:
                    self._print(f"  🟠 ERROR: {stripped[:120]}")
        elif score >= 1:
            self.warnings_count += 1

        # Check special interest patterns
        self._check_special(stripped, line_num)

    def _print(self, msg: str):
        """Print with flush for real-time visibility. Safe for Windows cp1252."""
        try:
            print(msg, flush=True)
        except UnicodeEncodeError:
            # Windows terminal can't handle emoji — strip them
            safe = msg.encode("ascii", errors="replace").decode("ascii")
            print(safe, flush=True)

    def _gpu_summary(self) -> str:
        """Summarize GPU status from events."""
        if not self.gpu_events:
            return "no GPU/Rust events detected"

        texts = [e["text"] for e in self.gpu_events]
        joined = " ".join(texts).lower()

        # Check for tok/s
        best_tok_s = 0.0
        for e in self.gpu_events:
            m = TOK_S_PATTERN.search(e["text"])
            if m:
                val = float(m.group(1))
                if val > best_tok_s:
                    best_tok_s = val

        parts = []

        if "rust bridge" in joined and ("online" in joined or "available" in joined or "loaded" in joined):
            parts.append("Rust bridge ONLINE")
        elif "rust" in joined and "not available" in joined:
            parts.append("Rust bridge NOT available (CPU fallback)")
        elif "rust" in joined:
            parts.append("Rust bridge detected")

        if best_tok_s > 0:
            speed_label = "GPU" if best_tok_s > 50 else "CPU-speed"
            parts.append(f"{best_tok_s:.1f} tok/s ({speed_label})")

        if "cuda" in joined and ("true" in joined or "available" in joined):
            parts.append("CUDA available")
        elif "cpu-only" in joined or "cpu only" in joined:
            parts.append("CPU-only mode")

        return ", ".join(parts) if parts else f"{len(self.gpu_events)} GPU-related events"

    def _guild_summary(self) -> str:
        """Summarize guild status from events."""
        if not self.guild_events:
            return "no guild events"

        texts = [e["text"] for e in self.guild_events]
        joined = " ".join(texts).lower()

        if "match=true" in joined or "guild bridge" in joined:
            return "inference bridge active"
        elif "no subscribers" in joined:
            return "⚠ guild.inference.request has NO subscribers"
        else:
            return f"{len(self.guild_events)} guild events"

    def build_digest(self) -> dict:
        """Build the final digest."""
        elapsed = time.time() - self.start_time

        # Health score: start at 100, deduct for issues
        score = 100
        score -= len(self.critical_events) * 15
        score -= len(self.errors) * 3
        score -= self.warnings_count * 0.5
        score = max(0, min(100, score))

        status = "complete" if self.boot_complete else "timeout"

        # Best fairy count: prefer CASCADE BOOTED count, fall back to reported/scanned
        best_fairy_count = self.fairy_count  # individual BOOTED lines
        if best_fairy_count == 0:
            best_fairy_count = self._fairies_reported or self._fairies_scanned

        digest = {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": self.boot_duration or round(elapsed, 1),
            "fairies_booted": best_fairy_count,
            "fairies_scanned": self._fairies_scanned,
            "planes": self.planes_seen,
            "gpu_status": self._gpu_summary(),
            "guild_status": self._guild_summary(),
            "health_score": round(score),
            "critical_events": self.critical_events[:10],
            "critical_count": len(self.critical_events),
            "errors": self.errors[:15],
            "error_count": len(self.errors),
            "warnings_count": self.warnings_count,
            "slow_operations": sorted(
                self.slow_operations, key=lambda x: x["seconds"], reverse=True
            )[:10],
            "gpu_events": self.gpu_events[:10],
            "guild_events": self.guild_events[:10],
            "total_lines": self.total_lines,
            "watcher_runtime_seconds": round(elapsed, 1),
        }
        return digest

    def save_digest(self, digest: dict):
        """Save digest to state/boot_digest.json."""
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(DIGEST_FILE, "w", encoding="utf-8") as f:
            json.dump(digest, f, indent=2)

    def print_digest(self, digest: dict):
        """Print a human-readable summary."""
        self._print("")
        self._print("=" * 60)
        self._print("  BOOT DIGEST")
        self._print("=" * 60)
        self._print(f"  Status:       {digest['status'].upper()}")
        self._print(f"  Duration:     {digest['duration_seconds']}s")
        self._print(f"  Fairies:      {digest['fairies_booted']}")
        self._print(f"  Planes:       {', '.join(digest['planes'])}")
        self._print(f"  GPU:          {digest['gpu_status']}")
        self._print(f"  Guild:        {digest['guild_status']}")
        self._print(f"  Health:       {digest['health_score']}/100")
        self._print(f"  Critical:     {digest['critical_count']}")
        self._print(f"  Errors:       {digest['error_count']}")
        self._print(f"  Warnings:     {digest['warnings_count']}")
        if digest["slow_operations"]:
            self._print(f"  Slowest:      {digest['slow_operations'][0]['seconds']}s — {digest['slow_operations'][0]['text'][:80]}")
        self._print(f"  Log lines:    {digest['total_lines']}")
        self._print("=" * 60)
        self._print(f"  Digest saved: {DIGEST_FILE}")
        self._print("")

    def wait_for_boot_start(self) -> bool:
        """Wait for boot to start (signal file or log file appears)."""
        self._print("[BootWatcher] Waiting for boot to start...")
        self._print(f"  Watching: {BOOT_FULL_LOG}")
        self._print(f"  Signal:   {BOOT_SIGNAL}")
        self._print(f"  Timeout:  {self.timeout}s")
        self._print("")

        while time.time() - self.start_time < self.timeout:
            # Check signal file
            if BOOT_SIGNAL.exists():
                try:
                    txt = BOOT_SIGNAL.read_text().strip()
                    if txt.startswith("BOOT_START:"):
                        ts = float(txt.split(":")[1])
                        # Only if signal is recent (within last 30 seconds)
                        if time.time() - ts < 30:
                            self.boot_start_time = ts
                            self._print(f"[BootWatcher] Boot signal detected ({time.time() - ts:.0f}s ago)")
                            return True
                except Exception:
                    pass

            # Check if log file exists and is growing
            if BOOT_FULL_LOG.exists():
                try:
                    size = BOOT_FULL_LOG.stat().st_size
                    mtime = BOOT_FULL_LOG.stat().st_mtime
                    # Log file recently modified (within 10s)
                    if time.time() - mtime < 10 and size > 0:
                        self.boot_start_time = mtime
                        self._print(f"[BootWatcher] Boot log detected ({size} bytes)")
                        return True
                except Exception:
                    pass

            time.sleep(0.5)

        return False

    def tail_log(self):
        """Tail boot_full.log until BOOT_COMPLETE or timeout."""
        line_num = 0
        last_activity = time.time()
        stall_warned = False

        self._print("[BootWatcher] Tailing boot log...")
        self._print("")

        while time.time() - self.start_time < self.timeout:
            if not BOOT_FULL_LOG.exists():
                time.sleep(0.2)
                continue

            try:
                with open(BOOT_FULL_LOG, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(self.file_position)
                    new_lines = f.readlines()
                    self.file_position = f.tell()
            except Exception:
                time.sleep(0.2)
                continue

            if new_lines:
                last_activity = time.time()
                stall_warned = False
                for line in new_lines:
                    line_num += 1
                    self.process_line(line, line_num)

                    # Print plane transitions (first discovery only)
                    m = PLANE_PATTERN.search(line)
                    if m:
                        _p = m.group(1)
                        if _p not in self._announced_planes:
                            self._announced_planes.add(_p)
                            self._print(f"  📦 Plane {_p} starting...")

            # Check for boot complete
            if self.boot_complete:
                self._print("")
                self._print("  ✅ BOOT COMPLETE detected!")
                return True

            # Check boot_signal.txt for completion too
            if BOOT_SIGNAL.exists():
                try:
                    txt = BOOT_SIGNAL.read_text().strip()
                    if txt.startswith("BOOT_COMPLETE:"):
                        ts = float(txt.split(":")[1])
                        if self.boot_start_time and self.boot_duration is None:
                            self.boot_duration = ts - self.boot_start_time
                        self.boot_complete = True
                        self._print("")
                        self._print("  ✅ BOOT COMPLETE (signal file)!")
                        return True
                except Exception:
                    pass

            # Stall detection: warn if no new output for 30s
            if time.time() - last_activity > 30 and not stall_warned and line_num > 0:
                self._print(f"  ⏳ No new output for 30s (line {line_num})...")
                stall_warned = True

            time.sleep(0.1)

        self._print("")
        self._print(f"  ⏰ TIMEOUT after {self.timeout}s")
        return False

    def analyze_existing(self):
        """Analyze an existing boot_full.log without waiting."""
        if not BOOT_FULL_LOG.exists():
            self._print(f"[BootWatcher] No log found at {BOOT_FULL_LOG}")
            return False

        self._print(f"[BootWatcher] Analyzing existing log: {BOOT_FULL_LOG}")
        self._print(f"  Size: {BOOT_FULL_LOG.stat().st_size:,} bytes")
        self._print("")

        with open(BOOT_FULL_LOG, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                self.process_line(line, i)

        return True

    def run(self, analyze_only: bool = False) -> int:
        """Main run loop. Returns exit code (0=success, 1=timeout/error)."""
        self._print("=" * 60)
        self._print("  BOOT WATCHER — Real-time boot monitor for Nous")
        self._print("=" * 60)
        self._print("")

        if analyze_only:
            if not self.analyze_existing():
                return 1
        else:
            # Wait for boot to start
            if not self.wait_for_boot_start():
                self._print("[BootWatcher] Timeout waiting for boot to start.")

                # Try analyzing existing log as fallback
                if BOOT_FULL_LOG.exists():
                    self._print("[BootWatcher] Analyzing existing log instead...")
                    self.analyze_existing()
                else:
                    return 1

            if not self.boot_complete:
                # Tail log until complete
                self.tail_log()

        # Build and save digest
        digest = self.build_digest()
        self.save_digest(digest)
        self.print_digest(digest)

        # Also print JSON for machine consumption
        self._print("--- JSON DIGEST ---")
        print(json.dumps(digest, indent=2), flush=True)

        return 0 if self.boot_complete else 1


def main():
    parser = argparse.ArgumentParser(description="Boot Watcher — monitor Akashic boot")
    parser.add_argument("--timeout", type=int, default=300, help="Max wait seconds (default 300)")
    parser.add_argument("--analyze", action="store_true", help="Analyze existing log without waiting")
    args = parser.parse_args()

    watcher = BootWatcher(timeout=args.timeout)
    exit_code = watcher.run(analyze_only=args.analyze)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
