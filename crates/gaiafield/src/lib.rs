//! gaiafield — deterministic knowledge-graph extraction over an agentic-toolkit vault.
//!
//! v1 scope (`docs/PLAN.md`, Engines): parse wikilinks, frontmatter, and tags into a queryable
//! SQLite store. No model call, no inferred edge — see
//! `vault/04_Resources/Concepts/Deterministic-vs-Inferred-Graph-Edges.md`. Inferred/similarity
//! edges are a later increment (R3+), not this crate.
//!
//! Mirrors `crates/farsight` for vault resolution and tolerant frontmatter parsing so the two
//! engines behave consistently for a caller that uses both.

use rusqlite::Connection;
use serde::Serialize;
use std::collections::{HashMap, HashSet, VecDeque};
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

// ---------------------------------------------------------------------------
// Vault resolution (contract/PROFILE.md) — mirrors crates/farsight/src/lib.rs
// ---------------------------------------------------------------------------

const MARKETPLACE_MARKER: &str = ".claude-plugin/marketplace.json";

/// Folders that hold graph nodes under the schema's active-content filter
/// (`contract/VAULT_SCHEMA.md`). `00_Memory`, `01_Capture`, and `05_Archive` are never nodes.
pub const ACTIVE_CONTENT_FOLDERS: [&str; 3] = ["02_Projects", "03_Areas", "04_Resources"];

/// Folders whose notes are never graph nodes and any wikilink into them from active content is
/// a boundary violation (`contract/VAULT_SCHEMA.md`: "never link here from new notes").
pub const BOUNDARY_FOLDERS: [&str; 3] = ["00_Memory", "01_Capture", "05_Archive"];

const EXCLUDE_DIRS: [&str; 8] = [
    "assets",
    "node_modules",
    "out",
    "public",
    "src",
    ".obsidian",
    ".trash",
    ".gaiafield",
];

#[derive(Debug, Clone)]
pub struct VaultResolution {
    pub path: PathBuf,
    pub source: &'static str,
}

pub fn find_repo_root(start: &Path) -> Option<PathBuf> {
    let start = std::fs::canonicalize(start).unwrap_or_else(|_| start.to_path_buf());
    let mut candidate = Some(start.as_path());
    while let Some(dir) = candidate {
        if dir.join(MARKETPLACE_MARKER).is_file() {
            return Some(dir.to_path_buf());
        }
        candidate = dir.parent();
    }
    None
}

/// Resolve the vault: `--vault` flag wins, else `TOOLKIT_VAULT` env, else `./vault` relative to
/// a repo root found by walking up from the current directory.
pub fn resolve_vault(vault_flag: Option<&Path>) -> Result<VaultResolution, String> {
    if let Some(p) = vault_flag {
        return Ok(VaultResolution {
            path: p.to_path_buf(),
            source: "flag:--vault",
        });
    }
    if let Ok(env_value) = std::env::var("TOOLKIT_VAULT") {
        if !env_value.is_empty() {
            let expanded = shellexpand_home(&env_value);
            return Ok(VaultResolution {
                path: PathBuf::from(expanded),
                source: "env:TOOLKIT_VAULT",
            });
        }
    }
    let cwd = std::env::current_dir().map_err(|e| format!("cannot read current directory: {e}"))?;
    match find_repo_root(&cwd) {
        Some(root) => Ok(VaultResolution {
            path: root.join("vault"),
            source: "default:./vault",
        }),
        None => Err(
            "No vault found: pass --vault, set TOOLKIT_VAULT, or run from inside the \
             agentic-toolkit repo (needs .claude-plugin/marketplace.json above the cwd)."
                .to_string(),
        ),
    }
}

pub fn require_vault(vault_flag: Option<&Path>) -> Result<PathBuf, String> {
    let res = resolve_vault(vault_flag)?;
    if !res.path.is_dir() {
        return Err(format!(
            "Vault path does not exist: {} (resolved via {})",
            res.path.display(),
            res.source
        ));
    }
    Ok(res.path)
}

fn shellexpand_home(value: &str) -> String {
    if let Some(rest) = value.strip_prefix("~/") {
        if let Ok(home) = std::env::var("HOME") {
            return format!("{home}/{rest}");
        }
    }
    value.to_string()
}

