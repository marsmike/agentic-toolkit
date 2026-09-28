"""`unisphere`: one front door to the vault, its engines and the plugins, for people and agents.
Named for the Commonwealth's unisphere, the network everything connects through, next to the
engines' own Hamilton names (farsight, gaiafield). It was `toolkit` until 2026-09-28; the Python
package keeps its name (`toolkit_core`), so `python -m toolkit_core.cli` reaches it in any version.

People get readable, coloured text (colour only on a TTY; NO_COLOR is honoured). Agents pass
`--json` to any command for a stable object, and start from `unisphere commands --json`: every
command, its arguments, what its JSON carries, and the companion CLIs next to it. Exit codes:
0 ok, 1 a problem or an error (the JSON says which), 2 a usage error.
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import importlib.metadata
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path

from toolkit_core import demo, engines, knowledge, profile, status, term, ui, vault
from toolkit_core import link as linker


def _json_default(obj):
    """Frontmatter can carry YAML-native date/datetime values; render them as ISO strings."""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _dumps(result: dict) -> str:
    return json.dumps(result, indent=2, default=_json_default)


def _emit(result: dict, as_json: bool, render_text: Callable[[dict], str]) -> None:
    if as_json:
        print(_dumps(result))
    else:
        print(render_text(result))


def _error(args: argparse.Namespace, message: str) -> dict:
    """The `{ok: false, error}` shape every command falls back to on a fatal, non-catalogued
    failure — text output is just `error: <message>`."""
    result = {"ok": False, "error": message}
    _emit(result, args.json, lambda r: f"error: {r['error']}")
    return result


# --- vault init --------------------------------------------------------------------


def _vault_agents_template_path(repo_root: Path | None) -> Path | None:
    if repo_root is None:
        return None
    candidate = repo_root / "contract" / "templates" / "VAULT_AGENTS.md"
    return candidate if candidate.is_file() else None


def cmd_vault_init(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser().resolve()
    repo_root = vault.find_repo_root(Path.cwd()) or vault.find_repo_root(Path(__file__).resolve().parent)
    template_path = _vault_agents_template_path(repo_root)

    if template_path is None:
        _error(args, "could not locate contract/templates/VAULT_AGENTS.md (repo root not found)")
        return 1

    try:
        vault.scaffold_vault(target, template_path, force=args.force)
    except (vault.VaultInitError, OSError) as exc:
        _error(args, str(exc))
        return 1

    result = {"ok": True, "path": str(target)}
    _emit(result, args.json, lambda r: f"initialized vault at {r['path']}")
    return 0


# --- doctor --------------------------------------------------------------------------


def _render_doctor_text(result: dict) -> str:
    lines = [f"vault: {result['vault_path']} (via {result['vault_source']})"]
    if not result["vault_exists"]:
        lines.append("  vault directory does not exist yet")
        return "\n".join(lines)

    lines.append("PARA folders:")
    for folder, present in result["para_folders"].items():
        mark = "ok" if present else "MISSING"
        count = result["note_counts"].get(folder, 0)
        lines.append(f"  {folder:<12} {mark:<8} {count} note(s)")

    errors = result["frontmatter_parse_errors"]
    lines.append(f"frontmatter parse errors: {len(errors)}")
    for err in errors:
        lines.append(f"  {err['path']}: {err['error']}")

    lines.append("profiles:")
    if result["profiles"]:
        for plugin_name, present in result["profiles"].items():
            lines.append(f"  {plugin_name:<12} {'present' if present else 'missing'}")
    else:
        lines.append("  (no known plugins)")

    dlq = result["dlq"]
    lines.append(f"DLQ: {dlq['note']}")

    graph = result["graph"]
    if not graph["present"]:
        lines.append(f"graph: {graph['note']}")
    else:
        stale_mark = " (stale)" if graph.get("stale") else ""
        lines.append(
            f"graph: nodes={graph.get('nodes')} edges={graph.get('edges')} "
            f"dangling={graph.get('dangling_edges')} boundary={graph.get('boundary_violations')}"
            f"{stale_mark}"
        )
        inference = graph.get("inference")
        if inference:
            lines.append(f"  inference: {inference['note']}")
    return "\n".join(lines)


def cmd_doctor(args: argparse.Namespace) -> int:
    resolution = vault.resolve_vault()
    if resolution.path is None:
        _error(args, "no vault found: set TOOLKIT_VAULT, or run from inside the agentic-toolkit repo")
        return 1

    vault_path = resolution.path
    exists = vault_path.is_dir()

    para_status = vault.para_folder_status(vault_path) if exists else dict.fromkeys(vault.PARA_FOLDERS, False)
    counts = vault.note_counts(vault_path) if exists else dict.fromkeys(vault.PARA_FOLDERS, 0)
    parse_errors = vault.frontmatter_parse_errors(vault_path) if exists else []
    dlq = vault.dlq_status(vault_path) if exists else {"present": False, "count": 0, "open": 0, "open_notes": [], "note": "no DLQ entries"}
    graph = knowledge.graph_status(vault_path) if exists else {"present": False, "note": "vault does not exist"}

    repo_root = resolution.repo_root or vault.find_repo_root(Path(__file__).resolve().parent)
    plugin_names = profile.known_plugins(repo_root)
    profile_status = {name: profile.profile_note_path(vault_path, name).is_file() for name in plugin_names} if exists else {}

    result = {
        "ok": True,
        "vault_path": str(vault_path),
        "vault_source": resolution.source,
        "vault_exists": exists,
        "para_folders": para_status,
        "note_counts": counts,
        "frontmatter_parse_errors": parse_errors,
        "profiles": profile_status,
        "dlq": dlq,
        "graph": graph,
    }
    _emit(result, args.json, _render_doctor_text)
    return 0


# --- profile ---------------------------------------------------------------------------


def cmd_profile(args: argparse.Namespace) -> int:
    resolution = vault.resolve_vault()
    if resolution.path is None:
        print(_dumps({"ok": False, "error": "no vault found"}))
        return 1

    merged = profile.resolve_profile(resolution.path, args.plugin)
    result = {"ok": True, "plugin": args.plugin, "vault_path": str(resolution.path), "profile": merged}
    # `unisphere profile` always prints JSON: it's a data command, not a status report.
    print(_dumps(result))
    return 0


# --- engines -------------------------------------------------------------------------


def _render_engines_action_result(result: dict) -> str:
    lines = []
    for r in result["results"]:
        if not r.get("ok"):
            lines.append(f"  {r['engine']:<10} ERROR: {r['error']}")
            continue
        action = r["action"]
        lines.append(
            f"  {r['engine']:<10} up to date ({r['tag']})"
            if action == "up-to-date"
            else f"  {r['engine']:<10} {action} {r['tag']} -> {r['path']}"
        )
        if r.get("warning"):
            lines.append(f"    warning: {r['warning']}")
    triple = engines.target_triple()
    if triple and engines.is_windows_triple(triple):
        lines.append("note: Windows support is unverified by this toolkit's own CI/tests.")
    return "\n".join(lines) if lines else "no engines processed"


def cmd_engines_install(args: argparse.Namespace) -> int:
    results = engines.install_all(force=args.force)
    ok = all(r.get("ok") for r in results)
    _emit({"ok": ok, "results": results}, args.json, _render_engines_action_result)
    return 0 if ok else 1


def _render_engines_status(result: dict) -> str:
    lines = []
    for r in result["engines"]:
        installed = r["installed_tag"] or "not installed"
        latest = r["latest_tag"] or "unknown"
        if r["up_to_date"]:
            mark = "up to date"
        elif r["installed_tag"]:
            mark = "update available"
        else:
            mark = "run: unisphere engines install"
        lines.append(f"  {r['engine']:<10} installed={installed:<20} latest={latest:<20} {mark}")
        if r.get("note"):
            lines.append(f"    {r['note']}")
    return "\n".join(lines)


def cmd_engines_status(args: argparse.Namespace) -> int:
    rows = engines.status_all()
    _emit({"ok": True, "engines": rows}, args.json, _render_engines_status)
    return 0


# --- demo ------------------------------------------------------------------------------


def cmd_demo(args: argparse.Namespace) -> int:
    return demo.run(as_json=args.json)


# --- status ----------------------------------------------------------------------------


def _render_status(result: dict) -> str:
    st = ui.Style()
    tk = result["toolkit"]
    head = st.bold("agentic-toolkit")
    if tk.get("found"):
        head += f" {tk.get('version') or ''} " + st.dim(f"· {tk.get('branch')}@{tk.get('head')} · {tk['path']}")
    out = [head, ""]

    def checkout_note(info: dict) -> str:
        bits = []
        if info.get("uncommitted"):
            bits.append(f"{info['uncommitted']} uncommitted")
        if info.get("behind"):
            bits.append(f"{info['behind']} behind")
        if info.get("ahead"):
            bits.append(f"{info['ahead']} ahead")
        return ", ".join(bits)

    if tk.get("found") and checkout_note(tk):
        out += ui.section(st, "CHECKOUT", [f"{st.mark('warn')} {checkout_note(tk)}"])

    rows = []
    eng = result["engines"]
    for r in eng["engines"]:
        installed = (r["installed_tag"] or "").split("-v", 1)[-1] or "not installed"
        if not r["installed_tag"]:
            level, tail = "bad", "unisphere engines install"
        elif r["up_to_date"]:
            level, tail = "ok", "latest"
        elif r["latest_tag"]:
            level, tail = "warn", f"{r['latest_tag'].split('-v', 1)[-1]} available — unisphere engines update"
        else:
            level, tail = "info", "latest not checked"
        where = "" if r.get("on_path") else st.dim("  (not on PATH — unisphere link)")
        rows.append(f"{st.mark(level)} {r['engine']:<10} {installed:<8} {st.level(tail, level)}{where}")
    if eng.get("cloud_pin"):
        rows.append(f"{st.mark('info')} {st.dim('cloud setup clones ' + eng['cloud_pin'])}")
    out += ui.section(st, "ENGINES", rows)

    rows = []
    for r in result["plugins"]["plugins"]:
        # A plugin installed from a git commit reports the full sha as its version; seven characters identify it.
        versions = sorted({str(i["version"])[:7] if re.fullmatch(r"[0-9a-f]{12,40}", str(i["version"])) else str(i["version"])
                           for i in r["installs"]}) or ["—"]
        scopes = ", ".join(sorted({str(i["scope"]) for i in r["installs"]}))
        level, tail = {
            "current": ("ok", "current"),
            "outdated": ("warn", f"{r['latest']} available — claude plugin update {r['plugin']}@{status.MARKETPLACE}"),
            "orphaned": ("warn", "no longer in the marketplace — claude plugin uninstall"),
            "not-installed": ("info", "not installed"),
        }[r["state"]]
        rows.append(f"{st.mark(level)} {r['plugin']:<10} {' / '.join(versions):<8} {st.level(tail, level)}"
                    + (st.dim(f"  ({scopes})") if scopes else ""))
    if any(r["installs"] for r in result["plugins"]["plugins"]):
        rows.append(f"{st.mark('info')} {st.dim('a running Claude Code loads updated plugins after a restart')}")
    out += ui.section(st, "PLUGINS", rows)

    v = result["vault"]
    if not v["found"]:
        rows = [f"{st.mark('bad')} no vault at {v['path']} — set TOOLKIT_VAULT"]
    else:
        rows = [f"{st.mark('info')} {v['path']} " + st.dim(f"(via {v['source']})"),
                f"{st.mark('info')} {v['notes']} notes · {v['inbox']} in the inbox"]
        g = v["graph"]
        if g.get("nodes") is not None:
            level = "warn" if g.get("stale") else "ok"
            rows.append(f"{st.mark(level)} graph {g['nodes']} nodes · {g['edges']} edges · {g['dangling_edges']} dangling"
                        + (st.dim("  (stale — refreshed by the next graph call)") if g.get("stale") else ""))
        else:
            rows.append(f"{st.mark('info')} graph: {g.get('note')}")
        dlq = v["dlq"]
        rows.append(f"{st.mark('warn' if dlq.get('open') else 'ok')} {dlq.get('note')}")
        note = checkout_note(v.get("checkout") or {})
        if note:
            rows.append(f"{st.mark('warn')} checkout: {note}")
    out += ui.section(st, "VAULT", rows)

    # U-SHADOWS: the cloud routines that run TheVoid's pipeline unattended (cloud/routines.json),
    # alongside the local watchdog check that runs for a vault that has one.
    p = result["pipeline"]
    routines = p.get("routines") or []
    if p.get("present") or routines:
        rows = []
        if p.get("present") and not p.get("checked"):
            rows.append(f"{st.mark('warn')} {p['note']}")
        elif p.get("present"):
            rows += [f"{st.mark('bad')} {item.get('detail')}" for item in p.get("problems", [])]
        for r in routines:
            if r.get("last"):
                when = r["last"][:16].replace("T", " ")
                age = st.dim(f" ({r['age_hours']} h ago)") if r.get("age_hours") is not None else ""
                rows.append(f"{st.mark('ok' if p.get('ok', True) else 'warn')} {r['name']}: last {when} UTC{age}"
                            + (st.dim(f" — {r['note']}") if r.get("note") else ""))
            elif r.get("note"):
                rows.append(f"{st.mark('info')} {r['name']}: {r['note']}"
                            + (st.dim(f" ({r['age_hours']} h ago)") if r.get("age_hours") is not None else ""))
            else:
                rows.append(f"{st.mark('info')} {r['name']}: {st.dim('no local run recorded')}")
        out += ui.section(st, "U-SHADOWS", rows)

    rows = []
    for c in result["companions"]:
        level = "ok" if c.get("ready") else "info"
        detail = c.get("version") or ""
        if c.get("auth_mode"):
            detail += " · authenticated" if c["auth_mode"] == "authenticated" else f" · logged in ({c['auth_mode']})"
        if c.get("note"):
            detail = (detail + " · " if detail else "") + c["note"]
        where = "" if c.get("on_path") or not c.get("path") else st.dim("  (not on PATH — unisphere link)")
        rows.append(f"{st.mark(level)} {c['cli']:<10} {detail}{where}")
    out += ui.section(st, "COMPANIONS", rows)

    out.append("")
    if result["ok"]:
        out.append(f"{st.mark('ok')} {st.level('all current and healthy', 'ok')}")
    else:
        out.append(st.level(f"{len(result['problems'])} to look at:", "warn"))
        out += [f"  {st.mark('warn')} {st.dim(pr['section'] + ':')} {pr['detail']}" for pr in result["problems"]]
    return "\n".join(out)


def cmd_status(args: argparse.Namespace) -> int:
    result = status.collect(offline=args.offline)
    _emit(result, args.json, _render_status)
    return 0 if result["ok"] else 1


# --- search and graph (farsight, gaiafield) -------------------------------------------


def _vault_or_fail(args: argparse.Namespace) -> Path | None:
    resolution = vault.resolve_vault()
    if resolution.path is None or not resolution.path.is_dir():
        where = resolution.path or "(none)"
        _error(args, f"no vault at {where}: set TOOLKIT_VAULT")
        return None
    return resolution.path


def _engine_json(binary: str | None, name: str, argv: list[str], timeout: int) -> tuple[object, str | None]:
    """Run an engine with --json; (parsed, None) or (None, error). `knowledge._run_json` is the
    one subprocess-probing/JSON-parsing recipe for an engine binary; this just names the engine
    in the error."""
    if binary is None:
        return None, f"{name} not installed — unisphere engines install"
    data, error = knowledge._run_json(binary, argv, timeout)
    return (data, None) if error is None else (None, f"{name}: {error}")


def _note_lines(st: ui.Style, rank: str, note: dict, extra: str = "") -> list[str]:
    title = note.get("title") or Path(note.get("path", "?")).stem
    lines = [f"{st.dim(rank)} {st.bold(title)}{extra}", f"{' ' * len(rank)} {st.accent(note.get('path', ''))}"]
    if note.get("description"):
        lines += ui.wrap(note["description"], len(rank) + 1)
    return lines


def _render_search(result: dict) -> str:
    st = ui.Style()
    hits = result["results"]
    if not hits:
        return f"no notes match {result['query']!r}"
    out = [st.dim(f"{len(hits)} note(s) for {result['query']!r} in {result['vault']}"), ""]
    for i, hit in enumerate(hits, 1):
        out += _note_lines(st, f"{i:>2}.", hit, st.dim(f"  score {hit.get('score', 0):.2f}"))
        out.append("")
    return "\n".join(out).rstrip()


def cmd_search(args: argparse.Namespace) -> int:
    vault_path = _vault_or_fail(args)
    if vault_path is None:
        return 1
    query = " ".join(args.terms)
    hits, error = _engine_json(knowledge.farsight_binary(), "farsight",
                               ["query", *args.terms, "--vault", str(vault_path), "--k", str(args.limit)],
                               knowledge.QUERY_TIMEOUT)
    if error:
        _error(args, error)
        return 1
    _emit({"ok": True, "query": query, "vault": str(vault_path), "results": hits}, args.json, _render_search)
    return 0


def _render_graph(result: dict) -> str:
    st = ui.Style()
    op, data = result["op"], result["result"]
    if op == "stats":
        out = [f"{st.bold(str(data.get('nodes')))} nodes · {data.get('edges')} edges · "
               f"{data.get('dangling_edges')} dangling · {data.get('boundary_violations')} boundary violations", ""]
        top = data.get("top_linked") or []
        if top:
            out.append(st.dim("most linked"))
            out += [f"  {r.get('in_degree', 0):>4}  {r.get('title')}  {st.dim(r.get('path', ''))}" for r in top]
        inferred = {k: v for k, v in data.items() if k.startswith("inferred") or k.startswith("ambiguous")}
        if inferred:
            out += ["", st.dim("inference: " + ", ".join(f"{k}={v}" for k, v in inferred.items()))]
        return "\n".join(out)
    if op == "path":
        if not data.get("connected"):
            return f"{data.get('from')} and {data.get('to')} are not connected"
        # With --include-inferred each hop is an object ({path, kind, …}), otherwise a plain path.
        chain = [p.get("path", "?") if isinstance(p, dict) else p for p in data.get("path") or []]
        return "\n".join([st.dim(f"{len(chain) - 1} hop(s)")] + [
            f"  {'  ' * i}{'└ ' if i else ''}{st.bold(Path(p).stem)}  {st.dim(p)}" for i, p in enumerate(chain)])
    rows = data if isinstance(data, list) else []
    if not rows:
        return f"no {op} for {result.get('note')!r}" + (" (run `gaiafield infer` first)" if op == "candidates" else "")
    out = [st.dim(f"{len(rows)} {op} of {result.get('note')}"), ""]
    for i, row in enumerate(rows, 1):
        extra = ""
        if "depth" in row:
            extra = st.dim(f"  depth {row['depth']}" + (f" · {row['direction']}" if row.get("direction") else "")
                           + (f" · {row['edge_type']}" if row.get("edge_type") else ""))
        elif "score" in row or "similarity" in row:
            extra = st.dim(f"  {row.get('label', '')} {row.get('score', row.get('similarity', 0)):.2f}".rstrip())
        out += _note_lines(st, f"{i:>2}.", row, extra)
        out.append("")
    return "\n".join(out).rstrip()


def _render_graph_error(result: dict) -> str:
    st = ui.Style()
    out = [f"error: {result['error']}"]
    if result.get("suggestions"):
        out.append(st.dim("did you mean:"))
        out += [f"  {st.bold(h['title'] or '')}  {st.dim(h['path'] or '')}" for h in result["suggestions"]]
    return "\n".join(out)


def cmd_graph(args: argparse.Namespace) -> int:
    vault_path = _vault_or_fail(args)
    if vault_path is None:
        return 1
    binary = knowledge.gaiafield_binary()
    base = ["--vault", str(vault_path)]
    if not args.no_index:
        # Incremental and cheap; a query against a stale graph would answer about yesterday's vault.
        _, error = _engine_json(binary, "gaiafield", ["index", *base], knowledge.INDEX_TIMEOUT)
        if error:
            _error(args, f"index: {error}")
            return 1
    op = args.graph_command
    if op == "stats":
        argv, note = ["stats", *base], None
    elif op == "neighbors":
        argv, note = ["neighbors", args.note, *base, "--depth", str(args.depth), "--direction", args.direction], args.note
        if args.include_inferred:
            argv.append("--include-inferred")
    elif op == "path":
        argv, note = ["path", args.source, args.target, *base], None
        if args.include_inferred:
            argv.append("--include-inferred")
    else:
        argv, note = ["candidates", args.note, *base, "--k", str(args.limit)], args.note
        if args.include_ambiguous:
            argv.append("--include-ambiguous")
    data, error = _engine_json(binary, "gaiafield", argv, knowledge.STATS_TIMEOUT)
    if error:
        result = {"ok": False, "error": error}
        missing = re.search(r'No indexed note matches "(.+)"', error)
        if missing:
            # A dead end helps no one: offer the notes a search for the same words finds.
            asked = missing.group(1)
            hits, _ = _engine_json(knowledge.farsight_binary(), "farsight",
                                   ["query", *asked.replace("-", " ").split(), "--vault", str(vault_path), "--k", "5"],
                                   knowledge.QUERY_TIMEOUT)
            result["suggestions"] = [{"path": h.get("path"), "title": h.get("title")} for h in hits or []]
        _emit(result, args.json, _render_graph_error)
        return 1
    result = {"ok": True, "op": op, "vault": str(vault_path), "result": data}
    if note:
        result["note"] = note
    _emit(result, args.json, _render_graph)
    return 0


# --- link --------------------------------------------------------------------------------


def _render_link(result: dict) -> str:
    st = ui.Style()
    out = []
    for r in result["links"]:
        level = {"created": "ok", "updated": "ok", "removed": "info", "skipped": "warn"}[r["action"]]
        target = st.dim(f" → {r['target']}") if r.get("target") else ""
        note = st.dim(f"  ({r['note']})") if r.get("note") else ""
        out.append(f"  {st.mark(level)} {r['name']:<10} {r['action']:<8} {r['path']}{target}{note}")
    if result["vault"]:
        out.append(st.dim(f"  unisphere defaults to TOOLKIT_VAULT={result['vault']} (an exported value wins)"))
    if not result["on_path"]:
        out.append(f"  {st.mark('warn')} {result['bin_dir']} is not on PATH — add it to your shell profile")
    return "\n".join(out)


def cmd_link(args: argparse.Namespace) -> int:
    resolution = vault.resolve_vault()
    repo_root = resolution.repo_root or vault.find_repo_root(Path(__file__).resolve().parent)
    if repo_root is None:
        _error(args, "run from an agentic-toolkit checkout")
        return 1
    vault_path = Path(args.vault).expanduser().resolve() if args.vault else (
        resolution.path if resolution.source.startswith("env:") else None)
    bin_dir = Path(args.bin_dir).expanduser() if args.bin_dir else linker.default_bin_dir()
    try:
        result = linker.link(repo_root, bin_dir, vault_path, force=args.force)
    except OSError as exc:
        _error(args, str(exc))
        return 1
    _emit(result, args.json, _render_link)
    return 0 if result["ok"] else 1


# --- commands: the catalogue ------------------------------------------------------------

# What each command is, does and returns — the one declarative table behind both `--help` and
# `unisphere commands --json` (item 7: a new command with no entry here can't ship — see
# test_every_command_is_in_the_catalogue and test_every_command_has_real_help below). Every leaf
# command must have an entry; "group" only appears on the ones shown as their own row in the
# top-level COMMANDS listing (TOP_LEVEL, below) — a subcommand of `graph`/`engines` is reached
# through its parent's row instead, so it carries no group of its own.
CATALOG = {
    "status": {
        "summary": "Is everything current and healthy? Engines, plugins, vault, pipeline, companion CLIs.",
        "description": "One read-only sweep: the toolkit checkout, the engines (installed vs. latest release), "
                        "the Claude Code plugins installed from this marketplace, the vault (notes, DLQ, graph), "
                        "the obsidian pipeline's watchdog verdict when the vault runs one, and the companion "
                        "CLIs agents use next to unisphere. Touches the network only to check for newer engine "
                        "releases (skip with --offline); writes nothing.",
        "json": "{ok, problems[{section, detail}], toolkit, engines{engines[], cloud_pin}, plugins{plugins[{plugin, latest, "
                "state, installs[]}]}, vault{notes, inbox, dlq, graph}, pipeline{ok, problems, facts}, companions[]}",
        "examples": [
            ("unisphere status", "the full read for a person: what to look at, if anything"),
            ("unisphere status --offline", "skip the GitHub release check — no network"),
            ("unisphere status --json", "the same sweep as one object, for an agent"),
        ],
        "example": "unisphere status --json",
        "exit": "1 when problems is non-empty",
        "group": "Start here",
        "see_also": ["doctor", "engines status"],
    },
    "search": {
        "summary": "Ranked full-text (BM25) search over the vault's active notes (farsight).",
        "description": "Runs the farsight engine's BM25 ranking over the vault's active PARA folders "
                        "(02_Projects, 03_Areas, 04_Resources) and prints the best matches with their score. "
                        "Read-only, no network, needs `unisphere engines install` to have put farsight in place.",
        "json": "{ok, query, vault, results[{path, score, title, description}]}",
        "examples": [
            ("unisphere search agent memory", "the best-matching notes for those words"),
            ("unisphere search dead letter queue --limit 5", "fewer, tighter results"),
            ("unisphere search gaiafield --json", "the same search as parseable JSON"),
        ],
        "example": "unisphere search agent memory --limit 5 --json",
        "group": "Find things",
        "see_also": ["graph candidates"],
    },
    "graph stats": {
        "summary": "Graph size, dangling links, boundary violations and the most-linked notes (gaiafield).",
        "description": "Reports the shape of the vault's link graph after indexing it: node and edge counts, "
                        "dangling wikilinks, PARA boundary violations, and the most-linked notes. Read-only "
                        "against the graph; indexing itself only writes the local .gaiafield/graph.db cache.",
        "json": "{ok, op, vault, result{nodes, edges, dangling_edges, boundary_violations, top_linked[]}}",
        "examples": [
            ("unisphere graph stats", "a health check of the graph, for a person"),
            ("unisphere graph stats --json", "the same numbers as JSON, for an agent"),
        ],
        "example": "unisphere graph stats --json",
    },
    "graph neighbors": {
        "summary": "Notes linked to or from a note, out to a depth (gaiafield). NOTE is a path or a bare note name.",
        "description": "Walks the link graph from one note out to --depth hops, in the --direction given. NOTE "
                        "may be a vault-relative path or a bare note name (e.g. Gaiafield); an unresolved name "
                        "prints search suggestions instead of failing silently.",
        "json": "{ok, op, vault, note, result[{path, title, description, depth}]}",
        "examples": [
            ("unisphere graph neighbors Gaiafield", "one hop out, both directions"),
            ("unisphere graph neighbors Gaiafield --depth 2 --direction out", "two hops, outgoing links only"),
            ("unisphere graph neighbors Gaiafield --include-inferred --json", "also inferred edges, as JSON"),
        ],
        "example": "unisphere graph neighbors Gaiafield --depth 2 --json",
    },
    "graph path": {
        "summary": "Shortest link path between two notes (gaiafield).",
        "description": "Finds the shortest chain of links between two notes and prints it hop by hop, or reports "
                        "them unconnected. --include-inferred also traverses embedding-similarity edges, not "
                        "just explicit wikilinks.",
        "json": "{ok, op, vault, result{from, to, connected, path[]}}",
        "examples": [
            ("unisphere graph path Alex-Vega Gaiafield", "the shortest chain of explicit links"),
            ("unisphere graph path Alex-Vega Gaiafield --include-inferred", "also allow inferred edges"),
        ],
        "example": "unisphere graph path Alex-Vega Gaiafield --json",
    },
    "graph candidates": {
        "summary": "Same-topic notes with no link to this one yet — link suggestions (gaiafield infer must have run).",
        "description": "Surfaces notes that look like the same topic (by embedding similarity) but carry no link "
                        "to this one yet — the suggestions `obsidian:distill` turns into real links. Needs "
                        "`gaiafield infer` to have populated the graph first; an empty result usually means it hasn't.",
        "json": "{ok, op, vault, note, result[{path, score, label, kind, det_distance, surprise}]}",
        "examples": [
            ("unisphere graph candidates Gaiafield", "link suggestions for one note"),
            ("unisphere graph candidates Gaiafield --include-ambiguous", "also the lower-confidence band"),
            ("unisphere graph candidates Gaiafield --limit 5 --json", "fewer results, machine-readable"),
        ],
        "example": "unisphere graph candidates Gaiafield --json",
    },
    "doctor": {
        "summary": "The vault's structure: PARA folders, note counts, frontmatter errors, profiles, DLQ, graph.",
        "description": "A structural read of the active vault: which PARA folders exist and how many notes each "
                        "holds, any frontmatter that fails to parse, which plugins have a profile note, the DLQ "
                        "(dead-letter queue) and the graph's own health. Read-only; writes nothing.",
        "json": "{ok, vault_path, para_folders, note_counts, frontmatter_parse_errors[], profiles, dlq, graph}",
        "examples": [
            ("unisphere doctor", "a structural read of the active vault"),
            ("unisphere doctor --json", "the same read as JSON"),
        ],
        "example": "unisphere doctor --json",
        "group": "Start here",
        "see_also": ["status", "vault init"],
    },
    "profile": {
        "summary": "A plugin's resolved profile (defaults merged with the vault's Config/toolkit/<plugin>.md). Always JSON.",
        "description": "Resolves one plugin's configuration per contract/PROFILE.md: TOOLKIT_<PLUGIN>_<KEY> env "
                        "vars override the vault's Config/toolkit/<plugin>.md frontmatter, which overrides the "
                        "plugin's own defaults. Always prints JSON — this is a data command, not a status report.",
        "json": "{ok, plugin, vault_path, profile}",
        "examples": [
            ("unisphere profile obsidian", "the obsidian plugin's resolved settings"),
            ("unisphere profile radar", "the radar plugin's resolved settings"),
        ],
        "example": "unisphere profile obsidian",
        "group": "Set up",
    },
    "engines status": {
        "summary": "Installed vs. latest release of each engine (farsight, gaiafield).",
        "description": "Reads the local install manifest and, unless network access fails, GitHub's release "
                        "list, and reports each engine's installed tag against the latest one. Never downloads "
                        "anything — that's `engines install`/`engines update`.",
        "json": "{ok, engines[{engine, installed_tag, latest_tag, up_to_date, installed_path}]}",
        "examples": [
            ("unisphere engines status", "installed vs. latest, for a person"),
            ("unisphere engines status --json", "the same, for an agent"),
        ],
        "example": "unisphere engines status --json",
    },
    "engines install": {
        "summary": "Download, verify (sha256) and install the latest engine releases.",
        "description": "Downloads the latest farsight and gaiafield release for this platform from GitHub "
                        "Releases, checks each against its published sha256 (when the release carries one), and "
                        "installs it to the well-known engines dir. --force re-downloads even if already current.",
        "json": "{ok, results[{engine, ok, action, tag, path}]}",
        "examples": [
            ("unisphere engines install", "install whatever engines are missing or outdated"),
            ("unisphere engines install --force", "re-download and reverify even if already current"),
        ],
        "example": "unisphere engines install",
    },
    "engines update": {
        "summary": "Same as engines install: bring every engine to its latest release.",
        "description": "An alias for `engines install` — bring every engine to its latest release, "
                        "sha256-verified. Kept as its own subcommand since `update` reads better once "
                        "something is already installed.",
        "json": "{ok, results[{engine, ok, action, tag, path}]}",
        "examples": [
            ("unisphere engines update", "bring every engine to its latest release"),
            ("unisphere engines update --json", "the same, machine-readable"),
        ],
        "example": "unisphere engines update --json",
    },
    "vault init": {
        "summary": "Scaffold a new vault (PARA folders and AGENTS.md) at PATH.",
        "description": "Creates the PARA folder skeleton (00_Memory .. Templates) and an AGENTS.md at PATH, from "
                        "contract/templates/VAULT_AGENTS.md — the same scaffold a plugin then fills in. Refuses "
                        "a non-empty directory unless --force is given. Writes only under PATH.",
        "json": "{ok, path}",
        "examples": [
            ("unisphere vault init ~/Notes", "scaffold a new personal vault"),
            ("unisphere vault init ~/Notes --force", "scaffold into a directory that already has files"),
        ],
        "example": "unisphere vault init ~/Notes",
        "group": "Set up",
        "see_also": ["doctor", "link"],
    },
    "demo": {
        "summary": "Sixty seconds of first-hand value on the example vault: scan, search, graph, candidates.",
        "description": "Runs a real filesystem scan, then (once `unisphere engines install` has put binaries "
                        "in place) a real farsight search and gaiafield graph query against a real vault — the "
                        "bundled ./vault inside a checkout, or a tiny scaffolded one otherwise. No canned output.",
        "json": "{ok, steps[]}",
        "examples": [
            ("unisphere demo", "watch it work against a real vault"),
            ("unisphere demo --json", "the same steps as JSON"),
        ],
        "example": "unisphere demo",
        "group": "Start here",
        "see_also": ["status", "vault init"],
    },
    "link": {
        "summary": "Put unisphere, the engines and Obsidian's CLI on PATH (~/.local/bin); --vault sets its default vault.",
        "description": "Writes small shims in --bin-dir (default ~/.local/bin) for unisphere itself, the "
                        "installed engines, and Obsidian's bundled CLI when present, so they all run without "
                        "`uv run` or a PATH edit. --vault bakes a default TOOLKIT_VAULT into the unisphere shim; "
                        "an exported TOOLKIT_VAULT still overrides it. Never overwrites a file it didn't write "
                        "itself unless --force is given.",
        "json": "{ok, bin_dir, on_path, vault, links[{name, path, action, target}]}",
        "examples": [
            ("unisphere link --vault ~/Notes", "put everything on PATH, default to this vault"),
            ("unisphere link --bin-dir ~/bin", "link into a different bin directory"),
        ],
        "example": "unisphere link --vault ~/Notes",
        "group": "Set up",
    },
    "commands": {
        "summary": "This catalogue: every command, its arguments, its JSON, and the companion CLIs.",
        "description": "Prints the same declarative table that drives `--help` everywhere in this CLI: every "
                        "command's summary, arguments, JSON shape and examples, plus the companion CLIs "
                        "(tvly, obsidian, td) next to it. The starting point for an agent that hasn't used "
                        "unisphere before.",
        "json": "{ok, conventions, commands[{name, summary, group, arguments[], json, example, examples[]}], companions[]}",
        "examples": [
            ("unisphere commands --json", "the full catalogue, for an agent"),
            ("unisphere commands", "the same catalogue, for a person skimming it"),
        ],
        "example": "unisphere commands --json",
        "group": "For agents",
    },
    "version": {
        "summary": "unisphere's own version, plus each installed engine's (no network).",
        "description": "Prints the installed toolkit-core package version and, from the local install manifest "
                        "only (no network call), each engine's installed release tag. Use `engines status` "
                        "instead to also check what's newest upstream.",
        "json": "{ok, unisphere, engines[{engine, installed_tag}]}",
        "examples": [
            ("unisphere --version", "the short form"),
            ("unisphere version --json", "the same, machine-readable"),
        ],
        "example": "unisphere --version",
        "group": "Start here",
        "see_also": ["engines status"],
    },
}

# Parent commands with their own subcommands (graph, engines, vault) aren't in CATALOG — that
# dict is leaf-only (test_every_command_is_in_the_catalogue depends on it) — but their own
# `--help` page still needs a description, a group and a couple of examples spanning their
# subcommands. Their subcommand rows come straight out of CATALOG at render time, so there is
# nothing here for those to drift against.
GROUP_HELP = {
    "graph": {
        "summary": "The vault's link graph: stats, neighbors, shortest path, link candidates (gaiafield).",
        "description": "Wraps the gaiafield engine's read side. Indexes the vault first — incremental and "
                        "cheap, skip with --no-index — so every answer reflects the notes on disk, not "
                        "yesterday's graph, then runs one of: stats, neighbors, path or candidates.",
        "group": "Find things",
        "examples": [
            ("unisphere graph stats", "size, dangling links, most-linked notes"),
            ("unisphere graph neighbors Gaiafield --depth 2", "notes linked to/from Gaiafield, two hops out"),
            ("unisphere graph path Alex-Vega Gaiafield", "the shortest chain of links between two notes"),
        ],
        "see_also": ["search", "doctor"],
    },
    "engines": {
        "summary": "Install, update and check the Rust engines that power search and graph (farsight, gaiafield).",
        "description": "Downloads sha256-verified engine binaries from GitHub Releases into the well-known "
                        "install dir (unisphere link puts them on PATH too), and reports installed vs. latest "
                        "so `unisphere status` and this command never disagree.",
        "group": "Set up",
        "examples": [
            ("unisphere engines status", "installed vs. latest release of each engine"),
            ("unisphere engines install", "fetch and verify the latest release of each engine"),
        ],
        "see_also": ["status", "link"],
    },
    "vault": {
        "summary": "Scaffold a new vault (PARA folders and AGENTS.md).",
        "description": "The one vault-creation command; everything else (search, graph, doctor, profile) reads "
                        "an existing vault, found via TOOLKIT_VAULT or the repo's own ./vault.",
        "group": "Set up",
        "examples": [
            ("unisphere vault init ~/Notes", "scaffold a new personal vault"),
        ],
        "see_also": ["doctor", "link"],
    },
}

# The bare `unisphere` COMMANDS listing, grouped by task and in display order. Each row is
# either a CATALOG leaf key (a command with no subcommands of its own, or "vault init" — vault's
# one subcommand, shown directly since a bare "vault" row would say nothing "graph"/"engines"
# don't already say better with "…") or a GROUP_HELP parent key ("graph", "engines").
TOP_LEVEL: list[tuple[str, str]] = [
    ("status", "Start here"),
    ("demo", "Start here"),
    ("doctor", "Start here"),
    ("version", "Start here"),
    ("search", "Find things"),
    ("graph", "Find things"),
    ("vault init", "Set up"),
    ("link", "Set up"),
    ("engines", "Set up"),
    ("profile", "Set up"),
    ("commands", "For agents"),
]

GLOBAL_FLAGS = [
    ("--json", "Print machine-readable JSON instead of text (every command)"),
    ("-h, --help", "Show this help, or a command's — same as `unisphere help [command]`"),
    ("--version", "Print unisphere's version and exit — same as `unisphere version`"),
]

# Env vars the CLI (or a module it calls directly) actually reads — grepped, not guessed.
ENVIRONMENT = [
    ("TOOLKIT_VAULT", "The active vault. Unset: the repo's own ./vault."),
    ("TOOLKIT_GAIAFIELD_BIN", "Path to the gaiafield binary. Unset: PATH, then the engines install dir."),
    ("TOOLKIT_FARSIGHT_BIN", "Path to the farsight binary. Unset: PATH, then the engines install dir."),
    ("TOOLKIT_<PLUGIN>_<KEY>", "Overrides one profile field for a plugin, e.g. TOOLKIT_OBSIDIAN_MODEL."),
    ("XDG_DATA_HOME", "Where `engines install` puts binaries. Unset: ~/.local/share."),
    ("CLAUDE_CONFIG_DIR", "Where Claude Code's plugin registry lives, for `status`'s PLUGINS section."),
    ("NO_COLOR", "Any value disables colour, even on a TTY (https://no-color.org)."),
    ("FORCE_COLOR", "Forces colour on even off a TTY, e.g. for a captured sample. NO_COLOR still wins."),
    ("UNISPHERE_ASCII", "Forces plain ASCII glyphs (*, x, !) even on a terminal that looks emoji-capable."),
    ("FORCE_HYPERLINK", "Forces clickable OSC 8 links in `help`/`--help` even off a detected terminal."),
]

COMPANIONS = [
    {
        "cli": "tvly",
        "use_for": "Tavily, the toolkit's one way to the web beyond the vault: search, extract a page, crawl or map "
                   "a site, deep research. The radar and distill call it through their scripts.",
        "not_for": "Anything in the vault — use unisphere search / unisphere graph.",
        "setup": "uv tool install tavily-cli; it reads TAVILY_API_KEY (unisphere link needs nothing more).",
        "discover": "tvly --help",
        "agent_tips": ["pass --json for parseable output", "search: --depth basic (1 credit), --time-range, "
                       "--include-domains", "extract: tvly extract <url> --format markdown --json"],
    },
    {
        "cli": "obsidian",
        "use_for": "The running Obsidian app: open a note, the daily note, search in the app, run an Obsidian command, "
                   "read or change a note through Obsidian so plugins and the UI see it.",
        "not_for": "Search and link analysis over the vault files — use unisphere search / unisphere graph (no app needed).",
        "setup": "Obsidian 1.12+: Settings → General → Advanced → Command line interface; unisphere link puts it on PATH.",
        "discover": "obsidian help",
    },
    {
        "cli": "td",
        "use_for": "Todoist: today's and upcoming tasks, adding and completing tasks, projects, labels.",
        "not_for": "Notes — tasks live in Todoist, knowledge in the vault; link one from the other by URL.",
        "setup": "npm install -g @doist/todoist-cli, then td auth login.",
        "discover": "td --help",
        "agent_tips": ["pass --json (or --ndjson) for parseable output", "use `td task add` with flags, not `td add`",
                       "--ids-only on list commands when only ids are needed"],
    },
]


def _leaf_commands(parser: argparse.ArgumentParser, prefix: str = "") -> list[tuple[str, argparse.ArgumentParser]]:
    sub = next((a for a in parser._actions if isinstance(a, argparse._SubParsersAction)), None)
    if sub is None:
        return [(prefix, parser)]
    leaves = []
    for name, child in sub.choices.items():
        leaves += _leaf_commands(child, f"{prefix} {name}".strip())
    return leaves


def _arguments(parser: argparse.ArgumentParser) -> list[dict]:
    out = []
    for action in parser._actions:
        if isinstance(action, (argparse._HelpAction, argparse._SubParsersAction)) or action.dest == "json":
            continue
        arg = {"name": action.dest if not action.option_strings else action.option_strings[-1],
               "positional": not action.option_strings, "help": action.help or ""}
        if action.nargs in ("+", "*"):
            arg["repeatable"] = True
        if isinstance(action, argparse._StoreTrueAction):
            arg["flag"] = True
        elif action.option_strings and action.default is not None:
            arg["default"] = action.default
        if action.choices:
            arg["choices"] = list(action.choices)
        out.append(arg)
    return sorted(out, key=lambda a: not a["positional"])


def catalog(parser: argparse.ArgumentParser) -> dict:
    commands = []
    for name, sub in _leaf_commands(parser):
        entry = CATALOG[name]
        commands.append({"name": name, "summary": entry["summary"], "description": entry["description"],
                         "arguments": _arguments(sub), "json": entry["json"], "example": entry["example"],
                         "examples": [f"{cmd}  # {note}" for cmd, note in entry["examples"]],
                         **({"group": entry["group"]} if "group" in entry else {}),
                         **({"exit": entry["exit"]} if "exit" in entry else {})})
    return {
        "ok": True,
        "conventions": {
            "json": "add --json to any command for one JSON object on stdout; text output is for people and may change",
            "exit_codes": {"0": "ok", "1": "a problem or an error — the JSON carries ok:false and error or problems",
                           "2": "usage error"},
            "vault": "TOOLKIT_VAULT, else ./vault at the repo root",
            "errors": "{ok: false, error: <message>}",
        },
        "commands": commands,
        "companions": COMPANIONS,
    }


def _render_catalog(result: dict) -> str:
    st = ui.Style()
    out = [st.bold("unisphere") + st.dim(" — every command takes --json for agents"), ""]
    wide = max(len(c["name"]) for c in result["commands"])
    for c in result["commands"]:
        args = " ".join(a["name"].upper() if a["positional"] else f"[{a['name']}]" for a in c["arguments"])
        out.append(f"  {st.accent(c['name'].ljust(wide))}  {c['summary']}")
        if args:
            out.append(f"  {' ' * wide}  {st.dim(args)}")
    out += ["", st.bold("companion CLIs")]
    for c in result["companions"]:
        out.append(f"  {st.accent(c['cli'].ljust(wide))}  {c['use_for']}")
        out.append(f"  {' ' * wide}  {st.dim('setup: ' + c['setup'])}")
    out += ["", st.dim("agents: unisphere commands --json · exit 0 ok, 1 problem/error, 2 usage")]
    return "\n".join(out)


def cmd_commands(args: argparse.Namespace) -> int:
    _emit(catalog(_build_parser()), args.json, _render_catalog)
    return 0


# --- argument parsing ------------------------------------------------------------------


class _UsageError(Exception):
    """Raised by `_Parser.error()` instead of argparse's own print-usage-and-exit(2), so `main()`
    can render one consistent gh-style error (a one-liner, the USAGE line, a hint) for every
    parser and subparser alike — bad flag values and missing required arguments included, not
    just the unknown-command case `main()` already catches earlier by walking the command tree."""

    def __init__(self, parser: argparse.ArgumentParser, message: str):
        super().__init__(message)
        self.parser = parser
        self.message = message


class _Parser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        # Python 3.13+ colorizes argparse's own format_usage()/format_help() the same way we
        # do (it honours FORCE_COLOR/NO_COLOR too), which would double-colour every usage line
        # `_colorize_usage_line` builds from it. `color=False` is a 3.13+-only kwarg; older
        # Python's argparse never colourized anything, so a TypeError there just means it's
        # already off. [earned: 2026-09-28 — a real FORCE_COLOR capture showed nested escapes
        # and a literal stray "usage:" inside the coloured USAGE line]
        kwargs.setdefault("color", False)
        try:
            super().__init__(*args, **kwargs)
        except TypeError:
            kwargs.pop("color", None)
            super().__init__(*args, **kwargs)

    # Matches argparse's own "the following arguments are required: <dest>" message when the
    # missing argument is one of this file's `add_subparsers(dest=...)` calls (`command`,
    # `vault_command`, `graph_command`, `engines_command`) — never a real positional's dest
    # (`note`, `path`, `plugin`, ...), which argparse phrases the same way but whose name IS the
    # right word to show a user. [battle-test 2026-09-28: `unisphere vault`/`graph`/`engines`
    # with no subcommand leaked "vault_command"/"graph_command"/"engines_command" — an internal
    # Python variable name, not anything a user typed or would recognise]
    _MISSING_SUBCOMMAND_RE = re.compile(r"^the following arguments are required: (\w*_?command)$")

    def error(self, message: str) -> None:  # type: ignore[override]
        if self._MISSING_SUBCOMMAND_RE.match(message):
            message = "a subcommand is required"
        raise _UsageError(self, message)


def _build_parser() -> argparse.ArgumentParser:
    # add_help=False everywhere: `main()` walks argv for "-h"/"--help" itself (see `_walk_command`)
    # so every level renders the same styled help — argparse's own [-h] auto-action never fires.
    common = _Parser(add_help=False)
    common.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of text")

    parser = _Parser(
        prog="unisphere", parents=[common], add_help=False,
        description="unisphere — the network your notes, agents and engines connect through.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    vault_parser = subparsers.add_parser("vault", parents=[common], add_help=False, help=GROUP_HELP["vault"]["summary"])
    vault_subparsers = vault_parser.add_subparsers(dest="vault_command", required=True, parser_class=_Parser)
    init_parser = vault_subparsers.add_parser("init", parents=[common], add_help=False, help=CATALOG["vault init"]["summary"])
    init_parser.add_argument("path", help="Directory to scaffold the vault into")
    init_parser.add_argument("--force", action="store_true", help="Scaffold even if the directory already has files")

    subparsers.add_parser("doctor", parents=[common], add_help=False, help=CATALOG["doctor"]["summary"])

    profile_parser = subparsers.add_parser("profile", parents=[common], add_help=False, help=CATALOG["profile"]["summary"])
    profile_parser.add_argument("plugin", help="Plugin name to resolve a profile for, e.g. obsidian")

    engines_parser = subparsers.add_parser("engines", parents=[common], add_help=False, help=GROUP_HELP["engines"]["summary"])
    engines_subparsers = engines_parser.add_subparsers(dest="engines_command", required=True, parser_class=_Parser)
    for name in ("install", "update"):
        sub = engines_subparsers.add_parser(name, parents=[common], add_help=False, help=CATALOG[f"engines {name}"]["summary"])
        sub.add_argument("--force", action="store_true",
                          help="Re-download even if the installed release is already the latest")
    engines_subparsers.add_parser("status", parents=[common], add_help=False, help=CATALOG["engines status"]["summary"])

    subparsers.add_parser("demo", parents=[common], add_help=False, help=CATALOG["demo"]["summary"])

    subparsers.add_parser("version", parents=[common], add_help=False, help=CATALOG["version"]["summary"])

    status_parser = subparsers.add_parser("status", parents=[common], add_help=False, help=CATALOG["status"]["summary"])
    status_parser.add_argument("--offline", action="store_true",
                                help="Skip the GitHub check for newer engine releases (no network)")

    search_parser = subparsers.add_parser("search", parents=[common], add_help=False, help=CATALOG["search"]["summary"])
    search_parser.add_argument("terms", nargs="+", help="One or more query words")
    search_parser.add_argument("--limit", type=int, default=10, help="Maximum number of results to show (default: 10)")

    graph_parser = subparsers.add_parser("graph", parents=[common], add_help=False, help=GROUP_HELP["graph"]["summary"])
    graph_subparsers = graph_parser.add_subparsers(dest="graph_command", required=True, parser_class=_Parser)
    graph_common = _Parser(add_help=False, parents=[common])
    graph_common.add_argument("--no-index", action="store_true",
                               help="Query the graph as currently indexed, without refreshing it first")
    graph_subparsers.add_parser("stats", parents=[graph_common], add_help=False, help=CATALOG["graph stats"]["summary"])
    sub = graph_subparsers.add_parser("neighbors", parents=[graph_common], add_help=False,
                                       help=CATALOG["graph neighbors"]["summary"])
    sub.add_argument("note", help="A vault-relative note path or a bare note name (e.g. Gaiafield)")
    sub.add_argument("--depth", type=int, default=1, help="How many hops out to follow (default: 1)")
    sub.add_argument("--direction", choices=("in", "out", "both"), default="both",
                      help="Follow links into the note, out of it, or both (default: both)")
    sub.add_argument("--include-inferred", action="store_true",
                      help="Also include inferred (embedding-similarity) edges, not just explicit links")
    sub = graph_subparsers.add_parser("path", parents=[graph_common], add_help=False, help=CATALOG["graph path"]["summary"])
    sub.add_argument("source", help="The note to start from")
    sub.add_argument("target", help="The note to reach")
    sub.add_argument("--include-inferred", action="store_true",
                      help="Also traverse inferred edges, not just explicit links")
    sub = graph_subparsers.add_parser("candidates", parents=[graph_common], add_help=False,
                                       help=CATALOG["graph candidates"]["summary"])
    sub.add_argument("note", help="A vault-relative note path or a bare note name (e.g. Gaiafield)")
    sub.add_argument("--limit", type=int, default=10, help="Maximum number of candidates to show (default: 10)")
    sub.add_argument("--include-ambiguous", action="store_true", help="Also include the lower-confidence AMBIGUOUS band")

    link_parser = subparsers.add_parser("link", parents=[common], add_help=False, help=CATALOG["link"]["summary"])
    link_parser.add_argument("--vault", help="Vault the unisphere shim defaults to (an exported TOOLKIT_VAULT still wins)")
    link_parser.add_argument("--bin-dir", help="Where to write the shims (default: ~/.local/bin)")
    link_parser.add_argument("--force", action="store_true", help="Replace files already there that unisphere did not write")

    subparsers.add_parser("commands", parents=[common], add_help=False, help=CATALOG["commands"]["summary"])

    return parser


# --- help, usage and version -------------------------------------------------------------
#
# Every level (bare `unisphere`, `unisphere <command>`, `unisphere <command> <subcommand>`)
# renders through the same handful of functions below, built from CATALOG/GROUP_HELP — never
# argparse's own `-h`/`--help` action (every parser above is `add_help=False`; `main()` scans
# argv for "-h"/"--help" itself via `_walk_command`, so a typo'd subcommand plus `--help` still
# gets a "did you mean" rather than a help page for a command that doesn't exist).


def _prog(path: list[str]) -> str:
    return "unisphere" if not path else "unisphere " + " ".join(path)


def _walk_command(parser: argparse.ArgumentParser, tokens: list[str]):
    """Consume leading `tokens` that name a subcommand, as far as they go — one step per
    nested subparsers level (graph -> neighbors, vault -> init, ...). Returns
    `(path, deepest_parser_reached, its_subparsers_action_or_None, remaining_tokens)`."""
    path: list[str] = []
    node = parser
    remaining = list(tokens)
    while True:
        sub = next((a for a in node._actions if isinstance(a, argparse._SubParsersAction)), None)
        if sub is None or not remaining or remaining[0] not in sub.choices:
            return path, node, sub, remaining
        name = remaining[0]
        path.append(name)
        node = sub.choices[name]
        remaining = remaining[1:]


def _colorize_usage_line(st: ui.Style, parser: argparse.ArgumentParser) -> str:
    """argparse already knows how to lay out a usage line correctly (bracket nesting, wrapping
    choice); this just re-colours its tokens — flags in the flag colour, placeholders
    underlined — rather than hand-building one and risking it drifting from the real parser."""
    raw = re.sub(r"\s+", " ", parser.format_usage().removeprefix("usage: ").strip())
    prog = parser.prog
    rest = raw[len(prog) :].strip() if raw.startswith(prog) else raw
    toks = []
    for tok in (rest.split(" ") if rest else []):
        lead = ""
        while tok and tok[0] in "[{":
            lead, tok = lead + tok[0], tok[1:]
        trail = ""
        while tok and tok[-1] in "]}":
            trail, tok = tok[-1] + trail, tok[:-1]
        if tok.startswith("-"):
            tok = st.flag(tok)
        elif tok:
            tok = st.metavar(tok)
        toks.append(lead + tok + trail)
    return (st.command(prog) + " " + " ".join(toks)).rstrip()


def _flag_label(arg: dict) -> str:
    if arg.get("flag"):
        return arg["name"]
    meta = "|".join(arg["choices"]) if arg.get("choices") else arg["name"].lstrip("-").upper().replace("-", "_")
    return f"{arg['name']} {meta}"


_EXAMPLE_COMMENT_CAP = 48  # brew/kubectl-style: align comments to one column, but not past this


def _example_lines(examples: list[tuple[str, str]], st: ui.Style | None = None) -> list[str]:
    """EXAMPLES rows, comments aligned to one column the way brew/kubectl do it: the pad is the
    longest command in *this* block plus 2, capped at `_EXAMPLE_COMMENT_CAP`. A command past the
    cap gets its comment dimmed on the next line instead of pushing the whole column out."""
    st = st or ui.Style()
    short = [len(cmd) for cmd, _ in examples if len(cmd) <= _EXAMPLE_COMMENT_CAP]
    pad = min(max(short, default=_EXAMPLE_COMMENT_CAP) + 2, _EXAMPLE_COMMENT_CAP)
    out = []
    for cmd, note in examples:
        comment = st.dim(f"# {note}")
        if len(cmd) > _EXAMPLE_COMMENT_CAP:
            out.append(f"  {cmd}")
            out.append(f"      {comment}")
        else:
            out.append(f"  {cmd.ljust(pad)}  {comment}")
    return out


def _see_also_lines(st: ui.Style, entry: dict) -> list[str]:
    if not entry.get("see_also"):
        return []
    return ["", st.heading("SEE ALSO"), "  " + ", ".join(f"unisphere {s}" for s in entry["see_also"])]


_GROUP_GLYPH = {"Start here": "start", "Find things": "find", "Set up": "setup", "For agents": "agents"}
_TOP_EXAMPLE_KEYS = ["status", "search", "graph neighbors", "vault init", "link", "commands"]


def _top_level_help_text(st: ui.Style) -> str:
    out = [st.bold("unisphere") + " — the network your notes, agents and engines connect through."]
    out += ui.wrap(
        "The agentic-toolkit's front door for people and agents: the vault, its search and graph, "
        "the engines, plugins and pipeline health.", 0)
    out += ["", st.heading("USAGE"),
            f"  {st.command('unisphere')} {st.metavar('<command>')} {st.metavar('[subcommand]')} {st.dim('[flags]')}",
            "", st.heading("COMMANDS")]

    groups: list[str] = []
    for _, group in TOP_LEVEL:
        if group not in groups:
            groups.append(group)
    wide = max(len(name) for name, _ in TOP_LEVEL)
    for group in groups:
        gl = term.glyph(_GROUP_GLYPH[group])
        out.append(f"  {st.dim((gl + ' ' + group) if gl else group)}")
        for name, row_group in TOP_LEVEL:
            if row_group != group:
                continue
            summary = CATALOG[name]["summary"] if name in CATALOG else GROUP_HELP[name]["summary"]
            out += ui.wrap_field(f"    {st.command(name.ljust(wide))}  ", summary)
        out.append("")

    out.append(st.heading("GLOBAL FLAGS"))
    fw = max(len(f) for f, _ in GLOBAL_FLAGS)
    for f, desc in GLOBAL_FLAGS:
        out += ui.wrap_field(f"  {st.flag(f.ljust(fw))}  ", desc)

    out += ["", st.heading("EXAMPLES")]
    out += _example_lines([CATALOG[key]["examples"][0] for key in _TOP_EXAMPLE_KEYS], st)

    out += ["", st.heading("ENVIRONMENT")]
    ew = max(len(n) for n, _ in ENVIRONMENT)
    for n, desc in ENVIRONMENT:
        out += ui.wrap_field(f"  {st.flag(n.ljust(ew))}  ", desc)

    docs_url = "https://marsmike.github.io/agentic-toolkit/"
    book = term.glyph("book")
    out += ["", st.heading("LEARN MORE"),
            "  unisphere help <command>       more about any command, same as `<command> --help`",
            "  unisphere commands --json      the full catalogue — arguments, JSON, examples — for an agent",
            f"  {(book + ' ') if book else ''}{term.link(docs_url)}"]
    return "\n".join(out)


def _leaf_help_text(path: list[str], parser: argparse.ArgumentParser, st: ui.Style) -> str:
    name = " ".join(path)
    entry = CATALOG[name]
    out = [st.bold(f"unisphere {name}") + " — " + entry["summary"], ""]
    out += ui.wrap(entry["description"], 0)
    out += ["", st.heading("USAGE"), "  " + _colorize_usage_line(st, parser)]

    args = _arguments(parser)
    positionals = [a for a in args if a["positional"]]
    flags = [a for a in args if not a["positional"]]
    if positionals:
        out += ["", st.heading("ARGUMENTS")]
        w = max(len(a["name"]) for a in positionals)
        for a in positionals:
            out += ui.wrap_field(f"  {st.metavar(a['name'].upper().ljust(w))}  ", a["help"])
    if flags:
        out += ["", st.heading("FLAGS")]
        labelled = [(a, _flag_label(a)) for a in flags]
        w = max(len(lbl) for _, lbl in labelled)
        for a, lbl in labelled:
            out += ui.wrap_field(f"  {st.flag(lbl.ljust(w))}  ", a["help"])

    out += ["", st.heading("EXAMPLES")]
    out += _example_lines(entry["examples"], st)
    out += ["", st.dim("JSON: --json prints ") + entry["json"]]
    out += _see_also_lines(st, entry)
    return "\n".join(out)


def _parent_help_text(path: list[str], sub: argparse._SubParsersAction, st: ui.Style) -> str:
    name = " ".join(path)
    entry = GROUP_HELP[name]
    out = [st.bold(f"unisphere {name}") + " — " + entry["summary"], ""]
    out += ui.wrap(entry["description"], 0)
    out += ["", st.heading("USAGE"), f"  {st.command('unisphere ' + name)} {st.metavar('<command>')} {st.dim('[flags]')}"]

    out += ["", st.heading("COMMANDS")]
    wide = max(len(c) for c in sub.choices)
    for sub_name in sub.choices:
        out += ui.wrap_field(f"  {st.command(sub_name.ljust(wide))}  ", CATALOG[f"{name} {sub_name}"]["summary"])

    out += ["", st.heading("EXAMPLES")]
    out += _example_lines(entry["examples"], st)
    out += _see_also_lines(st, entry)
    return "\n".join(out)


def _print_command_help(path: list[str], node: argparse.ArgumentParser, st: ui.Style) -> None:
    if not path:
        print(_top_level_help_text(st))
        return
    sub = next((a for a in node._actions if isinstance(a, argparse._SubParsersAction)), None)
    print(_parent_help_text(path, sub, st) if sub is not None else _leaf_help_text(path, node, st))


def _unknown_command_error(path: list[str], bad: str, choices, st: ui.Style) -> int:
    prog = _prog(path)
    print(st.err(f'unknown command "{bad}" for "{prog}"'), file=sys.stderr)
    close = difflib.get_close_matches(bad, list(choices), n=1)
    if close:
        tip = term.glyph("tip")
        print(st.good(f"{(tip + ' ') if tip else ''}Did you mean this?"), file=sys.stderr)
        print(f"  {st.command(close[0])}", file=sys.stderr)
    print(st.dim(f"Run '{prog} --help' for usage."), file=sys.stderr)
    return 2


def _usage_error(exc: _UsageError, st: ui.Style) -> int:
    """Every other parser failure (a missing required argument, an invalid --flag value, an
    unrecognized flag): one line, that command's USAGE, a pointer to its --help — not argparse's
    own multi-line usage-plus-message dump."""
    print(st.err(f"error: {exc.message}"), file=sys.stderr)
    print("  " + _colorize_usage_line(st, exc.parser), file=sys.stderr)
    print(st.dim(f"Run '{exc.parser.prog} --help' for more."), file=sys.stderr)
    return 2


def cmd_help(rest: list[str], st: ui.Style) -> int:
    path, node, sub, leftover = _walk_command(_build_parser(), rest)
    if leftover:
        return _unknown_command_error(path, leftover[0], sub.choices if sub is not None else {}, st)
    _print_command_help(path, node, st)
    return 0


def _unisphere_version() -> str:
    try:
        return importlib.metadata.version("toolkit-core")
    except importlib.metadata.PackageNotFoundError:
        try:
            import tomllib

            pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
            return tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
        except (OSError, KeyError, ValueError):
            return "unknown"


def _render_version(result: dict) -> str:
    st = ui.Style()
    lines = [f"{st.bold('unisphere')} {st.good(result['unisphere'])}"]
    for row in result["engines"]:
        tag = row["installed_tag"]
        lines.append(f"  {row['engine']:<10} {tag if tag else st.dim('not installed')}")
    return "\n".join(lines)


def cmd_version(as_json: bool) -> int:
    """Installed versions only — no network. `engines status` also checks what's newest upstream."""
    rows = [{"engine": r["engine"], "installed_tag": r["installed_tag"]} for r in engines.status_all(fetch=False)]
    _emit({"ok": True, "unisphere": _unisphere_version(), "engines": rows}, as_json, _render_version)
    return 0


