//! Lean integration coverage for gaiafield — one test file, run against the repo's own
//! `./vault` (never a user's vault, per `CONTRIBUTING.md`), asserting the planted structure
//! documented in `vault/04_Resources/Guides/Test-Corpus-Map.md`.
//!
//! Every test uses its own throwaway DB under the system temp dir (never
//! `vault/.gaiafield/graph.db`) so a test run never leaves an untracked database inside the
//! example vault.

use gaiafield::{self, Direction, ResolveError};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicU32, Ordering};

fn vault_path() -> PathBuf {
    // crates/gaiafield/ -> repo root -> vault/
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../../vault")
}

static COUNTER: AtomicU32 = AtomicU32::new(0);

/// A throwaway DB path under the system temp dir, unique per call so parallel test functions
/// never collide.
fn fresh_db_path(label: &str) -> PathBuf {
    let n = COUNTER.fetch_add(1, Ordering::SeqCst);
    let dir = std::env::temp_dir().join(format!(
        "gaiafield-test-{}-{}-{}",
        std::process::id(),
        label,
        n
    ));
    dir.join("graph.db")
}

fn index_full(db: &Path) -> gaiafield::IndexReport {
    let vault = vault_path();
    let conn = gaiafield::open_db(db).expect("open db");
    gaiafield::index(&vault, &conn, true).expect("index should succeed")
}

/// (a) Indexing recovers the expected node count — `vault/Index.md`'s stated 72 active-content
/// notes plus the one root-level note (`Alex-Vega.md`) whose own frontmatter declares
/// `status: active` (see `discover_nodes`'s doc comment for why that root note is included) —
/// and a link density in the ~8-12/note ballpark `Test-Corpus-Map.md` targets. Driven through
/// the real `index`/`stats` CLI binary (not just the library) so `--json` wiring is covered too.
#[test]
fn index_recovers_expected_node_count_and_density() {
    let db = fresh_db_path("density");
    let vault = vault_path();

    let index_out = Command::new(env!("CARGO_BIN_EXE_gaiafield"))
        .args(["index", "--vault"])
        .arg(&vault)
        .args(["--db"])
        .arg(&db)
        .args(["--full", "--json"])
        .output()
        .expect("failed to run gaiafield index");
    assert!(
        index_out.status.success(),
        "index exited non-zero: {index_out:?}"
    );
    let index_json: serde_json::Value =
        serde_json::from_slice(&index_out.stdout).expect("index --json should parse");
    assert_eq!(
        index_json["total_nodes"], 73,
        "expected 72 active-content notes (Index.md) + Alex-Vega.md (root, status: active)"
    );

    let stats_out = Command::new(env!("CARGO_BIN_EXE_gaiafield"))
        .args(["stats", "--vault"])
        .arg(&vault)
        .args(["--db"])
        .arg(&db)
        .arg("--json")
        .output()
        .expect("failed to run gaiafield stats");
    assert!(
        stats_out.status.success(),
        "stats exited non-zero: {stats_out:?}"
    );
    let stats_json: serde_json::Value =
        serde_json::from_slice(&stats_out.stdout).expect("stats --json should parse");
    assert_eq!(stats_json["nodes"], 73);
    assert_eq!(stats_json["dangling_edges"], 1);
    assert_eq!(stats_json["boundary_violations"], 0);

    let edges = stats_json["edges"].as_u64().unwrap();
    let avg = edges as f64 / 73.0;
    assert!(
        (5.0..=15.0).contains(&avg),
        "average resolved out-links per node ({avg:.2}) should be near the vault's ~8-12 target"
    );

    let _ = std::fs::remove_dir_all(db.parent().unwrap());
}

