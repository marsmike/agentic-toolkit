import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

import sessionSource from "../capture/from-source-main-0dd21a7/session.cast";
import music from "../music.json";
import { parseCast, screenLines } from "./cast";
import { parseSceneText } from "./scene-text";
import board from "./storyboard.json";

// The explainer: the locked storyboard (src/storyboard.json, copied verbatim
// and checked by scripts/check_storyboard.py), scene by scene. Every
// terminal line is a line of the captured session, replayed by src/cast.ts;
// this file only decides when each line appears and what is highlighted
// (the pacing the storyboard allows), never what it says.

export const FPS = 30;

type Scene = (typeof board.scenes)[number];
export const TOTAL_SECONDS = board.scenes[board.scenes.length - 1].end;

const session = parseCast(sessionSource);
// session.txt line N is SESSION[N - 1] (test/cast.test.ts holds them equal).
const SESSION = screenLines(session.events.map((e) => e[1]).join(""), session.width);

const COLOR = {
  bg: "#0d1117",
  panel: "#010409",
  text: "#e6edf3",
  dim: "#8b949e",
  accent: "#f2cc60",
  mark: "rgba(242, 204, 96, 0.30)",
};
const SANS = '-apple-system, "SF Pro Display", "Helvetica Neue", Helvetica, Arial, sans-serif';
const MONO = 'Menlo, "DejaVu Sans Mono", monospace';
const MONO_ADVANCE = 0.6021; // Menlo glyph advance, in em
const GUTTER = 96;
const TEXT_WIDTH = 1920 - 2 * GUTTER;

const useSeconds = (): number => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return frame / fps;
};

