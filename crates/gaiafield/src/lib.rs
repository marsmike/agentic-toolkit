//! gaiafield — knowledge-graph extraction and inference over an agentic-toolkit vault.
//!
//! Two layers, never conflated (`contract/KNOWLEDGE_API.md`, "v2 — inferred edges"):
//!
//! - **v1, `extracted`** (top half of this file): deterministic — parse wikilinks, frontmatter,
//!   and tags into a queryable SQLite store. No model call, can't hallucinate an edge — see
//!   `vault/04_Resources/Concepts/Deterministic-vs-Inferred-Graph-Edges.md`.
//! - **v2, `inferred`** (bottom half, from `MODEL_REPO` on): statistical — embed each node's
//!   content with a static (non-transformer) Model2Vec model and score pairwise similarity.
//!   Report-only, forever: nothing in this half ever writes vault content, and nothing in it ever
//!   mutates an `extracted` row (contract rules 1–2). See README "Embedding backend" for the model
//!   choice and its musl cross-compilation story, and "Calibration" for the gates.
//!
//! Mirrors `crates/farsight` for vault resolution and tolerant frontmatter parsing so the two
//! engines behave consistently for a caller that uses both.

use model2vec_rs::model::StaticModel;
use rusqlite::Connection;
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet, VecDeque};
use std::io::Read;
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

        -- v2 — inferred edges (contract/KNOWLEDGE_API.md, 'v2 — inferred edges (R5)'). Additive:
        -- these tables never share rows with `nodes`/`edges` above, and `infer --reset` (see
        -- `infer`) deletes exactly these three, restoring the exact v1 graph (contract rule 2).
        CREATE TABLE IF NOT EXISTS embeddings (
            path   TEXT PRIMARY KEY,
            mtime  INTEGER NOT NULL,
            size   INTEGER NOT NULL,
            model  TEXT NOT NULL,
            dims   INTEGER NOT NULL,
            vector BLOB NOT NULL
        );
        CREATE TABLE IF NOT EXISTS inferred_edges (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            target TEXT NOT NULL,
            score  REAL NOT NULL,
            label  TEXT NOT NULL,
            model  TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS inferred_edges_source_idx ON inferred_edges(source);
        CREATE INDEX IF NOT EXISTS inferred_edges_target_idx ON inferred_edges(target);
        CREATE TABLE IF NOT EXISTS gaiafield_meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
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
            // The removed note's own outgoing links are meaningless now — it no longer exists to
            // author them. But other notes' *incoming* edges into it are not deleted: those
            // wikilinks are still real text sitting in other notes' bodies ("dangling links are
            // data" — see the module doc). Re-flag them dangling rather than dropping the row, so
            // `stats` still counts them and `neighbors`/`path` exclude them exactly like any
            // scan-time dangling edge, instead of silently traversing into a node that no longer
            // has a row in `nodes` (the crash/misroute this fixes).
            conn.execute("DELETE FROM edges WHERE source = ?1", [old_path])?;
            conn.execute(
                "UPDATE edges SET target = NULL, dangling = 1 WHERE target = ?1",
                [old_path],
            )?;
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
    /// v2 fields below are `None`/0 until `infer` has run at least once against this db.
    pub inferred_edges: usize,
    pub ambiguous_edges: usize,
    pub model: Option<String>,
    pub high_gate: Option<f64>,
    pub low_gate: Option<f64>,
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

    let inferred_edges = conn.query_row(
        "SELECT COUNT(*) FROM inferred_edges WHERE label = 'INFERRED'",
        [],
        |r| r.get::<_, i64>(0),
    )? as usize;
    let ambiguous_edges = conn.query_row(
        "SELECT COUNT(*) FROM inferred_edges WHERE label = 'AMBIGUOUS'",
        [],
        |r| r.get::<_, i64>(0),
    )? as usize;
    let model = get_meta(conn, META_MODEL);
    let high_gate = get_meta(conn, META_HIGH_GATE).and_then(|v| v.parse::<f64>().ok());
    let low_gate = get_meta(conn, META_LOW_GATE).and_then(|v| v.parse::<f64>().ok());

    Ok(StatsReport {
        nodes,
        edges,
        dangling_edges,
        boundary_violations,
        top_linked,
        inferred_edges,
        ambiguous_edges,
        model,
        high_gate,
        low_gate,
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

// ---------------------------------------------------------------------------
// v2 — inferred edges (contract/KNOWLEDGE_API.md, "v2 — inferred edges (R5)")
//
// Everything below is a report-only statistical layer on top of the deterministic graph above:
// it never mutates `nodes`/`edges` (contract rule 2 — "inference never mutates extraction"), it
// never writes vault content (contract rule 1 — "report-only, forever"), and its gates are
// properties of `MODEL_NAME`/`MODEL_REVISION`, not universal constants (contract rule 3). See
// README "Embedding backend" for the model choice and its musl cross-compilation story, and
// "Calibration" for how `DEFAULT_HIGH_GATE`/`DEFAULT_LOW_GATE` were derived.
// ---------------------------------------------------------------------------

/// HuggingFace repo + pinned commit this crate downloads (or reuses, once verified) the Model2Vec
/// static-embedding model from. Static embeddings — not a transformer forward pass — so encoding
/// is a deterministic lookup-and-average with no C/ONNX runtime involved (README explains why
/// this is what makes the model musl-friendly). Switching either constant invalidates the gates
/// below and requires a fresh `calibrate` run (contract rule 3).
pub const MODEL_REPO: &str = "minishlab/potion-base-8M";
pub const MODEL_NAME: &str = "potion-base-8M";
pub const MODEL_REVISION: &str = "bf8b056651a2c21b8d2565580b8569da283cab23";
pub const MODEL_DIMS: usize = 256;

/// `(filename, pinned sha256)` — every file this crate ever fetches from the network. A file
/// already present locally with a matching hash is never re-downloaded; a mismatch (corrupted
/// download, or the pinned revision moved) is a hard error, never a silent fallback to whatever
/// bytes happen to be on disk or on the wire.
const MODEL_FILES: [(&str, &str); 3] = [
    (
        "config.json",
        "2a6ac0e9aaa356a68a5688070db78fc3a464fefe85d2f06a1905ce3718687553",
    ),
    (
        "tokenizer.json",
        "e67e803f624fb4d67dea1c730d06e1067e1b14d830e2c2202569e3ef0f70bb50",
    ),
    (
        "model.safetensors",
        "f65d0f325faadc1e121c319e2faa41170d3fa07d8c89abd48ca5358d9a223de2",
    ),
];

/// Default gates, calibrated against `./vault`'s planted clusters (README "Calibration") via
/// `gaiafield calibrate --clusters <toolkit-concepts/birding/homelab spec>`.
///
/// **R5 recalibration, replacing the original pooled-mean method (the bias lesson, README
/// "Calibration"):** the original `calibrate()` pooled every intra-cluster pair into one mean and
/// every cross-cluster pair into another, regardless of which cluster contributed how many pairs.
/// `toolkit-concepts` (57 notes, C(57,2) = 1596 intra pairs) drowned out `birding`/`homelab` (7
/// notes each, 21 intra pairs apiece) in that pool, and its own intra-mean (0.617) turned out to
/// be *lower* than the birding↔homelab cross-mean (0.630) — a grab-bag cluster's "same topic"
/// pairs scored less self-similar than two genuinely different topics scored to each other. Gates
/// derived from the pooled numbers (`intra_mean: 0.6222, cross_mean: 0.5418`) inherited that
/// distortion: at high/low 0.60/0.56, 70% of all non-linked pairs in the full vault landed
/// `INFERRED`+`AMBIGUOUS`, and a birding note's top-15 candidates by raw score held only 2
/// same-cluster hits.
///
/// `calibrate()` now computes per-cluster-pair statistics and derives intra/cross means from only
/// the *tight* clusters (see its doc comment for the leave-one-out tightness rule) — on this
/// vault, `birding`/`homelab` (`toolkit-concepts` self-excludes). Re-running against `./vault`
/// (copied to scratch) gave `intra_mean: 0.8067, cross_mean: 0.6298, separation: 0.1769,
/// suggested_high_gate: 0.7183 (cross + 0.5·separation — see "Calibration" for why the midpoint,
/// not the old 0.75-of-gap, is the right split now), suggested_low_gate: 0.6740` — rounded to 2
/// decimals here. A snapshot, not recomputed at runtime — recalibrate and update these if
/// `MODEL_REVISION` ever changes.
pub const DEFAULT_HIGH_GATE: f64 = 0.72;
pub const DEFAULT_LOW_GATE: f64 = 0.67;

const META_MODEL: &str = "model";
const META_DIMS: &str = "dims";
const META_REVISION: &str = "revision";
const META_HIGH_GATE: &str = "high_gate";
const META_LOW_GATE: &str = "low_gate";

fn sha256_hex(bytes: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    Sha256::digest(bytes)
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect()
}

/// Default model cache directory: a sibling of the db file (`<db-parent>/models/<model-name>/`),
/// so a fresh vault's first `infer` downloads once and every later run against the same db reuses
/// it untouched. Override with `TOOLKIT_GAIAFIELD_MODEL_DIR` to point many db paths at one shared
/// cache — the test suite does exactly this so parallel throwaway-db tests share one download.
pub fn resolve_model_dir(db_path: &Path) -> PathBuf {
    if let Ok(env_value) = std::env::var("TOOLKIT_GAIAFIELD_MODEL_DIR") {
        if !env_value.is_empty() {
            return PathBuf::from(shellexpand_home(&env_value));
        }
    }
    db_path
        .parent()
        .map(|p| p.join("models").join(MODEL_NAME))
        .unwrap_or_else(|| PathBuf::from(MODEL_NAME))
}

/// Connect timeout for the model-file download — the TCP+TLS handshake must complete within this
/// window or the call fails cleanly rather than hanging indefinitely on a stalled network.
const DOWNLOAD_CONNECT_TIMEOUT: std::time::Duration = std::time::Duration::from_secs(10);
/// Overall timeout for the whole download (connect + headers + body) — bounds a slow-drip
/// connection that completes the handshake but then stalls mid-transfer, which a connect-only
/// timeout would never catch.
const DOWNLOAD_TOTAL_TIMEOUT: std::time::Duration = std::time::Duration::from_secs(120);

fn download_agent() -> ureq::Agent {
    ureq::AgentBuilder::new()
        .timeout_connect(DOWNLOAD_CONNECT_TIMEOUT)
        .timeout(DOWNLOAD_TOTAL_TIMEOUT)
        .build()
}

fn download(url: &str) -> Result<Vec<u8>, String> {
    let response = download_agent().get(url).call().map_err(|e| match e {
        ureq::Error::Transport(ref t)
            if matches!(
                t.kind(),
                ureq::ErrorKind::ConnectionFailed | ureq::ErrorKind::Io
            ) =>
        {
            format!(
                "download failed for {url}: timed out or could not connect (connect timeout \
                 {DOWNLOAD_CONNECT_TIMEOUT:?}, overall timeout {DOWNLOAD_TOTAL_TIMEOUT:?}): {e}"
            )
        }
        other => format!("download failed for {url}: {other}"),
    })?;
    let mut bytes = Vec::new();
    response
        .into_reader()
        .read_to_end(&mut bytes)
        .map_err(|e| {
            format!(
                "failed reading response body for {url} (overall timeout \
                 {DOWNLOAD_TOTAL_TIMEOUT:?} may have been hit mid-transfer): {e}"
            )
        })?;
    Ok(bytes)
}

/// Guards the download-and-verify path below so two threads in the same process racing to warm
/// the same (or different) `model_dir` never step on each other — e.g. the test suite's several
/// `infer` tests, each on its own throwaway db but sharing one model cache directory (see
/// `shared_model_dir` in tests/graph_test.rs). Cross-process concurrent first-downloads are still
/// safe (each writes a uniquely-named temp file, see `unique_suffix`), just not deduplicated.
static ENSURE_MODEL_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

/// A per-call-unique string (process id + monotonic counter + timestamp) for temp-file names, so
/// two concurrent downloads of the same model file — even across processes — never share a temp
/// path and race each other's rename.
fn unique_suffix() -> String {
    static COUNTER: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
    let n = COUNTER.fetch_add(1, std::sync::atomic::Ordering::SeqCst);
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    format!("{}-{nanos}-{n}", std::process::id())
}

/// Ensure the pinned model files exist locally under `model_dir` and match their pinned sha256
/// (downloading whatever's missing or mismatched), then load them. Fully offline afterward — once
/// all three files are present and verified, no network call happens on this or any later run
/// against the same `model_dir`.
pub fn ensure_model(model_dir: &Path) -> Result<StaticModel, String> {
    let _guard = ENSURE_MODEL_LOCK.lock().unwrap_or_else(|e| e.into_inner());
    std::fs::create_dir_all(model_dir).map_err(|e| format!("cannot create model dir: {e}"))?;
    for (name, expected_sha) in MODEL_FILES {
        let path = model_dir.join(name);
        let needs_download = match std::fs::read(&path) {
            Ok(bytes) => sha256_hex(&bytes) != expected_sha,
            Err(_) => true,
        };
        if needs_download {
            let url =
                format!("https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{name}");
            let bytes = download(&url)?;
            let actual = sha256_hex(&bytes);
            if actual != expected_sha {
                return Err(format!(
                    "downloaded {name} sha256 mismatch: expected {expected_sha}, got {actual} \
                     — pinned model corrupted in transit or the pinned revision moved; refusing \
                     to load it"
                ));
            }
            let tmp = path.with_file_name(format!("{name}.tmp-{}", unique_suffix()));
            std::fs::write(&tmp, &bytes).map_err(|e| format!("cannot write {name}: {e}"))?;
            std::fs::rename(&tmp, &path).map_err(|e| format!("cannot install {name}: {e}"))?;
        }
    }
    StaticModel::from_pretrained(model_dir, None, None, None)
        .map_err(|e| format!("failed to load model from {}: {e}", model_dir.display()))
}

/// The text embedded for a note: title, description, tags, and body concatenated. Same text in,
/// same vector out (Model2Vec's static lookup-and-average has no sampling, no randomness).
fn embed_text(meta: &NoteMeta) -> String {
    format!(
        "{}\n{}\n{}\n{}",
        meta.title,
        meta.description,
        meta.tags.join(" "),
        meta.body
    )
}

fn vector_to_bytes(v: &[f32]) -> Vec<u8> {
    let mut out = Vec::with_capacity(v.len() * 4);
    for x in v {
        out.extend_from_slice(&x.to_le_bytes());
    }
    out
}

fn bytes_to_vector(b: &[u8]) -> Vec<f32> {
    b.chunks_exact(4)
        .map(|c| f32::from_le_bytes(c.try_into().expect("chunks_exact(4) yields 4 bytes")))
        .collect()
}

fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    let dot: f32 = a.iter().zip(b).map(|(x, y)| x * y).sum();
    let na: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let nb: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    if na == 0.0 || nb == 0.0 {
        0.0
    } else {
        dot / (na * nb)
    }
}

/// Canonical (unordered-pair) key: inferred edges are a symmetric similarity, stored once per
/// pair with the lexicographically smaller path first, so `candidates`/`surprise` never see the
/// same pair twice under two different orderings.
fn canonical_pair(a: &str, b: &str) -> (String, String) {
    if a <= b {
        (a.to_string(), b.to_string())
    } else {
        (b.to_string(), a.to_string())
    }
}

fn set_meta(conn: &Connection, key: &str, value: &str) -> rusqlite::Result<()> {
    conn.execute(
        "INSERT INTO gaiafield_meta (key, value) VALUES (?1, ?2)
         ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        rusqlite::params![key, value],
    )?;
    Ok(())
}

fn get_meta(conn: &Connection, key: &str) -> Option<String> {
    conn.query_row(
        "SELECT value FROM gaiafield_meta WHERE key = ?1",
        [key],
        |r| r.get::<_, String>(0),
    )
    .ok()
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct InferReport {
    pub embedded: usize,
    pub inferred_edges: usize,
    pub ambiguous_edges: usize,
    pub model: String,
    pub high_gate: f64,
    pub low_gate: f64,
    pub elapsed_ms: u64,
}

/// Embed every node's content and score every pair for similarity, writing `INFERRED`/`AMBIGUOUS`
/// rows into `inferred_edges` (contract rule 5, surprise scoring lives in `candidates`/`surprise`
/// below, not here).
///
/// - Default (incremental): re-embeds only new/changed notes (mtime+size, mirroring `index`), and
///   rescores only pairs where at least one side changed — a pair with neither side changed keeps
///   whatever row (or absence of one) it already had.
/// - `full`: drops `embeddings`/`inferred_edges` and recomputes everything from scratch.
/// - `reset`: drops `embeddings`/`inferred_edges`/`gaiafield_meta` and does nothing else —
///   `nodes`/`edges` are never touched, so the graph after a reset is byte-identical to a db that
///   was never `infer`'d (contract rule 2; exercised by
///   `infer_reset_restores_exact_v1_graph` in tests/graph_test.rs).
///
/// A pair that already has an `extracted` edge (either direction, non-dangling, non-boundary)
/// never gets an inferred row — nothing to suggest where a wikilink already exists.
pub fn infer(
    vault: &Path,
    conn: &Connection,
    model_dir: &Path,
    full: bool,
    reset: bool,
) -> Result<InferReport, String> {
    let start = std::time::Instant::now();

    if reset {
        conn.execute_batch(
            "DELETE FROM inferred_edges; DELETE FROM embeddings; DELETE FROM gaiafield_meta;",
        )
        .map_err(|e| e.to_string())?;
        return Ok(InferReport {
            elapsed_ms: start.elapsed().as_millis() as u64,
            ..Default::default()
        });
    }

    // Inference is a pass on top of the deterministic layer — keep it fresh, incrementally.
    index(vault, conn, false).map_err(|e| e.to_string())?;

    if full {
        conn.execute_batch("DELETE FROM inferred_edges; DELETE FROM embeddings;")
            .map_err(|e| e.to_string())?;
    }

    let model = ensure_model(model_dir)?;

    let node_files = discover_nodes(vault);
    let node_paths: HashSet<String> = node_files.iter().map(|f| f.rel.clone()).collect();

    let existing: HashMap<String, (i64, i64)> = {
        let mut stmt = conn
            .prepare("SELECT path, mtime, size FROM embeddings")
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map([], |row| {
                Ok((
                    row.get::<_, String>(0)?,
                    (row.get::<_, i64>(1)?, row.get::<_, i64>(2)?),
                ))
            })
            .map_err(|e| e.to_string())?;
        rows.filter_map(Result::ok).collect()
    };

    let mut embedded_count = 0usize;
    // Paths whose embedding changed this run (added or updated) — the only ones that need
    // rescoring against the rest of the corpus (incremental rule).
    let mut changed_paths: Vec<String> = Vec::new();

    for file in &node_files {
        let (mtime, size) = file_stat(&file.abs);
        let unchanged = existing
            .get(&file.rel)
            .map(|&(m, s)| m == mtime && s as u64 == size)
            .unwrap_or(false);
        if unchanged {
            continue;
        }
        let meta = read_note(file);
        let text = embed_text(&meta);
        let vector = model.encode_single(&text);
        conn.execute(
            "INSERT INTO embeddings (path, mtime, size, model, dims, vector)
             VALUES (?1, ?2, ?3, ?4, ?5, ?6)
             ON CONFLICT(path) DO UPDATE SET
                mtime=excluded.mtime, size=excluded.size, model=excluded.model,
                dims=excluded.dims, vector=excluded.vector",
            rusqlite::params![
                file.rel,
                mtime,
                size as i64,
                MODEL_NAME,
                MODEL_DIMS as i64,
                vector_to_bytes(&vector),
            ],
        )
        .map_err(|e| e.to_string())?;
        embedded_count += 1;
        changed_paths.push(file.rel.clone());
    }

    // Notes no longer in scope: drop their embedding and every inferred edge touching them —
    // mirrors `index`'s node-removal handling, but embeddings have no "dangling" concept (an
    // inferred edge to a vanished note is simply not a candidate anymore).
    for old_path in existing.keys() {
        if !node_paths.contains(old_path) {
            conn.execute("DELETE FROM embeddings WHERE path = ?1", [old_path])
                .map_err(|e| e.to_string())?;
            conn.execute(
                "DELETE FROM inferred_edges WHERE source = ?1 OR target = ?1",
                [old_path],
            )
            .map_err(|e| e.to_string())?;
        }
    }

    // Clear stale rows for changed paths before rescoring — a pair may have moved bands (or off
    // the low gate entirely) since its last score.
    for p in &changed_paths {
        conn.execute(
            "DELETE FROM inferred_edges WHERE source = ?1 OR target = ?1",
            [p],
        )
        .map_err(|e| e.to_string())?;
    }

    let all_embedded: Vec<(String, Vec<f32>)> = {
        let mut stmt = conn
            .prepare("SELECT path, vector FROM embeddings")
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map([], |row| {
                Ok((row.get::<_, String>(0)?, row.get::<_, Vec<u8>>(1)?))
            })
            .map_err(|e| e.to_string())?;
        rows.filter_map(Result::ok)
            .map(|(p, b)| (p, bytes_to_vector(&b)))
            .collect()
    };

    let extracted_pairs: HashSet<(String, String)> = {
        let mut stmt = conn
            .prepare(
                "SELECT source, target FROM edges \
                 WHERE dangling = 0 AND boundary_violation = 0 AND target IS NOT NULL",
            )
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map([], |row| {
                Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
            })
            .map_err(|e| e.to_string())?;
        rows.filter_map(Result::ok)
            .map(|(a, b)| canonical_pair(&a, &b))
            .collect()
    };

    let changed_set: HashSet<&String> = changed_paths.iter().collect();
    for i in 0..all_embedded.len() {
        for j in (i + 1)..all_embedded.len() {
            let (a, va) = &all_embedded[i];
            let (b, vb) = &all_embedded[j];
            if !changed_set.contains(a) && !changed_set.contains(b) {
                continue;
            }
            let (source, target) = canonical_pair(a, b);
            if extracted_pairs.contains(&(source.clone(), target.clone())) {
                continue;
            }
            let score = cosine_similarity(va, vb) as f64;
            if score < DEFAULT_LOW_GATE {
                continue;
            }
            let label = if score >= DEFAULT_HIGH_GATE {
                "INFERRED"
            } else {
                "AMBIGUOUS"
            };
            conn.execute(
                "INSERT INTO inferred_edges (source, target, score, label, model) \
                 VALUES (?1, ?2, ?3, ?4, ?5)",
                rusqlite::params![source, target, score, label, MODEL_NAME],
            )
            .map_err(|e| e.to_string())?;
        }
    }

    set_meta(conn, META_MODEL, MODEL_NAME).map_err(|e| e.to_string())?;
    set_meta(conn, META_DIMS, &MODEL_DIMS.to_string()).map_err(|e| e.to_string())?;
    set_meta(conn, META_REVISION, MODEL_REVISION).map_err(|e| e.to_string())?;
    set_meta(conn, META_HIGH_GATE, &DEFAULT_HIGH_GATE.to_string()).map_err(|e| e.to_string())?;
    set_meta(conn, META_LOW_GATE, &DEFAULT_LOW_GATE.to_string()).map_err(|e| e.to_string())?;

    let inferred_edges = conn
        .query_row(
            "SELECT COUNT(*) FROM inferred_edges WHERE label = 'INFERRED'",
            [],
            |r| r.get::<_, i64>(0),
        )
        .map_err(|e| e.to_string())? as usize;
    let ambiguous_edges = conn
        .query_row(
            "SELECT COUNT(*) FROM inferred_edges WHERE label = 'AMBIGUOUS'",
            [],
            |r| r.get::<_, i64>(0),
        )
        .map_err(|e| e.to_string())? as usize;

    Ok(InferReport {
        embedded: embedded_count,
        inferred_edges,
        ambiguous_edges,
        model: MODEL_NAME.to_string(),
        high_gate: DEFAULT_HIGH_GATE,
        low_gate: DEFAULT_LOW_GATE,
        elapsed_ms: start.elapsed().as_millis() as u64,
    })
}

/// Build an adjacency map over `extracted` edges only (undirected — mirrors `neighbors`'/
/// `shortest_path`'s `Both` view), reused across many BFS calls so `surprise` doesn't rebuild it
/// once per pair.
fn build_extracted_adjacency(conn: &Connection) -> rusqlite::Result<HashMap<String, Vec<String>>> {
    let mut adj: HashMap<String, Vec<String>> = HashMap::new();
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
    Ok(adj)
}

/// BFS distance from `start` to every node reachable over `adj` (deterministic/`extracted` edges
/// only). Absence from the returned map means unreachable — `det_distance: null`.
fn bfs_distances_from(adj: &HashMap<String, Vec<String>>, start: &str) -> HashMap<String, usize> {
    let mut dist: HashMap<String, usize> = HashMap::from([(start.to_string(), 0)]);
    let mut queue: VecDeque<String> = VecDeque::from([start.to_string()]);
    while let Some(current) = queue.pop_front() {
        let d = dist[&current];
        if let Some(next) = adj.get(&current) {
            for n in next {
                if !dist.contains_key(n) {
                    dist.insert(n.clone(), d + 1);
                    queue.push_back(n.clone());
                }
            }
        }
    }
    dist
}

/// Surprise formula (contract rule 5 — "derived, not stored magic"): `score * (1 - 1/(1+d))`
/// where `d` is the deterministic BFS distance; unreachable (`d = ∞`) collapses the fraction to 1,
/// i.e. `score * 1`. A same-neighborhood inferred edge (small `d`) is unsurprising even at a high
/// score; a high-score edge between two notes with no deterministic route at all is maximally
/// surprising. Documented here and in README "Surprise scoring" as the single source of truth —
/// both `candidates` and `surprise` call this, never reimplement it.
fn surprise_score(score: f64, det_distance: Option<usize>) -> f64 {
    match det_distance {
        Some(d) => score * (1.0 - 1.0 / (1.0 + d as f64)),
        None => score,
    }
}

/// Same "subtree" per README "Surprise scoring": the first two path segments (e.g.
/// `02_Projects/field-guide`), or the whole path when there's no second segment (a root note).
/// Cheap, deterministic, and matches the granularity this vault's planted clusters are organized
/// at — a project's own sub-notes share a subtree; two different projects, or a project and a
/// resource, do not.
fn same_subtree(a: &str, b: &str) -> bool {
    fn key(p: &str) -> &str {
        match p.match_indices('/').nth(1) {
            Some((idx, _)) => &p[..idx],
            None => p,
        }
    }
    key(a) == key(b)
}

#[derive(Debug, Clone, Serialize)]
pub struct CandidateRow {
    pub path: String,
    pub score: f64,
    pub label: String,
    pub kind: String,
    pub det_distance: Option<usize>,
    pub surprise: f64,
}

/// Inferred candidates for `note`: every stored inferred edge touching it (already excludes pairs
/// with an existing extracted edge — `infer` never stores those), `INFERRED` always included,
/// `AMBIGUOUS` only when `include_ambiguous`. Sorted by score descending, top `k`.
pub fn candidates(
    conn: &Connection,
    note: &str,
    k: usize,
    include_ambiguous: bool,
) -> rusqlite::Result<Vec<CandidateRow>> {
    let mut stmt = conn.prepare(
        "SELECT source, target, score, label FROM inferred_edges WHERE source = ?1 OR target = ?1",
    )?;
    let rows = stmt.query_map([note], |row| {
        Ok((
            row.get::<_, String>(0)?,
            row.get::<_, String>(1)?,
            row.get::<_, f64>(2)?,
            row.get::<_, String>(3)?,
        ))
    })?;

    let adj = build_extracted_adjacency(conn)?;
    let dist = bfs_distances_from(&adj, note);

    let mut out: Vec<CandidateRow> = Vec::new();
    for row in rows.filter_map(Result::ok) {
        let (source, target, score, label) = row;
        if label == "AMBIGUOUS" && !include_ambiguous {
            continue;
        }
        let other = if source == note { target } else { source };
        let det_distance = dist.get(&other).copied();
        let surprise = surprise_score(score, det_distance);
        out.push(CandidateRow {
            path: other,
            score,
            label,
            kind: "inferred".to_string(),
            det_distance,
            surprise,
        });
    }
    out.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.path.cmp(&b.path))
    });
    out.truncate(k);
    Ok(out)
}

