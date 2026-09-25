import React from "react";
import { AbsoluteFill, Audio, Easing, interpolate, staticFile, useCurrentFrame } from "remotion";

import sessionSource from "../capture/from-source-main-0dd21a7/session.cast";
import music from "../music.json";
import { parseCast, screenLines } from "./cast";
import graph from "./graph.json";
import timeline from "./timeline.json";

// The explainer, v2: one picture that keeps moving. The example vault's real link graph
// (src/graph.json, from gaiafield) stays on screen the whole time; a camera glides over it and
// each scene fades its layer in over the last one, so nothing ever cuts. Words are one label per
// scene; the concepts are shown, not written. Every search score, count, note name and terminal
// line comes from the recorded session the old cut replayed (capture/from-source-main-0dd21a7).

export const FPS = 30;
export const TOTAL_SECONDS = timeline.total;

type SceneId = (typeof timeline.scenes)[number]["id"];
const SCENE = Object.fromEntries(timeline.scenes.map((s) => [s.id, s])) as Record<SceneId, (typeof timeline.scenes)[number]>;
const CUE = timeline.cues.map((c) => c.at);
const CF = timeline.crossfade;

const session = parseCast(sessionSource);
const SESSION = screenLines(session.events.map((e) => e[1]).join(""), session.width);

const W = 1920;
const H = 1080;
const C = {
  bg: "#0a0e1c",
  bg2: "#141a33",
  ink: "#eef1ff",
  dim: "#8d94b8",
  line: "#6d78b8",
  label: "#6d3fe0",
  labelSub: "#10142a",
  accent: "#ffcf5c",
  inferred: "#ff7ab6",
};
const GROUP: Record<string, string> = {
  Concepts: "#9b87ff",
  Guides: "#2fd4c0",
  Tools: "#ffb547",
  "field-guide": "#ff7ab6",
  "home-lab-migration": "#ff7ab6",
  "03_Areas": "#5fb0ff",
};
const DISPLAY = '"DIN Condensed", "Oswald", "Arial Narrow", sans-serif';
const SANS = '-apple-system, "SF Pro Display", "Helvetica Neue", Helvetica, Arial, sans-serif';
const MONO = 'Menlo, "DejaVu Sans Mono", monospace';

// ---------------------------------------------------------------- time helpers

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const smooth = Easing.bezier(0.45, 0, 0.25, 1);
const ramp = (t: number, a: number, b: number, from = 0, to = 1, easing = smooth) =>
  interpolate(t, [a, b], [from, to], { ...clamp, easing });
/** 0 -> 1 -> 0 around a scene, with half a crossfade either side of its edges. */
const presence = (t: number, id: SceneId) => {
  const s = SCENE[id];
  return Math.min(ramp(t, s.start - CF / 2, s.start + CF / 2), 1 - ramp(t, s.end - CF / 2, s.end + CF / 2));
};
const useT = () => useCurrentFrame() / FPS;

// ---------------------------------------------------------------- graph geometry

// The layout has a dense core and a few far notes; a radial power curve opens the core up.
const SPREAD = 800;
const spread = (x: number, y: number) => {
  const r = Math.hypot(x, y / 0.62) || 1;
  const f = Math.pow(r, 0.55) / r;
  return { gx: x * f * SPREAD, gy: y * f * SPREAD * 0.62 };
};
const nodes = graph.nodes.map((n, i) => ({ ...n, i, ...spread(n.x, n.y), color: GROUP[n.group] ?? "#b8bdd6" }));
const links = graph.links as [number, number][];
const hitIds = graph.hits.map((h) => h.node);
const neighborIds = new Set(graph.neighbors);
const focus = nodes[graph.focus];
const inferredPairs = graph.inferred;
// Where along each suggested link its tag sits, clear of the note names at either end.
const TAG_AT = [0.35, 0.62, 0.55];

// Links draw outward from the centre, so the map grows like a crystal.
const linkOrder = links
  .map((l, k) => ({ k, d: Math.hypot((nodes[l[0]].gx + nodes[l[1]].gx) / 2, (nodes[l[0]].gy + nodes[l[1]].gy) / 2) }))
  .sort((a, b) => a.d - b.d)
  .reduce<number[]>((acc, x, rank) => ((acc[x.k] = rank / links.length), acc), []);

