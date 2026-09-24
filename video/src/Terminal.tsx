import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";

import { Cast, promptLines, screenAt } from "./cast";

// One recorded command, replayed at its recorded pace (times `speed`): the
// prompt line from the capture header (a session has its own), then the screen as it stood at this
// frame. Long lines wrap at the recorded terminal width, as they did live.
export const Terminal: React.FC<{ cast: Cast; speed?: number; label?: string }> = ({
  cast,
  speed = 1,
  label,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const lines = [...promptLines(cast), ...screenAt(cast, (frame / fps) * speed)].flatMap((l) =>
    l.length <= cast.width ? [l] : (l.match(new RegExp(`.{1,${cast.width}}`, "gu")) ?? [l]),
  );
  const visible = lines.slice(-cast.height);
  return (
    <AbsoluteFill style={{ backgroundColor: "#0d1117", padding: 64 }}>
      {label ? (
        <div style={{ color: "#8b949e", fontFamily: "Menlo, monospace", fontSize: 22, marginBottom: 16 }}>
          {label}
        </div>
      ) : null}
      <pre
        style={{
          margin: 0,
          color: "#e6edf3",
          fontFamily: "Menlo, monospace",
          fontSize: 25,
          lineHeight: 1.35,
          whiteSpace: "pre",
        }}
      >
        {visible.join("\n")}
      </pre>
    </AbsoluteFill>
  );
};