/// Default DB location: `<vault>/.gaiafield/graph.db`.
pub fn default_db_path(vault: &Path) -> PathBuf {
    vault.join(".gaiafield").join("graph.db")
}

// ---------------------------------------------------------------------------
// Note discovery
// ---------------------------------------------------------------------------

/// A `.md` file anywhere in the vault, relative to it, POSIX-separated. Used both to determine
/// the node set and to resolve wikilink targets (a link can point at a real file that still
/// isn't a node — see `LinkTarget::OutOfScope`).
#[derive(Debug, Clone)]
pub struct VaultFile {
    pub rel: String,
    pub abs: PathBuf,
}

/// Walk the whole vault (skipping the excluded dirs) and return every `.md` file. This is the
/// universe used to decide whether a wikilink is dangling — "doesn't resolve anywhere in the
/// vault" per the brief, not just "doesn't resolve to a node."
pub fn discover_all_files(vault: &Path) -> Vec<VaultFile> {
    let mut found = Vec::new();
    walk_dir(vault, vault, &mut found);
    found.sort_by(|a, b| a.rel.cmp(&b.rel));
    found
}

fn walk_dir(dir: &Path, vault: &Path, found: &mut Vec<VaultFile>) {
    let entries = match std::fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return,
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let name = entry.file_name();
        let name = name.to_string_lossy();
        if path.is_dir() {
            if name.starts_with('.') || EXCLUDE_DIRS.contains(&name.as_ref()) {
                continue;
            }
            walk_dir(&path, vault, found);
        } else if name.ends_with(".md") && !name.starts_with('.') {
            let rel = path
                .strip_prefix(vault)
                .unwrap_or(&path)
                .to_string_lossy()
                .replace(std::path::MAIN_SEPARATOR, "/");
            found.push(VaultFile { rel, abs: path });
        }
    }
}

/// Node scope for the graph: `02_Projects`/`03_Areas`/`04_Resources` (the schema's active-content
/// filter, matching `Index.md`'s count) **plus** any note directly at the vault root whose own
/// frontmatter declares `status: active`.
///
/// **Deviation, documented:** `contract/VAULT_SCHEMA.md` and the vault's own `CLAUDE.md` state
/// the active-content filter as exactly those three folders for "any generated index." Taken
/// perfectly literally that would exclude `Alex-Vega.md` (vault root). But
/// `vault/04_Resources/Guides/Test-Corpus-Map.md` names Alex-Vega as *the* bridge note ("root
/// persona, links into all three clusters") and Alex-Vega's own frontmatter self-declares
/// `status: active` — the note-lifecycle meaning of "active" in the same schema's frontmatter
/// table, distinct from the folder-level filter. Excluding it would make the planted bridge
/// structure this vault was built to test unreachable (no note titled Alex-Vega would exist in
/// the graph at all). This crate resolves the tension narrowly: a root-level note only joins the
/// node set if it opts in via `status: active`; nothing else at the root (`Index.md`, `CLAUDE.md`
/// — neither carries frontmatter at all) is pulled in. `Config/` and `Templates/` are never
/// scanned — they hold plugin config and templates, not vault content (schema: "Templates — Not
/// itself vault content").
pub fn discover_nodes(vault: &Path) -> Vec<VaultFile> {
    let mut found = Vec::new();
    for folder in ACTIVE_CONTENT_FOLDERS {
        let root = vault.join(folder);
        if root.is_dir() {
            walk_dir(&root, vault, &mut found);
        }
    }
    // Root-level notes (direct children of the vault only, not recursive — Config/ and
    // Templates/ are separate top-level dirs, not root-level files).
    if let Ok(entries) = std::fs::read_dir(vault) {
        for entry in entries.flatten() {
            let path = entry.path();
            let name = entry.file_name();
            let name = name.to_string_lossy();
            if path.is_file() && name.ends_with(".md") && !name.starts_with('.') {
                let raw = std::fs::read_to_string(&path).unwrap_or_default();
                let (fm_text, _) = split_frontmatter(&raw);
                let status = fm_text
                    .as_deref()
                    .map(extract_field(FIELD_STATUS))
                    .unwrap_or_default();
                if status == "active" {
                    found.push(VaultFile {
                        rel: name.to_string(),
                        abs: path,
                    });
                }
            }
        }
    }
    found.sort_by(|a, b| a.rel.cmp(&b.rel));
    found
}

