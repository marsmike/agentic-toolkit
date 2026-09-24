//! Regression fixtures are scratch copies of ./vault, never an owner's vault.
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU32, Ordering};

static COUNTER: AtomicU32 = AtomicU32::new(0);

fn copy_dir(src: &Path, dst: &Path) {
    std::fs::create_dir_all(dst).unwrap();
    for entry in std::fs::read_dir(src).unwrap() {
        let entry = entry.unwrap();
        let dest = dst.join(entry.file_name());
        if entry.file_type().unwrap().is_dir() {
            copy_dir(&entry.path(), &dest);
        } else {
            std::fs::copy(entry.path(), dest).unwrap();
        }
    }
}

struct Fixture(PathBuf);
impl Fixture {
    fn new() -> Self {
        let root = std::env::temp_dir().join(format!(
            "gaiafield-regression-{}-{}",
            std::process::id(),
            COUNTER.fetch_add(1, Ordering::Relaxed)
        ));
        copy_dir(&Path::new(env!("CARGO_MANIFEST_DIR")).join("../../vault"), &root);
        Self(root)
    }
    fn write(&self, path: &str, body: &str) {
        let path = self.0.join(path);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(path, body).unwrap();
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

type Edge = (String, Option<String>, String, i64, i64);
fn edges(conn: &rusqlite::Connection) -> Vec<Edge> {
    let mut stmt = conn.prepare("SELECT source, target, raw_target, dangling, boundary_violation FROM edges ORDER BY source, target, raw_target, dangling, boundary_violation").unwrap();
    stmt.query_map([], |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?, r.get(3)?, r.get(4)?)))
        .unwrap().map(Result::unwrap).collect()
}

#[test]
fn incremental_target_changes_match_full_resolution() {
    for change in ["add", "rename", "scope", "boundary", "duplicate", "remove-out-of-scope"] {
        let vault = Fixture::new();
        // A duplicate must be visible from outside both target folders; otherwise
        // same-folder precedence keeps the original target and no edge can change.
        let source = if change == "duplicate" {
            "02_Projects/Regression-Source.md"
        } else {
            "04_Resources/Regression-Source.md"
        };
        vault.write(source, "[[Regression-Target]] [[Regression-Target]]");
        match change {
            "rename" => vault.write("04_Resources/Regression-Old.md", "target"),
            "scope" => vault.write("Regression-Target.md", "---\nstatus: dormant\n---\ntarget"),
            "boundary" | "duplicate" => vault.write("04_Resources/Regression-Target.md", "target"),
            "remove-out-of-scope" => vault.write("Templates/Regression-Target.md", "target"),
            _ => (),
        }
        let conn = gaiafield::open_db(&vault.0.join(".gaiafield/test.db")).unwrap();
        gaiafield::index(&vault.0, &conn, true).unwrap();
        match change {
            "add" => vault.write("04_Resources/Regression-Target.md", "target"),
            "rename" => std::fs::rename(vault.0.join("04_Resources/Regression-Old.md"), vault.0.join("04_Resources/Regression-Target.md")).unwrap(),
            "scope" => vault.write("Regression-Target.md", "---\nstatus: active\n---\ntarget"),
            "boundary" => std::fs::rename(vault.0.join("04_Resources/Regression-Target.md"), vault.0.join("05_Archive/Regression-Target.md")).unwrap(),
            "duplicate" => vault.write("03_Areas/Regression-Target.md", "target"),
            "remove-out-of-scope" => std::fs::remove_file(vault.0.join("Templates/Regression-Target.md")).unwrap(),
            _ => unreachable!(),
        }
        let report = gaiafield::index(&vault.0, &conn, false).unwrap();
        assert_eq!(report.updated, 0, "unchanged sources need only their edges refreshed: {change}");
        let incremental = edges(&conn);
        if change == "duplicate" {
            let targets: Vec<_> = incremental.iter()
                .filter(|edge| edge.0 == source)
                .map(|edge| edge.1.as_deref())
                .collect();
            assert_eq!(targets, [
                Some("03_Areas/Regression-Target.md"),
                Some("03_Areas/Regression-Target.md"),
                Some("04_Resources/Regression-Target.md"),
                Some("04_Resources/Regression-Target.md"),
            ], "each repeated link must resolve to both duplicate targets");
        }
        gaiafield::index(&vault.0, &conn, true).unwrap();
        assert_eq!(incremental, edges(&conn), "incremental differs from full after {change}");
    }
}

