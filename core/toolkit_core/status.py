"""`unisphere status`: one read-only answer to "is everything current and healthy?".

Sections: the toolkit checkout, the engines (installed vs. latest release, the cloud pin), the Claude
Code plugins installed from this marketplace (per scope, vs. the version in this checkout), the
vault (notes, graph, DLQ), the pipeline (the obsidian plugin's watchdog verdict, when the vault
runs one) and the companion CLIs agents use next to `unisphere` (Obsidian's, Todoist's `td`).

Every check collapses its failure into data: a `problems` list of {section, detail} the caller can
render or branch on, and `ok` is true only when that list is empty. Nothing here writes anything.
[earned: 2026-09-28 — "make sure we have the latest versions active": the answer took a dozen
commands across three tools]
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from toolkit_core import engines, knowledge, vault

MARKETPLACE = "agentic-toolkit"
WATCHDOG_TIMEOUT = 60
COMPANION_TIMEOUT = 10
OBSIDIAN_APP_CLI = Path("/Applications/Obsidian.app/Contents/MacOS/obsidian-cli")


def _run(args: list[str], timeout: int = COMPANION_TIMEOUT, **kwargs) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, **kwargs)
    except (OSError, subprocess.SubprocessError):
        return None


def _git(repo: Path, *args: str) -> str | None:
    proc = _run(["git", "-C", str(repo), *args])
    return proc.stdout.strip() if proc and proc.returncode == 0 else None


def _checkout(path: Path) -> dict:
    """Head, branch, uncommitted files and ahead/behind against the upstream as last fetched."""
    info: dict = {"path": str(path), "git": _git(path, "rev-parse", "--is-inside-work-tree") == "true"}
    if not info["git"]:
        return info
    info["head"] = _git(path, "rev-parse", "--short", "HEAD")
    info["branch"] = _git(path, "rev-parse", "--abbrev-ref", "HEAD")
    status = _git(path, "status", "--porcelain") or ""
    info["uncommitted"] = len([line for line in status.splitlines() if line.strip()])
    counts = _git(path, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if counts:
        ahead, behind = (int(n) for n in counts.split())
        info["ahead"], info["behind"] = ahead, behind
    return info


def _marketplace(repo_root: Path | None) -> dict:
    path = repo_root / vault.MARKETPLACE_MARKER if repo_root else None
    if not path or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def toolkit_section(repo_root: Path | None) -> dict:
    if repo_root is None:
        return {"found": False}
    market = _marketplace(repo_root)
    return {
        "found": True,
        "version": (market.get("metadata") or {}).get("version") or market.get("version"),
        **_checkout(repo_root),
    }


def cloud_pin(repo_root: Path | None) -> str | None:
    """The release tag `cloud/setup.sh` clones to install engines in the cloud routine."""
    setup = repo_root / "cloud" / "setup.sh" if repo_root else None
    if not setup or not setup.is_file():
        return None
    match = re.search(r"^TOOLKIT_PIN=(\S+)", setup.read_text(encoding="utf-8"), re.M)
    return match.group(1) if match else None


def engines_section(repo_root: Path | None, offline: bool) -> dict:
    rows = engines.status_all(fetch=not offline)
    for row in rows:
        row["on_path"] = shutil.which(row["engine"])
    return {"engines": rows, "cloud_pin": cloud_pin(repo_root), "checked_latest": not offline}


def claude_config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def plugins_section(repo_root: Path | None) -> dict:
    """Each marketplace plugin: its version here, and every Claude Code install of it (per scope).
    An install recorded under this marketplace whose plugin the marketplace no longer lists is
    reported as `orphaned` — it can never update."""
    market = _marketplace(repo_root)
    registry = claude_config_dir() / "plugins" / "installed_plugins.json"
    if not market.get("plugins"):
        # `uv tool install` puts toolkit on PATH without a checkout: nothing to compare against,
        # and calling every install orphaned would be wrong.
        return {"registry": str(registry), "registry_found": registry.is_file(), "marketplace_found": False,
                "plugins": []}
    available = {p["name"]: p.get("version") for p in market.get("plugins", []) if p.get("name")}
    try:
        installed = json.loads(registry.read_text(encoding="utf-8")).get("plugins", {})
    except (OSError, json.JSONDecodeError):
        installed = {}

    rows = []
    names = sorted(set(available) | {k.split("@", 1)[0] for k in installed if k.endswith(f"@{MARKETPLACE}")})
    for name in names:
        installs = [
            {"scope": i.get("scope"), "project": i.get("projectPath"), "version": i.get("version")}
            for i in installed.get(f"{name}@{MARKETPLACE}", [])
        ]
        latest = available.get(name)
        if latest is None:
            state = "orphaned"
        elif not installs:
            state = "not-installed"
        elif all(i["version"] == latest for i in installs):
            state = "current"
        else:
            state = "outdated"
        rows.append({"plugin": name, "latest": latest, "state": state, "installs": installs})
    return {"registry": str(registry), "registry_found": registry.is_file(), "marketplace_found": True, "plugins": rows}


def vault_section(resolution: vault.VaultResolution) -> dict:
    path = resolution.path
    if path is None or not path.is_dir():
        return {"found": False, "path": str(path) if path else None, "source": resolution.source}
    counts = vault.note_counts(path)
    return {
        "found": True,
        "path": str(path),
        "source": resolution.source,
        "notes": sum(counts.values()),
        "inbox": counts.get("01_Capture", 0),
        "dlq": vault.dlq_status(path),
        "graph": knowledge.graph_status(path),
        "checkout": _checkout(path),
    }


def pipeline_section(repo_root: Path | None, vault_path: Path | None) -> dict:
    """The obsidian plugin's watchdog, run as the pipeline's own routine runs it. Only for a vault
    that has a pipeline (00_Memory/pipeline-state.json); the example vault has none."""
    if vault_path is None or not (vault_path / "00_Memory" / "pipeline-state.json").is_file():
        return {"present": False, "note": "this vault runs no pipeline"}
    scripts = repo_root / "plugins" / "obsidian" / "scripts" if repo_root else None
    if not scripts or not (scripts / "watchdog.py").is_file() or not shutil.which("uv"):
        return {"present": True, "checked": False, "note": "watchdog unavailable (needs the repo checkout and uv)"}
    proc = _run(
        ["uv", "run", "--quiet", "--locked", "--project", str(scripts), "python3", str(scripts / "watchdog.py"), "--json"],
        timeout=WATCHDOG_TIMEOUT, env={**os.environ, "TOOLKIT_VAULT": str(vault_path)},
    )
    try:
        verdict = json.loads(proc.stdout) if proc else None
    except json.JSONDecodeError:
        verdict = None
    if not isinstance(verdict, dict):
        detail = (proc.stderr.strip().splitlines() or ["no output"])[-1] if proc else "did not run"
        return {"present": True, "checked": False, "note": f"watchdog failed: {detail}"}
    return {"present": True, "checked": True, "ok": verdict.get("ok"), "problems": verdict.get("problems", []),
            "facts": verdict.get("facts", {})}


def _first_line(proc: subprocess.CompletedProcess | None) -> str:
    return ((proc.stdout or proc.stderr).strip().splitlines() or [""])[0] if proc else ""


def companions_section() -> dict:
    """The CLIs an agent reaches for next to `unisphere`: Obsidian's own (the running app) and
    Todoist's `td` (tasks). Presence, version and readiness only — never account details."""
    rows = []

    obsidian = shutil.which("obsidian") or (str(OBSIDIAN_APP_CLI) if OBSIDIAN_APP_CLI.is_file() else None)
    row = {"cli": "obsidian", "path": obsidian, "on_path": shutil.which("obsidian") is not None}
    if obsidian is None:
        row.update(ready=False, note="not found — Obsidian 1.12+ ships it; install or update Obsidian")
    else:
        proc = _run([obsidian, "version"])
        out = _first_line(proc)
        if "not enabled" in out:
            row.update(ready=False, note="turn it on in Obsidian: Settings → General → Advanced → Command line interface")
        elif proc and proc.returncode == 0 and out:
            row.update(ready=True, version=out)
        else:
            row.update(ready=False, note=f"did not answer ({out or 'is Obsidian running?'})")
    rows.append(row)

    td = shutil.which("td")
    row = {"cli": "td", "path": td, "on_path": td is not None}
    if td is None:
        row.update(ready=False, note="not found — npm install -g @doist/todoist-cli")
    else:
        row["version"] = _first_line(_run([td, "--version"]))
        proc = _run([td, "auth", "status", "--json"])
        try:
            auth = json.loads(proc.stdout) if proc and proc.returncode == 0 else None
        except json.JSONDecodeError:
            auth = None
        if isinstance(auth, dict) and auth.get("id"):
            row.update(ready=True, auth_mode=auth.get("authMode"))
        else:
            row.update(ready=False, note="not logged in — td auth login")
    rows.append(row)
    return {"companions": rows}