#[derive(Debug, Clone, Serialize)]
pub struct SurpriseRow {
    pub a: String,
    pub b: String,
    pub score: f64,
    pub surprise: f64,
    pub det_distance: Option<usize>,
    pub same_subtree: bool,
    /// `INFERRED`/`AMBIGUOUS` (contract/KNOWLEDGE_API.md's v2 gates) — added alongside
    /// `include_ambiguous` below so `surprise` gates its AMBIGUOUS-band pairs the same way
    /// `candidates` always has; the CLI spec this crate was originally built against omitted both
    /// (a spec bug — the binding contract requires every inferred row to carry a label and every
    /// AMBIGUOUS-surfacing surface to gate on it), which let `surprise` leak the ambiguous band by
    /// default with no way for a caller to even see which label a row carried.
    pub label: String,
    /// The embedding model name (contract rule 3 — "a gate value without its model name is
    /// meaningless"). `candidates` doesn't repeat this per-row (see README "Embedding backend"),
    /// but `surprise` gains it here since a row's `label` is only meaningful alongside the model
    /// that produced its score, and unlike `candidates` (always scoped to one queried note),
    /// `surprise` rows can span calls against differently-inferred dbs.
    pub model: String,
}

/// Every stored inferred edge at or above `min_score`, ranked by surprise descending — the
/// cross-domain candidates worth a human look (contract rule 5). `include_ambiguous` mirrors
/// `candidates`: `false` (the default) excludes `AMBIGUOUS`-labeled rows, since `surprise` is a
/// *reporting* surface subject to the same v2 contract rule as `candidates` ("AMBIGUOUS ...
/// surfaced only when a caller explicitly asks; never proposed proactively") — the original CLI
/// spec this crate was built against had no such flag and no `label` field at all, which is a spec
/// bug the contract overrides, not a real exemption for `surprise`.
pub fn surprise(
    conn: &Connection,
    top: usize,
    min_score: f64,
    include_ambiguous: bool,
) -> rusqlite::Result<Vec<SurpriseRow>> {
    let mut stmt = conn.prepare(
        "SELECT source, target, score, label, model FROM inferred_edges WHERE score >= ?1",
    )?;
    let rows = stmt.query_map([min_score], |row| {
        Ok((
            row.get::<_, String>(0)?,
            row.get::<_, String>(1)?,
            row.get::<_, f64>(2)?,
            row.get::<_, String>(3)?,
            row.get::<_, String>(4)?,
        ))
    })?;

    let adj = build_extracted_adjacency(conn)?;
    let mut dist_cache: HashMap<String, HashMap<String, usize>> = HashMap::new();

    let mut out: Vec<SurpriseRow> = Vec::new();
    for row in rows.filter_map(Result::ok) {
        let (a, b, score, label, model) = row;
        if label == "AMBIGUOUS" && !include_ambiguous {
            continue;
        }
        let dist = dist_cache
            .entry(a.clone())
            .or_insert_with(|| bfs_distances_from(&adj, &a));
        let det_distance = dist.get(&b).copied();
        let surprise = surprise_score(score, det_distance);
        out.push(SurpriseRow {
            same_subtree: same_subtree(&a, &b),
            a,
            b,
            score,
            surprise,
            det_distance,
            label,
            model,
        });
    }
    out.sort_by(|x, y| {
        y.surprise
            .partial_cmp(&x.surprise)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| x.a.cmp(&y.a))
            .then_with(|| x.b.cmp(&y.b))
    });
    out.truncate(top);
    Ok(out)
}

