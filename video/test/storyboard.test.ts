// Holds what the render depends on together without the (out-of-repo)
// storyboard: scripts/check_storyboard.py compares against the locked file.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

const video = join(import.meta.dirname, "..");
const board = JSON.parse(readFileSync(join(video, "src", "storyboard.json"), "utf8"));
const music = JSON.parse(readFileSync(join(video, "music.json"), "utf8"));
const session = readFileSync(join(video, board.capture.replace(/\.cast$/, ".txt")), "utf8").split("\n");

test("11 contiguous scenes, 118 s, inside 90-120 s", () => {
  assert.equal(board.scenes.length, 11);
  board.scenes.forEach((s: { n: number; start: number; end: number }, i: number) => {
    assert.equal(s.n, i + 1);
    if (i) assert.equal(s.start, board.scenes[i - 1].end);
  });
  const total = board.scenes.at(-1).end;
  assert.equal(total, 118);
});

test("terminal scenes point at real session lines, in order, not overlapping", () => {
  let last = 0;
  for (const s of board.scenes.filter((x: { terminal?: unknown }) => x.terminal)) {
    const [first, end] = s.terminal.lines;
    assert.ok(first > last && end >= first && end <= session.length, `scene ${s.n}`);
    last = end;
    if (s.terminal.crop) assert.ok(session[s.terminal.crop.line - 1].includes(s.terminal.crop.endsWith));
  }
});

test("MUSIC.md documents the same file music.json fetches", () => {
  const doc = readFileSync(join(video, "MUSIC.md"), "utf8");
  assert.ok(doc.includes(music.sha256));
  assert.ok(doc.includes(music.url));
  assert.match(music.sha256, /^[0-9a-f]{64}$/);
  assert.ok(music.file.startsWith("public/music/"));
});