/// (b) Exactly one dangling edge, and it's the planted
/// `[[Nonexistent-Note-For-Linting-Demo]]` in `Vault-Maintenance-and-Linting.md`.
#[test]
fn exactly_one_dangling_edge_is_the_planted_specimen() {
    let db = fresh_db_path("dangling");
    let report = index_full(&db);
    assert_eq!(
        report.dangling_edges, 1,
        "expected exactly one dangling edge"
    );

    let conn = gaiafield::open_db(&db).expect("open db");
    let (source, raw_target): (String, String) = conn
        .query_row(
            "SELECT source, raw_target FROM edges WHERE dangling = 1",
            [],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .expect("the one dangling row should be readable");
    assert_eq!(
        source,
        "04_Resources/Guides/Vault-Maintenance-and-Linting.md"
    );
    assert_eq!(raw_target, "Nonexistent-Note-For-Linting-Demo");

    let _ = std::fs::remove_dir_all(db.parent().unwrap());
}

/// (c) Zero boundary violations — no active note links into `00_Memory`/`01_Capture`/
/// `05_Archive`. The planted archived note (`Deprecated-Plugin-Notebooklm.md`) has zero
/// inbound wikilinks from active content, exactly as its own body claims.
#[test]
fn zero_boundary_violations() {
    let db = fresh_db_path("boundary");
    let report = index_full(&db);
    assert_eq!(report.boundary_violations, 0);

    let _ = std::fs::remove_dir_all(db.parent().unwrap());
}

/// (d) `neighbors` on the bridge note Alex-Vega (vault root, per `Test-Corpus-Map.md`: "root
/// persona, links into all three clusters") reaches a representative note from all three
/// clusters (toolkit-concepts, birding, homelab) within depth 2.
#[test]
fn alex_vega_bridge_reaches_all_three_clusters_within_depth_2() {
    let db = fresh_db_path("bridge");
    index_full(&db);
    let conn = gaiafield::open_db(&db).expect("open db");

    let result =
        gaiafield::neighbors(&conn, "Alex-Vega.md", 2, Direction::Both).expect("neighbors");
    let paths: Vec<&str> = result.iter().map(|n| n.path.as_str()).collect();

    assert!(
        paths.contains(&"02_Projects/field-guide/Field-Guide-Project.md"),
        "should reach the birding cluster: {paths:?}"
    );
    assert!(
        paths.contains(&"02_Projects/home-lab-migration/Home-Lab-Migration.md"),
        "should reach the homelab cluster: {paths:?}"
    );
    assert!(
        paths.contains(&"03_Areas/Toolkit-Maintenance.md"),
        "should reach the toolkit-concepts cluster: {paths:?}"
    );

    let _ = std::fs::remove_dir_all(db.parent().unwrap());
}

/// (e) A path exists between a birding note and a homelab note, crossing clusters through a
/// real, intentional cross-link rather than failing to connect. Every project sub-note routes
/// through its own project hub, and the field-guide/home-lab hubs directly cross-reference each
/// other (see `Test-Corpus-Map.md`'s "same title, different folders" specimen) — that direct
/// hub-to-hub edge is *shorter* than any route via the named bridge notes (Alex-Vega,
/// Toolkit-Maintenance, Running-Evals, Farsight), so BFS correctly prefers it. This test asserts
/// the path is connected, crosses from one cluster's hub to the other's, and passes through no
/// spurious node.
#[test]
fn path_between_birding_and_homelab_note_crosses_via_project_hubs() {
    let db = fresh_db_path("path");
    index_full(&db);
    let conn = gaiafield::open_db(&db).expect("open db");

    let report = gaiafield::shortest_path(
        &conn,
        "02_Projects/field-guide/Illustration-Sourcing.md",
        "02_Projects/home-lab-migration/Hardware-Inventory.md",
    )
    .expect("path query");

    assert!(
        report.connected,
        "birding and homelab notes should be connected"
    );
    assert_eq!(
        report.path,
        vec![
            "02_Projects/field-guide/Illustration-Sourcing.md".to_string(),
            "02_Projects/field-guide/Field-Guide-Project.md".to_string(),
            "02_Projects/home-lab-migration/Home-Lab-Migration.md".to_string(),
            "02_Projects/home-lab-migration/Hardware-Inventory.md".to_string(),
        ],
        "expected the path to cross via each cluster's own project hub"
    );

    let _ = std::fs::remove_dir_all(db.parent().unwrap());
}

/// (f) The planted duplicate-title case: `Weekly-Review` exists under both `field-guide/` and
/// `home-lab-migration/`. A bare-name lookup with no folder context to disambiguate must report
/// both candidates rather than silently picking one.
#[test]
fn ambiguous_bare_name_lookup_reports_both_weekly_review_candidates() {
    let db = fresh_db_path("ambiguous");
    index_full(&db);
    let conn = gaiafield::open_db(&db).expect("open db");

    match gaiafield::resolve_note_arg(&conn, "Weekly-Review") {
        Err(ResolveError::Ambiguous(mut candidates)) => {
            candidates.sort();
            assert_eq!(
                candidates,
                vec![
                    "02_Projects/field-guide/Weekly-Review.md".to_string(),
                    "02_Projects/home-lab-migration/Weekly-Review.md".to_string(),
                ]
            );
        }
        other => panic!("expected Ambiguous with both Weekly-Review candidates, got {other:?}"),
    }

    let _ = std::fs::remove_dir_all(db.parent().unwrap());
}

/// (g) Incremental indexing: touching one note's mtime and re-indexing re-extracts only that
/// note (`updated_at` as the cheap proxy) while every other row is left untouched.
#[test]
fn incremental_reindex_touches_only_the_changed_note() {
    let db = fresh_db_path("incremental");
    index_full(&db);

    let touched = "04_Resources/Concepts/Atomic-Notes.md";
    let touched_abs = vault_path().join(touched);

    let before: Vec<(String, i64)> = {
        let conn = gaiafield::open_db(&db).expect("open db");
        let mut stmt = conn.prepare("SELECT path, updated_at FROM nodes").unwrap();
        stmt.query_map([], |row| Ok((row.get(0)?, row.get(1)?)))
            .unwrap()
            .filter_map(Result::ok)
            .collect()
    };

    // Bump mtime without changing content or size, past whatever second-resolution boundary
    // the filesystem/original write landed on.
    std::thread::sleep(std::time::Duration::from_millis(1100));
    let now = std::time::SystemTime::now();
    filetime_touch(&touched_abs, now);

    let conn = gaiafield::open_db(&db).expect("open db");
    let report = gaiafield::index(&vault_path(), &conn, false).expect("incremental index");
    assert_eq!(report.added, 0);
    assert_eq!(report.removed, 0);
    assert_eq!(
        report.updated, 1,
        "only the touched note should be re-extracted"
    );
    assert_eq!(report.unchanged, before.len() - 1);

    let after: Vec<(String, i64)> = {
        let mut stmt = conn.prepare("SELECT path, updated_at FROM nodes").unwrap();
        stmt.query_map([], |row| Ok((row.get(0)?, row.get(1)?)))
            .unwrap()
            .filter_map(Result::ok)
            .collect()
    };

    let before_map: std::collections::HashMap<_, _> = before.into_iter().collect();
    let after_map: std::collections::HashMap<_, _> = after.into_iter().collect();
    for (path, ts) in &after_map {
        if path == touched {
            assert_ne!(
                before_map.get(path),
                Some(ts),
                "the touched note's updated_at should change"
            );
        } else {
            assert_eq!(
                before_map.get(path),
                Some(ts),
                "untouched note {path} should keep its updated_at"
            );
        }
    }

    let _ = std::fs::remove_dir_all(db.parent().unwrap());
}

/// Bump a file's mtime (and access time) without touching its contents — std has no stable
/// "touch," so re-write the same bytes back, which updates mtime on every platform this crate
/// targets without a filetime dependency.
fn filetime_touch(path: &Path, _now: std::time::SystemTime) {
    let contents = std::fs::read(path).expect("read note to touch");
    std::fs::write(path, contents).expect("rewrite note to bump mtime");
}
