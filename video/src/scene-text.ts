// Parses a scene's composed-text cell, copied verbatim from the locked
// storyboard (src/storyboard.json), into what the scene shows. The cell's
// markup is the storyboard's own: parts separated by " / ", **heading**,
// "Label: *…*", "Caption: *…*" (whole scene) and "Caption N (a–b s): *…*"
// (absolute seconds). The text inside the markup is shown as is.
// No imports, so Node can test it directly.

export type Caption = { from: number; to: number; text: string }; // seconds from scene start
export type SceneText = { heading: string | null; lines: string[]; label: string | null; captions: Caption[] };

export const parseSceneText = (cell: string, start: number, end: number): SceneText => {
  const out: SceneText = { heading: null, lines: [], label: null, captions: [] };
  for (const part of cell.split(" / ")) {
    let m: RegExpMatchArray | null;
    if ((m = part.match(/^\*\*(.+)\*\*$/))) {
      if (out.heading === null && out.lines.length === 0) out.heading = m[1];
      else out.lines.push(m[1]);
    } else if ((m = part.match(/^Label: \*(.+)\*$/))) {
      out.label = m[1];
    } else if ((m = part.match(/^Caption: \*(.+)\*$/))) {
      out.captions.push({ from: 0, to: end - start, text: m[1] });
    } else if ((m = part.match(/^Caption \d+ \((\d+)–(\d+) s\): \*(.+)\*$/))) {
      out.captions.push({ from: Number(m[1]) - start, to: Number(m[2]) - start, text: m[3] });
    } else if (part.includes("*")) {
      throw new Error(`unrecognised markup in storyboard text: ${part}`);
    } else {
      out.lines.push(part);
    }
  }
  return out;
};
