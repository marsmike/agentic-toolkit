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
        vault.write("04_Resources/Regression-Source.md", "[[Regression-Target]] [[Regression-Target]]");
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
        gaiafield::index(&vault.0, &conn, true).unwrap();
        assert_eq!(incremental, edges(&conn), "incremental differs from full after {change}");
    }
}
