//! A `.md` link or linked folder that resolves outside the vault is not vault content
//! (Copilot review of #28): the engine must not read or return it. A link inside the vault counts.
#![cfg(unix)]

use std::os::unix::fs::symlink;
use std::path::PathBuf;

fn scratch(tag: &str) -> PathBuf {
    let root = std::env::temp_dir().join(format!("gaiafield-containment-{tag}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&root);
    std::fs::create_dir_all(root.join("outside/dir")).unwrap();
    std::fs::write(root.join("outside/private.md"), "---\nstatus: active\n---\n\nprivate words\n").unwrap();
    std::fs::write(root.join("outside/dir/Folder-Note.md"), "private folder note\n").unwrap();
    for folder in ["02_Projects", "03_Areas", "04_Resources"] {
        std::fs::create_dir_all(root.join("vault").join(folder)).unwrap();
    }
    std::fs::write(root.join("vault/03_Areas/Real-Note.md"), "---\nstatus: active\n---\n\nreal\n").unwrap();
    std::fs::write(root.join("vault/Persona.md"), "---\nstatus: active\n---\n\npersona\n").unwrap();
    symlink(root.join("outside/private.md"), root.join("vault/03_Areas/Planted.md")).unwrap();
    symlink(root.join("outside/private.md"), root.join("vault/Root-Planted.md")).unwrap();
    symlink(root.join("outside/dir"), root.join("vault/04_Resources/Linked-Dir")).unwrap();
    symlink(root.join("vault/03_Areas"), root.join("vault/03_Areas/Loop")).unwrap();
    symlink(root.join("vault/03_Areas/Real-Note.md"), root.join("vault/04_Resources/Alias.md")).unwrap();
    root
}

#[test]
fn links_out_of_the_vault_are_not_notes() {
    let root = scratch("nodes");
    let vault = root.join("vault");
    let names = gaiafield::discover_nodes(&vault).iter().map(|f| f.rel.rsplit('/').next().unwrap().to_string()).collect::<Vec<_>>();
    for kept in ["Real-Note.md", "Persona.md", "Alias.md"] {
        assert!(names.iter().any(|n| n == kept), "{kept} missing: {names:?}");
    }
    for gone in ["Planted.md", "Root-Planted.md", "Folder-Note.md"] {
        assert!(!names.iter().any(|n| n == gone), "{gone} leaked in: {names:?}");
    }
    let _ = std::fs::remove_dir_all(&root);
}

#[test]
fn the_full_walk_skips_them_too() {
    let root = scratch("all");
    let vault = root.join("vault");
    let names = gaiafield::discover_all_files(&vault).iter().map(|f| f.rel.rsplit('/').next().unwrap().to_string()).collect::<Vec<_>>();
    assert!(!names.iter().any(|n| n == "Planted.md" || n == "Folder-Note.md"), "{names:?}");
    assert!(names.iter().any(|n| n == "Real-Note.md"), "{names:?}");
    let _ = std::fs::remove_dir_all(&root);
}
