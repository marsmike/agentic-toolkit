"""`toolkit engines` — fetch and track the prebuilt Rust engine binaries (farsight,
gaiafield) from GitHub Releases, so a `uv tool install` user never hand-downloads a
binary or sets an env var.

Install location: `$XDG_DATA_HOME/agentic-toolkit/bin` if set, else
`~/.local/share/agentic-toolkit/bin` — the "well-known install dir" that
`toolkit_core.knowledge`'s binary-discovery chain (and the plugin-side
`plugins/obsidian/scripts/{graph,search}.py`, which mirror this path since plugin
scripts don't import `core`) probe as their last step before giving up.

Release convention (`.github/workflows/release-binaries.yml`): each engine tags its own
releases as `<engine>-v<version>` (e.g. `gaiafield-v0.2.0`), carrying one asset per
platform named `<engine>-<target-triple>` (`.exe` suffix on Windows). There is no
single repo-wide "latest release" — "latest" is scoped per engine, so this module lists
all releases and takes the newest tag matching each engine's own prefix.

Nothing here touches a checksum published by the release process (none is): a
downloaded file is instead verified for `size > 0` and its own sha256 is recorded in
`manifest.json` — enough to detect a corrupt re-download or advertise what shipped,
without inventing a checksum authority that doesn't exist yet.

Every network/platform failure raises `EngineError` with a message meant to be printed
as-is (no traceback) — see `cli.py`'s `cmd_engines_*` handlers.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import platform
import urllib.error
import urllib.request
from pathlib import Path

REPO = "marsmike/agentic-toolkit"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases?per_page=100"
USER_AGENT = "agentic-toolkit-engines"

ENGINES: tuple[str, ...] = ("farsight", "gaiafield")

HTTP_TIMEOUT = 15  # seconds, for the releases-list API call
DOWNLOAD_TIMEOUT = 60  # seconds, for a single binary download
DOWNLOAD_CHUNK = 256 * 1024


class EngineError(Exception):
    """A clean, printable failure — network, platform, or release-shape related.
    Callers print `str(exc)` directly; never a traceback."""


# ---------------------------------------------------------------------------
# Platform -> release target triple
# ---------------------------------------------------------------------------

# Normalizes the handful of spellings platform.machine() actually returns across the
# three OSes this toolkit ships binaries for.
_ARCH_ALIASES = {
    "arm64": "arm64",
    "aarch64": "arm64",
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "AMD64": "x86_64",
}

# Mirrors the exact matrix in .github/workflows/release-binaries.yml. Darwin/x86_64 is
# deliberately included (a real, well-formed target triple) even though no CI leg
# builds it yet — a user on Intel macOS gets a clean "no asset for this platform" error
# from install_engine() rather than this table silently pretending the arch doesn't
# exist. Windows is real too (windows-latest does build x86_64-pc-windows-msvc); support
# there is unverified by this toolkit's own tests, which is a documented note, not a
# refusal to try.
_TARGET_TRIPLES: dict[tuple[str, str], str] = {
    ("Darwin", "arm64"): "aarch64-apple-darwin",
    ("Darwin", "x86_64"): "x86_64-apple-darwin",
    ("Linux", "arm64"): "aarch64-unknown-linux-musl",
    ("Linux", "x86_64"): "x86_64-unknown-linux-musl",
    ("Windows", "x86_64"): "x86_64-pc-windows-msvc",
}


def target_triple(system: str | None = None, machine: str | None = None) -> str | None:
    """The release target triple for (`system`, `machine`) — `platform.system()` /
    `platform.machine()` spellings by default. `None` for anything not in the release
    matrix (e.g. a 32-bit arch, or an OS this toolkit doesn't ship for)."""
    system = platform.system() if system is None else system
    machine = platform.machine() if machine is None else machine
    arch = _ARCH_ALIASES.get(machine)
    if arch is None:
        return None
    return _TARGET_TRIPLES.get((system, arch))


def is_windows_triple(triple: str) -> bool:
    return triple.endswith("windows-msvc")


# ---------------------------------------------------------------------------
# Well-known install dir + manifest
# ---------------------------------------------------------------------------


def install_dir() -> Path:
    """`$XDG_DATA_HOME/agentic-toolkit/bin`, else `~/.local/share/agentic-toolkit/bin`.
    This exact path (mirrored, not imported, in the plugin-side discovery chains — see
    module docstring) is what makes `toolkit engines install` alone enough: no PATH or
    env var wiring required afterwards."""
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return base / "agentic-toolkit" / "bin"


def binary_path(engine: str) -> Path:
    """Where `engine`'s binary lives (or would land) in the well-known install dir.
    Invariant: suffix is `.exe` iff `os.name == "nt"` — deliberately independent of
    `target_triple()`/`is_windows_triple()` (which answer "which release asset to
    fetch", a build-matrix question) and identical to the plugin-side mirrors in
    `plugins/obsidian/scripts/{graph,search}.py::_engines_install_dir()`. Keep all
    three in sync."""
    suffix = ".exe" if os.name == "nt" else ""
    return install_dir() / f"{engine}{suffix}"


def manifest_path() -> Path:
    return install_dir() / "manifest.json"


def read_manifest() -> dict:
    """`{}` if no manifest exists yet, or if it's unreadable/corrupt — a missing/bad
    manifest is a normal pre-install state, never an error."""
    path = manifest_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def write_manifest(data: dict) -> None:
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# GitHub Releases
# ---------------------------------------------------------------------------


def _fetch_releases(timeout: int = HTTP_TIMEOUT) -> list[dict]:
    """All releases in the repo, newest first (the GitHub API's default order) — the
    only network call this module needs, since "latest per engine" is a client-side
    filter over one shared list rather than a separate request per engine."""
    req = urllib.request.Request(
        RELEASES_API, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            raise EngineError(
                "GitHub API rate limit reached — wait a while and try again"
            ) from exc
        raise EngineError(f"GitHub API returned HTTP {exc.code} ({exc.reason})") from exc
    except TimeoutError as exc:
        raise EngineError(f"GitHub API request timed out after {timeout}s") from exc
    except urllib.error.URLError as exc:
        raise EngineError(f"no network reaching api.github.com ({exc.reason})") from exc

    try:
        releases = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EngineError("GitHub API returned unparseable JSON") from exc
    if not isinstance(releases, list):
        raise EngineError("unexpected GitHub API response shape (expected a list of releases)")
    return releases


def _latest_for_engine(engine: str, releases: list[dict]) -> dict | None:
    """The newest non-draft, non-prerelease release whose tag starts with
    `<engine>-v` — `releases` is assumed newest-first (GitHub API's own ordering), so
    the first match is the latest for that engine specifically, independent of
    whatever the other engine's release cadence looks like."""
    prefix = f"{engine}-v"
    for release in releases:
        tag = release.get("tag_name", "")
        if tag.startswith(prefix) and not release.get("draft") and not release.get("prerelease"):
            return release
    return None


def _asset_filename(engine: str, triple: str) -> str:
    return f"{engine}-{triple}.exe" if is_windows_triple(triple) else f"{engine}-{triple}"


def _find_asset(release: dict, filename: str) -> dict | None:
    for asset in release.get("assets", []):
        if asset.get("name") == filename:
            return asset
    return None


def _download(url: str, dest: Path, timeout: int = DOWNLOAD_TIMEOUT) -> tuple[int, str]:
    """Stream `url` to `dest`, returning `(size_bytes, sha256_hex)`. Any failure removes
    the partial file and raises `EngineError`; a zero-byte download is treated as a
    failure too (the "verify size > 0" requirement), not a silently-installed empty
    binary."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    tmp_dest = dest.with_name(dest.name + ".part")
    digest = hashlib.sha256()
    size = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp_dest, "wb") as out:
            while chunk := resp.read(DOWNLOAD_CHUNK):
                digest.update(chunk)
                size += len(chunk)
                out.write(chunk)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        tmp_dest.unlink(missing_ok=True)
        raise EngineError(f"download failed ({url}): {exc}") from exc

    if size == 0:
        tmp_dest.unlink(missing_ok=True)
        raise EngineError(f"downloaded file is empty: {url}")

    tmp_dest.replace(dest)
    return size, digest.hexdigest()


# ---------------------------------------------------------------------------
# install / status
# ---------------------------------------------------------------------------


def install_engine(engine: str, releases: list[dict] | None = None, *, force: bool = False) -> dict:
    """Install (or update) one engine's binary. Returns a result dict — never raises;
    a failure comes back as `{"ok": False, "engine": ..., "error": ...}` so
    `install_all()` can report per-engine failures without one engine's network hiccup
    aborting the other's install."""
    triple = target_triple()
    if triple is None:
        return {
            "ok": False,
            "engine": engine,
            "error": f"no release binary for this platform ({platform.system()}/{platform.machine()})",
        }

    try:
        if releases is None:
            releases = _fetch_releases()
    except EngineError as exc:
        return {"ok": False, "engine": engine, "error": str(exc)}

    release = _latest_for_engine(engine, releases)
    if release is None:
        return {"ok": False, "engine": engine, "error": f"no release found for {engine} (expected tag {engine}-vX.Y.Z)"}

    tag = release.get("tag_name", "")
    manifest = read_manifest()
    current = manifest.get(engine)
    dest = binary_path(engine)
    if current and current.get("tag") == tag and not force and dest.is_file():
        return {"ok": True, "engine": engine, "action": "up-to-date", "tag": tag, "path": str(dest)}

    filename = _asset_filename(engine, triple)
    asset = _find_asset(release, filename)
    if asset is None:
        return {"ok": False, "engine": engine, "error": f"release {tag} has no asset named {filename}"}

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        size, sha256 = _download(asset["browser_download_url"], dest)
    except EngineError as exc:
        return {"ok": False, "engine": engine, "error": str(exc)}

    if not is_windows_triple(triple):
        dest.chmod(dest.stat().st_mode | 0o111)

    manifest[engine] = {
        "tag": tag,
        "version": tag.split("-v", 1)[-1],
        "target": triple,
        "sha256": sha256,
        "size": size,
        "installed_at": _now_iso(),
    }
    write_manifest(manifest)
    action = "updated" if current else "installed"
    return {"ok": True, "engine": engine, "action": action, "tag": tag, "path": str(dest), "sha256": sha256}


def install_all(force: bool = False) -> list[dict]:
    """Install/update every known engine. A single releases-list fetch is shared across
    both so a transient network failure is reported once, identically, for each engine
    rather than as two independent (and possibly differently-worded) failures."""
    try:
        releases = _fetch_releases()
    except EngineError as exc:
        return [{"ok": False, "engine": engine, "error": str(exc)} for engine in ENGINES]
    return [install_engine(engine, releases, force=force) for engine in ENGINES]


def status_all() -> list[dict]:
    """Installed vs. latest for every known engine — read-only, never downloads."""
    manifest = read_manifest()
    triple = target_triple()
    fetch_error: str | None = None
    try:
        releases = _fetch_releases()
    except EngineError as exc:
        releases = []
        fetch_error = str(exc)

    rows = []
    for engine in ENGINES:
        entry = manifest.get(engine)
        latest = _latest_for_engine(engine, releases) if releases else None
        latest_tag = latest.get("tag_name") if latest else None
        row = {
            "engine": engine,
            "installed_tag": entry.get("tag") if entry else None,
            "installed_path": str(binary_path(engine)) if entry else None,
            "latest_tag": latest_tag,
            "up_to_date": bool(entry and latest_tag and entry.get("tag") == latest_tag),
            "target": triple,
        }
        if fetch_error and latest_tag is None:
            row["note"] = f"could not check latest release: {fetch_error}"
        rows.append(row)
    return rows