// Where each note sits as a "file" before it becomes a dot: a loose drifting sheet of cards.
const COLS = 14;
const cardHome = nodes.map((n, i) => {
  const col = i % COLS;
  const row = Math.floor(i / COLS);
  const jitter = (s: number) => Math.sin(i * 12.9898 + s) * 18;
  return { x: (col - (COLS - 1) / 2) * 138 + jitter(1), y: (row - 2.5) * 172 + jitter(2) };
});

// ---------------------------------------------------------------- camera

type Cam = { x: number; y: number; s: number; r: number };
const inferMid = inferredPairs.reduce(
  (acc, p) => ({ x: acc.x + (nodes[p.a].gx + nodes[p.b].gx) / 6, y: acc.y + (nodes[p.a].gy + nodes[p.b].gy) / 6 }),
  { x: 0, y: 0 },
);
const KEYS: [number, Cam][] = [
  [0, { x: 0, y: 0, s: 1.06, r: -2 }],
  [9, { x: 0, y: 0, s: 1.0, r: 0 }],
  [19, { x: 0, y: 0, s: 0.9, r: 1 }],
  [23, { x: 0, y: 360, s: 0.25, r: 0 }],
  [31, { x: 0, y: 330, s: 0.27, r: 0 }],
  [35, { x: 0, y: 0, s: 0.88, r: 0 }],
  [44, { x: 0, y: 0, s: 0.92, r: 0 }],
  [48, { x: focus.gx, y: focus.gy, s: 1.9, r: 0 }],
  [56, { x: focus.gx * 0.9, y: focus.gy * 0.9, s: 1.75, r: 0 }],
  [59.5, { x: inferMid.x + 110, y: inferMid.y + 40, s: 0.95, r: 0 }],
  [70, { x: inferMid.x + 90, y: inferMid.y + 40, s: 0.92, r: 0 }],
  [75, { x: 0, y: 0, s: 1.05, r: 0 }],
  [81, { x: 0, y: 0, s: 1.0, r: 0 }],
  [93, { x: 0, y: 0, s: 0.86, r: 6 }],
];
const camera = (t: number): Cam => {
  const k = KEYS.findIndex(([at]) => at > t);
  if (k <= 0) return KEYS[k === 0 ? 0 : KEYS.length - 1][1];
  const [a, ca] = KEYS[k - 1];
  const [b, cb] = KEYS[k];
  const u = smooth((t - a) / (b - a));
  const lerp = (p: number, q: number) => p + (q - p) * u;
  return { x: lerp(ca.x, cb.x), y: lerp(ca.y, cb.y), s: lerp(ca.s, cb.s), r: lerp(ca.r, cb.r) };
};

// ---------------------------------------------------------------- the graph layer

