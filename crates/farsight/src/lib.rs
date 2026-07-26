//! farsight — stateless BM25 search over an agentic-toolkit vault.
//!
//! No persisted index: every `query` call re-scans the vault's active-content notes
//! (`02_Projects`, `03_Areas`, `04_Resources`, plus any root-level note whose own
//! frontmatter declares `status: active` — `contract/VAULT_SCHEMA.md`) and scores them
//! with BM25 over title + description + body. See the crate README for why this is
//! stateless by design and the condition under which that should change.
//!
//! Mirrors `core/toolkit_core/vault.py` and `plugins/obsidian/scripts/search.py` in
//! semantics (vault resolution, active-content filter, tolerant frontmatter, BM25
//! formula) so this Rust engine is a drop-in replacement, not a divergent reimplementation.

use serde::Serialize;
use std::collections::HashMap;
use std::path::{Path, PathBuf};

/// Marker file that identifies the repo root (contract/PROFILE.md, mirrored from
/// `core/toolkit_core/vault.py::MARKETPLACE_MARKER`).
const MARKETPLACE_MARKER: &str = ".claude-plugin/marketplace.json";

/// Folders that search is allowed to consider (contract/VAULT_SCHEMA.md's active-content
/// filter). `00_Memory`, `01_Capture`, and `05_Archive` are always excluded.
///
/// Not the whole story: `discover_notes` also pulls in any note directly at the vault root
/// whose own frontmatter declares `status: active` (contract/VAULT_SCHEMA.md's root-level-note
/// clause) — mirrors `crates/gaiafield::discover_nodes`, whose doc comment explains why (the
/// vault's planted bridge persona note, `Alex-Vega.md`, lives at the root and self-declares
/// `status: active`; excluding it here made the two engines disagree on the same query).
pub const ACTIVE_CONTENT_FOLDERS: [&str; 3] = ["02_Projects", "03_Areas", "04_Resources"];

/// Directory names skipped during note discovery regardless of which PARA folder they
/// live under — mirrors `plugins/obsidian/scripts/vault_utils.py::EXCLUDE_DIRS`.
const EXCLUDE_DIRS: [&str; 7] = [
    "assets",
    "node_modules",
    "out",
    "public",
    "src",
    ".obsidian",
    ".trash",
];

/// BM25 standard defaults (Robertson/Sparck Jones), matching `search.py`'s tunables.
pub const K1: f64 = 1.5;
pub const B: f64 = 0.75;

/// Characters of body text considered per note — enough for topic signal, cheap to scan.
/// Matches `search.py::BODY_HEAD`.
const BODY_HEAD: usize = 2000;

const STOPWORDS: &[&str] = &[
    "the", "a", "an", "of", "to", "in", "and", "or", "is", "are", "for", "on", "with", "this",
    "that", "it", "as", "by", "at", "be", "was", "were", "from", "into",
];

// ---------------------------------------------------------------------------
// Vault resolution (contract/PROFILE.md)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct VaultResolution {
    pub path: PathBuf,
    pub source: &'static str,
}

/// Walk upward from `start` looking for `.claude-plugin/marketplace.json`.
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

/// Resolve the vault: `--vault` flag wins, else `TOOLKIT_VAULT` env, else `./vault`
/// relative to a repo root found by walking up from the current directory.
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

/// Resolve `resolve_vault`'s result into a path guaranteed to exist as a directory.
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

// ---------------------------------------------------------------------------
// Note discovery
// ---------------------------------------------------------------------------

