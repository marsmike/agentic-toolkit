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

/// Shared model cache across every test in this binary — and across `cargo test` runs, since it's
/// a fixed path under the system temp dir, not process-id-suffixed like the throwaway db dirs
/// below. Model acquisition is decoupled from db path specifically so many throwaway-db tests can
/// share one ~30MB download (see `gaiafield::resolve_model_dir`'s doc comment); deliberately never
/// cleaned up here, unlike the per-test db dirs.
fn shared_model_dir() -> PathBuf {
    std::env::temp_dir().join("gaiafield-v2-test-model-cache")
}

/// Build a `{"clusters": {...}}` spec matching `Test-Corpus-Map.md`'s three planted clusters,
/// written to a fresh throwaway file. Paths are discovered from the real vault directories rather
/// than hardcoded, so this stays correct if a note is added/renamed within a cluster folder.
fn write_test_clusters_spec() -> PathBuf {
    fn md_files(dir: &Path) -> Vec<String> {
        let vault = vault_path();
        let mut out = Vec::new();
        if let Ok(entries) = std::fs::read_dir(dir) {
            for e in entries.flatten() {
                let p = e.path();
                if p.extension().and_then(|s| s.to_str()) == Some("md") {
                    let rel = p
                        .strip_prefix(&vault)
                        .unwrap()
                        .to_string_lossy()
                        .replace(std::path::MAIN_SEPARATOR, "/");
                    out.push(rel);
                }
            }
        }
        out
    }

    let vault = vault_path();
    let mut toolkit = md_files(&vault.join("04_Resources/Concepts"));
    toolkit.extend(md_files(&vault.join("04_Resources/Guides")));
    toolkit.extend(md_files(&vault.join("04_Resources/Tools")));
    toolkit.push("Alex-Vega.md".to_string());

    let mut birding = md_files(&vault.join("02_Projects/field-guide"));
    birding.push("03_Areas/Birding.md".to_string());

    let mut homelab = md_files(&vault.join("02_Projects/home-lab-migration"));
    homelab.push("03_Areas/Home-Network-Administration.md".to_string());

    let spec = serde_json::json!({
        "clusters": {
            "toolkit-concepts": toolkit,
            "birding": birding,
            "homelab": homelab,
        }
    });

    let n = COUNTER.fetch_add(1, Ordering::SeqCst);
    let path = std::env::temp_dir().join(format!(
        "gaiafield-test-clusters-{}-{}.json",
        std::process::id(),
        n
    ));
    std::fs::write(
        &path,
        serde_json::to_string(&spec).expect("serialize cluster spec"),
    )
    .expect("write clusters spec");
    path
}

/// (v2-a) `infer` on `./vault` produces `INFERRED` edges, and calibrating against the planted
/// clusters (`Test-Corpus-Map.md`) shows real separation — intra-cluster notes score higher on
/// average than cross-cluster ones. This validates the whole v2 approach against the ground truth
/// the vault was built to provide (contract rule 3: gates are model-calibrated, not universal).
#[test]
fn infer_produces_inferred_edges_with_calibration_separation() {
    let db = fresh_db_path("infer-calibrate");
    let conn = gaiafield::open_db(&db).expect("open db");
    let vault = vault_path();

    let report = gaiafield::infer(&vault, &conn, &shared_model_dir(), true, false)
        .expect("infer should succeed");
    assert!(
        report.inferred_edges > 0,
        "expected at least one INFERRED edge, got {report:?}"
    );
    assert_eq!(report.model, gaiafield::MODEL_NAME);

    let spec_path = write_test_clusters_spec();
    let calibration = gaiafield::calibrate(&conn, &spec_path).expect("calibrate should succeed");
    assert!(
        calibration.intra_mean > calibration.cross_mean,
        "expected intra-cluster similarity to exceed cross-cluster: {calibration:?}"
    );
    // A real gap, not the old pooled-mean's noise-thinned ~0.08 (README "Calibration" — the bias
    // lesson: pooled means overfit to cluster-size imbalance). The tight-clusters-only method
    // should recover most of `birding`/`homelab`'s ~0.177 separation.
    assert!(
        calibration.separation > 0.10,
        "expected a real, non-noise-thinned separation from the tight-clusters-only method, \
         got {calibration:?}"
    );

    let _ = std::fs::remove_file(&spec_path);
    let _ = std::fs::remove_dir_all(db.parent().unwrap());
}

