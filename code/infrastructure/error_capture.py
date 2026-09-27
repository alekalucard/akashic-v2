"""
Error Capture System — Comprehensive runtime error monitoring.

Intercepts stdout/stderr early in boot to capture ALL error patterns.
Classifies them by category, severity, and source. Persists to disk
and exposes via get_errors() for the dashboard /errors endpoint.

Usage:
    # At very start of boot (before any fairies load):
    from infrastructure.error_capture import start_capture, get_errors

    start_capture()  # Hooks stdout/stderr

    # Later, from server.py /errors endpoint:
    errors = get_errors()  # Returns structured error data

Design (2026-03-14 Nous):
    This replaces the ad-hoc error pattern matching scattered across
    BootWatcher, ForensicScribeFairy, and boot_monitor.py with a
    SINGLE comprehensive system that catches everything from the source.
"""

import io
import os
import re
import sys
import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict

ROOT = Path(__file__).parent.parent
STATE_DIR = ROOT / "state"


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR CATEGORIES
# ═══════════════════════════════════════════════════════════════════════════════

class Category:
    QUEUE       = "queue"        # Queue full, drops, backpressure
    HANDLER     = "handler"      # Handler errors, callback failures
    IMPORT      = "import"       # ImportError, ModuleNotFoundError
    CRASH       = "crash"        # Traceback, unhandled exception, segfault
    PERFORMANCE = "performance"  # Slow operations, timeouts, stalls
    POSTAL      = "postal"       # PostalCore routing, delivery failures
    FAIRY       = "fairy"        # Fairy boot/tick/shutdown errors
    MEMORY      = "memory"       # OOM, memory pressure, allocation failures
    NETWORK     = "network"      # Connection refused, timeout, socket errors
    PERMISSION  = "permission"   # Permission denied, access errors
    STALE       = "stale"        # GIL references, deprecated patterns
    RESOURCE    = "resource"     # File not found, disk full, resource exhaustion
    UNKNOWN     = "unknown"      # Unclassified errors


class Severity:
    CRITICAL = "critical"   # System-breaking, needs immediate attention
    ERROR    = "error"      # Functionality broken, fairy/subsystem impacted
    WARNING  = "warning"    # Degraded but functional, potential issue
    INFO     = "info"       # Notable event, not necessarily a problem


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR PATTERNS — The heart of the system
#
# Each pattern: (regex, category, severity, description)
# Patterns are checked in order — first match wins.
# ═══════════════════════════════════════════════════════════════════════════════

