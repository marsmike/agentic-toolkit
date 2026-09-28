"""`unisphere` (alias `toolkit`): one front door to the vault, its engines and the plugins, for people
and agents. Named for the Commonwealth's unisphere, the network everything connects through, next to
the engines' own Hamilton names (farsight, gaiafield). `toolkit` stays as an alias, so every existing
script, skill and routine that calls it keeps working.

People get readable, coloured text (colour only on a TTY; NO_COLOR is honoured). Agents pass
`--json` to any command for a stable object, and start from `unisphere commands --json`: every
command, its arguments, what its JSON carries, and the companion CLIs next to it. Exit codes:
0 ok, 1 a problem or an error (the JSON says which), 2 a usage error.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from toolkit_core import demo, engines, knowledge, profile, status, ui, vault
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
        result = {
            "ok": False,
            "error": "could not locate contract/templates/VAULT_AGENTS.md (repo root not found)",
        }
        _emit(result, args.json, lambda r: f"error: {r['error']}")
        return 1

    try:
        vault.scaffold_vault(target, template_path, force=args.force)
    except vault.VaultInitError as exc:
        result = {"ok": False, "error": str(exc)}
        _emit(result, args.json, lambda r: f"error: {r['error']}")
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
        result = {
            "ok": False,
            "error": "no vault found: set TOOLKIT_VAULT, or run from inside the agentic-toolkit repo",
        }
        _emit(result, args.json, lambda r: f"error: {r['error']}")
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
    # `toolkit profile` always prints JSON: it's a data command, not a status report.
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
            mark = "run: toolkit engines install"
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

    p = result["pipeline"]
    if p.get("present"):
        if not p.get("checked"):
            rows = [f"{st.mark('warn')} {p['note']}"]
        else:
            f = p.get("facts", {})
            rows = []
            if f.get("last_run"):
                rows.append(f"{st.mark('ok' if p.get('ok') else 'warn')} last run {f['last_run'][:16].replace('T', ' ')} UTC"
                            + st.dim(f" ({f.get('age_hours')} h ago) — {f.get('last_summary', '')}"))
            if f.get("signal_last"):
                rows.append(f"{st.mark('info')} radar {f['signal_last']}" + st.dim(f" ({f.get('signal_age_hours')} h ago)"))
            rows += [f"{st.mark('bad')} {item.get('detail')}" for item in p.get("problems", [])]
        out += ui.section(st, "PIPELINE", rows)

    rows = []
    for c in result["companions"]:
        level = "ok" if c.get("ready") else "info"
        detail = c.get("version") or ""
        if c.get("auth_mode"):
            detail += f" · logged in ({c['auth_mode']})"
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
        _emit({"ok": False, "error": f"no vault at {where}: set TOOLKIT_VAULT"}, args.json, lambda r: f"error: {r['error']}")
        return None
    return resolution.path


def _engine_json(binary: str | None, name: str, argv: list[str], timeout: int) -> tuple[object, str | None]:
    """Run an engine with --json; (parsed, None) or (None, error)."""
    if binary is None:
        return None, f"{name} not installed — unisphere engines install"
    try:
        proc = subprocess.run([binary, *argv, "--json"], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"{name} failed: {exc}"
    if proc.returncode != 0:
        return None, (proc.stderr.strip() or proc.stdout.strip() or f"{name} exited {proc.returncode}")
    try:
        return json.loads(proc.stdout), None
    except json.JSONDecodeError as exc:
        return None, f"{name} returned no JSON: {exc}"


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
        _emit({"ok": False, "error": error}, args.json, lambda r: f"error: {r['error']}")
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
            _emit({"ok": False, "error": f"index: {error}"}, args.json, lambda r: f"error: {r['error']}")
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
        level = {"created": "ok", "updated": "ok", "skipped": "warn"}[r["action"]]
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
        _emit({"ok": False, "error": "run from an agentic-toolkit checkout"}, args.json, lambda r: f"error: {r['error']}")
        return 1
    vault_path = Path(args.vault).expanduser().resolve() if args.vault else (
        resolution.path if resolution.source.startswith("env:") else None)
    bin_dir = Path(args.bin_dir).expanduser() if args.bin_dir else linker.default_bin_dir()
    result = linker.link(repo_root, bin_dir, vault_path, force=args.force)
    _emit(result, args.json, _render_link)
    return 0 if result["ok"] else 1


# --- commands: the catalogue ------------------------------------------------------------

# What each command returns, for the catalogue. Every leaf command must have an entry
# (core/tests/test_cli_interface.py enforces it), so the catalogue cannot drift from the parser.
CATALOG = {
    "status": {
        "summary": "Is everything current and healthy? Engines, plugins, vault, pipeline, companion CLIs.",
        "json": "{ok, problems[{section, detail}], toolkit, engines{engines[], cloud_pin}, plugins{plugins[{plugin, latest, "
                "state, installs[]}]}, vault{notes, inbox, dlq, graph}, pipeline{ok, problems, facts}, companions[]}",
        "example": "unisphere status --json",
        "exit": "1 when problems is non-empty",
    },
    "search": {
        "summary": "Ranked full-text (BM25) search over the vault's active notes (farsight).",
        "json": "{ok, query, vault, results[{path, score, title, description}]}",
        "example": "unisphere search agent memory --limit 5 --json",
    },
    "graph stats": {
        "summary": "Graph size, dangling links, boundary violations and the most-linked notes (gaiafield).",
        "json": "{ok, op, vault, result{nodes, edges, dangling_edges, boundary_violations, top_linked[]}}",
        "example": "unisphere graph stats --json",
    },
    "graph neighbors": {
        "summary": "Notes linked to or from a note, out to a depth (gaiafield). NOTE is a path or a bare note name.",
        "json": "{ok, op, vault, note, result[{path, title, description, depth}]}",
        "example": "unisphere graph neighbors Gaiafield --depth 2 --json",
    },
    "graph path": {
        "summary": "Shortest link path between two notes (gaiafield).",
        "json": "{ok, op, vault, result{from, to, connected, path[]}}",
        "example": "unisphere graph path Alex-Vega Gaiafield --json",
    },
    "graph candidates": {
        "summary": "Same-topic notes with no link to this one yet — link suggestions (gaiafield infer must have run).",
        "json": "{ok, op, vault, note, result[{path, score, label, kind, det_distance, surprise}]}",
        "example": "unisphere graph candidates Gaiafield --json",
    },
    "doctor": {
        "summary": "The vault's structure: PARA folders, note counts, frontmatter errors, profiles, DLQ, graph.",
        "json": "{ok, vault_path, para_folders, note_counts, frontmatter_parse_errors[], profiles, dlq, graph}",
        "example": "unisphere doctor --json",
    },
    "profile": {
        "summary": "A plugin's resolved profile (defaults merged with the vault's Config/toolkit/<plugin>.md). Always JSON.",
        "json": "{ok, plugin, vault_path, profile}",
        "example": "unisphere profile obsidian",
    },
    "engines status": {
        "summary": "Installed vs. latest release of each engine (farsight, gaiafield).",
        "json": "{ok, engines[{engine, installed_tag, latest_tag, up_to_date, installed_path}]}",
        "example": "unisphere engines status --json",
    },
    "engines install": {
        "summary": "Download, verify (sha256) and install the latest engine releases.",
        "json": "{ok, results[{engine, ok, action, tag, path}]}",
        "example": "unisphere engines install",
    },
    "engines update": {
        "summary": "Same as engines install: bring every engine to its latest release.",
        "json": "{ok, results[{engine, ok, action, tag, path}]}",
        "example": "unisphere engines update --json",
    },
    "vault init": {
        "summary": "Scaffold a new vault (PARA folders and AGENTS.md) at PATH.",
        "json": "{ok, path}",
        "example": "unisphere vault init ~/Notes",
    },
    "demo": {
        "summary": "Sixty seconds of first-hand value on the example vault: scan, search, graph, candidates.",
        "json": "{ok, steps[]}",
        "example": "unisphere demo",
    },
    "link": {
        "summary": "Put unisphere (and its alias toolkit), the engines and Obsidian's CLI on PATH (~/.local/bin); --vault sets its default vault.",
        "json": "{ok, bin_dir, on_path, vault, links[{name, path, action, target}]}",
        "example": "unisphere link --vault ~/Documents/TheVoid",
    },
    "commands": {
        "summary": "This catalogue: every command, its arguments, its JSON, and the companion CLIs.",
        "json": "{ok, conventions, commands[{name, summary, arguments[], json, example}], companions[]}",
        "example": "unisphere commands --json",
    },
}

COMPANIONS = [
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
        commands.append({"name": name, "summary": entry["summary"], "arguments": _arguments(sub),
                         "json": entry["json"], "example": entry["example"],
                         **({"exit": entry["exit"]} if "exit" in entry else {})})
    return {
        "ok": True,
        "conventions": {
            "json": "add --json to any command for one JSON object on stdout; text output is for people and may change",
            "alias": "toolkit is the same command under its older name",
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
    out = [st.bold("unisphere") + st.dim(" (alias toolkit) — every command takes --json for agents"), ""]
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


def _prog() -> str:
    """Usage lines name the command as it was typed: `toolkit` scripts see `toolkit`."""
    name = Path(sys.argv[0]).name
    return name if name in ("unisphere", "toolkit") else "unisphere"


def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="emit JSON output")

    parser = argparse.ArgumentParser(
        prog=_prog(), parents=[common],
        description="unisphere (alias toolkit): the agentic-toolkit CLI. People read the text; agents add --json and "
                    "start from `unisphere commands --json`.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    vault_parser = subparsers.add_parser("vault", parents=[common], help="create a vault")
    vault_subparsers = vault_parser.add_subparsers(dest="vault_command", required=True)
    init_parser = vault_subparsers.add_parser("init", parents=[common], help=CATALOG["vault init"]["summary"])
    init_parser.add_argument("path", help="where to create the vault")
    init_parser.add_argument("--force", action="store_true", help="init into a non-empty directory")

    subparsers.add_parser("doctor", parents=[common], help=CATALOG["doctor"]["summary"])

    profile_parser = subparsers.add_parser("profile", parents=[common], help=CATALOG["profile"]["summary"])
    profile_parser.add_argument("plugin", help="a plugin name, e.g. obsidian")

    engines_parser = subparsers.add_parser("engines", parents=[common], help="the Rust engines (farsight, gaiafield)")
    engines_subparsers = engines_parser.add_subparsers(dest="engines_command", required=True)
    for name in ("install", "update"):
        sub = engines_subparsers.add_parser(name, parents=[common], help=CATALOG[f"engines {name}"]["summary"])
        sub.add_argument("--force", action="store_true", help="re-download even if already at the latest release")
    engines_subparsers.add_parser("status", parents=[common], help=CATALOG["engines status"]["summary"])

    subparsers.add_parser("demo", parents=[common], help=CATALOG["demo"]["summary"])

    status_parser = subparsers.add_parser("status", parents=[common], help=CATALOG["status"]["summary"])
    status_parser.add_argument("--offline", action="store_true", help="skip the GitHub check for newer engine releases")

    search_parser = subparsers.add_parser("search", parents=[common], help=CATALOG["search"]["summary"])
    search_parser.add_argument("terms", nargs="+", help="query words")
    search_parser.add_argument("--limit", type=int, default=10, help="max results")

    graph_parser = subparsers.add_parser("graph", parents=[common], help="the vault's link graph (gaiafield)")
    graph_subparsers = graph_parser.add_subparsers(dest="graph_command", required=True)
    graph_common = argparse.ArgumentParser(add_help=False, parents=[common])
    graph_common.add_argument("--no-index", action="store_true", help="query the graph as stored, without refreshing it")
    graph_subparsers.add_parser("stats", parents=[graph_common], help=CATALOG["graph stats"]["summary"])
    sub = graph_subparsers.add_parser("neighbors", parents=[graph_common], help=CATALOG["graph neighbors"]["summary"])
    sub.add_argument("note", help="a vault-relative path or a bare note name")
    sub.add_argument("--depth", type=int, default=1, help="how many links out")
    sub.add_argument("--direction", choices=("in", "out", "both"), default="both", help="links to it, from it, or both")
    sub.add_argument("--include-inferred", action="store_true", help="also inferred (similarity) edges")
    sub = graph_subparsers.add_parser("path", parents=[graph_common], help=CATALOG["graph path"]["summary"])
    sub.add_argument("source", help="the note to start from")
    sub.add_argument("target", help="the note to reach")
    sub.add_argument("--include-inferred", action="store_true", help="also traverse inferred edges")
    sub = graph_subparsers.add_parser("candidates", parents=[graph_common], help=CATALOG["graph candidates"]["summary"])
    sub.add_argument("note", help="a vault-relative path or a bare note name")
    sub.add_argument("--limit", type=int, default=10, help="max candidates")
    sub.add_argument("--include-ambiguous", action="store_true", help="also the AMBIGUOUS band")

    link_parser = subparsers.add_parser("link", parents=[common], help=CATALOG["link"]["summary"])
    link_parser.add_argument("--vault", help="default TOOLKIT_VAULT for the toolkit shim (an exported value wins)")
    link_parser.add_argument("--bin-dir", help="where to link (default ~/.local/bin)")
    link_parser.add_argument("--force", action="store_true", help="replace files there that toolkit did not write")

    subparsers.add_parser("commands", parents=[common], help=CATALOG["commands"]["summary"])

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

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
    handlers = {"status": cmd_status, "search": cmd_search, "graph": cmd_graph, "link": cmd_link, "commands": cmd_commands}
    if args.command in handlers:
        return handlers[args.command](args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