/// (v2-a2) `calibrate`'s tightness rule (README "Calibration") correctly self-excludes the planted
/// `toolkit-concepts` grab-bag (57 notes, weak internal coherence relative to `birding`/`homelab`'s
/// tight 7-note clusters) from `tight_clusters`, and `cluster_pairs` reports every raw pair's
/// (mean, n) — not just the post-filter `intra_mean`/`cross_mean` summary. This is the calibration
/// fix itself under test, independent of whatever `DEFAULT_HIGH_GATE`/`DEFAULT_LOW_GATE` currently
/// are.
#[test]
fn calibrate_self_excludes_the_grab_bag_cluster_via_cluster_pairs_breakdown() {
    let db = fresh_db_path("calibrate-tightness");
    let conn = gaiafield::open_db(&db).expect("open db");
    let vault = vault_path();
    gaiafield::infer(&vault, &conn, &shared_model_dir(), true, false)
        .expect("infer should succeed");

    let spec_path = write_test_clusters_spec();
    let calibration = gaiafield::calibrate(&conn, &spec_path).expect("calibrate should succeed");

    assert_eq!(
        calibration.tight_clusters,
        vec!["birding".to_string(), "homelab".to_string()],
        "toolkit-concepts (the grab-bag) should self-exclude: {calibration:?}"
    );

    for expected_key in [
        "birding~birding",
        "birding~homelab",
        "birding~toolkit-concepts",
        "homelab~homelab",
        "homelab~toolkit-concepts",
        "toolkit-concepts~toolkit-concepts",
    ] {
        assert!(
            calibration.cluster_pairs.contains_key(expected_key),
            "expected cluster_pairs to report {expected_key:?}, got keys {:?}",
            calibration.cluster_pairs.keys().collect::<Vec<_>>()
        );
    }

    let toolkit_intra = calibration.cluster_pairs["toolkit-concepts~toolkit-concepts"].mean;
    let birding_homelab_cross = calibration.cluster_pairs["birding~homelab"].mean;
    assert!(
        birding_homelab_cross > toolkit_intra,
        "expected the tell that motivated the fix: a cross-cluster pair between two tight \
         clusters scoring higher than the grab-bag's own intra-mean ({birding_homelab_cross} \
         vs {toolkit_intra})"
    );

    let _ = std::fs::remove_file(&spec_path);
    let _ = std::fs::remove_dir_all(db.parent().unwrap());
}

/// (v2-b) Candidates for a birding note (`Publisher-Outreach-Log.md`) surface a same-cluster note
/// (`Birding.md`, the area) with a high score, and correctly exclude every note it already links
/// to (`Field-Guide-Project.md`, `Species-Accounts-Workflow.md`, `Weekly-Review.md`,
/// `Illustration-Sourcing.md`) — "nothing to suggest where a wikilink already exists."
#[test]
fn candidates_surfaces_same_cluster_note_and_excludes_wikilinked_pairs() {
    let db = fresh_db_path("candidates");
    let conn = gaiafield::open_db(&db).expect("open db");
    let vault = vault_path();
    gaiafield::infer(&vault, &conn, &shared_model_dir(), true, false)
        .expect("infer should succeed");

    let note = "02_Projects/field-guide/Publisher-Outreach-Log.md";
    let result = gaiafield::candidates(&conn, note, 50, true).expect("candidates query");
    assert!(
        !result.is_empty(),
        "expected at least one candidate for {note}"
    );

    let paths: Vec<&str> = result.iter().map(|c| c.path.as_str()).collect();
    assert!(
        paths.contains(&"03_Areas/Birding.md"),
        "expected the same-cluster Birding.md area note among candidates: {paths:?}"
    );
    let birding_row = result
        .iter()
        .find(|c| c.path == "03_Areas/Birding.md")
        .unwrap();
    assert!(
        birding_row.score >= gaiafield::DEFAULT_HIGH_GATE,
        "expected a high score for the same-cluster candidate, got {birding_row:?}"
    );

    for already_linked in [
        "02_Projects/field-guide/Field-Guide-Project.md",
        "02_Projects/field-guide/Species-Accounts-Workflow.md",
        "02_Projects/field-guide/Weekly-Review.md",
        "02_Projects/field-guide/Illustration-Sourcing.md",
    ] {
        assert!(
            !paths.contains(&already_linked),
            "already-wikilinked {already_linked} should never appear as an inferred candidate: {paths:?}"
        );
    }

    let _ = std::fs::remove_dir_all(db.parent().unwrap());
}

