"""Mechanically-checkable conformance of ./vault against contract/VAULT_SCHEMA.md.

Only rules that are checkable by a script without judgment calls: folder presence, every
note's frontmatter parsing, and required-for-status fields being present where the schema
says they must be. This is the "example vault as executable contract" check from docs/PLAN.md
— it is not a full schema validator and doesn't try to be.
"""

from __future__ import annotations

from conftest import EXAMPLE_VAULT, skip_if_example_vault_empty
from toolkit_core import knowledge
from toolkit_core.vault import PARA_FOLDERS, FrontmatterError, parse_frontmatter


def test_para_folders_exist():
    skip_if_example_vault_empty()
    for folder in PARA_FOLDERS:
        assert (EXAMPLE_VAULT / folder).is_dir(), f"./vault is missing {folder}/"


def test_every_note_frontmatter_parses():
    skip_if_example_vault_empty()
    failures = []
    for note_path in EXAMPLE_VAULT.rglob("*.md"):
        text = note_path.read_text(encoding="utf-8")
        try:
            parse_frontmatter(text)
        except FrontmatterError as exc:
            failures.append(f"{note_path.relative_to(EXAMPLE_VAULT)}: {exc}")
    assert not failures, "malformed frontmatter:\n" + "\n".join(failures)


def test_distilled_notes_carry_source_and_processed_date():
    skip_if_example_vault_empty()
    failures = []
    for note_path in EXAMPLE_VAULT.rglob("*.md"):
        text = note_path.read_text(encoding="utf-8")
        frontmatter, _, had_frontmatter = parse_frontmatter(text)
        if not had_frontmatter or frontmatter.get("status") != "distilled":
            continue
        missing = [f for f in ("source", "processed_date") if f not in frontmatter]
        if missing:
            rel = note_path.relative_to(EXAMPLE_VAULT)
            failures.append(f"{rel}: status=distilled but missing {missing}")
    assert not failures, "\n".join(failures)


def test_resources_carry_description_and_kind():
    skip_if_example_vault_empty()
    resources_dir = EXAMPLE_VAULT / "04_Resources"
    if not resources_dir.is_dir():
        return
    failures = []
    for note_path in resources_dir.rglob("*.md"):
        text = note_path.read_text(encoding="utf-8")
        frontmatter, _, had_frontmatter = parse_frontmatter(text)
        if not had_frontmatter:
            continue
        missing = [f for f in ("description", "kind") if f not in frontmatter]
        if missing:
            rel = note_path.relative_to(EXAMPLE_VAULT)
            failures.append(f"{rel}: in 04_Resources but missing {missing}")
    assert not failures, "\n".join(failures)


def test_areas_carry_description():
    skip_if_example_vault_empty()
    areas_dir = EXAMPLE_VAULT / "03_Areas"
    if not areas_dir.is_dir():
        return
    failures = []
    for note_path in areas_dir.rglob("*.md"):
        text = note_path.read_text(encoding="utf-8")
        frontmatter, _, had_frontmatter = parse_frontmatter(text)
        if not had_frontmatter or "description" in frontmatter:
            continue
        failures.append(str(note_path.relative_to(EXAMPLE_VAULT)))
    assert not failures, "03_Areas notes missing description:\n" + "\n".join(failures)


def test_capture_is_flat_no_subfolders():
    skip_if_example_vault_empty()
    capture_dir = EXAMPLE_VAULT / "01_Capture"
    if not capture_dir.is_dir():
        return
    subdirs = [p for p in capture_dir.iterdir() if p.is_dir()]
    assert not subdirs, f"01_Capture/ must be flat, found subfolders: {subdirs}"


def test_core_and_plugin_frontmatter_implementations_agree(tmp_path):
    """The obsidian and readwise plugins' standalone vault_utils must each apply the same
    floor rule as toolkit_core — independent implementations of the contract may never
    drift apart [earned: adversarial R0 review 2026-07-26 — duplicated logic with no
    shared test]."""
    import sys

    note = tmp_path / "note.md"
    note.write_text(
        "---\ndescription: parity check\nstatus: draft\nunknown_field: keep-me\n"
        "nested:\n  a: 1\n---\n\nBody text.\n",
        encoding="utf-8",
    )
    core_fm, core_body, _ = parse_frontmatter(note.read_text(encoding="utf-8"))

    # Both plugins ship a same-named `vault_utils` module in their own scripts/ dir — pop
    # the cached module between imports so each iteration loads the plugin under test's
    # own copy rather than a stale sys.modules hit from the previous one.
    for plugin_name in ("obsidian", "readwise", "radar"):
        scripts_dir = EXAMPLE_VAULT.parent / "plugins" / plugin_name / "scripts"
        sys.path.insert(0, str(scripts_dir))
        sys.modules.pop("vault_utils", None)
        try:
            import vault_utils

            plugin_fm, plugin_body = vault_utils.read_frontmatter(note)
        finally:
            sys.path.remove(str(scripts_dir))
            sys.modules.pop("vault_utils", None)

        assert plugin_fm == core_fm, f"plugins/{plugin_name}/scripts/vault_utils.read_frontmatter disagreed"
        assert plugin_body.strip() == core_body.strip()
        assert plugin_fm["unknown_field"] == "keep-me"


