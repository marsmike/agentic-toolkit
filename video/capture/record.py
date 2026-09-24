#!/usr/bin/env python3
"""Record real terminal output as an asciicast v2 file.

Usage: record.py OUT.cast COLS ROWS -- COMMAND...
       record.py OUT.cast COLS ROWS --session COMMANDS.txt -- SHELL...

Runs COMMAND in a pseudo-terminal of COLS x ROWS with the caller's
environment, and writes every byte it prints with its time offset. The
command line itself goes in the header ("command"), so the video can show
the prompt without retyping anything. The exit status is the command's.

With --session, SHELL is an interactive shell whose prompt is "$ ": each
line of COMMANDS.txt is typed into it once the prompt is back, then `exit`.
Prompts and commands are the shell's own echo, so the recording is one
continuous session and the header has "session": true instead of a
command. The exit status is the shell's (that of the last command).
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

PROMPT = "$ "
QUIET_SECONDS = 0.5  # the prompt counts as back after this long without output


def main() -> int:
    args = sys.argv[1:]
    session = None
    if len(args) > 4 and args[3] == "--session":
        session = open(args[4], encoding="utf-8").read().splitlines()
        args = args[:3] + args[5:]
    if len(args) < 5 or args[3] != "--":
        print(__doc__, file=sys.stderr)
        return 2
    out, cols, rows, argv = args[0], int(args[1]), int(args[2]), args[4:]

    pid, fd = pty.fork()
    if pid == 0:
        os.execvp(argv[0], argv)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))

    start = time.monotonic()
    header = {"version": 2, "width": cols, "height": rows, "timestamp": int(time.time())}
    if session is not None:
        header["session"] = True
        to_type = [*session, "exit"]
    else:
        # `/bin/sh -c CMD` is recorded as CMD, the line the viewer would type.
        header["command"] = argv[2] if argv[:2] == ["/bin/sh", "-c"] else " ".join(argv)
        to_type = []
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    status = None
    tail = ""
    last_output = time.monotonic()
    with open(out, "w", encoding="utf-8") as f:
        f.write(json.dumps(header) + "\n")
        while True:
            ready, _, _ = select.select([fd], [], [], 0.1)
            if not ready:
                done, st = os.waitpid(pid, os.WNOHANG)
                if done:
                    status = st
                    break
                if to_type and tail.endswith(PROMPT) and time.monotonic() - last_output > QUIET_SECONDS:
                    os.write(fd, (to_type.pop(0) + "\n").encode())
                    tail = ""
                continue
            try:
                data = os.read(fd, 65536)
            except OSError:  # EIO: the child closed the terminal
                break
            if not data:
                break
            text = decoder.decode(data)
            if text:
                last_output = time.monotonic()
                tail = (tail + text)[-64:]
                f.write(json.dumps([round(last_output - start, 6), "o", text]) + "\n")
                sys.stdout.write(text)
                sys.stdout.flush()
    if status is None:
        _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


if __name__ == "__main__":
    sys.exit(main())