/// (v2-c) The planted bridge structure guarantees cross-subtree pairs among the top-surprise
/// results — a high-scoring inferred edge between notes with no short deterministic route between
/// them (contract rule 5: surprise scoring is derived, not stored magic).
#[test]
fn surprise_top_results_include_cross_subtree_pairs() {
    let db = fresh_db_path("surprise");
    let conn = gaiafield::open_db(&db).expect("open db");
    let vault = vault_path();
    gaiafield::infer(&vault, &conn, &shared_model_dir(), true, false)
        .expect("infer should succeed");

    let result = gaiafield::surprise(&conn, 20, 0.0, true).expect("surprise query");
    assert!(
        !result.is_empty(),
        "expected at least one inferred edge above min_score 0.0"
    );
    assert!(
        result.iter().any(|r| !r.same_subtree),
        "expected at least one cross-subtree pair among top-surprise results: {result:?}"
    );
    for w in result.windows(2) {
        assert!(
            w[0].surprise >= w[1].surprise,
            "surprise results should be sorted descending: {result:?}"
        );
    }

    let _ = std::fs::remove_dir_all(db.parent().unwrap());
}

/// (v2-f) `surprise` gates its AMBIGUOUS-band pairs exactly like `candidates` does (Fix 2 — the
/// original CLI spec this crate was built against had no `label`/`model` fields and no
/// `--include-ambiguous` flag at all, which let the AMBIGUOUS band leak by default with no way to
/// even see which label a row carried; the contract wins over that spec). Every row carries
/// `label`/`model`; the default (`include_ambiguous: false`) excludes AMBIGUOUS rows even though
/// they exist in the db, and `include_ambiguous: true` surfaces them again.
#[test]
fn surprise_gates_ambiguous_band_and_every_row_carries_label_and_model() {
    let db = fresh_db_path("surprise-ambiguous-gate");
    let conn = gaiafield::open_db(&db).expect("open db");
    let vault = vault_path();
    gaiafield::infer(&vault, &conn, &shared_model_dir(), true, false)
        .expect("infer should succeed");

    let default_result = gaiafield::surprise(&conn, 1000, 0.0, false).expect("surprise query");
    assert!(
        !default_result.is_empty(),
        "expected at least one INFERRED-labeled edge in the default (non-ambiguous) result"
    );
    assert!(
        default_result.iter().all(|r| r.label == "INFERRED"),
        "default surprise() (include_ambiguous: false) must exclude every AMBIGUOUS row: {default_result:?}"
    );
    assert!(
        default_result
            .iter()
            .all(|r| r.model == gaiafield::MODEL_NAME),
        "every row should carry the model name: {default_result:?}"
    );

    let with_ambiguous = gaiafield::surprise(&conn, 1000, 0.0, true).expect("surprise query");
    assert!(
        with_ambiguous.iter().any(|r| r.label == "AMBIGUOUS"),
        "include_ambiguous: true should surface AMBIGUOUS rows that exist in the db: \
         {with_ambiguous:?}"
    );
    assert!(
        with_ambiguous.len() > default_result.len(),
        "include_ambiguous: true should return strictly more rows than the gated default \
         (default {}, with_ambiguous {})",
        default_result.len(),
        with_ambiguous.len()
    );

    let _ = std::fs::remove_dir_all(db.parent().unwrap());
}

