use clap::{Parser, Subcommand, ValueEnum};
use gaiafield::{Direction, ResolveError};
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Parser)]
#[command(
    name = "gaiafield",
    version,
    about = "Deterministic knowledge-graph extraction over an agentic-toolkit vault"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Clone, Copy, ValueEnum)]
enum DirectionArg {
    In,
    Out,
    Both,
}

impl From<DirectionArg> for Direction {
    fn from(d: DirectionArg) -> Self {
        match d {
            DirectionArg::In => Direction::In,
            DirectionArg::Out => Direction::Out,
            DirectionArg::Both => Direction::Both,
        }
    }
}

#[derive(Subcommand)]
enum Command {
    /// Extract the wikilink/frontmatter graph into SQLite. Incremental by default (compares
    /// mtime+size against the stored value); `--full` rebuilds from scratch.
    Index {
        #[arg(long)]
        vault: Option<PathBuf>,

        /// DB path. Defaults to `<vault>/.gaiafield/graph.db`.
        #[arg(long)]
        db: Option<PathBuf>,

        /// Rebuild every node's rows and edges even if unchanged.
        #[arg(long)]
        full: bool,

        #[arg(long)]
        json: bool,
    },
    /// Neighbors of a note out to a given depth.
    Neighbors {
        /// A vault-relative path or bare note name (wikilink semantics).
        note: String,

        #[arg(long)]
        vault: Option<PathBuf>,

        #[arg(long)]
        db: Option<PathBuf>,

        #[arg(long, default_value_t = 1)]
        depth: usize,

        #[arg(long, value_enum, default_value_t = DirectionArg::Both)]
        direction: DirectionArg,

        /// Also surface `inferred` edges directly touching this note (default: `extracted` only
        /// — contract rule 4). Inferred neighbors always report at depth 1 regardless of
        /// `--depth` — see `gaiafield::neighbors_with_inferred`'s doc comment.
        #[arg(long)]
        include_inferred: bool,

        #[arg(long)]
        json: bool,
    },
    /// Node/edge counts, top-linked notes, dangling-edge and boundary-violation counts.
    Stats {
        #[arg(long)]
        vault: Option<PathBuf>,

        #[arg(long)]
        db: Option<PathBuf>,

        #[arg(long)]
        json: bool,
    },
    /// Shortest path between two notes (BFS over the undirected graph).
    Path {
        from: String,
        to: String,

        #[arg(long)]
        vault: Option<PathBuf>,

        #[arg(long)]
        db: Option<PathBuf>,

        /// Also traverse `inferred` edges (default: `extracted` only — contract rule 4).
        #[arg(long)]
        include_inferred: bool,

        #[arg(long)]
        json: bool,
    },
    /// Embed every node's content and score inferred (similarity) edges on top of the
    /// deterministic graph. Report-only: never writes vault content (contract rule 1).
    Infer {
        #[arg(long)]
        vault: Option<PathBuf>,

        #[arg(long)]
        db: Option<PathBuf>,

        /// Recompute every embedding and rescore every pair from scratch.
        #[arg(long, conflicts_with = "reset")]
        full: bool,

        /// Drop all inferred edges/embeddings, restoring the exact v1 (extracted-only) graph.
        #[arg(long, conflicts_with = "full")]
        reset: bool,

        #[arg(long)]
        json: bool,
    },
    /// Inferred candidates for a note — same-topic notes with no extracted link to it yet.
    Candidates {
        note: String,

        #[arg(long)]
        vault: Option<PathBuf>,

        #[arg(long)]
        db: Option<PathBuf>,

        #[arg(long, default_value_t = 10)]
        k: usize,

        /// Also include `AMBIGUOUS`-labeled candidates (default: `INFERRED` only).
        #[arg(long)]
        include_ambiguous: bool,

        #[arg(long)]
        json: bool,
    },
    /// Every stored inferred edge ranked by surprise (cross-domain candidates worth a look).
    Surprise {
        #[arg(long)]
        vault: Option<PathBuf>,

        #[arg(long)]
        db: Option<PathBuf>,

        #[arg(long, default_value_t = 20)]
        top: usize,

        #[arg(long, default_value_t = 0.0)]
        min_score: f64,

        /// Also include `AMBIGUOUS`-labeled pairs (default: excluded — mirrors `candidates`;
        /// contract/KNOWLEDGE_API.md's v2 gates: AMBIGUOUS is surfaced only on explicit request).
        #[arg(long)]
        include_ambiguous: bool,

        #[arg(long)]
        json: bool,
    },
    /// Calibrate high/low gates against a named-cluster spec (report-only — never writes gates).
    Calibrate {
        #[arg(long)]
        vault: Option<PathBuf>,

        #[arg(long)]
        db: Option<PathBuf>,

        /// Path to a `{"clusters": {"name": [paths...]}}` JSON spec.
        #[arg(long)]
        clusters: PathBuf,

        #[arg(long)]
        json: bool,
    },
}