const fade = (t: number, at: number, duration = 0.6): number =>
  interpolate(t, [at, at + duration], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

const Appear: React.FC<{ at: number; children: React.ReactNode; style?: React.CSSProperties }> = ({
  at,
  children,
  style,
}) => {
  const t = useSeconds();
  const o = fade(t, at);
  return <div style={{ opacity: o, transform: `translateY(${(1 - o) * 16}px)`, ...style }}>{children}</div>;
};

// ---------------------------------------------------------------- cards

const Heading: React.FC<{ children: React.ReactNode; size?: number }> = ({ children, size = 64 }) => (
  <div style={{ fontFamily: SANS, fontWeight: 700, fontSize: size, color: COLOR.accent, marginBottom: 40 }}>
    {children}
  </div>
);

const Body: React.FC<{ children: React.ReactNode; size?: number }> = ({ children, size = 52 }) => (
  <div style={{ fontFamily: SANS, fontSize: size, lineHeight: 1.3, color: COLOR.text, marginBottom: 28 }}>
    {children}
  </div>
);

const Card: React.FC<{ children: React.ReactNode; clear?: boolean }> = ({ children, clear }) => (
  <AbsoluteFill
    style={{ backgroundColor: clear ? undefined : COLOR.bg, justifyContent: "center", padding: `0 ${GUTTER + 64}px` }}
  >
    {children}
  </AbsoluteFill>
);

const TitleScene: React.FC<{ scene: Scene; end?: boolean }> = ({ scene, end }) => {
  const t = parseSceneText(scene.text, scene.start, scene.end);
  return (
    <Card>
      <div style={{ textAlign: "center" }}>
        <Appear at={0.2}>
          <div style={{ fontFamily: SANS, fontWeight: 800, fontSize: 140, color: COLOR.text, letterSpacing: -2 }}>
            {t.heading}
          </div>
        </Appear>
        {t.lines.map((line, i) => (
          <Appear key={line} at={(end ? 0.9 : 1.4) + i * 0.8}>
            <div
              style={{
                fontFamily: end && i === 0 ? MONO : SANS,
                fontSize: end && i === 0 ? 44 : 52,
                color: end && i === 0 ? COLOR.accent : COLOR.dim,
                marginTop: 36,
              }}
            >
              {line}
            </div>
          </Appear>
        ))}
      </div>
    </Card>
  );
};

// Drawn note-file icons (no names, no text) for scene 2's slow pan.
const FileIcons: React.FC = () => {
  const t = useSeconds();
  const shift = interpolate(t, [0, 12], [0, -520]);
  const icons = Array.from({ length: 36 }, (_, i) => i);
  return (
    <AbsoluteFill style={{ opacity: 0.11, overflow: "hidden" }}>
      <div style={{ position: "absolute", top: 120, left: shift, display: "flex", flexWrap: "wrap", width: 2800, gap: 70 }}>
        {icons.map((i) => (
          <svg key={i} width="130" height="160" viewBox="0 0 130 160">
            <path d="M10 6 H88 L122 40 V154 H10 Z" fill="none" stroke={COLOR.text} strokeWidth="5" />
            <path d="M88 6 V40 H122" fill="none" stroke={COLOR.text} strokeWidth="5" />
            {[62, 84, 106, 128].map((y) => (
              <line key={y} x1="30" y1={y} x2={y === 128 ? 70 : 102} y2={y} stroke={COLOR.text} strokeWidth="5" />
            ))}
          </svg>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const WhatScene: React.FC<{ scene: Scene }> = ({ scene }) => {
  const t = parseSceneText(scene.text, scene.start, scene.end);
  return (
    <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
      <FileIcons />
      <Card clear>
        <Appear at={0.2}>
          <Heading>{t.heading}</Heading>
        </Appear>
        {t.lines.map((line, i) => (
          <Appear key={line} at={0.9 + i * 3.4}>
            <Body>{line}</Body>
          </Appear>
        ))}
      </Card>
    </AbsoluteFill>
  );
};

// Scene 3: the heading, the audience line, then three stacked cards, one per
// sentence of the storyboard's third line (the text is split, not changed).
const WhoScene: React.FC<{ scene: Scene }> = ({ scene }) => {
  const t = parseSceneText(scene.text, scene.start, scene.end);
  const [audience, uses] = t.lines;
  const cards = uses.match(/[^.]+\./g)?.map((s) => s.trim()) ?? [uses];
  return (
    <Card>
      <Appear at={0.2}>
        <Heading>{t.heading}</Heading>
      </Appear>
      <Appear at={0.9}>
        <Body>{audience}</Body>
      </Appear>
      <div style={{ marginTop: 24 }}>
        {cards.map((card, i) => (
          <Appear key={card} at={3.4 + i * 2.4}>
            <div
              style={{
                fontFamily: SANS,
                fontSize: 44,
                color: COLOR.text,
                background: "#161b22",
                border: "2px solid #30363d",
                borderLeft: `8px solid ${COLOR.accent}`,
                borderRadius: 12,
                padding: "22px 32px",
                marginBottom: 20,
                width: 1200,
              }}
            >
              {card}
            </div>
          </Appear>
        ))}
      </div>
    </Card>
  );
};

const WhyScene: React.FC<{ scene: Scene }> = ({ scene }) => {
  const t = parseSceneText(scene.text, scene.start, scene.end);
  return (
    <Card>
      <Appear at={0.2}>
        <Heading>{t.heading}</Heading>
      </Appear>
      {t.lines.map((line, i) => (
        <Appear key={line} at={0.9 + i * 3.2}>
          <Body>{line}</Body>
        </Appear>
      ))}
    </Card>
  );
};

// ------------------------------------------------------------- terminal

type Mark = { line: number; text?: string; from: number; to?: number }; // text: highlight only that substring
type TerminalPlan = {
  at: Record<number, number>; // session line -> second it appears (prompt lines type in from then)
  typeSeconds?: number;
  marks?: Mark[];
  zoom?: { line: number; from: number; to: number; scale: number };
};

// Pacing and emphasis per scene, as the storyboard's "On screen" column
// directs. Times are seconds from the start of the scene.
const PLANS: Record<number, TerminalPlan> = {
  4: {
    at: {
      1: 0.3, 2: 1.5, 3: 1.9, 4: 2.3, 5: 2.7, 6: 3.1, 7: 3.5, 8: 3.9, 9: 4.2, 10: 4.8,
      11: 6.0, 12: 6.4, 13: 6.8, 14: 7.3, 15: 7.7, 16: 8.1, 17: 8.5, 18: 8.9,
    },
    marks: [
      { line: 16, from: 9 },
      { line: 18, from: 9 },
    ],
  },
  5: {
    at: { 19: 0.4, 20: 1.8, 21: 2.1, 22: 2.4, 23: 3.0 },
    marks: [{ line: 23, from: 3.6 }],
  },
  6: {
    at: { 25: 0.4, 26: 1.0, 27: 1.3, 28: 1.6 },
    marks: [
      { line: 26, from: 3.0, to: 5.8 },
      { line: 27, from: 5.8, to: 8.6 },
      { line: 28, from: 8.6 },
    ],
  },
  7: {
    at: { 30: 0.4, 31: 1.0, 32: 1.4 },
    marks: [{ line: 31, text: "nodes=83 edges=783", from: 3.2 }],
    zoom: { line: 31, from: 4.0, to: 9.5, scale: 1.7 },
  },
  8: {
    at: { 34: 0.4, 35: 1.0, 36: 1.5, 37: 1.9, 38: 2.3 },
    marks: [
      { line: 34, text: "never auto-applied, always a human decision", from: 2.8 },
      { line: 36, text: "[INFERRED]", from: 6.0 },
      { line: 37, text: "[INFERRED]", from: 7.2 },
      { line: 38, text: "[INFERRED]", from: 8.4 },
    ],
  },
  9: {
    at: { 39: 0.4, 40: 2.4 },
    typeSeconds: 1.4,
    marks: [{ line: 40, from: 3.0 }],
  },
};

const PROMPT = "$ ";

// The lines a scene shows, as the checker computes them (T7's crop applied).
export const sceneLines = (scene: Scene): { n: number; text: string }[] => {
  const terminal = scene.terminal!;
  const [first, last] = terminal.lines;
  const lines = [];
  for (let n = first; n <= last; n++) {
    let text = SESSION[n - 1];
    const crop = "crop" in terminal ? terminal.crop : undefined;
    if (crop && crop.line === n) text = text.slice(0, text.indexOf(crop.endsWith) + crop.endsWith.length);
    lines.push({ n, text });
  }
  return lines;
};

const markedLine = (n: number, text: string, marks: Mark[], t: number): React.ReactNode => {
  const active = marks.filter((m) => m.line === n && t >= m.from && (m.to === undefined || t < m.to));
  if (!active.length) return text;
  if (active.some((m) => m.text === undefined)) {
    return <span style={{ background: COLOR.mark, boxShadow: `0 0 0 4px ${COLOR.mark}` }}>{text}</span>;
  }
  const parts: React.ReactNode[] = [];
  let rest = text;
  let key = 0;
  for (const m of active) {
    const i = rest.indexOf(m.text!);
    if (i < 0) continue;
    parts.push(rest.slice(0, i));
    parts.push(
      <span key={key++} style={{ background: COLOR.mark, color: COLOR.accent }}>
        {m.text}
      </span>,
    );
    rest = rest.slice(i + m.text!.length);
  }
  parts.push(rest);
  return parts;
};

const TerminalScene: React.FC<{ scene: Scene; label: string | null }> = ({ scene, label }) => {
  const t = useSeconds();
  const plan = PLANS[scene.n];
  const lines = sceneLines(scene);
  const cropped = "crop" in scene.terminal! && scene.terminal!.crop;
  // Font size: the widest line fits the frame (never cut), up to 26 px. For
  // T7 the declared crop is the frame edge, so its cut line sets the size.
  const widest = Math.max(...lines.map((l) => l.text.length));
  const fontSize = cropped ? TEXT_WIDTH / (widest * MONO_ADVANCE) : Math.min(26, TEXT_WIDTH / (widest * MONO_ADVANCE));
  const cols = Math.floor(TEXT_WIDTH / (fontSize * MONO_ADVANCE) + 1e-6); // widest line: exactly one row
  const typeSeconds = plan.typeSeconds ?? 0.9;

  const zoom = plan.zoom
    ? interpolate(
        t,
        [plan.zoom.from, plan.zoom.from + 1.2, plan.zoom.to - 1.2, plan.zoom.to],
        [1, plan.zoom.scale, plan.zoom.scale, 1],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic) },
      )
    : 1;
  const zoomIndex = plan.zoom ? lines.findIndex((l) => l.n === plan.zoom!.line) : 0;
  const lineHeight = 1.4;

  const text = parseSceneText(scene.text, scene.start, scene.end);
  const caption = text.captions.find((c) => t >= c.from && t < c.to);

  return (
    <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
      {label ? (
        <div style={{ position: "absolute", top: 44, left: GUTTER, fontFamily: SANS, fontSize: 28, color: COLOR.dim }}>
          {label}
        </div>
      ) : null}
      <div
        style={{
          position: "absolute",
          top: 110,
          left: 0,
          right: 0,
          bottom: 190,
          background: COLOR.panel,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: 36,
            left: GUTTER,
            width: TEXT_WIDTH,
            fontFamily: MONO,
            fontSize,
            lineHeight,
            color: COLOR.text,
            transform: `scale(${zoom})`,
            transformOrigin: `0px ${(zoomIndex + 0.5) * fontSize * lineHeight}px`,
          }}
        >
          {lines.map(({ n, text: full }) => {
            const at = plan.at[n];
            if (at === undefined || t < at) return null;
            const isPrompt = full.startsWith(PROMPT);
            const typed = isPrompt
              ? full.slice(0, PROMPT.length + Math.round(((t - at) / typeSeconds) * (full.length - PROMPT.length)))
              : full;
            const shown = isPrompt && typed.length < full.length ? typed : full;
            return (
              <div
                key={n}
                style={{
                  // Half a column of slack absorbs subpixel rounding; it cannot fit a character.
                  width: cropped ? undefined : `${cols + 0.5}ch`,
                  whiteSpace: cropped ? "pre" : "pre-wrap",
                  wordBreak: "break-all",
                  minHeight: `${lineHeight}em`,
                }}
              >
                {shown.length < full.length ? shown : markedLine(n, full, plan.marks ?? [], t)}
              </div>
            );
          })}
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height: 190,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: `0 ${GUTTER}px`,
        }}
      >
        {caption ? (
          <div
            key={caption.text}
            style={{
              fontFamily: SANS,
              fontSize: 44,
              lineHeight: 1.25,
              color: COLOR.text,
              textAlign: "center",
              opacity: fade(t, caption.from, 0.35),
            }}
          >
            {caption.text}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- whole

const SceneView: React.FC<{ scene: Scene; label: string | null }> = ({ scene, label }) => {
  if (scene.terminal) return <TerminalScene scene={scene} label={label} />;
  if (scene.n === 1) return <TitleScene scene={scene} />;
  if (scene.n === 2) return <WhatScene scene={scene} />;
  if (scene.n === 3) return <WhoScene scene={scene} />;
  if (scene.n === 10) return <WhyScene scene={scene} />;
  if (scene.n === 11) return <TitleScene scene={scene} end />;
  throw new Error(`no view for scene ${scene.n}`);
};

export const Explainer: React.FC = () => {
  const { fps, durationInFrames } = useVideoConfig();
  // The corner label is written once, in scene 4, and stays on through 9.
  const label = parseSceneText(board.scenes[3].text, board.scenes[3].start, board.scenes[3].end).label;
  return (
    <AbsoluteFill style={{ backgroundColor: COLOR.bg }}>
      {board.scenes.map((scene) => (
        <Sequence key={scene.n} from={scene.start * fps} durationInFrames={(scene.end - scene.start) * fps}>
          <SceneView scene={scene} label={scene.terminal ? label : null} />
        </Sequence>
      ))}
      <Audio
        src={staticFile(music.file.replace(/^public\//, ""))}
        // Skip the recording's silent lead-in (2.2 s) so the music starts under the title.
        trimBefore={Math.round(music.startSeconds * fps)}
        volume={(f) =>
          interpolate(f, [0, fps, durationInFrames - 3 * fps, durationInFrames], [0, 0.7, 0.7, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          })
        }
      />
    </AbsoluteFill>
  );
};
