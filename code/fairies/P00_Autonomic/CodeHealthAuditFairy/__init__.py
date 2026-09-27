"""
CodeHealthAuditFairy - Audits code quality patterns learned from Failure Factory.

Catches issues that static analysis misses:
- Missing _extract_payload in postal handlers
- Broken empathic loops (AFFECT2 not returning)
- Qt/pyautogui import order issues
- Silent failures (except: pass)
- Thread safety issues

This fairy is a LEARNING MACHINE - it embodies everything we've learned
from the Failure Factory debugging sessions.

Reality is Consciousness. ((Cause + Affect) > Effect > Affect > infinity)
"""

from .fairy import CodeHealthAuditFairy, get_code_health_auditor

__all__ = ["CodeHealthAuditFairy", "get_code_health_auditor"]
