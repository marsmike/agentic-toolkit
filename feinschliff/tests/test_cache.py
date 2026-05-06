from pathlib import Path

from lib.cache import cache_dir, cache_path


def test_cache_dir_default_uses_xdg_cache_home(tmp_cache_root):
    d = cache_dir(brand="bsh", version="1.6.2")
    assert d == tmp_cache_root / "feinschliff" / "bsh" / "1.6.2"


def test_cache_dir_creates_directory(tmp_cache_root):
    d = cache_dir(brand="bsh", version="1.6.2")
    assert d.is_dir()


def test_cache_path_is_content_addressed(tmp_cache_root):
    p = cache_path(brand="bsh", version="1.6.2", kind="icons", sha256="a" * 64, ext="svg")
    assert p == tmp_cache_root / "feinschliff" / "bsh" / "1.6.2" / "icons" / ("a" * 64 + ".svg")


def test_cache_path_creates_parent_directory(tmp_cache_root):
    p = cache_path(brand="bsh", version="1.6.2", kind="templates/pptx", sha256="b" * 64, ext="pptx")
    assert p.parent.is_dir()