def _problems(result: dict) -> list[dict]:
    problems = []

    def add(section: str, detail: str) -> None:
        problems.append({"section": section, "detail": detail})

    for row in result["engines"]["engines"]:
        if not row["installed_tag"]:
            add("engines", f"{row['engine']} not installed — unisphere engines install")
        elif result["engines"]["checked_latest"] and row["latest_tag"] and not row["up_to_date"]:
            add("engines", f"{row['engine']} {row['installed_tag']} → {row['latest_tag']} — unisphere engines update")
        elif result["engines"]["checked_latest"] and not row["latest_tag"]:
            # Unknown is not current: only --offline may skip the check. [earned: PR #71 review]
            add("engines", f"{row['engine']}: latest release unknown — {row.get('note') or 'release check failed'}")
    for row in result["plugins"]["plugins"]:
        if row["state"] == "outdated":
            old = ", ".join(sorted({str(i["version"]) for i in row["installs"] if i["version"] != row["latest"]}))
            add("plugins", f"{row['plugin']} {old} → {row['latest']} — claude plugin update {row['plugin']}@{MARKETPLACE}")
        elif row["state"] == "orphaned":
            add("plugins", f"{row['plugin']} is no longer in the marketplace — claude plugin uninstall {row['plugin']}@{MARKETPLACE}")
    v = result["vault"]
    if not v["found"]:
        add("vault", f"no vault at {v['path']} — set TOOLKIT_VAULT")
    else:
        if v["dlq"].get("open"):
            add("vault", f"{v['dlq']['note']}: {', '.join(Path(n).stem for n in v['dlq']['open_notes'][:5])}")
        if v["checkout"].get("behind"):
            add("vault", f"checkout is {v['checkout']['behind']} commit(s) behind its upstream — git pull")
    p = result["pipeline"]
    for item in p.get("problems") or []:
        add("pipeline", item.get("detail", str(item)))
    if p.get("present") and not p.get("checked", True):
        add("pipeline", p["note"])
    return problems


def collect(offline: bool = False) -> dict:
    resolution = vault.resolve_vault()
    repo_root = resolution.repo_root or vault.find_repo_root(Path(__file__).resolve().parent)
    result = {
        "toolkit": toolkit_section(repo_root),
        "engines": engines_section(repo_root, offline),
        "plugins": plugins_section(repo_root),
        "vault": vault_section(resolution),
        "pipeline": pipeline_section(repo_root, resolution.path),
        **companions_section(),
    }
    result["problems"] = _problems(result)
    result["ok"] = not result["problems"]
    return {"ok": result.pop("ok"), **result}
