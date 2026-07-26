//! Lean integration coverage for farsight — a handful of essential cases against the
//! repo's own `./vault`, per the R1 brief (no unit-test sprawl, no mocking).

use std::path::{Path, PathBuf};
use std::process::Command;

fn vault_path() -> PathBuf {
    // crates/farsight/ -> repo root -> vault/
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../vault")
}

/// The BM25-dilution specimen pair (vault/04_Resources/Guides/Test-Corpus-Map.md): the
/// condensed-description note must outrank its long-prose sibling for the exact phrase
/// the vault's own BM25-Dilution note names as the query to check this against.
#[test]
fn condensed_specimen_outranks_long_prose_sibling() {
    let vault = vault_path();
    let results = farsight::search("retrieval verification loop", &vault, 20);

    let rank_of = |needle: &str| results.iter().position(|r| r.path.contains(needle));
    let condensed = rank_of("Retrieval-Verification-Loop-Condensed-Description-Specimen")
        .expect("condensed specimen should be in the results");
    let long = rank_of("Retrieval-Verification-Loop-Long-Description-Specimen")
        .expect("long-prose specimen should be in the results");

    assert!(
        condensed < long,
        "condensed specimen (rank {condensed}) should outrank the long-prose sibling (rank {long})"
    );
}

/// contract/VAULT_SCHEMA.md's active-content filter: 00_Memory, 01_Capture, and
/// 05_Archive are never in scope for search — but the root-level-note clause of the same
/// filter means the vault's bridge persona note, `Alex-Vega.md` (root, `status: active`),
/// *is* in scope, and a query matching its own content must return it (this used to
/// disagree with `gaiafield`, which already indexed the note as a graph node — see
/// `contract/VAULT_SCHEMA.md`'s root-level-note clause).
#[test]
fn active_content_filter_excludes_memory_capture_and_archive() {
    let vault = vault_path();
    let notes = farsight::discover_notes(&vault);
    assert!(
        !notes.is_empty(),
        "expected the example vault to yield active-content notes"
    );

    for excluded in ["00_Memory", "01_Capture", "05_Archive"] {
        let leaked: Vec<_> = notes
            .iter()
            .filter(|p| {
                p.strip_prefix(&vault)
                    .map(|r| r.starts_with(excluded))
                    .unwrap_or(false)
            })
            .collect();
        assert!(
            leaked.is_empty(),
            "{excluded} should never appear in discovered notes, found {leaked:?}"
        );
    }

    let results = farsight::search("Alex Vega", &vault, 10);
    assert!(
        results.iter().any(|r| r.path.contains("Alex-Vega")),
        "a query matching the root-level persona note's content should return it: {results:?}"
    );
}

/// contract/VAULT_SCHEMA.md: a note with no frontmatter block at all is valid, not an
/// error. The planted case is 04_Resources/Guides/Migrating-Notes-From-Plain-Markdown.md.
#[test]
fn no_frontmatter_note_does_not_crash_and_is_searchable() {
    let vault = vault_path();
    let results = farsight::search("plain markdown migrating notes", &vault, 10);

    let hit = results
        .iter()
        .find(|r| r.path.contains("Migrating-Notes-From-Plain-Markdown"))
        .expect("no-frontmatter note should still be discoverable and scored");
    assert_eq!(
        hit.description, "",
        "a note with no frontmatter has no description field to report"
    );
}

/// `--json` output must be a JSON array of {path, score, title, description} that parses
/// cleanly and actually has results for a real query.
#[test]
fn json_output_parses() {
    let vault = vault_path();
    let output = Command::new(env!("CARGO_BIN_EXE_farsight"))
        .args(["query", "retrieval verification loop", "--vault"])
        .arg(&vault)
        .args(["--k", "5", "--json"])
        .output()
        .expect("failed to run the farsight binary");
    assert!(
        output.status.success(),
        "farsight query exited non-zero: {output:?}"
    );

    let stdout = String::from_utf8(output.stdout).expect("stdout should be valid UTF-8");
    let parsed: Vec<serde_json::Value> =
        serde_json::from_str(&stdout).expect("--json output must parse as a JSON array");
    assert!(
        !parsed.is_empty(),
        "expected at least one result for a query that hits planted specimen notes"
    );
    for row in &parsed {
        for field in ["path", "score", "title", "description"] {
            assert!(
                row.get(field).is_some(),
                "result row missing {field}: {row}"
            );
        }
    }
}
