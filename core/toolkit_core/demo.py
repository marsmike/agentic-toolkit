"""`toolkit demo` — 60 seconds to first-hand value, zero setup.

Every line this prints comes from actually running something: a real filesystem scan
(always, no engines required) and, once `toolkit engines install` has put binaries where
`knowledge.py`'s discovery chain looks, real farsight/gaiafield calls against a real
vault. There is no "as if installed" canned output — if the engines aren't there yet,
this says so once and stops after the pure-Python step, honestly.

Vault used: the bundled `./vault` when run from inside a repo checkout, or a tiny
scaffolded mini-vault (reusing `vault.scaffold_vault`) in a temp dir otherwise, so the
demo works identically for a `uv tool install` user with no local checkout at all.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from toolkit_core import knowledge, vault

DEMO_QUERY = "graph"

_SAMPLE_NOTES = {
    "04_Resources/Concepts/Knowledge-Graphs.md": (
        "# Knowledge Graphs\n\n"
        "A knowledge graph connects notes via wikilinks — see [[BM25-Search]] for how "
        "keyword search complements graph traversal.\n"
    ),
    "04_Resources/Concepts/BM25-Search.md": (
        "# BM25 Search\n\n"
        "BM25 ranks notes by keyword relevance. Pairs well with [[Knowledge-Graphs]] for "
        "hybrid retrieval.\n"
    ),
    "03_Areas/Demo-Area.md": (
        "# Demo Area\n\n"
        "A tiny scaffolded area so `toolkit demo` has something real to query — see "
        "[[Knowledge-Graphs]] and [[BM25-Search]].\n"
    ),
}

_DEMO_CLAUDE_MD = (
    "# demo vault\n\n"
    "Scaffolded on the fly by `toolkit demo` (no repo checkout was found on disk). Not a "
    "real vault — this whole directory is temporary and safe to delete.\n"
)


def _bundled_repo_vault() -> Path | None:
    repo_root = vault.find_repo_root(Path.cwd()) or vault.find_repo_root(Path(__file__).resolve().parent)
    if repo_root is None:
        return None
    candidate = repo_root / "vault"
    return candidate if candidate.is_dir() else None


def _scaffold_demo_vault() -> tuple[Path, Path]:
    """A handful of tiny sample notes, generated inline, scaffolded via the same
    `vault.scaffold_vault` a real `toolkit vault init` uses. Returns
    `(vault_path, temp_root_to_clean_up)`."""
    temp_root = Path(tempfile.mkdtemp(prefix="agentic-toolkit-demo-"))
    template_path = temp_root / "_claude_md_template.md"
    template_path.write_text(_DEMO_CLAUDE_MD, encoding="utf-8")
    target = temp_root / "vault"
    vault.scaffold_vault(target, template_path)
    for rel, content in _SAMPLE_NOTES.items():
        note_path = target / rel
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(content, encoding="utf-8")
    return target, temp_root


def _resolve_demo_vault() -> tuple[Path, str, Path | None]:
    bundled = _bundled_repo_vault()
    if bundled is not None:
        return bundled, "bundled example vault (repo checkout)", None
    demo_vault, temp_root = _scaffold_demo_vault()
    return demo_vault, "scaffolded temp mini-vault (no repo checkout found)", temp_root


def _gaiafield_surprise(vault_path: Path, top: int = 3) -> list | None:
    """Direct shell-out to `gaiafield surprise --json`, vault-wide. Kept local to
    demo.py rather than added to `knowledge.py` (out of scope for this fix) since this
    is a demo-only fallback: unlike `knowledge.gaiafield_candidates()`, it doesn't
    depend on any single note having candidates of its own, which is exactly what step
    4 needs when the top search hits are fully-linked hubs. Mirrors the shape of
    `knowledge.py`'s other gaiafield wrappers: `None` on any failure, never raises."""
    binary = knowledge.gaiafield_binary()
    if binary is None:
        return None
    try:
        proc = subprocess.run(
            [binary, "surprise", "--vault", str(vault_path), "--top", str(top), "--json"],
            capture_output=True, text=True, timeout=knowledge.STATS_TIMEOUT, check=True,
        )
        return json.loads(proc.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def _collect(vault_path: Path, vault_source: str) -> dict:
    steps: list[dict] = []

    def add_step(title: str, explanation: str, body: list[str]) -> None:
        steps.append({"title": title, "explanation": explanation, "lines": body})

    counts = vault.note_counts(vault_path)
    active_total = sum(counts.get(f, 0) for f in ("02_Projects", "03_Areas", "04_Resources"))
    add_step(
        "1/4 vault scan",
        "pure Python, no engines required — the same scan `toolkit doctor` runs",
        [f"{active_total} active note(s) across 02_Projects/03_Areas/04_Resources"],
    )

    farsight_bin = knowledge.farsight_binary()
    gaiafield_bin = knowledge.gaiafield_binary()
    engines_installed = farsight_bin is not None and gaiafield_bin is not None

    if not engines_installed:
        add_step(
            "engines",
            'not installed — run: toolkit engines install',
            ["the steps below need the Rust binaries; the vault scan above never did"],
        )
        return {
            "ok": True,
            "vault": str(vault_path),
            "vault_source": vault_source,
            "engines_installed": False,
            "steps": steps,
        }

    search_result = knowledge.farsight_query(vault_path, DEMO_QUERY, k=3)
    results = search_result.get("results") or []
    top_note = results[0]["path"] if results else None
    search_lines = [f"{r['score']:.3f}  {r['path']}" for r in results] or [search_result.get("note", "no results")]
    add_step(
        "2/4 farsight query",
        f'`farsight query "{DEMO_QUERY}"` — Rust BM25 search over active notes',
        search_lines,
    )

    knowledge.gaiafield_index(vault_path)
    stats = knowledge.graph_status(vault_path)
    graph_lines = (
        [f"nodes={stats.get('nodes')} edges={stats.get('edges')}"]
        if stats.get("present")
        else [stats.get("note", "graph unavailable")]
    )
    if top_note is None:
        active_notes = vault.list_active_notes(vault_path)
        top_note = active_notes[0].relative_to(vault_path).as_posix() if active_notes else None
    if top_note is not None:
        neighbors = knowledge.gaiafield_neighbors(vault_path, top_note)
        if neighbors:
            graph_lines.append(f"neighbors of {top_note}: " + ", ".join(n["path"] for n in neighbors))
        else:
            graph_lines.append(f"no neighbors found for {top_note}")
    add_step(
        "3/4 gaiafield graph",
        "`gaiafield stats` + one `neighbors` call — your wikilinks as a queryable graph",
        graph_lines,
    )

    infer_lines: list[str] = ["no note to query (empty vault)"]
    hit_paths = [r["path"] for r in results[:3]] if results else ([top_note] if top_note else [])
    if hit_paths:
        knowledge.gaiafield_infer(vault_path)
        infer_lines = None
        for hit_path in hit_paths:
            candidates = knowledge.gaiafield_candidates(vault_path, hit_path, k=3)
            if candidates:
                infer_lines = [f"candidates for {hit_path}:"] + [
                    f"  {c['score']:.3f}  {c['path']}  [{c['label']}]" for c in candidates
                ]
                break
        if infer_lines is None:
            # None of the step-2 top-k hits had candidates of their own — a fully-linked hub
            # legitimately has no *missing* link to propose. Fall back to a vault-wide surprise
            # scan, which doesn't depend on any one note's own candidate list.
            surprise = _gaiafield_surprise(vault_path, top=3)
            if surprise:
                infer_lines = ["cross-domain surprise candidates (vault-wide, not tied to the top search hit):"] + [
                    f"  {s['surprise']:.3f}  {s['a']} <-> {s['b']}  [{s['label']}]" for s in surprise
                ]
            else:
                infer_lines = [
                    "no inferred candidates anywhere in the vault — likely cause: a highly-linked "
                    "corpus (every plausible pair already has an extracted wikilink) or gaiafield's "
                    "gates filtering out every pair as too weak, not a broken binary"
                ]
    add_step(
        "4/4 inferred candidates",
        "report-only semantic similarity — never auto-applied, always a human decision",
        infer_lines,
    )

    return {
        "ok": True,
        "vault": str(vault_path),
        "vault_source": vault_source,
        "engines_installed": True,
        "steps": steps,
    }


def _render_text(result: dict) -> str:
    lines = [f"vault: {result['vault']} ({result['vault_source']})"]
    for step in result["steps"]:
        lines.append(f"\n[{step['title']}] {step['explanation']}")
        lines.extend(f"  {line}" for line in step["lines"])
    return "\n".join(lines)


def run(as_json: bool = False) -> int:
    vault_path, vault_source, temp_root = _resolve_demo_vault()
    try:
        result = _collect(vault_path, vault_source)
    finally:
        if temp_root is not None:
            shutil.rmtree(temp_root, ignore_errors=True)

    print(json.dumps(result, indent=2) if as_json else _render_text(result))
    return 0
