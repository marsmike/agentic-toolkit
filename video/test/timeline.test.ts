// Holds the v2 explainer's inputs together: the timeline both the picture and the music read,
// the real graph it animates, and the capture every number and name on screen comes from.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

const video = join(import.meta.dirname, "..");
const read = (p: string) => readFileSync(join(video, p), "utf8");
const timeline = JSON.parse(read("src/timeline.json"));
const graph = JSON.parse(read("src/graph.json"));
const music = JSON.parse(read("music.json"));
const session = read("capture/from-source-main-0dd21a7/session.txt");

test("scenes are contiguous, start on a bar, and run 90-120 s", () => {
  const bar = (4 * 60) / timeline.bpm;
  timeline.scenes.forEach((s: { start: number; end: number }, i: number) => {
    assert.ok(s.end > s.start);
    assert.equal(s.start % bar, 0, `scene ${i} starts off the bar grid`);
    if (i) assert.equal(s.start, timeline.scenes[i - 1].end);
  });
  assert.equal(timeline.scenes.at(-1).end, timeline.total);
  assert.ok(timeline.total >= 90 && timeline.total <= 120, `${timeline.total} s`);
});

test("one short label per scene: words stay few", () => {
  for (const s of timeline.scenes) {
    assert.ok(s.label.split(" ").length <= 6, s.label);
    assert.ok(s.sub.length <= 90, s.sub);
  }
});

test("every cue falls inside the film and in time order", () => {
  const at = timeline.cues.map((c: { at: number }) => c.at);
  assert.deepEqual(at, [...at].sort((a, b) => a - b));
  assert.ok(at[0] > 0 && at.at(-1) < timeline.total);
});

test("the graph is the one the recorded demo reports", () => {
  const m = session.match(/nodes=(\d+) edges=(\d+)/);
  assert.ok(m);
  assert.equal(graph.stats.nodes, Number(m[1]));
  assert.equal(graph.stats.edges, Number(m[2]));
  assert.equal(graph.nodes.length, graph.stats.nodes);
});

test("search hits, their scores and the INFERRED pairs are the recorded ones", () => {
  for (const h of graph.hits) {
    assert.ok(session.includes(`${h.score}  `) && session.includes(`${graph.nodes[h.node].title}.md`), h.score);
  }
  for (const p of graph.inferred) {
    const line = session.split("\n").find((l: string) => l.includes(p.score) && l.includes("[INFERRED]"));
    assert.ok(line?.includes(`${graph.nodes[p.a].title}.md`) && line.includes(`${graph.nodes[p.b].title}.md`), p.score);
  }
});

test("the music is generated from the same timeline and documented", () => {
  assert.equal(music.timeline, "src/timeline.json");
  assert.ok(music.file.startsWith("public/music/"));
  const doc = read("MUSIC.md");
  assert.ok(doc.includes(music.generator) && doc.includes(music.file));
});