/// (v2-d) `infer --reset` restores the exact v1 graph — `nodes`/`edges` after infer-then-reset are
/// row-for-row identical to a db that was only ever `index`'d, never `infer`'d (contract rule 2:
/// inference never mutates extraction).
///
/// Runs against a private scratch copy of the vault (like the deletion test above), not the
/// shared `./vault` directly: comparing two independent `index` runs' `mtime` columns would
/// otherwise be racy against `incremental_reindex_touches_only_the_changed_note`, which
/// deliberately bumps a real vault file's mtime while tests run in parallel.
#[test]
fn infer_reset_restores_exact_v1_graph() {
    let n = COUNTER.fetch_add(1, Ordering::SeqCst);
    let scratch = std::env::temp_dir().join(format!(
        "gaiafield-test-reset-vault-{}-{}",
        std::process::id(),
        n
    ));
    copy_dir_recursive(&vault_path(), &scratch);
    let vault = scratch.clone();

    let never_inferred = fresh_db_path("reset-baseline");
    {
        let conn = gaiafield::open_db(&never_inferred).expect("open db");
        gaiafield::index(&vault, &conn, true).expect("index should succeed");
    }

    let then_reset = fresh_db_path("reset-target");
    {
        let conn = gaiafield::open_db(&then_reset).expect("open db");
        gaiafield::index(&vault, &conn, true).expect("index should succeed");
        gaiafield::infer(&vault, &conn, &shared_model_dir(), true, false)
            .expect("infer should succeed");
        let before_reset: i64 = conn
            .query_row("SELECT COUNT(*) FROM inferred_edges", [], |r| r.get(0))
            .unwrap();
        assert!(
            before_reset > 0,
            "sanity: infer should produce inferred edges before the reset"
        );
        gaiafield::infer(&vault, &conn, &shared_model_dir(), false, true)
            .expect("infer --reset should succeed");
    }

    #[allow(clippy::type_complexity)]
    fn dump_nodes(db: &Path) -> Vec<(String, String, String, String, String, String, i64, i64)> {
        let conn = gaiafield::open_db(db).expect("open db");
        let mut stmt = conn
            .prepare("SELECT path, title, description, status, kind, tags, mtime, size FROM nodes ORDER BY path")
            .expect("valid SQL");
        stmt.query_map([], |row| {
            Ok((
                row.get(0)?,
                row.get(1)?,
                row.get(2)?,
                row.get(3)?,
                row.get(4)?,
                row.get(5)?,
                row.get(6)?,
                row.get(7)?,
            ))
        })
        .expect("valid query")
        .filter_map(Result::ok)
        .collect()
    }

    #[allow(clippy::type_complexity)]
    fn dump_edges(db: &Path) -> Vec<(String, Option<String>, String, String, i64, i64)> {
        let conn = gaiafield::open_db(db).expect("open db");
        let mut stmt = conn
            .prepare(
                "SELECT source, target, raw_target, edge_type, dangling, boundary_violation \
                 FROM edges ORDER BY source, raw_target, target",
            )
            .expect("valid SQL");
        stmt.query_map([], |row| {
            Ok((
                row.get(0)?,
                row.get(1)?,
                row.get(2)?,
                row.get(3)?,
                row.get(4)?,
                row.get(5)?,
            ))
        })
        .expect("valid query")
        .filter_map(Result::ok)
        .collect()
    }

    assert_eq!(
        dump_nodes(&never_inferred),
        dump_nodes(&then_reset),
        "nodes table must be row-for-row identical to a never-inferred index after infer --reset"
    );
    assert_eq!(
        dump_edges(&never_inferred),
        dump_edges(&then_reset),
        "edges table must be row-for-row identical to a never-inferred index after infer --reset"
    );

    let post_reset_v2_rows: i64 = {
        let conn = gaiafield::open_db(&then_reset).expect("open db");
        conn.query_row("SELECT COUNT(*) FROM inferred_edges", [], |r| r.get(0))
            .unwrap()
    };
    assert_eq!(
        post_reset_v2_rows, 0,
        "reset should leave zero inferred edges"
    );

    let _ = std::fs::remove_dir_all(never_inferred.parent().unwrap());
    let _ = std::fs::remove_dir_all(then_reset.parent().unwrap());
    let _ = std::fs::remove_dir_all(&scratch);
}

