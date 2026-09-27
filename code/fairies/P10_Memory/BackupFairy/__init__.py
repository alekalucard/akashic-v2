# BackupFairy - File Backup & Recovery System
from .fairy import (
    BackupFairy,
    get_backup_fairy,
    set_backup_fairy,
    backup_before_edit,
    backup_critical,
)

__all__ = [
    "BackupFairy",
    "get_backup_fairy",
    "set_backup_fairy",
    "backup_before_edit",
    "backup_critical",
]