const Graph: React.FC = () => {
  const t = useT();
  const cam = camera(t);
  const toDot = (i: number) => ramp(t, 9.4 + (i % 17) * 0.12, 12.6 + (i % 17) * 0.12);
  const drawn = (k: number) => ramp(t, 12.8 + linkOrder[k] * 6, 13.6 + linkOrder[k] * 6);
  const searching = Math.min(ramp(t, 35.5, 36.5), 1 - ramp(t, 44.5, 46));
  const mapping = Math.min(ramp(t, 49.2, 50.2), 1 - ramp(t, 56, 57.5));
  const inferring = Math.min(ramp(t, 58.5, 59.5), 1 - ramp(t, 71, 72.5));
  const hitLit = (i: number) => {
    const h = hitIds.indexOf(i);
    return h < 0 ? 0 : ramp(t, CUE[h], CUE[h] + 0.5) * searching;
  };
  const pairNodes = new Set(inferredPairs.flatMap((p) => [p.a, p.b]));
  const dimOthers = Math.max(searching * 0.75, mapping * 0.7, inferring * 0.7);
  const drift = (i: number, axis: number) => Math.sin(t * 0.35 + i * (axis ? 1.7 : 2.3)) * 7;
  const localDim = 1 - 0.72 * presence(t, "local");

  const pos = (i: number) => {
    const n = nodes[i];
    const u = toDot(i);
    const card = cardHome[i];
    return {
      x: card.x * (1 - u) + (n.gx + drift(i, 0)) * u + Math.sin(t * 0.3 + i) * 10 * (1 - u),
      y: card.y * (1 - u) + (n.gy + drift(i, 1)) * u + Math.cos(t * 0.25 + i) * 8 * (1 - u) - t * 6 * (1 - u),
    };
  };
  const P = nodes.map((_, i) => pos(i));

  return (
    <AbsoluteFill style={{ opacity: localDim, filter: `blur(${(1 - localDim) * 6}px)` }}>
      <svg width={W} height={H} viewBox={`${-W / 2} ${-H / 2 - 40} ${W} ${H}`}>
        <defs>
          <radialGradient id="glow">
            <stop offset="0%" stopColor={C.accent} stopOpacity="0.55" />
            <stop offset="100%" stopColor={C.accent} stopOpacity="0" />
          </radialGradient>
        </defs>
        <g transform={`rotate(${cam.r}) scale(${cam.s}) translate(${-cam.x} ${-cam.y})`}>
          {links.map(([a, b], k) => {
            const p = drawn(k);
            if (p <= 0) return null;
            const lit = mapping * ((a === focus.i && neighborIds.has(b)) || (b === focus.i && neighborIds.has(a)) ? 1 : 0);
            const hitLink = searching * (hitIds.includes(a) && hitIds.includes(b) ? 1 : 0);
            const op = (0.2 + 0.16 * p) * (1 - dimOthers * 0.8) + lit * 0.85 + hitLink * 0.5;
            return (
              <line
                key={k}
                x1={P[a].x}
                y1={P[a].y}
                x2={P[a].x + (P[b].x - P[a].x) * p}
                y2={P[a].y + (P[b].y - P[a].y) * p}
                stroke={lit > 0.01 ? C.accent : C.line}
                strokeOpacity={op}
                strokeWidth={(1.3 + lit * 2.2) / Math.sqrt(cam.s)}
              />
            );
          })}
          {inferredPairs.map((pair, k) => {
            const on = ramp(t, CUE[4 + k], CUE[4 + k] + 1.1) * inferring;
            if (on <= 0) return null;
            const a = P[pair.a];
            const b = P[pair.b];
            return (
              <g key={`inf${k}`} opacity={on}>
                <line
                  x1={a.x}
                  y1={a.y}
                  x2={a.x + (b.x - a.x) * on}
                  y2={a.y + (b.y - a.y) * on}
                  stroke={C.inferred}
                  strokeWidth={3.2 / cam.s}
                  strokeDasharray={`${10 / cam.s} ${9 / cam.s}`}
                  strokeDashoffset={-t * 18}
                  strokeLinecap="round"
                />
                <Tag x={a.x + (b.x - a.x) * TAG_AT[k]} y={a.y + (b.y - a.y) * TAG_AT[k] - 22 / cam.s} s={cam.s} color={C.inferred} text={`INFERRED ${pair.score}`} />
              </g>
            );
          })}
          {nodes.map((n, i) => {
            const u = toDot(i);
            const lit = Math.max(hitLit(i), mapping * (i === focus.i || neighborIds.has(i) ? 1 : 0), inferring * (pairNodes.has(i) ? 1 : 0));
            const r = (4 + Math.sqrt(n.degree) * 1.6 + lit * 5) / Math.sqrt(cam.s);
            const op = 1 - dimOthers * (1 - lit) * 0.8;
            if (u < 1) {
              // Still a file: a small card with markdown lines; a [[link]] line glows as it turns.
              const cw = 104 * (1 - u) + r * 2 * u;
              const ch = 128 * (1 - u) + r * 2 * u;
              return (
                <g key={i} transform={`translate(${P[i].x} ${P[i].y})`} opacity={0.35 + 0.65 * u}>
                  <rect x={-cw / 2} y={-ch / 2} width={cw} height={ch} rx={6 + (r - 6) * u} fill={u > 0.6 ? n.color : C.bg2} stroke={n.color} strokeOpacity={0.55} strokeWidth={1.5} />
                  {u < 0.5 &&
                    [0, 1, 2, 3, 4].map((l) => (
                      <rect
                        key={l}
                        x={-cw / 2 + 12}
                        y={-ch / 2 + 16 + l * 20}
                        width={(l === 0 ? 60 : l === 3 ? 46 : 78) * (1 - u * 2)}
                        height={6}
                        rx={3}
                        fill={l === 3 ? C.accent : C.dim}
                        opacity={(l === 3 ? 0.9 : 0.45) * (1 - u * 2)}
                      />
                    ))}
                </g>
              );
            }
            return (
              <g key={i} opacity={op}>
                {lit > 0.05 && <circle cx={P[i].x} cy={P[i].y} r={r * 4.5} fill="url(#glow)" opacity={lit} />}
                <circle cx={P[i].x} cy={P[i].y} r={r} fill={lit > 0.5 ? C.accent : n.color} />
              </g>
            );
          })}
          {/* Names beside the notes a scene is about. */}
          <NodeLabel x={P[focus.i].x} y={P[focus.i].y} s={cam.s} o={mapping} title={focus.title} note={`${graph.neighbors.length} links`} />
          {inferredPairs.flatMap((p, k) =>
            [p.a, p.b].map((i) => (
              <NodeLabel key={`i${k}${i}`} x={P[i].x} y={P[i].y} s={cam.s} o={ramp(t, CUE[4 + k] + 0.4, CUE[4 + k] + 1.2) * inferring} title={nodes[i].title} small />
            )),
          )}
        </g>
      </svg>
    </AbsoluteFill>
  );
};

