#!/usr/bin/env python3
"""Record one command's real terminal output as an asciicast v2 file.

Usage: record.py OUT.cast COLS ROWS -- COMMAND...

Runs COMMAND in a pseudo-terminal of COLS x ROWS with the caller's
environment, and writes every byte it prints with its time offset. The
command line itself goes in the header ("command"), so the video can show
the prompt without retyping anything. The exit status is the command's.
Stdlib only: no asciinema needed.
"""
import codecs
import fcntl
import json
import os
import pty
import select
import struct
import sys
import termios
import time


def main() -> int:
    if len(sys.argv) < 6 or sys.argv[4] != "--":
        print(__doc__, file=sys.stderr)
        return 2
    out, cols, rows, argv = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[5:]

    pid, fd = pty.fork()
    if pid == 0:
        os.execvp(argv[0], argv)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    start = time.monotonic()
    header = {
        "version": 2,
        "width": cols,
        "height": rows,
        "timestamp": int(time.time()),
        # `/bin/sh -c CMD` is recorded as CMD, the line the viewer would type.
        "command": argv[2] if argv[:2] == ["/bin/sh", "-c"] else " ".join(argv),
    }
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    status = None
    with open(out, "w", encoding="utf-8") as f:
        f.write(json.dumps(header) + "\n")
        while True:
            ready, _, _ = select.select([fd], [], [], 0.5)
            if not ready:
                done, st = os.waitpid(pid, os.WNOHANG)
                if done:
                    status = st
                    break
                continue
            try:
                data = os.read(fd, 65536)
            except OSError:  # EIO: the child closed the terminal
                break
            if not data:
                break
            text = decoder.decode(data)
            if text:
                f.write(json.dumps([round(time.monotonic() - start, 6), "o", text]) + "\n")
                sys.stdout.write(text)
                sys.stdout.flush()
    if status is None:
        _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


if __name__ == "__main__":
    sys.exit(main())