ERROR_PATTERNS = [
    # ── CRASHES (highest priority) ──
    (r"Traceback \(most recent call last\)",        Category.CRASH,       Severity.CRITICAL, "Python traceback"),
    (r"FATAL|fatal error|PANIC|panic:",             Category.CRASH,       Severity.CRITICAL, "Fatal error"),
    (r"Segmentation fault|SIGSEGV|segfault",        Category.CRASH,       Severity.CRITICAL, "Segmentation fault"),
    (r"SystemExit|sys\.exit",                       Category.CRASH,       Severity.ERROR,    "System exit"),

    # ── QUEUE / POSTAL DROPS ──
    (r"QUEUE FULL|queue full",                      Category.QUEUE,       Severity.ERROR,    "Queue full — messages being dropped"),
    (r"(\d+) drops? since last",                    Category.QUEUE,       Severity.ERROR,    "Message drops detected"),
    (r"backpressure|back.?pressure",                Category.QUEUE,       Severity.WARNING,  "Backpressure detected"),
    (r"evict.*queue|queue.*evict",                  Category.QUEUE,       Severity.WARNING,  "Queue eviction"),

    # ── HANDLER ERRORS ──
    (r"Handler error:",                             Category.HANDLER,     Severity.ERROR,    "Postal handler error"),
    (r"does not support item assignment",           Category.HANDLER,     Severity.ERROR,    "TensorEnvelope missing __setitem__"),
    (r"handler.*exception|exception.*handler",      Category.HANDLER,     Severity.ERROR,    "Handler exception"),
    (r"callback.*error|error.*callback",            Category.HANDLER,     Severity.WARNING,  "Callback error"),

    # ── IMPORT FAILURES ──
    (r"ImportError:",                               Category.IMPORT,      Severity.ERROR,    "Import error"),
    (r"ModuleNotFoundError:",                       Category.IMPORT,      Severity.ERROR,    "Module not found"),
    (r"No module named",                            Category.IMPORT,      Severity.ERROR,    "Missing module"),
    (r"cannot import name",                         Category.IMPORT,      Severity.ERROR,    "Import name error"),
    (r"DLL load failed|LoadLibrary",                Category.IMPORT,      Severity.ERROR,    "DLL/library load failure"),

    # ── PERFORMANCE / STALLS ──
    (r"SLOW capture|Capture took (\d{4,})",         Category.PERFORMANCE, Severity.WARNING,  "Slow screen capture"),
    (r"\[STALL\]",                                  Category.PERFORMANCE, Severity.WARNING,  "Stall detected"),
    (r"stuck|STUCK",                                Category.PERFORMANCE, Severity.WARNING,  "Process stuck"),
    (r"[Tt]imeout|TIMEOUT|timed? ?out",             Category.PERFORMANCE, Severity.WARNING,  "Timeout"),
    (r"took (\d{5,})ms",                            Category.PERFORMANCE, Severity.WARNING,  "Very slow operation (10s+)"),
    (r"deadlock|DEADLOCK",                          Category.PERFORMANCE, Severity.CRITICAL, "Deadlock detected"),
    (r"[Ss]low.*(\d{4,})ms",                        Category.PERFORMANCE, Severity.WARNING,  "Slow operation"),

    # ── FAIRY ERRORS ──
    (r"on_boot.*failed|boot.*failed|Failed to boot", Category.FAIRY,     Severity.ERROR,    "Fairy boot failure"),
    (r"fairy.*error|error.*fairy",                  Category.FAIRY,       Severity.WARNING,  "Fairy error"),
    (r"fairy.*crash|crash.*fairy",                  Category.FAIRY,       Severity.ERROR,    "Fairy crash"),
    (r"\[.*Fairy\].*[Ee]rror:",                     Category.FAIRY,       Severity.WARNING,  "Fairy reported error"),
    (r"No heartbeat|heartbeat.*missing",            Category.FAIRY,       Severity.WARNING,  "Missing heartbeat"),

    # ── POSTAL SYSTEM ──
    (r"\[PostalCore\].*error|\[PostalCore\].*fail", Category.POSTAL,      Severity.ERROR,    "PostalCore error"),
    (r"publish.*failed|route.*failed",              Category.POSTAL,      Severity.WARNING,  "Message delivery failure"),
    (r"subscriber.*error",                          Category.POSTAL,      Severity.WARNING,  "Subscriber error"),

    # ── MEMORY ──
    (r"MemoryError|OutOfMemory|OOM",                Category.MEMORY,      Severity.CRITICAL, "Out of memory"),
    (r"memory.*pressure|pressure.*memory",          Category.MEMORY,      Severity.WARNING,  "Memory pressure"),
    (r"allocation.*fail|alloc.*error",              Category.MEMORY,      Severity.ERROR,    "Allocation failure"),
    (r"gc\.collect|garbage collect",                Category.MEMORY,      Severity.INFO,     "Garbage collection"),

    # ── NETWORK ──
    (r"Connection refused|ECONNREFUSED",            Category.NETWORK,     Severity.WARNING,  "Connection refused"),
    (r"Connection reset|ECONNRESET",                Category.NETWORK,     Severity.WARNING,  "Connection reset"),
    (r"[Ss]ocket.*error|[Ee]rrno \d+",             Category.NETWORK,     Severity.WARNING,  "Socket error"),
    (r"urllib.*error|URLError|HTTPError",           Category.NETWORK,     Severity.WARNING,  "HTTP error"),

    # ── PERMISSIONS ──
    (r"[Pp]ermission denied|PermissionError",       Category.PERMISSION,  Severity.ERROR,    "Permission denied"),
    (r"[Aa]ccess denied|ACCESS_DENIED",             Category.PERMISSION,  Severity.ERROR,    "Access denied"),

    # ── STALE / DEPRECATED ──
    (r"GIL[- ]heavy|own GIL each",                 Category.STALE,       Severity.INFO,     "Stale GIL reference"),
    (r"[Dd]eprecated|DEPRECATED",                   Category.STALE,       Severity.INFO,     "Deprecated usage"),

    # ── RESOURCE ──
    (r"FileNotFoundError|No such file",             Category.RESOURCE,    Severity.WARNING,  "File not found"),
    (r"disk.*full|no space left",                   Category.RESOURCE,    Severity.CRITICAL, "Disk full"),
    (r"too many open files|EMFILE",                 Category.RESOURCE,    Severity.ERROR,    "File descriptor exhaustion"),

    # ── GENERIC ERROR PATTERNS (lowest priority — catches remaining) ──
    (r"[Ii]nvalid argument|EINVAL",                 Category.UNKNOWN,     Severity.WARNING,  "Invalid argument"),
    (r"(?<!\w)[Ee]rror(?!\w).*:",                   Category.UNKNOWN,     Severity.WARNING,  "Generic error"),
    (r"(?<!\w)[Ff]ailed(?!\w)",                     Category.UNKNOWN,     Severity.WARNING,  "Generic failure"),
    (r"CRITICAL|critical:",                         Category.UNKNOWN,     Severity.ERROR,    "Critical message"),
    (r"WARNING.*(?:error|fail|crash)",              Category.UNKNOWN,     Severity.WARNING,  "Warning with error context"),
]

