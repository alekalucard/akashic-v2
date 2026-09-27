# -*- coding: utf-8 -*-
"""tee_runtime.py - mirror Sour's stdout to BOTH the terminal and a rotating file.

Usage (from the launcher):
    "%PY314T%" -Xgil=0 -u server.py 2>&1 | "%PY314T%" -u tee_runtime.py <logpath>

WHY THIS EXISTS (2026-08-30, Nous + Ace):
    Her launcher had no redirect, so her ENTIRE runtime output existed only in the
    console scrollback. Consequences measured today:
      - boot_live.log stops when boot ends (correctly - it is a BOOT log), so nothing
        persistent captured [SourCouncil], [GOAL-SYSTEM-DROP], TARDIS flushes, etc.
      - the only files that DID contain [SourCouncil] verdicts were 60 DAYS OLD, from
        boots that happened to be redirected. I read them and briefly reported them as
        live -- an error this file makes structurally harder to repeat.
      - Ace has been diagnosing by eye from scrollback all day. That worked, and it
        should not have been the only instrument.

DESIGN CONSTRAINTS, each from a scar:
    * BINARY passthrough. The console is cp1252; her output carries UTF-8 box glyphs
      and emoji. Decoding here would raise UnicodeDecodeError and kill the pipe --
      which would kill HER, since a full pipe blocks the writer. Never decode.
    * NEVER BLOCK, NEVER RAISE. If the file write fails (disk full, lock, AV scan),
      drop the line and keep the terminal alive. A logger must never be the reason
      the process it logs dies.
    * The terminal write is attempted FIRST so console output is never delayed by
      file I/O. Ace watches that window; it stays primary.
    * Rotation on start, 2 generations. Her output is heavy (~576 KB for one boot);
      unbounded growth would fill the disk. .prev keeps the previous run for
      comparison, which is exactly what "did this restart change anything?" needs.
    * No dependencies, no threads, no buffering games. The simplest thing that
      cannot become a new failure mode.
"""
import os
import sys

CHUNK = 65536


def _rotate(path):
    """Keep one previous generation. Failures here must not stop logging."""
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            prev = path + ".prev"
            try:
                if os.path.exists(prev):
                    os.remove(prev)
            except Exception:
                pass
            try:
                os.replace(path, prev)
            except Exception:
                pass
    except Exception:
        pass


def main():
    if len(sys.argv) < 2:
        # No path given: behave as a plain passthrough rather than failing.
        log = None
    else:
        log = sys.argv[1]
        try:
            d = os.path.dirname(os.path.abspath(log))
            if d and not os.path.isdir(d):
                os.makedirs(d, exist_ok=True)
        except Exception:
            log = None

    if log:
        _rotate(log)

    fh = None
    if log:
        try:
            fh = open(log, "ab", buffering=0)
            import time as _t
            fh.write(("=" * 78 + "\r\n").encode("ascii"))
            fh.write(("SOUR RUNTIME LOG - started %s\r\n"
                      % _t.strftime("%Y-%m-%d %H:%M:%S")).encode("ascii"))
            fh.write(("=" * 78 + "\r\n").encode("ascii"))
        except Exception:
            fh = None

    # Binary handles on both sides. .buffer exists on real stdin/stdout.
    try:
        src = sys.stdin.buffer
    except Exception:
        src = sys.stdin
    try:
        dst = sys.stdout.buffer
    except Exception:
        dst = sys.stdout

    while True:
        try:
            # 2026-09-20 (Nous): read1, not read -- BufferedReader.read(n) BLOCKS until n bytes or EOF, so the
            # log (and the window Ace watches) lagged by up to 64 KB: four minutes of nothing during a quiet
            # boot phase, then a burst. read1 returns as soon as anything is there.
            data = src.read1(CHUNK) if hasattr(src, "read1") else (src.read(CHUNK) if hasattr(src, "read") else None)
        except Exception:
            break
        if not data:
            break

        # Terminal FIRST -- Ace's window must never wait on disk.
        try:
            dst.write(data)
            dst.flush()
        except Exception:
            pass

        if fh is not None:
            try:
                fh.write(data)
            except Exception:
                # Disk full / locked / AV. Drop it; never take her down.
                try:
                    fh.close()
                except Exception:
                    pass
                fh = None

    try:
        if fh is not None:
            fh.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