// ---------------------------------------------------------------------------
// Frontmatter — tolerant per contract/VAULT_SCHEMA.md's floor-not-ceiling rule.
// gaiafield only ever reads notes (it never writes into the vault), so "tolerant" here means
// "never errors on an unrecognized or malformed field," not "preserve on write-back."
// ---------------------------------------------------------------------------

/// Split `text` into (frontmatter block text, body). `(None, text)` when there's no frontmatter
/// block — a valid note, never an error (mirrors `crates/farsight`).
pub fn split_frontmatter(text: &str) -> (Option<String>, String) {
    let mut lines = text.lines();
    let first = match lines.next() {
        Some(l) => l,
        None => return (None, String::new()),
    };
    if first.trim_end_matches('\r') != "---" {
        return (None, text.to_string());
    }
    let mut fm_lines: Vec<&str> = Vec::new();
    let mut closed = false;
    for line in lines.by_ref() {
        if line.trim_end_matches('\r') == "---" {
            closed = true;
            break;
        }
        fm_lines.push(line);
    }
    if !closed {
        return (None, text.to_string());
    }
    let body: String = lines.collect::<Vec<_>>().join("\n");
    (Some(fm_lines.join("\n")), body)
}

const FIELD_STATUS: &str = "status";
const FIELD_DESCRIPTION: &str = "description";
const FIELD_KIND: &str = "kind";

/// Pull a single scalar string field out of a frontmatter block. Absent field, non-mapping
/// document, malformed YAML, or a non-string value all resolve to `""` — never an error, and
/// unknown keys are simply never looked at (ignored, not rejected).
fn extract_field(field: &'static str) -> impl Fn(&str) -> String {
    move |fm_text: &str| -> String {
        match serde_yaml::from_str::<serde_yaml::Value>(fm_text) {
            Ok(serde_yaml::Value::Mapping(map)) => map
                .get(serde_yaml::Value::String(field.to_string()))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string(),
            _ => String::new(),
        }
    }
}

/// `tags` may be a YAML sequence of strings or absent; non-string entries are skipped rather
/// than erroring (the floor-not-ceiling rule).
fn extract_tags(fm_text: &str) -> Vec<String> {
    match serde_yaml::from_str::<serde_yaml::Value>(fm_text) {
        Ok(serde_yaml::Value::Mapping(map)) => {
            match map.get(serde_yaml::Value::String("tags".to_string())) {
                Some(serde_yaml::Value::Sequence(seq)) => seq
                    .iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect(),
                Some(serde_yaml::Value::String(s)) => vec![s.clone()],
                _ => Vec::new(),
            }
        }
        _ => Vec::new(),
    }
}

// ---------------------------------------------------------------------------
// Wikilinks
// ---------------------------------------------------------------------------

/// A single `[[Target]]` or `[[Target|Alias]]` occurrence in a note's body. Frontmatter fields
/// (e.g. `enrichment_targets`) are not scanned — only body prose, matching the schema's own
/// framing of wikilinks as a body-content convention (backlinks, Related sections, enrichment).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RawLink {
    pub target: String,
}

/// Extract every `[[...]]` occurrence from `body`, taking the part before `|` as the target.
/// No anchor (`#Heading`) or block-ref (`^id`) syntax appears in this vault's corpus, so it is
/// deliberately not special-cased here — the removal condition is a planted specimen that needs it.
pub fn extract_links(body: &str) -> Vec<RawLink> {
    let mut links = Vec::new();
    let bytes = body.as_bytes();
    let mut i = 0;
    while i + 1 < bytes.len() {
        if bytes[i] == b'[' && bytes[i + 1] == b'[' {
            if let Some(end) = body[i + 2..].find("]]") {
                let inner = &body[i + 2..i + 2 + end];
                let target = inner.split('|').next().unwrap_or(inner).trim();
                if !target.is_empty() {
                    links.push(RawLink {
                        target: target.to_string(),
                    });
                }
                i += 2 + end + 2;
                continue;
            }
        }
        i += 1;
    }
    links
}