# Compiled patterns for performance
_COMPILED_PATTERNS = [(re.compile(p), cat, sev, desc) for p, cat, sev, desc in ERROR_PATTERNS]

# Lines to SKIP (normal operation, not errors)
SKIP_PATTERNS = [
    re.compile(r"^\[STATUS"),             # Status polling output
    re.compile(r"^\s*$"),                 # Empty lines
    re.compile(r"error_count.*: 0"),      # Zero error count reports
    re.compile(r"Error handling.*route"), # Normal error route setup
    re.compile(r"error_capture.*start"),  # Our own startup message
]


# ═══════════════════════════════════════════════════════════════════════════════
# CAPTURED ERROR
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class CapturedError:
    """A single captured error event."""
    message: str                        # The raw line that triggered
    category: str                       # Category classification
    severity: str                       # Severity level
    description: str                    # Human-readable pattern description
    timestamp: float = 0.0             # When captured
    source: str = "stdout"              # stdout or stderr
    count: int = 1                      # How many times this exact error occurred
    first_seen: float = 0.0            # First occurrence
    last_seen: float = 0.0             # Last occurrence
    context_before: List[str] = field(default_factory=list)  # Lines before this error
    context_after: List[str] = field(default_factory=list)   # Lines after (for tracebacks)


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR CAPTURE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class ErrorCapture:
    """
    Central error capture engine.

    Wraps stdout/stderr to intercept ALL output, pattern-matches against
    known error signatures, and stores structured error data.
    """

    MAX_ERRORS = 2000           # Max unique errors to store
    MAX_CONTEXT_LINES = 5       # Lines of context before/after
    TRACEBACK_WINDOW = 20       # Lines to capture after a traceback start
    PERSIST_INTERVAL = 30.0     # Save to disk every 30s

    def __init__(self):
        self._errors: Dict[str, CapturedError] = {}   # dedup key -> error
        self._lock = threading.Lock()
        self._running = False
        self._boot_time = time.time()

        # Rolling context buffer (last N lines for context)
        self._context_buffer: List[str] = []
        self._context_lock = threading.Lock()

        # Traceback accumulator
        self._in_traceback = False
        self._traceback_lines: List[str] = []
        self._traceback_countdown = 0

        # Original streams (saved for restoration)
        self._orig_stdout = None
        self._orig_stderr = None

        # ── FIFTH RING COMPLIANCE ──
        # ErrorCapture starts BEFORE postal exists (catches boot errors).
        # Once postal is online, we BRIDGE errors into the postal system
        # so ForensicScribe, shadows, and the whole organism can see them.
        # This respects Ring 3: POSTAL-ONLY communication.
        self._postal = None       # Set via wire_to_postal() after boot
        self._postal_ready = False

        # Stats
        self._total_lines = 0
        self._total_errors = 0
        self._total_warnings = 0

        # Persist thread
        self._persist_thread = None

    def start(self):
        """Start capturing. Wraps stdout/stderr."""
        if self._running:
            return

        self._running = True
        self._boot_time = time.time()

        # Wrap stdout
        self._orig_stdout = sys.stdout
        sys.stdout = _StreamInterceptor(self._orig_stdout, self, "stdout")

        # Wrap stderr
        self._orig_stderr = sys.stderr
        sys.stderr = _StreamInterceptor(self._orig_stderr, self, "stderr")

        # Start persistence thread
        self._persist_thread = threading.Thread(
            target=self._persist_loop, daemon=True, name="ErrorCapture_Persist"
        )
        self._persist_thread.start()

        # ── Register with InfraTracer ──
        try:
            from infrastructure.infra_tracer import get_infra_tracer
            _it = get_infra_tracer()
            _it.register_actor("error_capture", role="monitor",
                               description="Intercepts stdout/stderr, classifies errors by pattern")
            _it.lifecycle("error_capture", "started", {"patterns": len(ERROR_PATTERNS)})
        except Exception:
            pass

        # Don't print through our own interceptor for startup
        self._orig_stdout.write("[ErrorCapture] Started — monitoring stdout/stderr for errors\n")
        self._orig_stdout.flush()

    def wire_to_postal(self, postal):
        """
        FIFTH RING BRIDGE: Connect to postal system.

        Called after postal boots. From this point forward, every captured
        error is ALSO published to postal so ForensicScribe, shadows, and
        the whole organism can see it. Pre-postal errors that were captured
        before this call are flushed as a batch.

        Topic: telemetry.error.captured
        """
        self._postal = postal
        self._postal_ready = True

        # Flush pre-postal errors into the postal system
        with self._lock:
            pre_postal_count = 0
            for err in self._errors.values():
                self._publish_to_postal(err)
                pre_postal_count += 1

        if pre_postal_count > 0:
            print(f"[ErrorCapture] Bridged to postal — flushed {pre_postal_count} "
                  f"pre-boot errors into telemetry.error.captured")
        else:
            print(f"[ErrorCapture] Bridged to postal — clean boot so far")

    def _publish_to_postal(self, error: CapturedError):
        """Publish a captured error through postal (Fifth Ring compliance)."""
        if not self._postal_ready or not self._postal:
            return
        try:
            self._postal.publish("telemetry.error.captured", {
                "message": error.message[:500],
                "category": error.category,
                "severity": error.severity,
                "description": error.description,
                "count": error.count,
                "source": error.source,
                "first_seen": error.first_seen,
                "last_seen": error.last_seen,
                "ts": time.time(),
            })
        except Exception:
            pass  # Don't recurse on postal errors

    def stop(self):
        """Stop capturing. Restore original streams."""
        self._running = False

        if self._orig_stdout:
            sys.stdout = self._orig_stdout
        if self._orig_stderr:
            sys.stderr = self._orig_stderr

        self._persist_to_disk()

    def process_line(self, line: str, source: str = "stdout"):
        """Process a single line of output. Called by stream interceptor."""
        self._total_lines += 1
        stripped = line.rstrip()

        if not stripped:
            return

        # Skip known non-error patterns
        for skip_re in SKIP_PATTERNS:
            if skip_re.search(stripped):
                return

        # Update context buffer
        with self._context_lock:
            self._context_buffer.append(stripped)
            if len(self._context_buffer) > self.MAX_CONTEXT_LINES * 2:
                self._context_buffer = self._context_buffer[-self.MAX_CONTEXT_LINES:]

        # Handle traceback accumulation
        if self._in_traceback:
            self._traceback_lines.append(stripped)
            self._traceback_countdown -= 1
            # Tracebacks end with the actual exception line (no leading whitespace after File lines)
            if (self._traceback_countdown <= 0 or
                (not stripped.startswith(" ") and not stripped.startswith("Traceback") and
                 "File " not in stripped and len(self._traceback_lines) > 2)):
                # Traceback complete — record as one error
                full_tb = "\n".join(self._traceback_lines)
                self._record_error(
                    full_tb, Category.CRASH, Severity.ERROR,
                    "Python traceback", source
                )
                self._in_traceback = False
                self._traceback_lines = []
                return
            return

        # Check for traceback start
        if "Traceback (most recent call last)" in stripped:
            self._in_traceback = True
            self._traceback_lines = [stripped]
            self._traceback_countdown = self.TRACEBACK_WINDOW
            return

        # Match against error patterns
        for pattern_re, category, severity, description in _COMPILED_PATTERNS:
            if pattern_re.search(stripped):
                self._record_error(stripped, category, severity, description, source)
                return

    def _record_error(self, message: str, category: str, severity: str,
                      description: str, source: str):
        """Record a captured error (with deduplication)."""
        now = time.time()

        # Dedup key: first 120 chars of message + category
        # This groups repeated occurrences of the same error
        dedup_key = f"{category}:{message[:120]}"

        with self._lock:
            if dedup_key in self._errors:
                # Increment existing
                err = self._errors[dedup_key]
                err.count += 1
                err.last_seen = now
                # Upgrade severity if needed
                _sev_rank = {Severity.INFO: 0, Severity.WARNING: 1,
                             Severity.ERROR: 2, Severity.CRITICAL: 3}
                if _sev_rank.get(severity, 0) > _sev_rank.get(err.severity, 0):
                    err.severity = severity
            else:
                # New error
                if len(self._errors) >= self.MAX_ERRORS:
                    # Evict oldest by first_seen
                    oldest_key = min(self._errors, key=lambda k: self._errors[k].first_seen)
                    del self._errors[oldest_key]

                # Get context
                with self._context_lock:
                    ctx = list(self._context_buffer[-self.MAX_CONTEXT_LINES:])

                self._errors[dedup_key] = CapturedError(
                    message=message[:2000],  # Cap message length
                    category=category,
                    severity=severity,
                    description=description,
                    timestamp=now,
                    source=source,
                    count=1,
                    first_seen=now,
                    last_seen=now,
                    context_before=ctx,
                )

            # Update stats
            if severity in (Severity.ERROR, Severity.CRITICAL):
                self._total_errors += 1
            elif severity == Severity.WARNING:
                self._total_warnings += 1

        # FIFTH RING: Publish through postal if available
        # New errors get published immediately. Repeated errors only every 10th occurrence.
        if self._postal_ready:
            err = self._errors.get(dedup_key)
            if err and (err.count == 1 or err.count % 10 == 0):
                self._publish_to_postal(err)

    def get_errors(self, category: str = None, severity: str = None,
                   limit: int = 200) -> Dict[str, Any]:
        """
        Get captured errors for the /errors endpoint.

        Returns structured data suitable for dashboard display.
        """
        with self._lock:
            errors = list(self._errors.values())

        # Filter
        if category:
            errors = [e for e in errors if e.category == category]
        if severity:
            errors = [e for e in errors if e.severity == severity]

        # Sort: critical first, then by count (most frequent), then by recency
        _sev_rank = {Severity.CRITICAL: 0, Severity.ERROR: 1,
                     Severity.WARNING: 2, Severity.INFO: 3}
        errors.sort(key=lambda e: (_sev_rank.get(e.severity, 9), -e.count, -e.last_seen))

        # Limit
        errors = errors[:limit]

        # Category summary
        cat_counts = {}
        sev_counts = {Severity.CRITICAL: 0, Severity.ERROR: 0,
                      Severity.WARNING: 0, Severity.INFO: 0}
        with self._lock:
            for err in self._errors.values():
                cat_counts[err.category] = cat_counts.get(err.category, 0) + err.count
                sev_counts[err.severity] = sev_counts.get(err.severity, 0) + err.count

        return {
            "uptime_sec": round(time.time() - self._boot_time, 1),
            "total_lines_processed": self._total_lines,
            "total_error_events": self._total_errors,
            "total_warning_events": self._total_warnings,
            "unique_errors": len(self._errors),
            "by_category": cat_counts,
            "by_severity": sev_counts,
            "errors": [
                {
                    "message": e.message[:500],  # Truncate for JSON
                    "category": e.category,
                    "severity": e.severity,
                    "description": e.description,
                    "count": e.count,
                    "first_seen": e.first_seen,
                    "last_seen": e.last_seen,
                    "source": e.source,
                    "age_sec": round(time.time() - e.first_seen, 1),
                    "context": e.context_before[-3:] if e.context_before else [],
                }
                for e in errors
            ],
            "ts": time.time(),
        }

    def get_summary(self) -> Dict[str, Any]:
        """Quick summary for status endpoint (lightweight)."""
        with self._lock:
            critical = sum(1 for e in self._errors.values() if e.severity == Severity.CRITICAL)
            errors = sum(1 for e in self._errors.values() if e.severity == Severity.ERROR)
            warnings = sum(1 for e in self._errors.values() if e.severity == Severity.WARNING)

        return {
            "critical": critical,
            "errors": errors,
            "warnings": warnings,
            "total_unique": critical + errors + warnings,
            "total_events": self._total_errors + self._total_warnings,
            "uptime_sec": round(time.time() - self._boot_time, 1),
        }

    def _persist_loop(self):
        """Periodically save errors to disk."""
        while self._running:
            time.sleep(self.PERSIST_INTERVAL)
            try:
                self._persist_to_disk()
            except Exception:
                pass

    def _persist_to_disk(self):
        """Save current errors to state/error_capture.json."""
        try:
            data = self.get_errors(limit=500)
            data["persisted_at"] = time.time()

            out_path = STATE_DIR / "error_capture.json"
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception:
            pass  # Don't crash on persistence failure