def test_plugin_vault_utils_profile_and_write_agree(tmp_path):
    """The three plugin copies of vault_utils once disagreed on two contracts: `atomic_write` into
    a missing folder (radar created it, obsidian and readwise raised) and an unparseable profile
    note (readwise wrote a DLQ note, obsidian and radar silently read `{}` through a dead
    `except`) [earned: 2026-09-24 review GLM-3]. Each copy must now create the folder, and read a
    broken profile as defaults plus one DLQ note a day, however often it is read."""
    import sys

    for plugin_name in ("obsidian", "readwise", "radar"):
        vault = tmp_path / plugin_name
        scripts_dir = EXAMPLE_VAULT.parent / "plugins" / plugin_name / "scripts"
        sys.path.insert(0, str(scripts_dir))
        sys.modules.pop("vault_utils", None)
        try:
            import vault_utils

            vault_utils.atomic_write(vault / "new" / "folder" / "note.md", "written\n")
            profile = vault / "Config" / "toolkit" / f"{plugin_name}.md"
            profile.parent.mkdir(parents=True)
            profile.write_text("---\nbatch: [25\n---\n", encoding="utf-8")
            reads = [vault_utils.read_profile(vault), vault_utils.read_profile(vault)]
        finally:
            sys.path.remove(str(scripts_dir))
            sys.modules.pop("vault_utils", None)

        assert (vault / "new" / "folder" / "note.md").read_text(encoding="utf-8") == "written\n", plugin_name
        assert reads == [{}, {}], f"{plugin_name}: an unparseable profile must read as defaults"
        dlq = sorted(p.name for p in (vault / "00_Memory" / "dlq").glob("*.md"))
        assert len(dlq) == 1 and dlq[0].endswith(f"{plugin_name}-profile-unreadable.md"), f"{plugin_name}: {dlq}"


def test_each_script_reads_its_own_key_env_first_then_the_key_file(tmp_path, monkeypatch):
    """contract/PROFILE.md "Secrets": a key comes from the environment, else the owner's key file
    (`TOOLKIT_KEYS_FILE`), and is returned to the caller, never exported, so the unattended agent
    that starts the scripts holds none [earned: 2026-09-24, review-01 SEC-1]. All three copies."""
    import os
    import sys

    keys = tmp_path / "keys.env"
    keys.write_text("# comment\nexport READWISE_TOKEN='rw from file'\nKAGI_API_KEY=\"kagi\"\n"
                    "OPENROUTER_API_KEY=or=with=equals\nEMPTY_KEY=\n", encoding="utf-8")
    for plugin_name in ("obsidian", "readwise", "radar"):
        scripts_dir = EXAMPLE_VAULT.parent / "plugins" / plugin_name / "scripts"
        sys.path.insert(0, str(scripts_dir))
        sys.modules.pop("vault_utils", None)
        try:
            import vault_utils

            monkeypatch.setenv("TOOLKIT_KEYS_FILE", str(keys))
            for name in ("READWISE_TOKEN", "KAGI_API_KEY", "OPENROUTER_API_KEY", "EMPTY_KEY"):
                monkeypatch.delenv(name, raising=False)
            got = {n: vault_utils.secret(n) for n in ("READWISE_TOKEN", "KAGI_API_KEY", "OPENROUTER_API_KEY",
                                                      "EMPTY_KEY", "ABSENT_KEY")}
            assert got == {"READWISE_TOKEN": "rw from file", "KAGI_API_KEY": "kagi",
                           "OPENROUTER_API_KEY": "or=with=equals", "EMPTY_KEY": None, "ABSENT_KEY": None}, plugin_name
            assert "READWISE_TOKEN" not in os.environ, f"{plugin_name}: secret() exported the key"
            monkeypatch.setenv("KAGI_API_KEY", "from env")
            assert vault_utils.secret("KAGI_API_KEY") == "from env", f"{plugin_name}: the environment wins"
            monkeypatch.setenv("TOOLKIT_KEYS_FILE", str(tmp_path / "missing.env"))
            assert vault_utils.secret("READWISE_TOKEN") is None, plugin_name
        finally:
            sys.path.remove(str(scripts_dir))
            sys.modules.pop("vault_utils", None)


