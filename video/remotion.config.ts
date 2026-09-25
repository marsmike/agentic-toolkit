import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setCodec("h264");
// Remotion's default is 18; 20 keeps text sharp and the 118 s render under the 10 MB budget.
Config.setCrf(20);

// Captures are imported as text (`import demo from "../capture/....cast"`),
// so terminal scenes render from the recorded bytes, never retyped JSX.
Config.overrideWebpackConfig((config) => ({
  ...config,
  module: {
    ...config.module,
    rules: [...(config.module?.rules ?? []), { test: /\.(cast|txt)$/, type: "asset/source" }],
  },
}));