#[derive(Debug, Deserialize)]
struct ClusterSpec {
    clusters: HashMap<String, Vec<String>>,
}

/// Pairwise-similarity statistics for one cluster pair (`a == b` for an intra-cluster group).
#[derive(Debug, Clone, Serialize)]
pub struct ClusterPairStat {
    pub mean: f64,
    pub n: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct CalibrateReport {
    pub intra_mean: f64,
    pub cross_mean: f64,
    pub separation: f64,
    pub suggested_high_gate: f64,
    pub suggested_low_gate: f64,
    pub model: String,
    /// Clusters whose own intra-mean cleared the tightness bar (see `calibrate`'s doc comment) —
    /// `intra_mean`/`cross_mean`/`separation` above are derived from only these. Sorted for
    /// deterministic JSON output.
    pub tight_clusters: Vec<String>,
    /// Every cluster pair's raw (mean, n), keyed `"<a>~<b>"` with `a <= b` lexicographically (so
    /// an intra-cluster group reads `"<name>~<name>"`) — the full breakdown `intra_mean`/
    /// `cross_mean` above compress away. A `BTreeMap` so JSON output is key-sorted, not
    /// insertion-order-dependent.
    pub cluster_pairs: std::collections::BTreeMap<String, ClusterPairStat>,
}

fn pair_key(a: &str, b: &str) -> String {
    if a <= b {
        format!("{a}~{b}")
    } else {
        format!("{b}~{a}")
    }
}

fn mean_of(v: &[f64]) -> f64 {
    if v.is_empty() {
        0.0
    } else {
        v.iter().sum::<f64>() / v.len() as f64
    }
}

/// Calibration method (contract rule 3 — gates are model-calibrated, not universal): read a
/// `{"clusters": {"name": [paths...]}}` spec, look up each listed path's already-embedded vector
/// (run `infer` first — this measures the model's own embeddings, it never embeds anything
/// itself), and group all pairwise cosine similarities by cluster pair.
///
/// **The bias lesson (R5 rewrite — this crate's own calibration was broken, see
/// `DEFAULT_HIGH_GATE`'s doc comment for the incident): pooled means overfit to cluster-size
/// imbalance.** The original method pooled every intra-cluster pair across every cluster into one
/// `intra_mean`, and every cross-cluster pair into one `cross_mean`, weighted implicitly by
/// `C(n, 2)` — quadratic in cluster size. A 57-note grab-bag cluster contributes 1596 intra pairs;
/// two tight 7-note clusters contribute 21 apiece. The grab-bag's own weak internal coherence
/// (real notes about a shared *toolkit*, not a shared *topic*) then dominates the pooled
/// `intra_mean` almost completely (1596 of 1638 total intra pairs on this vault, ~97%), while
/// still nominally "exceeding" a `cross_mean` that's *also* diluted by that same grab-bag's many
/// (weak) cross-cluster pairs against the two tight clusters. Both numbers end up measuring the
/// grab-bag, not the signal — the tell is that the tight clusters' own cross-pair similarity to
/// *each other* (birding↔homelab, ≈0.630) is higher than the grab-bag's diluted intra-mean
/// (≈0.617): a "different topic" pair scored more self-similar than a "same topic" pair, which
/// makes any gate derived from the pooled numbers meaningless.
///
/// **Tightness rule, objective and self-excluding:** for each cluster `C`, compute a reference
/// cross-mean pooled over every cross-cluster pair *not involving* `C` (leave-one-out — this
/// deliberately excludes any cross pair `C` itself might be contaminating). `C` is **tight** iff
/// its own intra-mean exceeds that reference. With ≥ 3 clusters this is always well-defined; with
/// exactly 2, there's no "pair not involving C" for either one, so both are trivially treated as
/// tight (nothing else to compare against); with 1, there are no cross pairs at all, so it's
/// trivially tight too (`separation` will read `0.0`, correctly signaling "no cross-cluster signal
/// available"). On this crate's `./vault` spec: `birding` (intra 0.806) and `homelab` (intra
/// 0.808) both clear the bar set by the OTHER pair excluding them; `toolkit-concepts` (intra
/// 0.617) does not clear the bar set by `birding~homelab` (0.630) — it self-excludes exactly as
/// its own diluted intra-mean predicts it should.
///
/// `intra_mean`/`cross_mean` are then recomputed pooled over only the tight clusters' own pairs
/// (intra: within a tight cluster; cross: between two tight clusters — a pair touching a
/// non-tight cluster is dropped from both, not folded into either). `separation = intra_mean -
/// cross_mean` should be positive and now measures a real signal instead of grab-bag noise.
///
/// Suggested gates: `suggested_high_gate` sits at the **midpoint** of the tightened gap
/// (`cross_mean + 0.5 * separation`), `suggested_low_gate` at 25% of the way (unchanged shape from
/// the original quartile split, `cross_mean + 0.25 * separation`). The original 75%-of-gap high
/// gate was deliberately biased toward precision *to compensate for a gap it couldn't trust* — now
/// that `separation` reflects the tight clusters' real gap (≈0.177 vs. the old ≈0.080), that
/// compensation is no longer needed, so the midpoint (an unbiased split between the two
/// distributions) replaces it; see README "Calibration" for the measured consequence (edge counts
/// at old vs. new gates).
///
/// `cluster_pairs` reports every pair's raw `(mean, n)` — intra and cross, tight and not — so a
/// caller can see the full breakdown this method's tightness call was made from, not just the
/// post-filter summary. This is advisory only — `calibrate` reports numbers, it never writes them
/// into a db or changes `infer`'s behavior (contract rule 1: report-only).
pub fn calibrate(conn: &Connection, spec_path: &Path) -> Result<CalibrateReport, String> {
    let raw = std::fs::read_to_string(spec_path)
        .map_err(|e| format!("cannot read {}: {e}", spec_path.display()))?;
    let spec: ClusterSpec =
        serde_json::from_str(&raw).map_err(|e| format!("invalid cluster spec: {e}"))?;

    let mut path_cluster: HashMap<String, String> = HashMap::new();
    for (name, paths) in &spec.clusters {
        for p in paths {
            path_cluster.insert(p.clone(), name.clone());
        }
    }
    let cluster_names: Vec<String> = {
        let mut names: Vec<String> = spec.clusters.keys().cloned().collect();
        names.sort();
        names
    };

    let vectors: HashMap<String, Vec<f32>> = {
        let mut stmt = conn
            .prepare("SELECT path, vector FROM embeddings")
            .map_err(|e| e.to_string())?;
        let rows = stmt
            .query_map([], |row| {
                Ok((row.get::<_, String>(0)?, row.get::<_, Vec<u8>>(1)?))
            })
            .map_err(|e| e.to_string())?;
        rows.filter_map(Result::ok)
            .filter(|(p, _)| path_cluster.contains_key(p))
            .map(|(p, b)| (p, bytes_to_vector(&b)))
            .collect()
    };

    // Group every pairwise similarity by (sorted) cluster-pair key — one bucket per pair,
    // regardless of which/how-many notes contribute (the fix for the pooling bias above).
    let mut pair_scores: HashMap<(String, String), Vec<f64>> = HashMap::new();
    let paths: Vec<&String> = vectors.keys().collect();
    for i in 0..paths.len() {
        for j in (i + 1)..paths.len() {
            let a = paths[i];
            let b = paths[j];
            let ca = path_cluster[a].clone();
            let cb = path_cluster[b].clone();
            let sim = cosine_similarity(&vectors[a], &vectors[b]) as f64;
            let key = if ca <= cb { (ca, cb) } else { (cb, ca) };
            pair_scores.entry(key).or_default().push(sim);
        }
    }

    let mut cluster_pairs: std::collections::BTreeMap<String, ClusterPairStat> =
        std::collections::BTreeMap::new();
    for ((a, b), scores) in &pair_scores {
        cluster_pairs.insert(
            pair_key(a, b),
            ClusterPairStat {
                mean: mean_of(scores),
                n: scores.len(),
            },
        );
    }

    let intra_mean_of = |name: &str| -> f64 {
        pair_scores
            .get(&(name.to_string(), name.to_string()))
            .map(|v| mean_of(v))
            .unwrap_or(0.0)
    };

    // Leave-one-out reference cross-mean for `name`: pooled over every cross pair between two
    // OTHER clusters (never one that `name` itself is a party to).
    let ref_cross_mean_excluding = |name: &str| -> Option<f64> {
        let mut pooled: Vec<f64> = Vec::new();
        for ((a, b), scores) in &pair_scores {
            if a != b && a != name && b != name {
                pooled.extend(scores.iter().copied());
            }
        }
        if pooled.is_empty() {
            None
        } else {
            Some(mean_of(&pooled))
        }
    };

    let mut tight_clusters: Vec<String> = cluster_names
        .iter()
        .filter(|name| match ref_cross_mean_excluding(name) {
            // ≥ 3 clusters: a real bar to clear.
            Some(reference) => intra_mean_of(name) > reference,
            // < 3 clusters: no cross pair excludes `name` to compare against — trivially tight.
            None => true,
        })
        .cloned()
        .collect();
    tight_clusters.sort();
    let tight_set: HashSet<&String> = tight_clusters.iter().collect();

    let mut intra_pooled: Vec<f64> = Vec::new();
    let mut cross_pooled: Vec<f64> = Vec::new();
    for ((a, b), scores) in &pair_scores {
        if !tight_set.contains(a) || !tight_set.contains(b) {
            continue;
        }
        if a == b {
            intra_pooled.extend(scores.iter().copied());
        } else {
            cross_pooled.extend(scores.iter().copied());
        }
    }

    let intra_mean = mean_of(&intra_pooled);
    let cross_mean = mean_of(&cross_pooled);
    let separation = intra_mean - cross_mean;
    let suggested_high_gate = cross_mean + 0.5 * separation;
    let suggested_low_gate = cross_mean + 0.25 * separation;

    Ok(CalibrateReport {
        intra_mean,
        cross_mean,
        separation,
        suggested_high_gate,
        suggested_low_gate,
        model: MODEL_NAME.to_string(),
        tight_clusters,
        cluster_pairs,
    })
}

#[derive(Debug, Clone, Serialize)]
pub struct NeighborNodeV2 {
    pub path: String,
    pub title: String,
    pub description: String,
    pub depth: usize,
    pub kind: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub label: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub score: Option<f64>,
}

/// `neighbors` with `--include-inferred`: the exact `extracted` BFS from `neighbors` above
/// (`kind: "extracted"`, unchanged — contract rule 4, traversal defaults to deterministic) unioned
/// with every note that has a *direct* inferred edge to `start` (`kind: "inferred"`, `depth: 1`).
///
/// Inferred edges are a similarity score, not a chain to walk hop-by-hop the way wikilinks are —
/// so unlike the extracted side, inferred neighbors always surface at "one similarity step" from
/// `start` regardless of `--depth` (see README "neighbors --include-inferred" for why chaining
/// inferred edges together isn't attempted). A note reachable both ways keeps its `extracted`
/// record — the deterministic edge always wins a conflict.
pub fn neighbors_with_inferred(
    conn: &Connection,
    start: &str,
    depth: usize,
    direction: Direction,
) -> rusqlite::Result<Vec<NeighborNodeV2>> {
    let extracted = neighbors(conn, start, depth, direction)?;
    let mut seen: HashSet<String> = extracted.iter().map(|n| n.path.clone()).collect();
    seen.insert(start.to_string());

    let mut out: Vec<NeighborNodeV2> = extracted
        .into_iter()
        .map(|n| NeighborNodeV2 {
            path: n.path,
            title: n.title,
            description: n.description,
            depth: n.depth,
            kind: "extracted".to_string(),
            label: None,
            score: None,
        })
        .collect();

    let mut stmt = conn.prepare(
        "SELECT source, target, score, label FROM inferred_edges WHERE source = ?1 OR target = ?1",
    )?;
    let rows = stmt.query_map([start], |row| {
        Ok((
            row.get::<_, String>(0)?,
            row.get::<_, String>(1)?,
            row.get::<_, f64>(2)?,
            row.get::<_, String>(3)?,
        ))
    })?;
    for row in rows.filter_map(Result::ok) {
        let (source, target, score, label) = row;
        let other = if source == start { target } else { source };
        if seen.contains(&other) {
            continue;
        }
        seen.insert(other.clone());
        let (title, description): (String, String) = conn
            .query_row(
                "SELECT title, description FROM nodes WHERE path = ?1",
                [&other],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .unwrap_or_default();
        out.push(NeighborNodeV2 {
            path: other,
            title,
            description,
            depth: 1,
            kind: "inferred".to_string(),
            label: Some(label),
            score: Some(score),
        });
    }
    out.sort_by(|a, b| a.depth.cmp(&b.depth).then_with(|| a.path.cmp(&b.path)));
    Ok(out)
}

#[derive(Debug, Clone, Serialize)]
pub struct PathEdge {
    pub path: String,
    pub kind: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub label: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub score: Option<f64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct PathReportV2 {
    pub from: String,
    pub to: String,
    pub connected: bool,
    pub path: Vec<PathEdge>,
}

/// `path` with `--include-inferred`: shortest path over the union of `extracted` and `inferred`
/// edges (unlike `neighbors`, chaining through inferred hops here is unambiguous — a path is one
/// concrete route, not an aggregated set — so both edge kinds are full BFS citizens). Each hop
/// after the first carries the `kind` of edge that produced it (`"extracted"` or `"inferred"`,
/// plus `label`/`score` for the latter); the first entry is the starting note itself, `kind:
/// "start"`. Extracted edges are offered to BFS before inferred ones at every node, so a tie
/// between an extracted and an inferred route of equal length prefers the deterministic one
/// (contract rule 4).
pub fn shortest_path_with_inferred(
    conn: &Connection,
    from: &str,
    to: &str,
) -> rusqlite::Result<PathReportV2> {
    let start_edge = PathEdge {
        path: from.to_string(),
        kind: "start".to_string(),
        label: None,
        score: None,
    };
    if from == to {
        return Ok(PathReportV2 {
            from: from.to_string(),
            to: to.to_string(),
            connected: true,
            path: vec![start_edge],
        });
    }

    type Hop = (String, &'static str, Option<String>, Option<f64>);
    let mut adj: HashMap<String, Vec<Hop>> = HashMap::new();
    {
        let mut stmt = conn.prepare(
            "SELECT source, target FROM edges WHERE dangling = 0 AND boundary_violation = 0 AND target IS NOT NULL",
        )?;
        let rows = stmt.query_map([], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
        })?;
        for row in rows.filter_map(Result::ok) {
            let (s, t) = row;
            adj.entry(s.clone())
                .or_default()
                .push((t.clone(), "extracted", None, None));
            adj.entry(t).or_default().push((s, "extracted", None, None));
        }
    }
    {
        let mut stmt = conn.prepare("SELECT source, target, score, label FROM inferred_edges")?;
        let rows = stmt.query_map([], |row| {
            Ok((
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, f64>(2)?,
                row.get::<_, String>(3)?,
            ))
        })?;
        for row in rows.filter_map(Result::ok) {
            let (s, t, score, label) = row;
            adj.entry(s.clone()).or_default().push((
                t.clone(),
                "inferred",
                Some(label.clone()),
                Some(score),
            ));
            adj.entry(t)
                .or_default()
                .push((s, "inferred", Some(label), Some(score)));
        }
    }

    let mut visited: HashSet<String> = HashSet::from([from.to_string()]);
    let mut queue: VecDeque<String> = VecDeque::from([from.to_string()]);
    let mut parent: HashMap<String, Hop> = HashMap::new();

    while let Some(current) = queue.pop_front() {
        if current == to {
            let mut edges_rev: Vec<PathEdge> = Vec::new();
            let mut cur = current;
            while let Some((p, kind, label, score)) = parent.get(&cur).cloned() {
                edges_rev.push(PathEdge {
                    path: cur.clone(),
                    kind: kind.to_string(),
                    label,
                    score,
                });
                cur = p;
            }
            edges_rev.reverse();
            let mut full = vec![start_edge];
            full.extend(edges_rev);
            return Ok(PathReportV2 {
                from: from.to_string(),
                to: to.to_string(),
                connected: true,
                path: full,
            });
        }
        if let Some(next) = adj.get(&current) {
            for (n, kind, label, score) in next {
                if visited.insert(n.clone()) {
                    parent.insert(n.clone(), (current.clone(), kind, label.clone(), *score));
                    queue.push_back(n.clone());
                }
            }
        }
    }

    Ok(PathReportV2 {
        from: from.to_string(),
        to: to.to_string(),
        connected: false,
        path: Vec::new(),
    })
}
