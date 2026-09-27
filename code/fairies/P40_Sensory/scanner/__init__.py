# Package marker -- DELIBERATELY NOT EMPTY.
#
# 2026-08-27 (Nous + Ace): an EMPTY __init__.py is not safe in this process. A/B-proven
# on fairies/P00_Autonomic/nervous_system/health/__init__.py -- empty killed the tracer
# daemon every boot, 986 bytes of comment brought it ONLINE, emptying it killed it again.
#
# Cause: inside her LIVE process a literal b"" fails to compile, via the GENUINE
# builtins.compile -- 'source code string cannot contain null bytes'. CPython's check is
# strlen(buf) != size; for an empty source that is 0 != 0 and should pass. b"" is a
# process-wide SINGLETON, so if a C extension writes out of bounds and clobbers its
# terminating NUL, EVERY empty-source compile in the process fails from then on.
# Files on disk are clean; a fresh interpreter compiles them fine. Not yet root-caused.
#
# Only packages imported AFTER the corruption lands are hit -- health/ is imported late,
# from the deferred tracer thread, which is why it was the only casualty. That is timing
# luck, not safety. One byte removes the whole class.
# See state/tracer_nul_capture.txt and the boot probe in TracerDaemonFairy/fairy.py.