// ---------------------------------------------------------------------------
// Link resolution
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub enum LinkTarget {
    /// Resolves to one or more graph nodes. More than one only happens when a bare-name target
    /// is genuinely ambiguous (two notes share a title) and the source note's own folder doesn't
    /// contain either candidate — the extractor records an edge to every candidate rather than
    /// silently guessing one (see `resolve_link`'s doc comment).
    Node(Vec<String>),
    /// Resolves to a real file inside `00_Memory`/`01_Capture`/`05_Archive` — the schema forbids
    /// linking there from active content; recorded as a boundary violation, not a node edge.
    BoundaryViolation(String),
    /// Resolves to a real vault file that simply isn't in the node set (e.g. `Config/`,
    /// `Templates/`, a root-level note without `status: active`). Not an error, not flagged —
    /// just outside what this graph models, the same way a search engine's active-content filter
    /// silently doesn't surface it either.
    OutOfScope(String),
    /// Doesn't resolve to any file anywhere in the vault.
    Dangling,
}

/// Resolve one wikilink's raw target string against the vault.
///
/// Resolution order: (1) treat `target` as a vault-relative path (with or without a trailing
/// `.md`) and check it exists; (2) otherwise treat it as a bare note name and match by filename
/// stem across every `.md` file in the vault — if the source note's own directory holds one of
/// the candidates, prefer it (mirrors Obsidian's same-folder-first resolution, and is exactly
/// how this vault's planted `Weekly-Review` bare links inside each project folder are meant to
/// resolve); otherwise, if still ambiguous, return every candidate rather than guessing.
pub fn resolve_link(
    raw_target: &str,
    source_rel: &str,
    all_files: &[VaultFile],
    by_path: &HashMap<String, usize>,
    by_stem: &HashMap<String, Vec<usize>>,
    node_paths: &HashSet<String>,
) -> LinkTarget {
    let cleaned = raw_target.trim().trim_start_matches("./");

    let direct = by_path.get(cleaned).copied().or_else(|| {
        if cleaned.ends_with(".md") {
            None
        } else {
            by_path.get(&format!("{cleaned}.md")).copied()
        }
    });

    let matches: Vec<usize> = if let Some(idx) = direct {
        vec![idx]
    } else {
        let stem = cleaned
            .rsplit('/')
            .next()
            .unwrap_or(cleaned)
            .trim_end_matches(".md");
        match by_stem.get(stem) {
            Some(v) if !v.is_empty() => v.clone(),
            _ => {
                // Case-insensitive fallback — cheap safety net, not load-bearing for this corpus.
                let lower = stem.to_ascii_lowercase();
                by_stem
                    .iter()
                    .find(|(k, _)| k.to_ascii_lowercase() == lower)
                    .map(|(_, v)| v.clone())
                    .unwrap_or_default()
            }
        }
    };

    if matches.is_empty() {
        return LinkTarget::Dangling;
    }

    let source_dir = source_rel.rsplit_once('/').map(|(d, _)| d).unwrap_or("");
    let chosen: Vec<usize> = if matches.len() > 1 {
        let same_folder: Vec<usize> = matches
            .iter()
            .copied()
            .filter(|&idx| {
                all_files[idx]
                    .rel
                    .rsplit_once('/')
                    .map(|(d, _)| d)
                    .unwrap_or("")
                    == source_dir
            })
            .collect();
        if same_folder.len() == 1 {
            same_folder
        } else {
            matches
        }
    } else {
        matches
    };

    let rels: Vec<&str> = chosen
        .iter()
        .map(|&idx| all_files[idx].rel.as_str())
        .collect();

    // Classify by the first candidate: a bare-name clash straddling a boundary folder and an
    // active one isn't a case this vault plants, so one bucket per resolution is sufficient.
    let first = rels[0];
    if BOUNDARY_FOLDERS
        .iter()
        .any(|f| first.starts_with(&format!("{f}/")))
    {
        return LinkTarget::BoundaryViolation(first.to_string());
    }

    let node_candidates: Vec<String> = rels
        .iter()
        .filter(|r| node_paths.contains(**r))
        .map(|s| s.to_string())
        .collect();
    if node_candidates.is_empty() {
        return LinkTarget::OutOfScope(first.to_string());
    }
    LinkTarget::Node(node_candidates)
}

