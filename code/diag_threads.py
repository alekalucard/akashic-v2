"""Dump thread stacks of the running server to diagnose deadlock."""
import ctypes
import sys
import os

# Send SIGBREAK to the server process to trigger thread dump
# On Windows we can use ctypes to call GenerateConsoleCtrlEvent
# But easier: just connect via debugger

# Actually let's just use the approach of injecting code via PyInjector
# Simpler approach: write a script that connects via Win32 debug API

# Simplest approach: Use py-spy to profile
# Let's just run py-spy dump
SERVER_PID = 57064

os.system(f'py-spy dump --pid {SERVER_PID}')
