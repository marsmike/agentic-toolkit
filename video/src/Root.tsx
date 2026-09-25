import React from "react";
import { Composition } from "remotion";

import { Explainer, FPS, TOTAL_SECONDS } from "./Explainer";

export const Root: React.FC = () => (
  <Composition
    id="Explainer"
    component={Explainer}
    durationInFrames={TOTAL_SECONDS * FPS}
    fps={FPS}
    width={1920}
    height={1080}
  />
);