// ---------------------------------------------------------------------------
// Metadata
// ---------------------------------------------------------------------------

pub struct NoteMeta {
    pub title: String,
    pub description: String,
    pub status: String,
    pub kind: String,
    pub tags: Vec<String>,
    pub body: String,
}

pub fn read_note(file: &VaultFile) -> NoteMeta {
    let title = Path::new(&file.rel)
        .file_stem()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_else(|| file.rel.clone());
    let raw = std::fs::read_to_string(&file.abs).unwrap_or_default();
    let (fm_text, body) = split_frontmatter(&raw);
    let description = fm_text
        .as_deref()
        .map(extract_field(FIELD_DESCRIPTION))
        .unwrap_or_default();
    let status = fm_text
        .as_deref()
        .map(extract_field(FIELD_STATUS))
        .unwrap_or_default();
    let kind = fm_text
        .as_deref()
        .map(extract_field(FIELD_KIND))
        .unwrap_or_default();
    let tags = fm_text.as_deref().map(extract_tags).unwrap_or_default();
    NoteMeta {
        title,
        description,
        status,
        kind,
        tags,
        body,
    }
}

fn file_stat(path: &Path) -> (i64, u64) {
    match std::fs::metadata(path) {
        Ok(meta) => {
            let mtime = meta
                .modified()
                .ok()
                .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
                .map(|d| d.as_secs() as i64)
                .unwrap_or(0);
            (mtime, meta.len())
        }
        Err(_) => (0, 0),
    }
}

fn now_secs() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

// ---------------------------------------------------------------------------
// SQLite schema
// ---------------------------------------------------------------------------

pub fn open_db(db_path: &Path) -> rusqlite::Result<Connection> {
    if let Some(parent) = db_path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let conn = Connection::open(db_path)?;
    conn.execute_batch(
        "
        CREATE TABLE IF NOT EXISTS nodes (
            path        TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            status      TEXT NOT NULL DEFAULT '',
            kind        TEXT NOT NULL DEFAULT '',
            tags        TEXT NOT NULL DEFAULT '[]',
            mtime       INTEGER NOT NULL,
            size        INTEGER NOT NULL,
            updated_at  INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS edges (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            source             TEXT NOT NULL,
            target             TEXT,
            raw_target         TEXT NOT NULL,
            edge_type          TEXT NOT NULL DEFAULT 'EXTRACTED',
            dangling           INTEGER NOT NULL DEFAULT 0,
            boundary_violation INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS edges_source_idx ON edges(source);
        CREATE INDEX IF NOT EXISTS edges_target_idx ON edges(target);
        ",
    )?;
    Ok(conn)
}

// ---------------------------------------------------------------------------
// Indexing
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize, Default)]
pub struct IndexReport {
    pub total_nodes: usize,
    pub added: usize,
    pub updated: usize,
    pub unchanged: usize,
    pub removed: usize,
    pub edges: usize,
    pub dangling_edges: usize,
    pub boundary_violations: usize,
}

