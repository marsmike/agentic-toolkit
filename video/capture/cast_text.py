#!/usr/bin/env python3
"""Write the final screen text of each .cast as a plain .txt beside it.

Usage: cast_text.py CAST...

The .txt is what the terminal showed once the command finished, with the
prompt line `$ <command>` first: a small terminal emulator replays the
output, so spinners, progress counters and cursor-positioned redraws end in
their last state, and colours are dropped. Lines are not wrapped. It is the
verbatim source the storyboard quotes from; the .cast stays the source of
timing.
"""
import json
import re
import sys
from pathlib import Path

TOKEN = re.compile(
    r"\x1b\[([0-?]*)[ -/]*([@-~])"      # CSI: params, final byte
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"  # OSC (titles, links)
    r"|\x1b[()][0-9A-Za-z]|\x1b[=>78DEM]"  # charset and 2-byte escapes
    r"|[\r\n\b]"
    r"|[^\x1b\r\n\b]+"
)


def screen_text(raw: str) -> str:
    screen: list[list[str]] = [[]]
    row = col = 0
    for m in TOKEN.finditer(raw):
        tok = m.group(0)
        if tok == "\r":
            col = 0
        elif tok == "\n":
            row += 1
            col = 0
        elif tok == "\b":
            col = max(0, col - 1)
        elif m.group(2):
            params, final = m.group(1), m.group(2)
            if not re.fullmatch(r"[\d;]*", params):
                continue  # private modes (`?25l`, `>4m`, `<u`) change no text
            n = int(params.split(";")[0] or 0)
            if final == "G":
                col = max(0, n - 1)
            elif final == "A":
                row = max(0, row - max(n, 1))
            elif final == "B":
                row += max(n, 1)
            elif final == "C":
                col += max(n, 1)
            elif final == "D":
                col = max(0, col - max(n, 1))
            elif final == "K":
                while len(screen) <= row:
                    screen.append([])
                line = screen[row]
                if n == 0:
                    del line[col:]
                elif n == 1:
                    line[:col] = [" "] * min(col, len(line))
                else:
                    line.clear()
            # Colours, modes and everything else change no text.
        elif not tok.startswith("\x1b"):
            while len(screen) <= row:
                screen.append([])
            line = screen[row]
            for ch in tok:
                if ch < " " and ch != "\t":
                    continue
                if col > len(line):
                    line.extend(" " * (col - len(line)))
                if col == len(line):
                    line.append(ch)
                else:
                    line[col] = ch
                col += 1
    return "\n".join("".join(line).rstrip() for line in screen).strip("\n")


def convert(cast: Path) -> Path:
    rows = cast.read_text(encoding="utf-8").splitlines()
    header = json.loads(rows[0])
    raw = "".join(json.loads(r)[2] for r in rows[1:] if r.strip())
    txt = cast.with_suffix(".txt")
    txt.write_text(f"$ {header['command']}\n{screen_text(raw)}\n", encoding="utf-8")
    return txt


if __name__ == "__main__":
    for name in sys.argv[1:]:
        print(convert(Path(name)))
