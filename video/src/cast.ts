// Replays an asciicast v2 recording (capture/record.py) into screen text.
// Same rules as capture/cast_text.py; test/cast.test.ts holds the two equal
// on every committed capture. No imports, so Node can test it directly.

export type Cast = {
  width: number;
  height: number;
  command: string; // "" for a session: prompts are in the output
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
  return { width: header.width, height: header.height, command: header.session ? "" : header.command, events };
};

export const castDuration = (cast: Cast): number =>
  cast.events.length ? cast.events[cast.events.length - 1][0] : 0;

const TOKEN =
  /\x1b\[([0-?]*)[ -/]*([@-~])|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][0-9A-Za-z]|\x1b[=>78DEM]|[\r\n\b]|[^\x1b\r\n\b]+/g;

// Final screen lines after replaying `raw` on a terminal `width` columns
// wide. Printing past the last column wraps to a new row and cursor moves
// count wrapped rows (progress bars redraw by moving up that many); rows
// that are soft-wrap continuations are joined back, so each returned line
// is one logical line.
export const screenLines = (raw: string, width: number): string[] => {
  const screen: string[][] = [[]];
  const wrapped = new Set<number>();
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
      col = Math.max(0, Math.min(col, width - 1) - 1);
    } else if (m[2] !== undefined) {
      const params = m[1];
      if (!/^[\d;]*$/.test(params)) continue; // private modes change no text
      const n = parseInt(params.split(";")[0] || "0", 10);
      const final = m[2];
      if (final === "G") col = Math.min(Math.max(0, n - 1), width - 1);
      else if (final === "A") row = Math.max(0, row - Math.max(n, 1));
      else if (final === "B") row += Math.max(n, 1);
      else if (final === "C") col = Math.min(col + Math.max(n, 1), width - 1);
      else if (final === "D") col = Math.max(0, Math.min(col, width - 1) - Math.max(n, 1));
      else if (final === "K") {
        const cells = line();
        if (n === 0) {
          cells.splice(col);
          if (col === 0) wrapped.delete(row); // the row is redrawn from scratch
        } else if (n === 1) {
          cells.fill(" ", 0, Math.min(col + 1, cells.length));
        } else {
          cells.length = 0;
          wrapped.delete(row);
        }
      }
    } else if (!tok.startsWith("\x1b")) {
      for (const ch of tok) {
        if (ch < " " && ch !== "\t") continue;
        if (col >= width) {
          // deferred autowrap, as xterm does
          row += 1;
          col = 0;
          wrapped.add(row);
        }
        const cells = line();
        while (cells.length < col) cells.push(" ");
        cells[col] = ch;
        col += 1;
      }
    }
  }
  const logical: string[] = [];
  screen.forEach((cells, i) => {
    const text = cells.join("");
    if (wrapped.has(i) && logical.length) logical[logical.length - 1] += text;
    else logical.push(text);
  });
  const lines = logical.map((l) => l.trimEnd());
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
    cast.width,
  );

// A single-command recording's prompt line (none for a session).
export const promptLines = (cast: Cast): string[] => (cast.command ? [`$ ${cast.command}`] : []);

// What the .txt transcript holds: the prompt line, then the final screen.
export const transcript = (cast: Cast): string =>
  [...promptLines(cast), ...screenLines(cast.events.map((e) => e[1]).join(""), cast.width)].join("\n") + "\n";