/// (v2-e) `neighbors` WITHOUT `--include-inferred` is byte-identical to v1 behavior on a db that
/// HAS been `infer`'d — the deterministic layer's own CLI output never changes shape just because
/// inferred edges now exist alongside it (contract rule 4: traversal defaults to deterministic).
#[test]
fn neighbors_without_include_inferred_is_byte_identical_on_an_inferred_db() {
    let vault = vault_path();
    let note = "Alex-Vega.md";

    let never_inferred = fresh_db_path("byte-identical-baseline");
    {
        let conn = gaiafield::open_db(&never_inferred).expect("open db");
        gaiafield::index(&vault, &conn, true).expect("index should succeed");
    }

    let inferred_db = fresh_db_path("byte-identical-inferred");
    {
        let conn = gaiafield::open_db(&inferred_db).expect("open db");
        gaiafield::index(&vault, &conn, true).expect("index should succeed");
        gaiafield::infer(&vault, &conn, &shared_model_dir(), true, false)
            .expect("infer should succeed");
    }

    let run = |db: &Path| -> Vec<u8> {
        Command::new(env!("CARGO_BIN_EXE_gaiafield"))
            .args(["neighbors", note, "--vault"])
            .arg(&vault)
            .args(["--db"])
            .arg(db)
            .args(["--depth", "2", "--json"])
            .output()
            .expect("failed to run gaiafield neighbors")
            .stdout
    };

    let baseline_stdout = run(&never_inferred);
    let inferred_stdout = run(&inferred_db);
    assert_eq!(
        baseline_stdout, inferred_stdout,
        "neighbors --json without --include-inferred must be byte-identical regardless of \
         whether the db has inferred edges"
    );

    let _ = std::fs::remove_dir_all(never_inferred.parent().unwrap());
    let _ = std::fs::remove_dir_all(inferred_db.parent().unwrap());
}

/// Bump a file's mtime (and access time) without touching its contents — std has no stable
/// "touch," so re-write the same bytes back, which updates mtime on every platform this crate
/// targets without a filetime dependency.
fn filetime_touch(path: &Path, _now: std::time::SystemTime) {
    let contents = std::fs::read(path).expect("read note to touch");
    std::fs::write(path, contents).expect("rewrite note to bump mtime");
}

/// Recursively copy `src` into `dst` (which must not yet exist). Used by the deletion test below
/// so it can remove a file without ever mutating the repo's own `./vault`.
fn copy_dir_recursive(src: &Path, dst: &Path) {
    std::fs::create_dir_all(dst).expect("create scratch vault dir");
    for entry in std::fs::read_dir(src).expect("read source dir") {
        let entry = entry.expect("dir entry");
        let file_type = entry.file_type().expect("file type");
        let src_path = entry.path();
        let dst_path = dst.join(entry.file_name());
        if file_type.is_dir() {
            copy_dir_recursive(&src_path, &dst_path);
        } else {
            std::fs::copy(&src_path, &dst_path).expect("copy vault file");
        }
    }
}