def test_no_plugin_script_reads_a_key_past_secret():
    """A key read straight from os.environ would bypass the key file, and the unattended run's
    agent has no key in its environment: that script would silently print SKIPPED. Every
    `*_KEY`/`*_TOKEN` read goes through `vault_utils.secret` instead."""
    import re

    direct = re.compile(r"os\.environ(?:\.get\(|\[)\s*[\"']([A-Z0-9_]*(?:_KEY|_TOKEN))[\"']")
    offenders = [f"{p.relative_to(EXAMPLE_VAULT.parent)}: {m}"
                 for p in (EXAMPLE_VAULT.parent / "plugins").glob("*/scripts/**/*.py")
                 for m in direct.findall(p.read_text(encoding="utf-8"))]
    assert not offenders, offenders


def test_shared_judgment_modules_are_byte_identical():
    """The judgment client and its helpers exist twice, in obsidian and radar, because a plugin
    never imports a sibling (contract/KNOWLEDGE_API.md). The copies are only safe while they are
    the same bytes [R10 plan, 2026-09-22 — the first module shared by copy rather than by note].
    Remove when the judgment client moves into core and both plugins depend on it there."""
    import hashlib

    plugins = EXAMPLE_VAULT.parent / "plugins"
    drifted = []
    for rel in ("judge.py", "judgments/urls.py", "judgments/state.py"):
        digests = {
            name: hashlib.sha256((plugins / name / "scripts" / rel).read_bytes()).hexdigest()
            for name in ("obsidian", "radar")
        }
        if len(set(digests.values())) != 1:
            drifted.append(rel)
    assert not drifted, f"copy the obsidian version over the radar one (or back): {drifted}"


def test_core_and_plugin_graph_discovery_agree(tmp_path, monkeypatch):
    """toolkit_core.knowledge's gaiafield binary discovery and default db path must agree
    with the obsidian plugin's graph.py — two independent reimplementations of the same
    preference chain (docs/PLAN.md's plugin-independence rule) that may never drift apart
    on the env var honored, the PATH fallback binary name, or the db path convention."""
    import sys

    scripts_dir = EXAMPLE_VAULT.parent / "plugins" / "obsidian" / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        import graph as graph_mod
    finally:
        sys.path.remove(str(scripts_dir))

    assert knowledge.GAIAFIELD_BIN_ENV == graph_mod.GAIAFIELD_BIN_ENV

    # `import shutil` in both modules refers to the same module object, so patching
    # either's `.which` patches both — asserted as calls below, not assumed.
    monkeypatch.delenv(knowledge.GAIAFIELD_BIN_ENV, raising=False)
    monkeypatch.setattr(knowledge.shutil, "which", lambda name: f"/usr/bin/{name}" if name == "gaiafield" else None)
    assert knowledge.gaiafield_binary() == graph_mod.gaiafield_binary() == "/usr/bin/gaiafield"

    monkeypatch.setenv(knowledge.GAIAFIELD_BIN_ENV, "/custom/gaiafield-bin")
    assert knowledge.gaiafield_binary() == graph_mod.gaiafield_binary() == "/custom/gaiafield-bin"

    assert knowledge.default_db_path(tmp_path) == graph_mod.default_db_path(tmp_path)


def _ledger_table() -> dict[str, tuple[str, set[str]]]:
    """contract/KNOWLEDGE_API.md's "Cross-plugin ledgers" table → {name: (path, fields)}."""
    import re

    text = (EXAMPLE_VAULT.parent / "contract" / "KNOWLEDGE_API.md").read_text(encoding="utf-8")
    section = text.split("## Cross-plugin ledgers", 1)[1].split("\n## ", 1)[0]
    table = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[1].startswith("`00_Memory/"):
            table[cells[0]] = (cells[1].strip("`"), set(re.findall(r"`(\w+)`", cells[4])))
    return table


def _row_keys_read(source: str, functions: set[str]) -> set[str]:
    """String keys read from a `row`/`r` dict in the named functions, less keys they set themselves."""
    import ast

    read, written = set(), set()
    for fn in ast.walk(ast.parse(source)):
        if not (isinstance(fn, ast.FunctionDef) and fn.name in functions):
            continue
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
                    and isinstance(node.func.value, ast.Name) and node.func.value.id in ("row", "r")
                    and node.args and isinstance(node.args[0], ast.Constant)):
                read.add(node.args[0].value)
            elif (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                  and node.value.id in ("row", "r") and isinstance(node.slice, ast.Constant)):
                (written if isinstance(node.ctx, ast.Store) else read).add(node.slice.value)
    return read - written