fn main() -> ExitCode {
    let cli = Cli::parse();
    match cli.command {
        Command::Index {
            vault,
            db,
            full,
            json,
        } => run_index(vault, db, full, json),
        Command::Neighbors {
            note,
            vault,
            db,
            depth,
            direction,
            include_inferred,
            json,
        } => run_neighbors(
            &note,
            vault,
            db,
            depth,
            direction.into(),
            include_inferred,
            json,
        ),
        Command::Stats { vault, db, json } => run_stats(vault, db, json),
        Command::Path {
            from,
            to,
            vault,
            db,
            include_inferred,
            json,
        } => run_path(&from, &to, vault, db, include_inferred, json),
        Command::Infer {
            vault,
            db,
            full,
            reset,
            json,
        } => run_infer(vault, db, full, reset, json),
        Command::Candidates {
            note,
            vault,
            db,
            k,
            include_ambiguous,
            json,
        } => run_candidates(&note, vault, db, k, include_ambiguous, json),
        Command::Surprise {
            vault,
            db,
            top,
            min_score,
            include_ambiguous,
            json,
        } => run_surprise(vault, db, top, min_score, include_ambiguous, json),
        Command::Calibrate {
            vault,
            db,
            clusters,
            json,
        } => run_calibrate(vault, db, &clusters, json),
    }
}

fn resolve_db(vault: &std::path::Path, db_flag: Option<PathBuf>) -> PathBuf {
    db_flag.unwrap_or_else(|| gaiafield::default_db_path(vault))
}

fn open_db_or_fail(db_path: &std::path::Path) -> Result<rusqlite::Connection, ExitCode> {
    if !db_path.is_file() {
        eprintln!(
            "No graph database at {} — run `gaiafield index` first.",
            db_path.display()
        );
        return Err(ExitCode::FAILURE);
    }
    gaiafield::open_db(db_path).map_err(|e| {
        eprintln!("failed to open {}: {e}", db_path.display());
        ExitCode::FAILURE
    })
}

fn run_index(
    vault_flag: Option<PathBuf>,
    db_flag: Option<PathBuf>,
    full: bool,
    json: bool,
) -> ExitCode {
    let vault = match gaiafield::require_vault(vault_flag.as_deref()) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("{e}");
            return ExitCode::FAILURE;
        }
    };
    let db_path = resolve_db(&vault, db_flag);
    let conn = match gaiafield::open_db(&db_path) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("failed to open {}: {e}", db_path.display());
            return ExitCode::FAILURE;
        }
    };
    let report = match gaiafield::index(&vault, &conn, full) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("index failed: {e}");
            return ExitCode::FAILURE;
        }
    };

    if json {
        println!("{}", serde_json::to_string_pretty(&report).unwrap());
    } else {
        println!("Indexed {} into {}", vault.display(), db_path.display());
        println!(
            "  nodes: {} (added {}, updated {}, unchanged {}, removed {})",
            report.total_nodes, report.added, report.updated, report.unchanged, report.removed
        );
        println!(
            "  edges: {} (dangling {}, boundary violations {})",
            report.edges, report.dangling_edges, report.boundary_violations
        );
    }
    ExitCode::SUCCESS
}