/// Walk the active PARA folders and return every eligible `.md` path, sorted, **plus** any note
/// directly at the vault root whose own frontmatter declares `status: active`
/// (contract/VAULT_SCHEMA.md's root-level-note clause). Mirrors
/// `crates/gaiafield::discover_nodes`'s narrow reading: only a root file that opts in via
/// `status: active` joins the set — `Index.md`/`CLAUDE.md` naturally stay out since neither
/// carries frontmatter at all, and `Config/`/`Templates/` are separate top-level dirs, not
/// root-level files, so they're never considered here.
pub fn discover_notes(vault: &Path) -> Vec<PathBuf> {
    let mut found = Vec::new();
    for folder in ACTIVE_CONTENT_FOLDERS {
        let root = vault.join(folder);
        if root.is_dir() {
            walk_dir(&root, &mut found);
        }
    }
    if let Ok(entries) = std::fs::read_dir(vault) {
        for entry in entries.flatten() {
            let path = entry.path();
            let name = entry.file_name();
            let name = name.to_string_lossy();
            if path.is_file() && name.ends_with(".md") && !name.starts_with('.') {
                let raw = std::fs::read_to_string(&path).unwrap_or_default();
                let (fm_text, _) = split_frontmatter(&raw);
                let status = fm_text.as_deref().map(extract_status).unwrap_or_default();
                if status == "active" {
                    found.push(path);
                }
            }
        }
    }
    found.sort();
    found
}

fn walk_dir(dir: &Path, found: &mut Vec<PathBuf>) {
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
            walk_dir(&path, found);
        } else if name.ends_with(".md") && !name.starts_with('.') {
            found.push(path);
        }
    }
}

// ---------------------------------------------------------------------------
// Frontmatter — tolerant per contract/VAULT_SCHEMA.md's floor-not-ceiling rule
// ---------------------------------------------------------------------------

/// Split `text` into (frontmatter block text, body). Returns `(None, text)` when no
/// frontmatter block is present at all — that is a valid note, never an error.
fn split_frontmatter(text: &str) -> (Option<String>, String) {
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
        // A `---` opener with no closer: not a real frontmatter block. Tolerant per the
        // floor-not-ceiling rule — treat the whole file as body rather than erroring.
        return (None, text.to_string());
    }
    let body: String = lines.collect::<Vec<_>>().join("\n");
    (Some(fm_lines.join("\n")), body)
}

/// Pull the `description` field out of a frontmatter block, tolerant of malformed YAML,
/// non-mapping documents, or the field being absent — all resolve to `""`, never an error.
/// Unknown keys are implicitly preserved (ignored, not rejected) since only `description`
/// is ever plucked out.
fn extract_description(fm_text: &str) -> String {
    match serde_yaml::from_str::<serde_yaml::Value>(fm_text) {
        Ok(serde_yaml::Value::Mapping(map)) => map
            .get(serde_yaml::Value::String("description".to_string()))
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        _ => String::new(),
    }
}

/// Pull the `status` field out of a frontmatter block, same tolerance rules as
/// `extract_description`. Used only to decide whether a root-level note opts into the active
/// content set (`discover_notes`) — never errors, absent/malformed all resolve to `""`.
fn extract_status(fm_text: &str) -> String {
    match serde_yaml::from_str::<serde_yaml::Value>(fm_text) {
        Ok(serde_yaml::Value::Mapping(map)) => map
            .get(serde_yaml::Value::String("status".to_string()))
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string(),
        _ => String::new(),
    }
}

// ---------------------------------------------------------------------------
// Corpus
// ---------------------------------------------------------------------------

pub struct Doc {
    pub rel: String,
    pub title: String,
    pub description: String,
    pub length: usize,
    pub term_counts: HashMap<String, u32>,
}

impl Doc {
    pub fn from_path(path: &Path, vault: &Path) -> Doc {
        let rel = path
            .strip_prefix(vault)
            .unwrap_or(path)
            .to_string_lossy()
            .replace(std::path::MAIN_SEPARATOR, "/");
        let title = path
            .file_stem()
            .map(|s| s.to_string_lossy().to_string())
            .unwrap_or_default();

        let raw = std::fs::read_to_string(path).unwrap_or_default();
        let (fm_text, body) = split_frontmatter(&raw);
        let description = fm_text
            .as_deref()
            .map(extract_description)
            .unwrap_or_default();

        let body_head: String = body.chars().take(BODY_HEAD).collect();
        // Title and description count for extra weight by repetition, not a separate
        // scoring path — keeps the ranker to one formula (mirrors search.py).
        let text = format!("{title} {title} {description} {description} {body_head}");
        let tokens = tokenize(&text);
        let mut term_counts: HashMap<String, u32> = HashMap::new();
        for t in &tokens {
            *term_counts.entry(t.clone()).or_insert(0) += 1;
        }
        let length = tokens.len();

        Doc {
            rel,
            title,
            description,
            length,
            term_counts,
        }
    }
}

