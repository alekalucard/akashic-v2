"""
Boot Monitor - Captures and analyzes system boot output
Run this INSTEAD of server.py - it will start the server and monitor it

Usage:
    python boot_monitor.py
"""
import subprocess
import sys
import time
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
LOG_FILE = ROOT / "state" / "boot_capture.log"
REPORT_FILE = ROOT / "Claude_Office" / "audits" / "BOOT_MONITOR_REPORT.md"
MONITOR_DURATION = 90  # 90 seconds

# Ensure directories exist
(ROOT / "state").mkdir(exist_ok=True)
(ROOT / "Claude_Office" / "audits").mkdir(parents=True, exist_ok=True)

def main():
    print(f"[BootMonitor] Starting server with {MONITOR_DURATION}s monitoring...")
    print(f"[BootMonitor] Log: {LOG_FILE}")
    print(f"[BootMonitor] Report will be written to: {REPORT_FILE}")
    print("=" * 60)

    # Patterns to look for
    patterns = {
        "chain_broken": re.compile(r"chain BROKEN", re.IGNORECASE),
        "debug": re.compile(r"DEBUG:", re.IGNORECASE),
        "error": re.compile(r"(error|exception|traceback)", re.IGNORECASE),
        "import_error": re.compile(r"(ImportError|ModuleNotFoundError)", re.IGNORECASE),
        "revival": re.compile(r"(reviving|auto-revival)", re.IGNORECASE),
        "warning": re.compile(r"\[WARN\]", re.IGNORECASE),
        "cannot_queue": re.compile(r"Cannot queue", re.IGNORECASE),
        "not_in_registry": re.compile(r"not in registry", re.IGNORECASE),
        "re_queued": re.compile(r"Re-queued sustain", re.IGNORECASE),
        "breaking_because": re.compile(r"Breaking chain because", re.IGNORECASE),
    }

    findings = {k: [] for k in patterns}
    all_lines = []

    # Start server process
    server_path = ROOT / "server.py"
    process = subprocess.Popen(
        [sys.executable, str(server_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(ROOT)
    )

    start_time = time.time()

    try:
        while time.time() - start_time < MONITOR_DURATION:
            line = process.stdout.readline()
            if not line:
                if process.poll() is not None:
                    print("[BootMonitor] Server process ended")
                    break
                continue

            line = line.rstrip()
            all_lines.append(line)
            print(line)  # Echo to console

            # Check patterns
            for name, pattern in patterns.items():
                if pattern.search(line):
                    findings[name].append((len(all_lines), line))

        elapsed = time.time() - start_time
        print(f"\n[BootMonitor] Monitoring complete after {elapsed:.1f}s")

    except KeyboardInterrupt:
        print("\n[BootMonitor] Interrupted by user")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except:
            process.kill()

    # Write raw log
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(all_lines))
    print(f"[BootMonitor] Wrote {len(all_lines)} lines to {LOG_FILE}")

    # Write analysis report
    report = generate_report(findings, all_lines)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[BootMonitor] Report written to {REPORT_FILE}")
    print("\n" + "=" * 60)
    print("DONE! Check Claude_Office/audits/BOOT_MONITOR_REPORT.md")
    print("=" * 60)

def generate_report(findings, all_lines):
    report = f"""# BOOT MONITOR REPORT
**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Total Lines:** {len(all_lines)}
**Monitor Duration:** {MONITOR_DURATION}s

---

## SUMMARY

| Category | Count |
|----------|-------|
| Chain Broken | {len(findings['chain_broken'])} |
| Debug Messages | {len(findings['debug'])} |
| Breaking Because (reason) | {len(findings['breaking_because'])} |
| Errors/Exceptions | {len(findings['error'])} |
| Import Errors | {len(findings['import_error'])} |
| Revival Attempts | {len(findings['revival'])} |
| Warnings | {len(findings['warning'])} |
| Cannot Queue | {len(findings['cannot_queue'])} |
| Not In Registry | {len(findings['not_in_registry'])} |
| Re-queued Sustain (fix working) | {len(findings['re_queued'])} |

---

## CHAIN BREAKS

"""
    if findings['chain_broken']:
        for line_num, line in findings['chain_broken'][:30]:
            report += f"- Line {line_num}: `{line}`\n"
    else:
        report += "*No chain breaks detected*\n"

    report += "\n---\n\n## DEBUG MESSAGES (Why chains break)\n\n"
    if findings['debug'] or findings['breaking_because']:
        combined = findings['debug'] + findings['breaking_because']
        combined.sort(key=lambda x: x[0])
        for line_num, line in combined[:50]:
            report += f"- Line {line_num}: `{line}`\n"
    else:
        report += "*No debug messages*\n"

    report += "\n---\n\n## ERRORS & EXCEPTIONS\n\n"
    if findings['error']:
        for line_num, line in findings['error'][:30]:
            report += f"- Line {line_num}: `{line}`\n"
    else:
        report += "*No errors detected*\n"

    report += "\n---\n\n## IMPORT ERRORS\n\n"
    if findings['import_error']:
        for line_num, line in findings['import_error'][:10]:
            report += f"- Line {line_num}: `{line}`\n"
    else:
        report += "*No import errors*\n"

    report += "\n---\n\n## REVIVAL ATTEMPTS\n\n"
    if findings['revival']:
        for line_num, line in findings['revival'][:30]:
            report += f"- Line {line_num}: `{line}`\n"
    else:
        report += "*No revival attempts*\n"

    report += "\n---\n\n## CANNOT QUEUE / NOT IN REGISTRY\n\n"
    queue_issues = findings['cannot_queue'] + findings['not_in_registry']
    if queue_issues:
        queue_issues.sort(key=lambda x: x[0])
        for line_num, line in queue_issues[:30]:
            report += f"- Line {line_num}: `{line}`\n"
    else:
        report += "*No queue issues detected*\n"

    report += "\n---\n\n## RE-QUEUED SUSTAIN SPELLS (FIX WORKING)\n\n"
    if findings['re_queued']:
        for line_num, line in findings['re_queued'][:20]:
            report += f"- Line {line_num}: `{line}`\n"
    else:
        report += "*No sustain spells re-queued (fix may not be triggered yet)*\n"

    report += "\n---\n\n*Report generated by boot_monitor.py*\n"

    return report

if __name__ == "__main__":
    main()