const Tag: React.FC<{ x: number; y: number; s: number; color: string; text: string }> = ({ x, y, s, color, text }) => (
  <g transform={`translate(${x} ${y}) scale(${1 / s})`}>
    <rect x={-86} y={-19} width={172} height={34} rx={17} fill={C.bg} stroke={color} strokeWidth={2} />
    <text x={0} y={5} textAnchor="middle" fill={color} fontFamily={DISPLAY} fontSize={24} letterSpacing={1.5}>
      {text}
    </text>
  </g>
);

const NodeLabel: React.FC<{ x: number; y: number; s: number; o: number; title: string; note?: string; small?: boolean }> = ({
  x,
  y,
  s,
  o,
  title,
  note,
  small,
}) =>
  o <= 0.01 ? null : (
    <g transform={`translate(${x} ${y}) scale(${1 / s})`} opacity={o}>
      <text x={22} y={small ? 8 : 2} fill={C.ink} fontFamily={SANS} fontWeight={600} fontSize={small ? 22 : 27} style={{ paintOrder: "stroke" }} stroke={C.bg} strokeWidth={6}>
        {title.replace(/-/g, " ")}
      </text>
      {note && (
        <text x={22} y={34} fill={C.accent} fontFamily={MONO} fontSize={22} style={{ paintOrder: "stroke" }} stroke={C.bg} strokeWidth={6}>
          {note}
        </text>
      )}
    </g>
  );

// ---------------------------------------------------------------- words: one label per scene

const Label: React.FC<{ id: SceneId; y?: number }> = ({ id, y = H - 250 }) => {
  const t = useT();
  const s = SCENE[id];
  const inn = ramp(t, s.start + 0.5, s.start + 1.3);
  const sub = ramp(t, s.start + 1.0, s.start + 1.8);
  const out = 1 - ramp(t, s.end - 0.9, s.end - 0.2);
  if (inn * out <= 0) return null;
  return (
    <div style={{ position: "absolute", left: 0, right: 0, top: y, display: "flex", flexDirection: "column", alignItems: "center", gap: 14, opacity: out }}>
      <div
        style={{
          background: C.label,
          padding: "14px 34px 4px",
          fontFamily: DISPLAY,
          fontSize: 104,
          lineHeight: 1,
          color: "#fff",
          letterSpacing: 2,
          clipPath: `inset(0 ${(1 - inn) * 100}% 0 0)`,
          transform: `translateY(${(1 - inn) * 10}px)`,
        }}
      >
        {s.label}
      </div>
      <div
        style={{
          background: C.labelSub,
          padding: "10px 24px",
          fontFamily: SANS,
          fontSize: 38,
          color: C.ink,
          opacity: sub,
          transform: `translateY(${(1 - sub) * 12}px)`,
        }}
      >
        {s.sub}
      </div>
    </div>
  );
};