def _row_keys_written(source: str, function: str, marker: str) -> set[str]:
    """Keys of the dict literal(s) in `function` that carry the key `marker`: the rows it writes."""
    import ast

    keys: set[str] = set()
    for fn in ast.walk(ast.parse(source)):
        if isinstance(fn, ast.FunctionDef) and fn.name == function:
            for node in ast.walk(fn):
                if isinstance(node, ast.Dict):
                    literal = {k.value for k in node.keys if isinstance(k, ast.Constant)}
                    if marker in literal:
                        keys |= literal
    return keys


def test_cross_plugin_ledgers_match_the_contract():
    """The pipeline and Now.md read radar's and readwise's JSONL ledgers; the path and row fields
    both sides use are the ones contract/KNOWLEDGE_API.md lists [earned: 2026-09-24 review GLM-2 —
    the schemas were private to each producer, and a rename would have zeroed the run summary
    silently]. Remove with that contract section."""
    import sys

    plugins = EXAMPLE_VAULT.parent / "plugins"
    table = _ledger_table()
    assert set(table) == {"judged", "promoted", "ingested"}, f"ledger table not parsed: {table}"

    scripts_dir = plugins / "obsidian" / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        import pipeline_run
    finally:
        sys.path.remove(str(scripts_dir))
    assert {k: p.as_posix() for k, p in pipeline_run.LEDGERS.items()} == {k: v[0] for k, v in table.items()}

    producers = {  # ledger → (file, the function that builds its row, a key only that row has)
        "judged": (plugins / "radar" / "scripts" / "radar.py", "to_row", "questions_version"),
        "promoted": (plugins / "radar" / "scripts" / "radar.py", "settle", "canonical"),
        "ingested": (plugins / "readwise" / "scripts" / "ingest.py", "ingest", "doc_id"),
    }
    for name, (path, fields) in table.items():
        file, function, marker = producers[name]
        source = file.read_text(encoding="utf-8")
        assert path.rsplit("/", 1)[-1] in source, f"{file.name} no longer names {path}"
        written = _row_keys_written(source, function, marker)
        assert written, f"{name}: no row found in {file.name}:{function} — the writer moved; update this test"
        assert fields <= written, f"{name}: {file.name}:{function} no longer writes {sorted(fields - written)}"

    now_build = (scripts_dir / "now_build.py").read_text(encoding="utf-8")
    assert '"radar" / "state.jsonl"' in now_build
    readers = {"judged": _row_keys_read(now_build, {"radar", "_radar_line"}),
               "ingested": _row_keys_read((scripts_dir / "pipeline_run.py").read_text(encoding="utf-8"), {"came_in"})}
    for name, keys in readers.items():
        assert keys, f"{name}: found no field reads — the reader moved; update this test"
        assert keys <= table[name][1], f"{name}: reader relies on undocumented fields {sorted(keys - table[name][1])}"


def test_core_and_plugin_engine_install_paths_agree(tmp_path, monkeypatch):
    """search.py's farsight discovery mirrors engines.py the way graph.py's gaiafield discovery
    does, but only graph.py had a parity test: moving the install dir in engines.py and graph.py
    alone would leave search silently on pure-Python BM25 [earned: 2026-09-24 review GLM-4].
    Both plugin mirrors must compute `engines.binary_path()` and fall back to it after the env
    var and PATH, in that order."""
    import sys

    from toolkit_core import engines

    scripts_dir = EXAMPLE_VAULT.parent / "plugins" / "obsidian" / "scripts"
    sys.path.insert(0, str(scripts_dir))
    try:
        import graph as graph_mod
        import search as search_mod
    finally:
        sys.path.remove(str(scripts_dir))

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert search_mod._engines_install_dir() == engines.binary_path("farsight")
    assert graph_mod._engines_install_dir() == engines.binary_path("gaiafield")

    for name, env, find in (("farsight", "TOOLKIT_FARSIGHT_BIN", search_mod.farsight_binary),
                            ("gaiafield", knowledge.GAIAFIELD_BIN_ENV, graph_mod.gaiafield_binary)):
        monkeypatch.delenv(env, raising=False)
        monkeypatch.setattr(search_mod.shutil, "which", lambda _: None)
        assert find() is None, f"{name}: nothing installed must find nothing"
        installed = engines.binary_path(name)
        installed.parent.mkdir(parents=True, exist_ok=True)
        installed.write_text("", encoding="utf-8")
        assert find() == str(installed), f"{name}: the engines install dir must be the last fallback"
        monkeypatch.setattr(search_mod.shutil, "which", lambda n, name=name: f"/usr/bin/{n}" if n == name else None)
        assert find() == f"/usr/bin/{name}", f"{name}: PATH must win over the install dir"
        monkeypatch.setenv(env, f"/custom/{name}-bin")
        assert find() == f"/custom/{name}-bin", f"{name}: the env var must win"
