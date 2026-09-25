import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

import { parseSceneText } from "../src/scene-text.ts";

const board = JSON.parse(readFileSync(join(import.meta.dirname, "..", "src", "storyboard.json"), "utf8"));

test("every scene's text parses, and nothing but markup is dropped", () => {
  for (const s of board.scenes) {
    const t = parseSceneText(s.text, s.start, s.end);
    const shown = [t.heading, t.label, ...t.lines, ...t.captions.map((c) => c.text)].filter(Boolean).join("");
    const markup = s.text.replace(/Caption \d+ \(\d+–\d+ s\): |Caption: |Label: | \/ |\*/g, "");
    assert.equal(shown.length, markup.length, `scene ${s.n}`);
  }
});

test("scene 4: label and three timed captions, scene-relative", () => {
  const s = board.scenes.find((x: { n: number }) => x.n === 4);
  const t = parseSceneText(s.text, s.start, s.end);
  assert.equal(t.label, "From source · bundled example vault");
  assert.deepEqual(
    t.captions.map((c) => [c.from, c.to]),
    [
      [0, 4],
      [4, 9],
      [9, 16],
    ],
  );
  assert.equal(t.captions[2].text, "Engine downloads are not publisher-verified.");
});

test("scene 10: heading and the three numbered lines", () => {
  const s = board.scenes.find((x: { n: number }) => x.n === 10);
  const t = parseSceneText(s.text, s.start, s.end);
  assert.equal(t.heading, "Why it is different:");
  assert.deepEqual(t.lines, [
    "1. Your own notes are the platform, and they stay yours.",
    "2. It suggests links but never applies them automatically.",
    "3. This demo runs locally, without an account or API key.",
  ]);
});

test("whole-scene caption spans the scene", () => {
  const s = board.scenes.find((x: { n: number }) => x.n === 9);
  assert.deepEqual(parseSceneText(s.text, s.start, s.end).captions, [
    { from: 0, to: 8, text: "One more command adds its plugin marketplace to Claude Code." },
  ]);
});