fn run_neighbors(
    note: &str,
    vault_flag: Option<PathBuf>,
    db_flag: Option<PathBuf>,
    depth: usize,
    direction: Direction,
    include_inferred: bool,
    json: bool,
) -> ExitCode {
    let vault = match gaiafield::require_vault(vault_flag.as_deref()) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("{e}");
            return ExitCode::FAILURE;
        }
    };
    let db_path = resolve_db(&vault, db_flag);
    let conn = match open_db_or_fail(&db_path) {
        Ok(c) => c,
        Err(code) => return code,
    };

    let resolved = match gaiafield::resolve_note_arg(&conn, note) {
        Ok(p) => p,
        Err(ResolveError::NotFound(arg)) => {
            eprintln!("No indexed note matches {arg:?}.");
            return ExitCode::FAILURE;
        }
        Err(ResolveError::Ambiguous(candidates)) => {
            eprintln!("{note:?} is ambiguous — matches more than one note:");
            for c in candidates {
                eprintln!("  {c}");
            }
            eprintln!("Pass a vault-relative path to disambiguate.");
            return ExitCode::FAILURE;
        }
    };

    if include_inferred {
        let result = match gaiafield::neighbors_with_inferred(&conn, &resolved, depth, direction) {
            Ok(r) => r,
            Err(e) => {
                eprintln!("neighbors query failed: {e}");
                return ExitCode::FAILURE;
            }
        };
        if json {
            println!("{}", serde_json::to_string_pretty(&result).unwrap());
        } else if result.is_empty() {
            println!("No neighbors of {resolved} within depth {depth}.");
        } else {
            for n in &result {
                println!("{:>2}  [{}]  {}  ({})", n.depth, n.kind, n.title, n.path);
                if !n.description.is_empty() {
                    println!("      {}", n.description);
                }
            }
        }
        return ExitCode::SUCCESS;
    }

    let result = match gaiafield::neighbors(&conn, &resolved, depth, direction) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("neighbors query failed: {e}");
            return ExitCode::FAILURE;
        }
    };

    if json {
        println!("{}", serde_json::to_string_pretty(&result).unwrap());
    } else if result.is_empty() {
        println!("No neighbors of {resolved} within depth {depth}.");
    } else {
        for n in &result {
            println!("{:>2}  {}  ({})", n.depth, n.title, n.path);
            if !n.description.is_empty() {
                println!("      {}", n.description);
            }
        }
    }
    ExitCode::SUCCESS
}

fn run_stats(vault_flag: Option<PathBuf>, db_flag: Option<PathBuf>, json: bool) -> ExitCode {
    let vault = match gaiafield::require_vault(vault_flag.as_deref()) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("{e}");
            return ExitCode::FAILURE;
        }
    };
    let db_path = resolve_db(&vault, db_flag);
    let conn = match open_db_or_fail(&db_path) {
        Ok(c) => c,
        Err(code) => return code,
    };
    let report = match gaiafield::stats(&conn) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("stats query failed: {e}");
            return ExitCode::FAILURE;
        }
    };

    if json {
        println!("{}", serde_json::to_string_pretty(&report).unwrap());
    } else {
        println!("nodes: {}", report.nodes);
        println!("edges: {}", report.edges);
        println!("dangling edges: {}", report.dangling_edges);
        println!("boundary violations: {}", report.boundary_violations);
        println!("top-linked notes:");
        for t in &report.top_linked {
            println!("  {:>3}  {}  ({})", t.in_degree, t.title, t.path);
        }
        match &report.model {
            Some(model) => {
                println!(
                    "inferred edges: {} (ambiguous {}) — model {} (high {:.2}, low {:.2})",
                    report.inferred_edges,
                    report.ambiguous_edges,
                    model,
                    report.high_gate.unwrap_or_default(),
                    report.low_gate.unwrap_or_default()
                );
            }
            None => println!("inferred edges: none (run `gaiafield infer` first)"),
        }
    }
    ExitCode::SUCCESS
}