/// Extract the graph into `conn`. `full` forces re-extraction of every node even if its
/// mtime+size are unchanged; otherwise only new/changed notes are re-extracted and removed
/// notes' rows (and their outgoing edges) are deleted — the default incremental path.
pub fn index(vault: &Path, conn: &Connection, full: bool) -> rusqlite::Result<IndexReport> {
    if full {
        conn.execute_batch("DELETE FROM nodes; DELETE FROM edges;")?;
    }

    let all_files = discover_all_files(vault);
    let node_files = discover_nodes(vault);
    let node_paths: HashSet<String> = node_files.iter().map(|f| f.rel.clone()).collect();

    let by_path: HashMap<String, usize> = all_files
        .iter()
        .enumerate()
        .map(|(i, f)| (f.rel.clone(), i))
        .collect();
    let mut by_stem: HashMap<String, Vec<usize>> = HashMap::new();
    for (i, f) in all_files.iter().enumerate() {
        let stem = f
            .rel
            .rsplit('/')
            .next()
            .unwrap_or(&f.rel)
            .trim_end_matches(".md");
        by_stem.entry(stem.to_string()).or_default().push(i);
    }

    let existing: HashMap<String, (i64, i64)> = {
        let mut stmt = conn.prepare("SELECT path, mtime, size FROM nodes")?;
        let rows = stmt.query_map([], |row| {
            Ok((
                row.get::<_, String>(0)?,
                (row.get::<_, i64>(1)?, row.get::<_, i64>(2)?),
            ))
        })?;
        rows.filter_map(Result::ok).collect()
    };

    let mut report = IndexReport {
        total_nodes: node_files.len(),
        ..Default::default()
    };
    let now = now_secs();

    for file in &node_files {
        let (mtime, size) = file_stat(&file.abs);
        let unchanged = !full
            && existing
                .get(&file.rel)
                .map(|&(m, s)| m == mtime && s as u64 == size)
                .unwrap_or(false);
        if unchanged {
            report.unchanged += 1;
            continue;
        }
        let is_new = !existing.contains_key(&file.rel);
        let meta = read_note(file);

        conn.execute(
            "INSERT INTO nodes (path, title, description, status, kind, tags, mtime, size, updated_at)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)
             ON CONFLICT(path) DO UPDATE SET
                title=excluded.title, description=excluded.description, status=excluded.status,
                kind=excluded.kind, tags=excluded.tags, mtime=excluded.mtime, size=excluded.size,
                updated_at=excluded.updated_at",
            rusqlite::params![
                file.rel,
                meta.title,
                meta.description,
                meta.status,
                meta.kind,
                serde_json::to_string(&meta.tags).unwrap_or_else(|_| "[]".to_string()),
                mtime,
                size as i64,
                now,
            ],
        )?;

        conn.execute("DELETE FROM edges WHERE source = ?1", [&file.rel])?;
        for link in extract_links(&meta.body) {
            let resolution = resolve_link(
                &link.target,
                &file.rel,
                &all_files,
                &by_path,
                &by_stem,
                &node_paths,
            );
            match resolution {
                LinkTarget::Dangling => {
                    conn.execute(
                        "INSERT INTO edges (source, target, raw_target, edge_type, dangling, boundary_violation)
                         VALUES (?1, NULL, ?2, 'EXTRACTED', 1, 0)",
                        rusqlite::params![file.rel, link.target],
                    )?;
                }
                LinkTarget::BoundaryViolation(target) => {
                    conn.execute(
                        "INSERT INTO edges (source, target, raw_target, edge_type, dangling, boundary_violation)
                         VALUES (?1, ?2, ?3, 'EXTRACTED', 0, 1)",
                        rusqlite::params![file.rel, target, link.target],
                    )?;
                }
                LinkTarget::OutOfScope(_) => {
                    // Not modeled — see `LinkTarget::OutOfScope` doc comment.
                }
                LinkTarget::Node(candidates) => {
                    for target in candidates {
                        conn.execute(
                            "INSERT INTO edges (source, target, raw_target, edge_type, dangling, boundary_violation)
                             VALUES (?1, ?2, ?3, 'EXTRACTED', 0, 0)",
                            rusqlite::params![file.rel, target, link.target],
                        )?;
                    }
                }
            }
        }

        if is_new {
            report.added += 1;
        } else {
            report.updated += 1;
        }
    }

    for old_path in existing.keys() {
        if !node_paths.contains(old_path) {
            conn.execute("DELETE FROM nodes WHERE path = ?1", [old_path])?;
            conn.execute("DELETE FROM edges WHERE source = ?1", [old_path])?;
            report.removed += 1;
        }
    }

    report.edges =
        conn.query_row("SELECT COUNT(*) FROM edges", [], |r| r.get::<_, i64>(0))? as usize;
    report.dangling_edges =
        conn.query_row("SELECT COUNT(*) FROM edges WHERE dangling = 1", [], |r| {
            r.get::<_, i64>(0)
        })? as usize;
    report.boundary_violations = conn.query_row(
        "SELECT COUNT(*) FROM edges WHERE boundary_violation = 1",
        [],
        |r| r.get::<_, i64>(0),
    )? as usize;

    Ok(report)
}

// ---------------------------------------------------------------------------
// Note resolution for CLI args (wikilink semantics)
// ---------------------------------------------------------------------------

#[derive(Debug)]
pub enum ResolveError {
    NotFound(String),
    Ambiguous(Vec<String>),
}

