#!/usr/bin/env python3
"""Write the final screen text of each .cast as a plain .txt beside it.

Usage: cast_text.py CAST...

The .txt is what the terminal showed once the command finished, with the
prompt line `$ <command>` first: a small terminal emulator replays the
output at the recorded width, so spinners, progress counters and
cursor-positioned redraws end in their last state, and colours are dropped.
Soft-wrapped rows are joined, so each line is one logical line. It is the
verbatim source the storyboard quotes from (a session recording has no
prompt line added: its prompts are the shell's own); the .cast stays the source of
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


def screen_text(raw: str, width: int) -> str:
    # Rows are screen rows of `width` columns, as the terminal drew them:
    # printing past the last column wraps to a new row, and cursor moves
    # count wrapped rows (progress bars redraw by moving up that many).
    # Rows that are soft-wrap continuations are joined back on output, so
    # a transcript line is one logical line however wide it is.
    screen: list[list[str]] = [[]]
    wrapped: set[int] = set()
    row = col = 0

    def line() -> list[str]:
        while len(screen) <= row:
            screen.append([])
        return screen[row]

    for m in TOKEN.finditer(raw):
        tok = m.group(0)
        if tok == "\r":
            col = 0
        elif tok == "\n":
            row += 1
            col = 0
        elif tok == "\b":
            col = max(0, min(col, width - 1) - 1)
        elif m.group(2):
            params, final = m.group(1), m.group(2)
            if not re.fullmatch(r"[\d;]*", params):
                continue  # private modes (`?25l`, `>4m`, `<u`) change no text
            n = int(params.split(";")[0] or 0)
            if final == "G":
                col = min(max(0, n - 1), width - 1)
            elif final == "A":
                row = max(0, row - max(n, 1))
            elif final == "B":
                row += max(n, 1)
            elif final == "C":
                col = min(col + max(n, 1), width - 1)
            elif final == "D":
                col = max(0, min(col, width - 1) - max(n, 1))
            elif final == "K":
                cells = line()
                if n == 0:
                    del cells[col:]
                    if col == 0:
                        wrapped.discard(row)  # the row is redrawn from scratch
                elif n == 1:
                    cells[: col + 1] = [" "] * min(col + 1, len(cells))
                else:
                    cells.clear()
                    wrapped.discard(row)  # the row is redrawn from scratch
            # Colours, modes and everything else change no text.
        elif not tok.startswith("\x1b"):
            for ch in tok:
                if ch < " " and ch != "\t":
                    continue
                if col >= width:  # deferred autowrap, as xterm does
                    row += 1
                    col = 0
                    wrapped.add(row)
                cells = line()
                if col > len(cells):
                    cells.extend(" " * (col - len(cells)))
                if col == len(cells):
                    cells.append(ch)
                else:
                    cells[col] = ch
                col += 1

    logical: list[str] = []
    for i, cells in enumerate(screen):
        text = "".join(cells)
        if i in wrapped and logical:
            logical[-1] += text
        else:
            logical.append(text)
    return "\n".join(l.rstrip() for l in logical).strip("\n")


def convert(cast: Path) -> Path:
    rows = cast.read_text(encoding="utf-8").splitlines()
    header = json.loads(rows[0])
    raw = "".join(json.loads(r)[2] for r in rows[1:] if r.strip())
    txt = cast.with_suffix(".txt")
    # A session's prompts and commands are in its output already.
    prompt = "" if header.get("session") else f"$ {header['command']}\n"
    txt.write_text(f"{prompt}{screen_text(raw, header['width'])}\n", encoding="utf-8")
    return txt


if __name__ == "__main__":
    for name in sys.argv[1:]:
        print(convert(Path(name)))
