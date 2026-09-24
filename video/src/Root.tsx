import React from "react";
import { Composition, Series } from "remotion";

import clone from "../capture/from-source-fixed/01-clone.cast";
import engines from "../capture/from-source-fixed/02-engines.cast";
import demo from "../capture/from-source-fixed/03-demo.cast";
import plugins from "../capture/from-source-fixed/04-plugins.cast";
import { castDuration, parseCast } from "./cast";
import { Terminal } from "./Terminal";

const FPS = 30;
const HOLD_SECONDS = 2; // final screen stays up after the last output

// Part A check (not the explainer): the D6 path replayed from its captures,
// one scene per command. The storyboard's scenes replace this in Part B.
const scenes = [clone, engines, demo, plugins].map((source) => {
  const cast = parseCast(source);
  return { cast, frames: Math.ceil((castDuration(cast) + HOLD_SECONDS) * FPS) };
});

const Capture: React.FC = () => (
  <Series>
    {scenes.map(({ cast, frames }) => (
      <Series.Sequence key={cast.command} durationInFrames={frames}>
        <Terminal cast={cast} label="From source · bundled example vault" />
      </Series.Sequence>
    ))}
  </Series>
);

export const Root: React.FC = () => (
  <Composition
    id="Capture"
    component={Capture}
    durationInFrames={scenes.reduce((sum, s) => sum + s.frames, 0)}
    fps={FPS}
    width={1920}
    height={1080}
  />
);