def _startup_line(st: ui.Style) -> None:
    """One line on a bare `unisphere`, TTY only: what vault is linked, its size, and how many
    cloud routines ("u-shadows") watch over it — every part read straight from disk/local db,
    nothing over the network, and any part that can't be read is dropped rather than failing
    the whole line."""
    if not term.is_tty():
        return
    try:
        parts = [st.bold(f"{term.glyph('node')} UNISPHERE".strip())]
        resolution = vault.resolve_vault()
        repo_root = resolution.repo_root or vault.find_repo_root(Path(__file__).resolve().parent)
        if resolution.path and resolution.path.is_dir():
            parts.append(f"linked to {resolution.path.name}")
            total = sum(vault.note_counts(resolution.path).values())
            if total:
                parts.append(f"{total:,} worlds")
            graph = knowledge.graph_status(resolution.path)
            if graph.get("present") and graph.get("edges") is not None:
                parts.append(f"{graph['edges']:,} wormholes")
        routines_file = repo_root / "cloud" / "routines.json" if repo_root else None
        if routines_file and routines_file.is_file():
            n = len(json.loads(routines_file.read_text(encoding="utf-8")).get("routines") or [])
            if n:
                parts.append(f"{n} u-shadow{'' if n == 1 else 's'}")
        print(st.dim(" · ").join(parts))
        print()
    except Exception:  # noqa: BLE001 - a startup banner must never be the reason unisphere fails
        pass


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    st = ui.Style()

    if not argv:
        _startup_line(st)
        print(_top_level_help_text(st))
        return 0
    if argv[0] in ("-h", "--help"):
        print(_top_level_help_text(st))
        return 0
    if argv[0] == "help":
        return cmd_help(argv[1:], st)
    if argv[0] == "--version":
        return cmd_version("--json" in argv[1:])

    parser = _build_parser()
    path, node, sub, rest = _walk_command(parser, argv)

    help_requested = (rest and rest[0] in ("-h", "--help")) or bool(path) and any(t in ("-h", "--help") for t in rest)
    if help_requested:
        _print_command_help(path, node, st)
        return 0

    if rest and sub is not None and not rest[0].startswith("-") and rest[0] not in sub.choices:
        return _unknown_command_error(path, rest[0], sub.choices, st)

    try:
        args, extras = parser.parse_known_args(argv)
    except _UsageError as exc:
        return _usage_error(exc, st)
    if extras:
        # `parser.parse_args()` would raise this "unrecognized arguments" error itself, but
        # always attributed to the top-level parser regardless of which subparser actually
        # rejected the flag (an argparse quirk: only the outermost parse_args() call checks for
        # leftovers, so self.error() always means the outermost self). `node` is the deepest
        # subparser `_walk_command` actually resolved for this argv, so its own usage/prog shows
        # up in the error instead of unisphere's top-level one. [battle-test 2026-09-28:
        # `unisphere search --unknown-flag foo` showed the top-level USAGE listing every command,
        # not `unisphere search`'s]
        try:
            node.error(f"unrecognized arguments: {' '.join(extras)}")
        except _UsageError as exc:
            return _usage_error(exc, st)

    if args.command == "vault" and args.vault_command == "init":
        return cmd_vault_init(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "profile":
        return cmd_profile(args)
    if args.command == "engines":
        if args.engines_command in ("install", "update"):
            return cmd_engines_install(args)
        if args.engines_command == "status":
            return cmd_engines_status(args)
    if args.command == "demo":
        return cmd_demo(args)
    if args.command == "version":
        return cmd_version(args.json)
    handlers = {"status": cmd_status, "search": cmd_search, "graph": cmd_graph, "link": cmd_link, "commands": cmd_commands}
    if args.command in handlers:
        return handlers[args.command](args)

    print(_top_level_help_text(st))  # unreached in practice: every parser choice is handled above
    return 1


if __name__ == "__main__":
    sys.exit(main())
