// Downloads the music track named in music.json and checks its sha256.
// The track is not committed (public/music/ is ignored); see MUSIC.md.
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

const root = join(import.meta.dirname, "..");
const music = JSON.parse(readFileSync(join(root, "music.json"), "utf8"));
const target = join(root, music.file);
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");

if (existsSync(target) && sha256(readFileSync(target)) === music.sha256) {
  console.log(`ok ${music.file} (already present, sha256 matches)`);
  process.exit(0);
}
const response = await fetch(music.url, { headers: { "User-Agent": "agentic-toolkit-explainer/1 (fetch-music)" } });
if (!response.ok) throw new Error(`download failed: HTTP ${response.status} for ${music.url}`);
const bytes = Buffer.from(await response.arrayBuffer());
const got = sha256(bytes);
if (got !== music.sha256) throw new Error(`sha256 mismatch for ${music.url}: got ${got}, want ${music.sha256}`);
mkdirSync(dirname(target), { recursive: true });
writeFileSync(target, bytes);
console.log(`ok ${music.file} (${bytes.length} bytes, sha256 matches)`);