pub fn build_corpus(vault: &Path) -> Vec<Doc> {
    discover_notes(vault)
        .iter()
        .map(|p| Doc::from_path(p, vault))
        .collect()
}

/// Tokenize ASCII alphanumeric runs (lowercased), length > 1, minus stopwords — matches
/// `search.py`'s `TOKEN_RE = [a-z0-9]+` regex behavior byte-for-byte, including that
/// non-ASCII letters (accents, umlauts) act as separators rather than being matched.
pub fn tokenize(text: &str) -> Vec<String> {
    let mut tokens = Vec::new();
    let mut cur = String::new();
    for ch in text.chars() {
        if ch.is_ascii_alphanumeric() {
            cur.push(ch.to_ascii_lowercase());
        } else if !cur.is_empty() {
            push_token(&mut tokens, std::mem::take(&mut cur));
        }
    }
    if !cur.is_empty() {
        push_token(&mut tokens, cur);
    }
    tokens
}

fn push_token(tokens: &mut Vec<String>, tok: String) {
    if tok.len() > 1 && !STOPWORDS.contains(&tok.as_str()) {
        tokens.push(tok);
    }
}

// ---------------------------------------------------------------------------
// BM25
// ---------------------------------------------------------------------------

pub fn bm25_scores(query: &str, corpus: &[Doc], k1: f64, b: f64) -> HashMap<String, f64> {
    let q_tokens = tokenize(query);
    if q_tokens.is_empty() || corpus.is_empty() {
        return HashMap::new();
    }

    let n = corpus.len() as f64;
    let avg_len: f64 = corpus.iter().map(|d| d.length as f64).sum::<f64>() / n;

    let unique_terms: std::collections::HashSet<&str> =
        q_tokens.iter().map(|s| s.as_str()).collect();
    let mut df: HashMap<&str, usize> = HashMap::new();
    for term in unique_terms {
        let count = corpus
            .iter()
            .filter(|d| d.term_counts.contains_key(term))
            .count();
        df.insert(term, count);
    }

    let mut scores = HashMap::new();
    for d in corpus {
        let mut score = 0.0f64;
        for term in &q_tokens {
            let f = *d.term_counts.get(term.as_str()).unwrap_or(&0) as f64;
            if f == 0.0 {
                continue;
            }
            let dfreq = *df.get(term.as_str()).unwrap_or(&0) as f64;
            let idf = ((n - dfreq + 0.5) / (dfreq + 0.5) + 1.0).ln();
            let denom = f + k1 * (1.0 - b + b * d.length as f64 / avg_len);
            score += idf * (f * (k1 + 1.0)) / denom;
        }
        if score > 0.0 {
            scores.insert(d.rel.clone(), score);
        }
    }
    scores
}

// ---------------------------------------------------------------------------
// Public search surface
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Serialize)]
pub struct SearchResult {
    pub path: String,
    pub score: f64,
    pub title: String,
    pub description: String,
}

/// Score every active-content note against `query` and return the top `k` by BM25 score.
pub fn search(query: &str, vault: &Path, k: usize) -> Vec<SearchResult> {
    let corpus = build_corpus(vault);
    let scores = bm25_scores(query, &corpus, K1, B);

    let mut ranked: Vec<(&Doc, f64)> = corpus
        .iter()
        .filter_map(|d| scores.get(&d.rel).map(|s| (d, *s)))
        .collect();
    ranked.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    ranked.truncate(k);

    ranked
        .into_iter()
        .map(|(d, s)| SearchResult {
            path: d.rel.clone(),
            score: (s * 10000.0).round() / 10000.0,
            title: d.title.clone(),
            description: d.description.clone(),
        })
        .collect()
}