const Title: React.FC<{ id: SceneId; url?: boolean }> = ({ id, url }) => {
  const t = useT();
  const s = SCENE[id];
  const o = presence(t, id);
  const a = ramp(t, s.start + 0.6, s.start + 2.0);
  const b = ramp(t, s.start + 1.6, s.start + 3.0);
  const c = ramp(t, s.start + 2.4, s.start + 3.8);
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", opacity: o }}>
      <div style={{ position: "absolute", inset: 0, background: `radial-gradient(ellipse at center, ${C.bg}ee 0%, ${C.bg}aa 38%, transparent 70%)` }} />
      <div style={{ textAlign: "center", position: "relative" }}>
        <div style={{ fontFamily: SANS, fontWeight: 800, fontSize: 150, color: C.ink, letterSpacing: -3, opacity: a, transform: `scale(${0.96 + 0.04 * a})` }}>
          {s.label}
        </div>
        {url && (
          <div style={{ fontFamily: MONO, fontSize: 44, color: C.accent, marginTop: 18, opacity: b }}>github.com/marsmike/agentic-toolkit</div>
        )}
        <div style={{ fontFamily: SANS, fontSize: 50, color: C.dim, marginTop: 26, opacity: url ? c : b }}>{s.sub}</div>
        {"for" in s && (
          <div style={{ fontFamily: SANS, fontSize: 36, color: C.accent, marginTop: 40, opacity: c }}>{s.for}</div>
        )}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- plugins: the vault at the centre

// From the README's architecture diagram: what flows into the vault and what reads from it.
const PLUGINS = [
  { name: "readwise", role: "capture what you read", into: true },
  { name: "memory", role: "what the agent learns", into: true },
  { name: "radar", role: "judge every feed item", into: true },
  { name: "obsidian", role: "distill & connect", into: false },
  { name: "farsight", role: "BM25 search, Rust", into: false },
  { name: "gaiafield", role: "knowledge graph, Rust", into: false },
];

const Plugins: React.FC = () => {
  const t = useT();
  const o = presence(t, "plugins");
  if (o <= 0) return null;
  const s = SCENE.plugins;
  const R = 250;
  return (
    <AbsoluteFill style={{ opacity: o }}>
      <svg width={W} height={H} viewBox={`${-W / 2} ${-H / 2 + 50} ${W} ${H}`}>
        <circle r={200} fill="none" stroke={C.accent} strokeOpacity={0.5} strokeWidth={2} strokeDasharray="4 10" transform={`rotate(${t * 6})`} />
        <text y={250} textAnchor="middle" fill={C.accent} fontFamily={DISPLAY} fontSize={40} letterSpacing={3}>
          YOUR VAULT
        </text>
        {PLUGINS.map((p, i) => {
          const ang = -Math.PI / 2 + ((i + 0.5) / PLUGINS.length) * Math.PI * 2;
          const x = Math.cos(ang) * R * 2.3;
          const y = Math.sin(ang) * R;
          const inn = ramp(t, s.start + 0.8 + i * 0.35, s.start + 1.8 + i * 0.35);
          const ex = Math.cos(ang) * 215;
          const ey = Math.sin(ang) * 215;
          const dots = [0, 1, 2].map((d) => {
            const u = (t * 0.45 + d / 3 + i * 0.13) % 1;
            const v = p.into ? u : 1 - u;
            return { x: x + (ex - x) * v, y: y + (ey - y) * v };
          });
          return (
            <g key={p.name} opacity={inn}>
              <line x1={x} y1={y} x2={ex} y2={ey} stroke={C.line} strokeOpacity={0.5} strokeWidth={2} />
              {dots.map((d, k) => (
                <circle key={k} cx={d.x} cy={d.y} r={5} fill={p.into ? "#2fd4c0" : C.accent} opacity={inn} />
              ))}
              <g transform={`translate(${x} ${y}) scale(${0.9 + 0.1 * inn})`}>
                <rect x={-150} y={-52} width={300} height={104} rx={18} fill={C.bg2} stroke={p.into ? "#2fd4c0" : C.accent} strokeWidth={2.5} />
                <text y={-4} textAnchor="middle" fill={C.ink} fontFamily={DISPLAY} fontSize={46} letterSpacing={1.5}>
                  {p.name.toUpperCase()}
                </text>
                <text y={32} textAnchor="middle" fill={C.dim} fontFamily={SANS} fontSize={22}>
                  {p.role}
                </text>
              </g>
            </g>
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- search: the query

const Search: React.FC = () => {
  const t = useT();
  const o = presence(t, "search");
  if (o <= 0) return null;
  const s = SCENE.search.start;
  const query = "graph";
  const typed = query.slice(0, Math.floor(ramp(t, s + 1.2, s + 2.6, 0, query.length + 0.99, Easing.linear)));
  const ping = (t - (s + 3.2)) % 1.6;
  return (
    <AbsoluteFill style={{ opacity: o }}>
      <div style={{ position: "absolute", top: 70, left: 0, right: 0, display: "flex", justifyContent: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 22, background: C.bg2, border: `2px solid ${C.accent}`, borderRadius: 60, padding: "16px 40px", minWidth: 560, boxShadow: `0 0 ${40 + 30 * Math.max(0, 1 - ping)}px ${C.accent}33` }}>
          <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke={C.accent} strokeWidth="2.4" strokeLinecap="round">
            <circle cx="10.5" cy="10.5" r="6.5" />
            <line x1="15.5" y1="15.5" x2="21" y2="21" />
          </svg>
          <span style={{ fontFamily: MONO, fontSize: 46, color: C.ink }}>
            farsight query "{typed}
            <span style={{ opacity: t < s + 3 ? (Math.floor(t * 2.5) % 2 ? 1 : 0) : 1 }}>{t < s + 3 ? "▌" : '"'}</span>
          </span>
        </div>
      </div>
      <div style={{ position: "absolute", top: 190, left: 0, right: 0, display: "flex", flexDirection: "column", alignItems: "center", gap: 10 }}>
        {graph.hits.map((h, k) => {
          const a = ramp(t, CUE[k], CUE[k] + 0.6);
          return (
            <div key={h.node} style={{ opacity: a, transform: `translateY(${(1 - a) * -10}px)`, display: "flex", gap: 22, alignItems: "baseline", background: `${C.bg}cc`, padding: "6px 22px", borderRadius: 10 }}>
              <span style={{ fontFamily: MONO, fontSize: 30, color: C.accent }}>{h.score}</span>
              <span style={{ fontFamily: SANS, fontSize: 32, color: C.ink, fontWeight: 600 }}>{nodes[h.node].title.replace(/-/g, " ")}</span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- map: the numbers

const MapStats: React.FC = () => {
  const t = useT();
  const o = presence(t, "map");
  if (o <= 0) return null;
  const s = SCENE.map.start;
  const n = Math.round(ramp(t, s + 1, s + 3.2, 0, graph.stats.nodes));
  const e = Math.round(ramp(t, s + 1.3, s + 3.6, 0, graph.stats.edges));
  return (
    <AbsoluteFill style={{ opacity: o }}>
      <div style={{ position: "absolute", top: 70, right: 110, textAlign: "right", fontFamily: DISPLAY, color: C.ink }}>
        <div style={{ fontSize: 120, lineHeight: 1 }}>
          {n} <span style={{ fontSize: 50, color: C.dim }}>NOTES</span>
        </div>
        <div style={{ fontSize: 120, lineHeight: 1, color: C.accent }}>
          {e} <span style={{ fontSize: 50, color: C.dim }}>LINKS</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- inferred: you decide

const Decide: React.FC = () => {
  const t = useT();
  const o = presence(t, "inferred");
  const at = CUE[7];
  const a = ramp(t, at, at + 0.8);
  if (o * a <= 0) return null;
  const pill = (text: string, color: string, filled: boolean) => (
    <div style={{ fontFamily: DISPLAY, fontSize: 44, letterSpacing: 2, padding: "12px 30px 4px", borderRadius: 40, border: `3px solid ${color}`, color: filled ? C.bg : color, background: filled ? color : "transparent" }}>
      {text}
    </div>
  );
  return (
    <AbsoluteFill style={{ opacity: o * a }}>
      <div style={{ position: "absolute", top: 80, left: 0, right: 0, display: "flex", justifyContent: "center", gap: 26, transform: `translateY(${(1 - a) * -14}px)` }}>
        {pill("REPORTED", C.inferred, true)}
        {pill("NOT WRITTEN TO YOUR NOTES", C.inferred, false)}
        {pill("YOUR CALL", C.accent, true)}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- local: the real session, big

// The commands and a few key results, as recorded (session.txt line numbers).
const SHOWN = [1, 9, 10, 15, 17, 19, 23, 26, 31, 39, 40];
const Terminal: React.FC = () => {
  const t = useT();
  const o = presence(t, "local");
  if (o <= 0) return null;
  const s = SCENE.local.start;
  const per = 5.2 / SHOWN.length;
  const rows = SHOWN.map((n, k) => {
    const text = SESSION[n - 1];
    const at = s + 0.9 + k * per;
    const isCmd = text.startsWith("$ ");
    const chars = isCmd ? Math.floor(ramp(t, at, at + per * 0.9, 0, text.length, Easing.linear)) : t >= at ? text.length : 0;
    return { n, text: text.slice(0, chars), shown: chars > 0, isCmd, strong: [23, 26, 31, 40].includes(n) };
  });
  const lift = ramp(t, s - CF / 2, s + 1);
  return (
    <AbsoluteFill style={{ opacity: o, justifyContent: "center", alignItems: "center" }}>
      <div style={{ width: 1500, marginTop: -150, borderRadius: 18, overflow: "hidden", background: "#05070fee", border: `1px solid ${C.line}66`, boxShadow: "0 40px 120px #000a", transform: `translateY(${(1 - lift) * 40}px) scale(${0.97 + 0.03 * lift})` }}>
        <div style={{ height: 46, background: C.bg2, display: "flex", alignItems: "center", gap: 12, paddingLeft: 20 }}>
          {["#ff5f57", "#febc2e", "#28c840"].map((c) => (
            <div key={c} style={{ width: 16, height: 16, borderRadius: 8, background: c }} />
          ))}
          <span style={{ marginLeft: 20, fontFamily: SANS, fontSize: 20, color: C.dim }}>recorded in a clean home directory, nothing retyped</span>
        </div>
        <div style={{ padding: "22px 30px", fontFamily: MONO, fontSize: 25, lineHeight: 1.55, minHeight: 560 }}>
          {rows.map((r) =>
            r.shown ? (
              <div key={r.n} style={{ whiteSpace: "pre", overflow: "hidden", textOverflow: "ellipsis", color: r.isCmd ? C.ink : r.strong ? C.accent : C.dim }}>
                {r.text}
              </div>
            ) : null,
          )}
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- the film

export const Explainer: React.FC = () => {
  const vignette = `radial-gradient(ellipse at 50% 45%, transparent 55%, ${C.bg} 100%)`;
  return (
    <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 40%, ${C.bg2} 0%, ${C.bg} 70%)` }}>
      <Graph />
      <Plugins />
      <AbsoluteFill style={{ background: vignette, pointerEvents: "none" }} />
      <Title id="open" />
      <Search />
      <MapStats />
      <Decide />
      <Terminal />
      {(["vault", "plugins", "search", "map", "inferred", "local"] as SceneId[]).map((id) => (
        <Label key={id} id={id} />
      ))}
      <Title id="end" url />
      <Audio
        src={staticFile(music.file.replace(/^public\//, ""))}
        volume={(f) => music.volume * Math.min(1, f / FPS / 1.5) * Math.min(1, (TOTAL_SECONDS - f / FPS) / 3)}
      />
    </AbsoluteFill>
  );
};