fn run_path(
    from: &str,
    to: &str,
    vault_flag: Option<PathBuf>,
    db_flag: Option<PathBuf>,
    include_inferred: bool,
    json: bool,
) -> ExitCode {
    let vault = match gaiafield::require_vault(vault_flag.as_deref()) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("{e}");
            return ExitCode::FAILURE;
        }
    };
    let db_path = resolve_db(&vault, db_flag);
    let conn = match open_db_or_fail(&db_path) {
        Ok(c) => c,
        Err(code) => return code,
    };

    let resolve = |arg: &str| -> Result<String, ExitCode> {
        match gaiafield::resolve_note_arg(&conn, arg) {
            Ok(p) => Ok(p),
            Err(ResolveError::NotFound(a)) => {
                eprintln!("No indexed note matches {a:?}.");
                Err(ExitCode::FAILURE)
            }
            Err(ResolveError::Ambiguous(candidates)) => {
                eprintln!("{arg:?} is ambiguous — matches more than one note:");
                for c in candidates {
                    eprintln!("  {c}");
                }
                Err(ExitCode::FAILURE)
            }
        }
    };
    let from_resolved = match resolve(from) {
        Ok(p) => p,
        Err(code) => return code,
    };
    let to_resolved = match resolve(to) {
        Ok(p) => p,
        Err(code) => return code,
    };

    if include_inferred {
        let report =
            match gaiafield::shortest_path_with_inferred(&conn, &from_resolved, &to_resolved) {
                Ok(r) => r,
                Err(e) => {
                    eprintln!("path query failed: {e}");
                    return ExitCode::FAILURE;
                }
            };
        if json {
            println!("{}", serde_json::to_string_pretty(&report).unwrap());
        } else if report.connected {
            let rendered: Vec<String> = report
                .path
                .iter()
                .map(|e| format!("{} [{}]", e.path, e.kind))
                .collect();
            println!("{}", rendered.join(" -> "));
        } else {
            println!("No path between {from_resolved} and {to_resolved}.");
        }
        return ExitCode::SUCCESS;
    }

    let report = match gaiafield::shortest_path(&conn, &from_resolved, &to_resolved) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("path query failed: {e}");
            return ExitCode::FAILURE;
        }
    };

    if json {
        println!("{}", serde_json::to_string_pretty(&report).unwrap());
    } else if report.connected {
        println!("{}", report.path.join(" -> "));
    } else {
        println!("No path between {from_resolved} and {to_resolved}.");
    }
    ExitCode::SUCCESS
}

fn run_infer(
    vault_flag: Option<PathBuf>,
    db_flag: Option<PathBuf>,
    full: bool,
    reset: bool,
    json: bool,
) -> ExitCode {
    let vault = match gaiafield::require_vault(vault_flag.as_deref()) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("{e}");
            return ExitCode::FAILURE;
        }
    };
    let db_path = resolve_db(&vault, db_flag);
    let conn = match gaiafield::open_db(&db_path) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("failed to open {}: {e}", db_path.display());
            return ExitCode::FAILURE;
        }
    };
    let model_dir = gaiafield::resolve_model_dir(&db_path);
    let report = match gaiafield::infer(&vault, &conn, &model_dir, full, reset) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("infer failed: {e}");
            return ExitCode::FAILURE;
        }
    };

    if json {
        println!("{}", serde_json::to_string_pretty(&report).unwrap());
    } else if reset {
        println!("Reset inferred edges for {}", db_path.display());
    } else {
        println!(
            "embedded {} note(s); {} inferred edge(s), {} ambiguous ({} in {}ms)",
            report.embedded,
            report.inferred_edges,
            report.ambiguous_edges,
            report.model,
            report.elapsed_ms
        );
        println!(
            "  high gate: {:.2}  low gate: {:.2}",
            report.high_gate, report.low_gate
        );
    }
    ExitCode::SUCCESS
}