/// Resolve a CLI note argument against indexed nodes: a vault-relative path (with or without
/// `.md`) or a bare note name. A bare name matching more than one node is reported as ambiguous
/// with every candidate listed — never picked silently (unlike the indexer's same-folder
/// fallback, there's no "source note" here to disambiguate by proximity).
pub fn resolve_note_arg(conn: &Connection, arg: &str) -> Result<String, ResolveError> {
    let cleaned = arg.trim().trim_start_matches("./");
    let exists = |p: &str| -> bool {
        conn.query_row("SELECT 1 FROM nodes WHERE path = ?1", [p], |_| Ok(()))
            .is_ok()
    };
    if exists(cleaned) {
        return Ok(cleaned.to_string());
    }
    if !cleaned.ends_with(".md") {
        let with_ext = format!("{cleaned}.md");
        if exists(&with_ext) {
            return Ok(with_ext);
        }
    }

    let stem = cleaned
        .rsplit('/')
        .next()
        .unwrap_or(cleaned)
        .trim_end_matches(".md");
    let mut stmt = conn
        .prepare("SELECT path FROM nodes WHERE title = ?1 ORDER BY path")
        .expect("valid SQL");
    let candidates: Vec<String> = stmt
        .query_map([stem], |row| row.get::<_, String>(0))
        .expect("valid query")
        .filter_map(Result::ok)
        .collect();

    match candidates.len() {
        0 => Err(ResolveError::NotFound(arg.to_string())),
        1 => Ok(candidates.into_iter().next().unwrap()),
        _ => Err(ResolveError::Ambiguous(candidates)),
    }
}

// ---------------------------------------------------------------------------
// Graph queries
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Direction {
    In,
    Out,
    Both,
}

#[derive(Debug, Clone, Serialize)]
pub struct NeighborNode {
    pub path: String,
    pub title: String,
    pub description: String,
    pub depth: usize,
}

/// BFS out to `depth` hops from `start` (a node path already resolved by `resolve_note_arg`).
/// `direction` selects which edges are traversable: `Out` follows `source -> target`, `In`
/// follows them in reverse, `Both` follows either — the default, since "what's connected to this
/// note" is usually the more useful question than a direction-strict one.
pub fn neighbors(
    conn: &Connection,
    start: &str,
    depth: usize,
    direction: Direction,
) -> rusqlite::Result<Vec<NeighborNode>> {
    let mut out_adj: HashMap<String, Vec<String>> = HashMap::new();
    let mut in_adj: HashMap<String, Vec<String>> = HashMap::new();
    {
        let mut stmt = conn.prepare(
            "SELECT source, target FROM edges WHERE dangling = 0 AND boundary_violation = 0 AND target IS NOT NULL",
        )?;
        let rows = stmt.query_map([], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
        })?;
        for row in rows.filter_map(Result::ok) {
            let (s, t) = row;
            out_adj.entry(s.clone()).or_default().push(t.clone());
            in_adj.entry(t).or_default().push(s);
        }
    }

    let mut visited: HashSet<String> = HashSet::from([start.to_string()]);
    let mut queue: VecDeque<(String, usize)> = VecDeque::from([(start.to_string(), 0)]);
    let mut result = Vec::new();

    while let Some((current, d)) = queue.pop_front() {
        if d >= depth {
            continue;
        }
        let mut next: Vec<String> = Vec::new();
        if direction == Direction::Out || direction == Direction::Both {
            if let Some(v) = out_adj.get(&current) {
                next.extend(v.iter().cloned());
            }
        }
        if direction == Direction::In || direction == Direction::Both {
            if let Some(v) = in_adj.get(&current) {
                next.extend(v.iter().cloned());
            }
        }
        for n in next {
            if visited.insert(n.clone()) {
                queue.push_back((n.clone(), d + 1));
                result.push((n, d + 1));
            }
        }
    }

    let mut out = Vec::with_capacity(result.len());
    for (path, d) in result {
        let (title, description): (String, String) = conn.query_row(
            "SELECT title, description FROM nodes WHERE path = ?1",
            [&path],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )?;
        out.push(NeighborNode {
            path,
            title,
            description,
            depth: d,
        });
    }
    out.sort_by(|a, b| a.depth.cmp(&b.depth).then_with(|| a.path.cmp(&b.path)));
    Ok(out)
}

