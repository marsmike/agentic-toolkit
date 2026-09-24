// Replays an asciicast v2 recording (capture/record.py) into screen text.
// Same rules as capture/cast_text.py; test/cast.test.ts holds the two equal
// on every committed capture. No imports, so Node can test it directly.

export type Cast = {
  width: number;
  height: number;
  command: string;
  events: [number, string][]; // [seconds, output]
};

export const parseCast = (source: string): Cast => {
  const rows = source.split("\n").filter((r) => r.trim());
  const header = JSON.parse(rows[0]);
  const events = rows
    .slice(1)
    .map((r) => JSON.parse(r) as [number, string, string])
    .filter((e) => e[1] === "o")
    .map((e): [number, string] => [e[0], e[2]]);
  return { width: header.width, height: header.height, command: header.command, events };
};

export const castDuration = (cast: Cast): number =>
  cast.events.length ? cast.events[cast.events.length - 1][0] : 0;

const TOKEN =
  /\x1b\[([0-?]*)[ -/]*([@-~])|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][0-9A-Za-z]|\x1b[=>78DEM]|[\r\n\b]|[^\x1b\r\n\b]+/g;

// Final screen lines (unwrapped) after replaying `raw`.
export const screenLines = (raw: string): string[] => {
  const screen: string[][] = [[]];
  let row = 0;
  let col = 0;
  const line = (): string[] => {
    while (screen.length <= row) screen.push([]);
    return screen[row];
  };
  for (const m of raw.matchAll(TOKEN)) {
    const tok = m[0];
    if (tok === "\r") {
      col = 0;
    } else if (tok === "\n") {
      row += 1;
      col = 0;
    } else if (tok === "\b") {
      col = Math.max(0, col - 1);
    } else if (m[2] !== undefined) {
      const params = m[1];
      if (!/^[\d;]*$/.test(params)) continue; // private modes change no text
      const n = parseInt(params.split(";")[0] || "0", 10);
      const final = m[2];
      if (final === "G") col = Math.max(0, n - 1);
      else if (final === "A") row = Math.max(0, row - Math.max(n, 1));
      else if (final === "B") row += Math.max(n, 1);
      else if (final === "C") col += Math.max(n, 1);
      else if (final === "D") col = Math.max(0, col - Math.max(n, 1));
      else if (final === "K") {
        const l = line();
        if (n === 0) l.splice(col);
        else if (n === 1) l.fill(" ", 0, Math.min(col, l.length));
        else l.length = 0;
      }
    } else if (!tok.startsWith("\x1b")) {
      const l = line();
      for (const ch of tok) {
        if (ch < " " && ch !== "\t") continue;
        while (l.length < col) l.push(" ");
        l[col] = ch;
        col += 1;
      }
    }
  }
  const lines = screen.map((l) => l.join("").trimEnd());
  while (lines.length && lines[0] === "") lines.shift();
  while (lines.length && lines[lines.length - 1] === "") lines.pop();
  return lines;
};

// Screen text after the output recorded up to `seconds`.
export const screenAt = (cast: Cast, seconds: number): string[] =>
  screenLines(
    cast.events
      .filter((e) => e[0] <= seconds)
      .map((e) => e[1])
      .join(""),
  );

// What the .txt transcript holds: the prompt line, then the final screen.
export const transcript = (cast: Cast): string =>
  [`$ ${cast.command}`, ...screenLines(cast.events.map((e) => e[1]).join(""))].join("\n") + "\n";
