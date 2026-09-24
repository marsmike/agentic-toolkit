//! Exercise the public CLI's inferred-edge gate without downloading a model.
use std::path::Path;
use std::process::Command;

#[test]
fn include_inferred_does_not_admit_ambiguous_neighbors_or_paths() {
    let root = std::env::temp_dir().join(format!("gaiafield-traversal-{}", std::process::id()));
    let db = root.join("graph.db");
    let vault = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../vault");
    let conn = gaiafield::open_db(&db).unwrap();
    gaiafield::index(&vault, &conn, true).unwrap();
    // Isolate the traversal decision from the planted corpus's existing routes.
    conn.execute_batch("DELETE FROM edges; DELETE FROM inferred_edges;").unwrap();
    let start = "Alex-Vega.md";
    let inferred = "04_Resources/Concepts/Atomic-Notes.md";
    let ambiguous_out = "03_Areas/Birding.md";
    let ambiguous_in = "03_Areas/Home-Network-Administration.md";
    for (source, target, label) in [
        (start, inferred, "INFERRED"),
        (start, ambiguous_out, "AMBIGUOUS"),
        (ambiguous_in, start, "AMBIGUOUS"),
        (inferred, ambiguous_out, "AMBIGUOUS"),
    ] {
        conn.execute("INSERT INTO inferred_edges (source, target, score, label, model) VALUES (?1, ?2, 0.8, ?3, 'test')", [source, target, label]).unwrap();
    }
    let run = |args: &[&str]| {
        let output = Command::new(env!("CARGO_BIN_EXE_gaiafield"))
            .args(args).arg("--vault").arg(&vault).arg("--db").arg(&db)
            .args(["--include-inferred", "--json"]).output().unwrap();
        assert!(output.status.success(), "{}", String::from_utf8_lossy(&output.stderr));
        serde_json::from_slice::<serde_json::Value>(&output.stdout).unwrap()
    };
    let neighbors = run(&["neighbors", start]);
    let neighbors = neighbors.as_array().unwrap();
    assert_eq!(neighbors.len(), 1, "{neighbors:?}");
    assert_eq!(neighbors[0]["path"], inferred);
    assert_eq!(neighbors[0]["label"], "INFERRED");
    assert_eq!(run(&["path", start, inferred])["connected"], true);
    for other in [ambiguous_out, ambiguous_in] {
        assert_eq!(run(&["path", start, other])["connected"], false);
    }
    drop(conn);
    std::fs::remove_dir_all(root).unwrap();
}
