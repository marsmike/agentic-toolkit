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
            json,
        } => run_neighbors(&note, vault, db, depth, direction.into(), json),
        Command::Stats { vault, db, json } => run_stats(vault, db, json),
        Command::Path {
            from,
            to,
            vault,
            db,
            json,
        } => run_path(&from, &to, vault, db, json),
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
    }
    ExitCode::SUCCESS
}

fn run_path(
    from: &str,
    to: &str,
    vault_flag: Option<PathBuf>,
    db_flag: Option<PathBuf>,
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