#[derive(Debug, Clone, Serialize)]
pub struct StatsReport {
    pub nodes: usize,
    pub edges: usize,
    pub dangling_edges: usize,
    pub boundary_violations: usize,
    pub top_linked: Vec<TopLinked>,
}

#[derive(Debug, Clone, Serialize)]
pub struct TopLinked {
    pub path: String,
    pub title: String,
    pub in_degree: usize,
}

pub fn stats(conn: &Connection) -> rusqlite::Result<StatsReport> {
    let nodes = conn.query_row("SELECT COUNT(*) FROM nodes", [], |r| r.get::<_, i64>(0))? as usize;
    let edges = conn.query_row(
        "SELECT COUNT(*) FROM edges WHERE dangling = 0 AND boundary_violation = 0",
        [],
        |r| r.get::<_, i64>(0),
    )? as usize;
    let dangling_edges =
        conn.query_row("SELECT COUNT(*) FROM edges WHERE dangling = 1", [], |r| {
            r.get::<_, i64>(0)
        })? as usize;
    let boundary_violations = conn.query_row(
        "SELECT COUNT(*) FROM edges WHERE boundary_violation = 1",
        [],
        |r| r.get::<_, i64>(0),
    )? as usize;

    let mut stmt = conn.prepare(
        "SELECT n.path, n.title, COUNT(e.id) AS in_degree
         FROM nodes n LEFT JOIN edges e
           ON e.target = n.path AND e.dangling = 0 AND e.boundary_violation = 0
         GROUP BY n.path
         ORDER BY in_degree DESC, n.path ASC
         LIMIT 10",
    )?;
    let top_linked = stmt
        .query_map([], |row| {
            Ok(TopLinked {
                path: row.get(0)?,
                title: row.get(1)?,
                in_degree: row.get::<_, i64>(2)? as usize,
            })
        })?
        .filter_map(Result::ok)
        .collect();

    Ok(StatsReport {
        nodes,
        edges,
        dangling_edges,
        boundary_violations,
        top_linked,
    })
}

#[derive(Debug, Clone, Serialize)]
pub struct PathReport {
    pub from: String,
    pub to: String,
    pub connected: bool,
    pub path: Vec<String>,
}

/// Shortest path between two nodes via BFS over the undirected view of the graph (an edge is
/// traversable in either direction) — the natural notion of "how are these connected" for a
/// wikilink graph, matching `neighbors`' `Both` default.
pub fn shortest_path(conn: &Connection, from: &str, to: &str) -> rusqlite::Result<PathReport> {
    if from == to {
        return Ok(PathReport {
            from: from.to_string(),
            to: to.to_string(),
            connected: true,
            path: vec![from.to_string()],
        });
    }
    let mut adj: HashMap<String, Vec<String>> = HashMap::new();
    {
        let mut stmt = conn.prepare(
            "SELECT source, target FROM edges WHERE dangling = 0 AND boundary_violation = 0 AND target IS NOT NULL",
        )?;
        let rows = stmt.query_map([], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
        })?;
        for row in rows.filter_map(Result::ok) {
            let (s, t) = row;
            adj.entry(s.clone()).or_default().push(t.clone());
            adj.entry(t).or_default().push(s);
        }
    }

    let mut visited: HashSet<String> = HashSet::from([from.to_string()]);
    let mut queue: VecDeque<String> = VecDeque::from([from.to_string()]);
    let mut parent: HashMap<String, String> = HashMap::new();

    while let Some(current) = queue.pop_front() {
        if current == to {
            let mut path = vec![current.clone()];
            let mut cur = current;
            while let Some(p) = parent.get(&cur) {
                path.push(p.clone());
                cur = p.clone();
            }
            path.reverse();
            return Ok(PathReport {
                from: from.to_string(),
                to: to.to_string(),
                connected: true,
                path,
            });
        }
        if let Some(next) = adj.get(&current) {
            for n in next {
                if visited.insert(n.clone()) {
                    parent.insert(n.clone(), current.clone());
                    queue.push_back(n.clone());
                }
            }
        }
    }

    Ok(PathReport {
        from: from.to_string(),
        to: to.to_string(),
        connected: false,
        path: Vec::new(),
    })
}
