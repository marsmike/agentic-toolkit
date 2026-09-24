// capture.py deletes and recreates its throwaway HOME on every run; it must
// only ever delete a directory it created itself.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";

const capture = join(import.meta.dirname, "..", "capture");
const freshHome = (home: string): { ok: boolean; err: string } => {
  try {
    execFileSync("python3", ["-c", "import sys; from pathlib import Path; from capture import fresh_home; fresh_home(Path(sys.argv[1]))", home], {
      cwd: capture,
      stdio: "pipe",
    });
    return { ok: true, err: "" };
  } catch (e) {
    return { ok: false, err: String((e as { stderr: Buffer }).stderr) };
  }
};

test("refuses an existing directory it did not create, and leaves it intact", () => {
  const home = join(mkdtempSync(join(tmpdir(), "guard-")), "newcomer");
  mkdirSync(home);
  writeFileSync(join(home, "precious.txt"), "someone else's");
  const r = freshHome(home);
  assert.equal(r.ok, false);
  assert.match(r.err, /is not the directory capture\.py created/);
  assert.ok(existsSync(join(home, "precious.txt")));
});

test("refuses a symlinked HOME", () => {
  const base = mkdtempSync(join(tmpdir(), "guard-"));
  mkdirSync(join(base, "target"));
  symlinkSync(join(base, "target"), join(base, "newcomer"));
  assert.equal(freshHome(join(base, "newcomer")).ok, false);
});

test("creates an empty HOME, then recreates its own on the next run", () => {
  const home = join(mkdtempSync(join(tmpdir(), "guard-")), "newcomer");
  assert.equal(freshHome(home).ok, true);
  writeFileSync(join(home, "left-over"), "from a capture");
  assert.equal(freshHome(home).ok, true);
  assert.deepEqual(readdirSync(home), []);
});

test("refuses a directory replaced by someone else even though the marker remains", () => {
  const home = join(mkdtempSync(join(tmpdir(), "guard-")), "newcomer");
  assert.equal(freshHome(home).ok, true); // ours, marker written
  rmSync(home, { recursive: true });
  mkdirSync(home); // someone else's directory at the same path, new inode
  writeFileSync(join(home, "precious.txt"), "someone else's");
  const r = freshHome(home);
  assert.equal(r.ok, false);
  assert.ok(existsSync(join(home, "precious.txt")));
});

test("a refused run deletes nothing, not even the old captures", () => {
  const base = mkdtempSync(join(tmpdir(), "guard-"));
  mkdirSync(join(base, "foreign-home"));
  mkdirSync(join(base, "out", "headline"), { recursive: true });
  writeFileSync(join(base, "out", "headline", "01-install.cast"), "committed capture");
  const script = [
    "import sys; from pathlib import Path; import capture",
    "capture.HERE = Path(sys.argv[1]) / 'out'; capture.HOME = Path(sys.argv[1]) / 'foreign-home'",
    "capture.fresh_home.__defaults__ = (capture.HOME,)",
    "try:\n    capture.capture('headline')\nexcept capture.NotOurs:\n    sys.exit(3)",
  ].join("\n");
  let code = 0;
  try {
    execFileSync("python3", ["-c", script, base], { cwd: capture, stdio: "pipe" });
  } catch (e) {
    code = (e as { status: number }).status;
  }
  assert.equal(code, 3);
  assert.ok(existsSync(join(base, "out", "headline", "01-install.cast")));
});