# ═══════════════════════════════════════════════════════════════════════════════
# STREAM INTERCEPTOR — Wraps stdout/stderr without breaking anything
# ═══════════════════════════════════════════════════════════════════════════════

class _StreamInterceptor(io.TextIOBase):
    """
    Wraps an output stream to intercept lines for error detection.

    CRITICAL: Must be completely transparent. Many things depend on
    stdout/stderr behaving exactly like a file object (flush, write,
    fileno, encoding, etc.). Any breakage here breaks the whole system.
    """

    def __init__(self, original_stream, capture: ErrorCapture, source: str):
        self._original = original_stream
        self._capture = capture
        self._source = source
        self._line_buffer = ""

    def write(self, text: str) -> int:
        """Write to original stream AND capture for error detection."""
        if not text:
            return 0
        # Always pass through to original (NEVER swallow output)
        result = self._original.write(text)

        # Buffer lines for pattern matching (handles partial writes)
        try:
            self._line_buffer += text
            while "\n" in self._line_buffer:
                line, self._line_buffer = self._line_buffer.split("\n", 1)
                if self._capture._running:
                    self._capture.process_line(line, self._source)
        except Exception:
            pass  # NEVER break output for error capture

        return result

    def flush(self):
        """Flush original stream."""
        try:
            self._original.flush()
        except Exception:
            pass

    def fileno(self):
        """Return original fileno (needed by subprocess, etc.)."""
        return self._original.fileno()

    @property
    def encoding(self):
        return getattr(self._original, 'encoding', 'utf-8')

    @property
    def errors(self):
        return getattr(self._original, 'errors', 'strict')

    @property
    def name(self):
        return getattr(self._original, 'name', f'<{self._source}>')

    def isatty(self):
        return getattr(self._original, 'isatty', lambda: False)()

    def readable(self):
        return False

    def writable(self):
        return True

    def seekable(self):
        return False

    # Forward any unknown attributes to the original stream
    def __getattr__(self, name):
        return getattr(self._original, name)


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON + PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

_instance: Optional[ErrorCapture] = None
_lock = threading.Lock()


def start_capture() -> ErrorCapture:
    """Start the error capture system. Call once at boot, as early as possible."""
    global _instance
    with _lock:
        if _instance is None:
            _instance = ErrorCapture()
            _instance.start()
        return _instance


def get_capture() -> Optional[ErrorCapture]:
    """Get the capture instance (None if not started)."""
    return _instance


def get_errors(**kwargs) -> Dict[str, Any]:
    """Get captured errors. Safe to call even if capture not started."""
    if _instance:
        return _instance.get_errors(**kwargs)
    return {
        "uptime_sec": 0, "total_lines_processed": 0,
        "total_error_events": 0, "total_warning_events": 0,
        "unique_errors": 0, "by_category": {}, "by_severity": {},
        "errors": [], "ts": time.time(),
    }


def get_summary() -> Dict[str, Any]:
    """Get quick error summary. Safe to call even if capture not started."""
    if _instance:
        return _instance.get_summary()
    return {"critical": 0, "errors": 0, "warnings": 0,
            "total_unique": 0, "total_events": 0, "uptime_sec": 0}