/// (h) Incremental deletion must not corrupt the graph. Deleting a note's row must not silently
/// drop *other* notes' incoming edges into it — those wikilinks are still real text sitting in
/// other notes' bodies, and the crate's own design treats dangling links as data (module doc).
/// The planted target is `04_Resources/Concepts/Atomic-Notes.md`, linked from exactly 4 distinct
/// active-content notes (`Species-Accounts-Workflow.md`, `Capture-Conventions.md` — twice —,
/// `Anonymized-Failure-Repros.md` — twice —, and `Vault-Größe-und-Skalierungsschwellen.md`), 6
/// resolved incoming edges total, with no other file in the vault sharing its filename stem (so
/// resolution is unambiguous). Runs against a scratch copy of the vault, never the repo's own
/// `./vault`, since this test deletes a file.
#[test]
fn incremental_deletion_reflags_incoming_edges_dangling_not_corrupt() {
    let n = COUNTER.fetch_add(1, Ordering::SeqCst);
    let scratch = std::env::temp_dir().join(format!(
        "gaiafield-test-deletion-vault-{}-{}",
        std::process::id(),
        n
    ));
    copy_dir_recursive(&vault_path(), &scratch);

    let db = fresh_db_path("deletion");
    let conn = gaiafield::open_db(&db).expect("open db");
    gaiafield::index(&scratch, &conn, true).expect("full index should succeed");

    let deleted = "04_Resources/Concepts/Atomic-Notes.md";

    let before_incoming: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM edges WHERE target = ?1 AND dangling = 0",
            [deleted],
            |r| r.get(0),
        )
        .expect("count incoming edges before deletion");
    assert_eq!(
        before_incoming, 6,
        "expected 6 resolved incoming wikilink occurrences into Atomic-Notes.md before deletion"
    );
    let before_dangling: i64 = conn
        .query_row("SELECT COUNT(*) FROM edges WHERE dangling = 1", [], |r| {
            r.get(0)
        })
        .expect("count dangling edges before deletion");

    std::fs::remove_file(scratch.join(deleted)).expect("delete the note from the scratch vault");

    let report =
        gaiafield::index(&scratch, &conn, false).expect("incremental re-index should succeed");
    assert_eq!(report.removed, 1, "exactly one node should be removed");

    let node_exists = conn
        .query_row("SELECT 1 FROM nodes WHERE path = ?1", [deleted], |_| Ok(()))
        .is_ok();
    assert!(!node_exists, "deleted note should be absent from nodes");

    // Former incoming edges survive as data but are re-flagged dangling, never left resolved
    // against a node that no longer has a row, and never silently dropped.
    let after_incoming_resolved: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM edges WHERE target = ?1 AND dangling = 0",
            [deleted],
            |r| r.get(0),
        )
        .expect("count incoming edges after deletion");
    assert_eq!(
        after_incoming_resolved, 0,
        "no edge should still resolve to the deleted node"
    );
    let stray_target: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM edges WHERE target = ?1",
            [deleted],
            |r| r.get(0),
        )
        .expect("count any edge still pointing at the deleted path");
    assert_eq!(
        stray_target, 0,
        "re-flagged edges should clear target to NULL like any other dangling edge"
    );
    let after_dangling: i64 = conn
        .query_row("SELECT COUNT(*) FROM edges WHERE dangling = 1", [], |r| {
            r.get(0)
        })
        .expect("count dangling edges after deletion");
    assert_eq!(
        after_dangling,
        before_dangling + 6,
        "the 6 former incoming edges should have joined the dangling count"
    );

    // `neighbors` of a former neighbor must not crash querying a vanished node, and must exclude
    // the deleted note from its results.
    let former_neighbor = "04_Resources/Guides/Capture-Conventions.md";
    let neighbor_result = gaiafield::neighbors(&conn, former_neighbor, 2, Direction::Both)
        .expect("neighbors of a former neighbor of the deleted note should not error");
    assert!(
        !neighbor_result.iter().any(|n| n.path == deleted),
        "neighbors should never surface the deleted note: {neighbor_result:?}"
    );

    // `path` between two notes previously connected through the deleted note must never route
    // through it — either it finds another route, or it correctly reports not-connected.
    let other_former_neighbor = "02_Projects/field-guide/Species-Accounts-Workflow.md";
    let path_report = gaiafield::shortest_path(&conn, other_former_neighbor, former_neighbor)
        .expect("path query should not error");
    assert!(
        !path_report.path.iter().any(|p| p == deleted),
        "path must never route through the deleted node: {:?}",
        path_report.path
    );

    let _ = std::fs::remove_dir_all(db.parent().unwrap());
    let _ = std::fs::remove_dir_all(&scratch);
}