fn set_mtime(path: &Path, millis: u64) {
    let time = std::time::UNIX_EPOCH + std::time::Duration::from_millis(millis);
    std::fs::File::options()
        .write(true)
        .open(path)
        .unwrap()
        .set_times(std::fs::FileTimes::new().set_modified(time))
        .unwrap();
}

fn same_second_edit(infer: bool) {
    let vault = Fixture::new();
    let source = "04_Resources/Regression-Source.md";
    let original = "---\ndescription: birds\n---\n[[Foo]] birds birds birds";
    let changed = "---\ndescription: notes\n---\n[[Bar]] notes notes notes";
    assert_eq!(original.len(), changed.len());
    vault.write(source, original);
    set_mtime(&vault.0.join(source), 1_700_000_000_100);
    let conn = gaiafield::open_db(&vault.0.join(".gaiafield/test.db")).unwrap();
    gaiafield::index(&vault.0, &conn, true).unwrap();
    let model = std::env::temp_dir().join("gaiafield-v2-test-model-cache");
    let before: Option<Vec<u8>> = if infer {
        gaiafield::infer(&vault.0, &conn, &model, true, false).unwrap();
        Some(conn.query_row("SELECT vector FROM embeddings WHERE path = ?1", [source], |r| r.get(0)).unwrap())
    } else {
        None
    };

    // Same integer second and byte count, with no sleep or wall-clock race.
    vault.write(source, changed);
    set_mtime(&vault.0.join(source), 1_700_000_000_200);
    let report = gaiafield::index(&vault.0, &conn, false).unwrap();
    assert_eq!(report.updated, 1);
    assert_eq!(conn.query_row("SELECT description FROM nodes WHERE path = ?1", [source], |r| r.get::<_, String>(0)).unwrap(), "notes");
    assert_eq!(conn.query_row("SELECT raw_target FROM edges WHERE source = ?1", [source], |r| r.get::<_, String>(0)).unwrap(), "Bar");
    if let Some(before) = before {
        let report = gaiafield::infer(&vault.0, &conn, &model, false, false).unwrap();
        assert_eq!(report.embedded, 1);
        let after: Vec<u8> = conn.query_row("SELECT vector FROM embeddings WHERE path = ?1", [source], |r| r.get(0)).unwrap();
        assert_ne!(before, after, "the changed content must produce a fresh embedding");
        assert_eq!(gaiafield::infer(&vault.0, &conn, &model, false, false).unwrap().embedded, 0);
    }
    assert_eq!(gaiafield::index(&vault.0, &conn, false).unwrap().updated, 0);

    // A database written by an older version used seconds; it must refresh once.
    conn.execute("UPDATE nodes SET mtime = mtime / 1000000000", []).unwrap();
    let report = gaiafield::index(&vault.0, &conn, false).unwrap();
    assert_eq!(report.updated, report.total_nodes);
    if infer {
        conn.execute("UPDATE embeddings SET mtime = mtime / 1000000000", []).unwrap();
        assert_eq!(gaiafield::infer(&vault.0, &conn, &model, false, false).unwrap().embedded, report.total_nodes);
    }
}

#[test]
fn incremental_same_second_equal_size_edit_refreshes_metadata_and_links() {
    same_second_edit(false);
}

#[test]
fn incremental_same_second_equal_size_edit_refreshes_embedding() {
    same_second_edit(true);
}
