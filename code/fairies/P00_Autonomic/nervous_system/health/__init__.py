# Package marker -- DELIBERATELY NOT EMPTY.
#
# 2026-08-27 (Nous + Ace): every boot, importing
#   fairies.P00_Autonomic.nervous_system.health.tracer_daemon_core
# died with 'SyntaxError: source code string cannot contain null bytes', which took
# the TracerDaemonFairy engine down -- her error-catching daemon, dark for months.
#
# Instrumented at the failure point inside her own process: a chain walk named THIS
# package as the level that raises, and a live re-compile showed the ZERO-BYTE
# __init__.py files failing while the non-empty ones in the same loop passed.
# The files are clean on disk (0 NUL bytes) and compile fine in a standalone 3.14.7
# free-threaded interpreter, so the trigger is something about her live process --
# NOT yet understood. This is a WORKAROUND, not a root-cause fix.
#
# The sibling nervous_system/__init__.py is left EMPTY on purpose, as the control.
# Do not 'tidy' either file without reading state/tracer_nul_capture.txt first.