fn run_candidates(
    note: &str,
    vault_flag: Option<PathBuf>,
    db_flag: Option<PathBuf>,
    k: usize,
    include_ambiguous: bool,
    json: bool,
) -> ExitCode {
    let vault = match gaiafield::require_vault(vault_flag.as_deref()) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("{e}");
            return ExitCode::FAILURE;
        }
    };
    let db_path = resolve_db(&vault, db_flag);
    let conn = match open_db_or_fail(&db_path) {
        Ok(c) => c,
        Err(code) => return code,
    };

    let resolved = match gaiafield::resolve_note_arg(&conn, note) {
        Ok(p) => p,
        Err(ResolveError::NotFound(arg)) => {
            eprintln!("No indexed note matches {arg:?}.");
            return ExitCode::FAILURE;
        }
        Err(ResolveError::Ambiguous(candidates)) => {
            eprintln!("{note:?} is ambiguous — matches more than one note:");
            for c in candidates {
                eprintln!("  {c}");
            }
            return ExitCode::FAILURE;
        }
    };

    let result = match gaiafield::candidates(&conn, &resolved, k, include_ambiguous) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("candidates query failed: {e}");
            return ExitCode::FAILURE;
        }
    };

    if json {
        println!("{}", serde_json::to_string_pretty(&result).unwrap());
    } else if result.is_empty() {
        println!("No inferred candidates for {resolved}.");
    } else {
        for c in &result {
            println!(
                "{:.3}  [{}]  {}  (surprise {:.3}, det_distance {:?})",
                c.score, c.label, c.path, c.surprise, c.det_distance
            );
        }
    }
    ExitCode::SUCCESS
}

fn run_surprise(
    vault_flag: Option<PathBuf>,
    db_flag: Option<PathBuf>,
    top: usize,
    min_score: f64,
    include_ambiguous: bool,
    json: bool,
) -> ExitCode {
    let vault = match gaiafield::require_vault(vault_flag.as_deref()) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("{e}");
            return ExitCode::FAILURE;
        }
    };
    let db_path = resolve_db(&vault, db_flag);
    let conn = match open_db_or_fail(&db_path) {
        Ok(c) => c,
        Err(code) => return code,
    };

    let result = match gaiafield::surprise(&conn, top, min_score, include_ambiguous) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("surprise query failed: {e}");
            return ExitCode::FAILURE;
        }
    };

    if json {
        println!("{}", serde_json::to_string_pretty(&result).unwrap());
    } else if result.is_empty() {
        println!("No inferred edges at or above min-score {min_score}.");
    } else {
        for r in &result {
            println!(
                "{:.3}  [{}]  {} <-> {}  (score {:.3}, det_distance {:?}, same_subtree {})",
                r.surprise, r.label, r.a, r.b, r.score, r.det_distance, r.same_subtree
            );
        }
    }
    ExitCode::SUCCESS
}

fn run_calibrate(
    vault_flag: Option<PathBuf>,
    db_flag: Option<PathBuf>,
    clusters: &std::path::Path,
    json: bool,
) -> ExitCode {
    let vault = match gaiafield::require_vault(vault_flag.as_deref()) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("{e}");
            return ExitCode::FAILURE;
        }
    };
    let db_path = resolve_db(&vault, db_flag);
    let conn = match open_db_or_fail(&db_path) {
        Ok(c) => c,
        Err(code) => return code,
    };

    let report = match gaiafield::calibrate(&conn, clusters) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("calibrate failed: {e}");
            return ExitCode::FAILURE;
        }
    };

    if json {
        println!("{}", serde_json::to_string_pretty(&report).unwrap());
    } else {
        println!("model: {}", report.model);
        println!("tight clusters: {}", report.tight_clusters.join(", "));
        println!(
            "intra_mean: {:.4}  cross_mean: {:.4}  separation: {:.4}",
            report.intra_mean, report.cross_mean, report.separation
        );
        println!(
            "suggested_high_gate: {:.4}  suggested_low_gate: {:.4}",
            report.suggested_high_gate, report.suggested_low_gate
        );
        println!("cluster pairs:");
        for (key, stat) in &report.cluster_pairs {
            println!("  {key:<40} mean {:.4}  n {}", stat.mean, stat.n);
        }
    }
    ExitCode::SUCCESS
}
