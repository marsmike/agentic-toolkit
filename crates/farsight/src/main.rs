use clap::{Parser, Subcommand};
use std::path::PathBuf;
use std::process::ExitCode;

#[derive(Parser)]
#[command(
    name = "farsight",
    version,
    about = "Stateless BM25 search over an agentic-toolkit vault"
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    /// Search active-content notes and print ranked results.
    Query {
        /// Query terms (quote them, or pass several words — both are joined and tokenized).
        #[arg(required = true, num_args = 1..)]
        terms: Vec<String>,

        /// Vault path. Falls back to TOOLKIT_VAULT, then ./vault at the repo root.
        #[arg(long)]
        vault: Option<PathBuf>,

        /// Max number of results to return.
        #[arg(long, default_value_t = 10)]
        k: usize,

        /// Emit a JSON array of {path, score, title, description} instead of a table.
        #[arg(long)]
        json: bool,
    },
}

fn main() -> ExitCode {
    let cli = Cli::parse();
    match cli.command {
        Command::Query {
            terms,
            vault,
            k,
            json,
        } => run_query(&terms.join(" "), vault, k, json),
    }
}

fn run_query(query: &str, vault_flag: Option<PathBuf>, k: usize, json: bool) -> ExitCode {
    let vault = match farsight::require_vault(vault_flag.as_deref()) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("{e}");
            return ExitCode::FAILURE;
        }
    };

    let results = farsight::search(query, &vault, k);

    if json {
        match serde_json::to_string_pretty(&results) {
            Ok(s) => println!("{s}"),
            Err(e) => {
                eprintln!("failed to serialize results: {e}");
                return ExitCode::FAILURE;
            }
        }
    } else if results.is_empty() {
        println!("No results for {query:?}.");
    } else {
        for r in &results {
            println!("{:>7.4}  {}  ({})", r.score, r.title, r.path);
            if !r.description.is_empty() {
                println!("         {}", r.description);
            }
        }
    }
    ExitCode::SUCCESS
}
