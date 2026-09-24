// The video replays captures with src/cast.ts; the storyboard quotes the
// .txt transcripts written by capture/cast_text.py. Both must show the same
// screen, or a scene would differ from the text it was approved as.
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

import { parseCast, screenAt, screenLines, transcript } from "../src/cast.ts";

const capture = join(import.meta.dirname, "..", "capture");
const casts = readdirSync(capture, { recursive: true, encoding: "utf8" })
  .filter((f) => f.endsWith(".cast"))
  .sort();

test("there are captures to check", () => {
  assert.ok(casts.length >= 11, `found ${casts.length}`);
});

for (const name of casts) {
  test(`${name}: replay matches its .txt transcript`, () => {
    const cast = parseCast(readFileSync(join(capture, name), "utf8"));
    const txt = readFileSync(join(capture, name.replace(/\.cast$/, ".txt")), "utf8");
    assert.equal(transcript(cast), txt);
  });
}

test("carriage-return redraws keep only the last state", () => {
  assert.deepEqual(screenLines("50%\r100% done\r\n"), ["100% done"]);
});

test("cursor-column and cursor-up redraws overwrite in place", () => {
  // What `claude plugin marketplace add` prints: the success line is drawn
  // over the progress line, reusing characters that already match.
  const raw = "Adding\x1b[8Gmarketplace…\r\n\x1b[1A✔ Successfully \x1b[17Gdded\x1b[22Gmarketplace\r\n";
  assert.deepEqual(screenLines(raw), ["✔ Successfully added marketplace"]);
});

test("colours and private modes change no text", () => {
  assert.deepEqual(screenLines("\x1b[?25l\x1b[1mbold\x1b[0m \x1b[>4m\x1b[<uok\r\n"), ["bold ok"]);
});

test("screenAt shows only output recorded by then", () => {
  const cast = parseCast(
    ['{"version":2,"width":80,"height":24,"command":"x"}', '[0.5,"o","one\\r\\n"]', '[2.0,"o","two\\r\\n"]'].join("\n"),
  );
  assert.deepEqual(screenAt(cast, 1), ["one"]);
  assert.deepEqual(screenAt(cast, 2), ["one", "two"]);
});
