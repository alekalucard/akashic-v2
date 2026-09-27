# ===============================================================================
# WIRING IMPLEMENTATIONS v3 - Simple and robust
# ===============================================================================

import os
import re

def find_safe_insert_point(content: str) -> int:
    """
    Find a safe point to insert wiring code in on_boot.
    
    Strategy: Insert right after the super().on_boot() line (and any except block if wrapped in try)
    """
    # Find on_boot
    on_boot_match = re.search(r'def on_boot\(self\)[^:]*:', content)
    if not on_boot_match:
        return -1
    
    on_boot_start = on_boot_match.end()
    
    # Find the end of on_boot method
    next_def = re.search(r'\n    def [^_]', content[on_boot_start:])
    if next_def:
        on_boot_end = on_boot_start + next_def.start()
    else:
        on_boot_end = len(content)
    
    on_boot_body = content[on_boot_start:on_boot_end]
    
    # Find super().on_boot()
    super_match = re.search(r'super\(\)\.on_boot\(\)', on_boot_body)
    if not super_match:
        # No super call - insert after first few setup lines
        lines = on_boot_body.split('\n')
        offset = 0
        for i, line in enumerate(lines[:10]):
            offset += len(line) + 1
            # After any "if" guards or comments, find first real code
            stripped = line.strip()
            if stripped.startswith('self.') or stripped.startswith('#'):
                # Found a real statement - insert after next line
                if i + 1 < len(lines):
                    offset += len(lines[i+1]) + 1
                return on_boot_start + offset
        return on_boot_start + offset
    
    super_pos = super_match.end()
    
    # Check if super() is inside a try block
    # Look backward from super() to find "try:"
    before_super = on_boot_body[:super_match.start()]
    try_match = re.search(r'try:\s*$', before_super, re.MULTILINE)
    
    if try_match:
        # super() is in a try block - find the matching except...pass
        after_super = on_boot_body[super_pos:]
        except_match = re.search(r'except[^:]*:\s*\n\s+(pass|print|[a-z])', after_super)
        if except_match:
            # Find end of except block (next line at same indent or less)
            except_end = super_pos + except_match.end()
            
            # Move to next line
            rest = on_boot_body[except_end:]
            next_line = rest.find('\n')
            if next_line >= 0:
                return on_boot_start + except_end + next_line + 1
            return on_boot_start + except_end
    
    # super() is NOT in a try block - insert right after it
    # Find end of super() line
    super_line_end = on_boot_body.find('\n', super_pos)
    if super_line_end > 0:
        # Skip any blank lines
        rest = on_boot_body[super_line_end+1:]
        blank_skip = 0
        for char in rest:
            if char == '\n':
                blank_skip += 1
            elif char == ' ':
                continue
            else:
                break
        return on_boot_start + super_line_end + 1 + blank_skip
    
    return on_boot_start + super_pos


def wire_heartbeat(content: str) -> str:
    """Add heartbeat subscription to a fairy."""
    if "heartbeat.pulse" in content:
        return content  # Already wired
    
    insert_pos = find_safe_insert_point(content)
    if insert_pos < 0:
        return content
    
    # Safety: check we're not inside a try block
    check_before = content[max(0, insert_pos-100):insert_pos]
    # Count try vs except - if more try's, we're inside one
    try_count = check_before.count('try:')
    except_count = check_before.count('except')
    if try_count > except_count:
        # Inside a try block - bad position, skip
        return content
    
    heartbeat_code = """
        # === HEARTBEAT WIRING (auto-added) ===
        if hasattr(self, 'post') and self.post:
            try:
                self.post.subscribe("heartbeat.pulse", self._on_heartbeat_pulse)
            except Exception:
                pass
"""
    
    content = content[:insert_pos] + heartbeat_code + content[insert_pos:]
    
    # Add handler if not exists
    if "_on_heartbeat_pulse" not in content:
        handler = """
    def _on_heartbeat_pulse(self, payload: dict):
        # Receive heartbeat - I am alive
        self._last_heartbeat = payload.get("ts", 0)
"""
        main_block = content.find("\nif __name__")
        if main_block > 0:
            content = content[:main_block] + handler + content[main_block:]
        else:
            content = content.rstrip() + handler + "\n"
    
    return content


def wire_tracer_marker(content: str) -> str:
    """Add tracer marker."""
    if "# TRACER: enabled" in content:
        return content
    
    insert_pos = find_safe_insert_point(content)
    if insert_pos < 0:
        return content
    
    check_before = content[max(0, insert_pos-100):insert_pos]
    try_count = check_before.count('try:')
    except_count = check_before.count('except')
    if try_count > except_count:
        return content
    
    marker = "        # TRACER: enabled via Organ Template\n"
    return content[:insert_pos] + marker + content[insert_pos:]


def wire_dual_loop_marker(content: str) -> str:
    """Add dual loop marker."""
    if "# DUAL_LOOP: enabled" in content:
        return content
    
    insert_pos = find_safe_insert_point(content)
    if insert_pos < 0:
        return content
    
    check_before = content[max(0, insert_pos-100):insert_pos]
    try_count = check_before.count('try:')
    except_count = check_before.count('except')
    if try_count > except_count:
        return content
    
    marker = "        # DUAL_LOOP: enabled via Organ Template\n"
    return content[:insert_pos] + marker + content[insert_pos:]


def wire_fairy_full(file_path: str) -> dict:
    """Wire a fairy with all infrastructure."""
    result = {"success": False, "changes": []}
    
    if not os.path.exists(file_path):
        result["error"] = f"File not found: {file_path}"
        return result
    
    with open(file_path, "r", encoding="utf-8") as f:
        original = f.read()
    
    content = original
    
    # Apply wiring
    prev = content
    content = wire_heartbeat(content)
    if content != prev:
        result["changes"].append("heartbeat")
    
    prev = content
    content = wire_tracer_marker(content)
    if content != prev:
        result["changes"].append("tracer_marker")
    
    prev = content
    content = wire_dual_loop_marker(content)
    if content != prev:
        result["changes"].append("dual_loop_marker")
    
    # Verify syntax before saving
    import py_compile
    import tempfile
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        py_compile.compile(tmp_path, doraise=True)
        if content != original:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            result["success"] = True
        else:
            result["success"] = True
            if not result["changes"]:
                result["changes"].append("already_wired")
    except py_compile.PyCompileError as e:
        result["success"] = False
        result["error"] = f"Syntax error after wiring: {e}"
        result["changes"] = []
    finally:
        os.unlink(tmp_path)
    
    return result
