from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from lib.fetcher import Fetcher, AuthSpec


def test_file_scheme_returns_bytes(tmp_path):
    src = tmp_path / "x.bin"
    src.write_bytes(b"hello")
    f = Fetcher()
    assert f.fetch(f"file://{src}") == b"hello"


def test_relative_path_resolves_against_base_url_https(tmp_path):
    f = Fetcher(base_url="https://example.test/foo/")
    with patch("lib.fetcher.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = b"abc"
        f.fetch("bar/baz.bin")
        called_url = mock_open.call_args[0][0].full_url
    assert called_url == "https://example.test/foo/bar/baz.bin"


def test_query_token_auth_appends_token(tmp_path):
    auth = AuthSpec(type="query_token", env="TEST_TOKEN")
    f = Fetcher(base_url="https://example.test/", auth=auth)
    with patch("lib.fetcher.urlopen") as mock_open, patch.dict("os.environ", {"TEST_TOKEN": "tok123"}):
        mock_open.return_value.__enter__.return_value.read.return_value = b"abc"
        f.fetch("x.bin")
        called_url = mock_open.call_args[0][0].full_url
    assert called_url == "https://example.test/x.bin?tok123"


def test_missing_auth_env_raises_clear_error():
    auth = AuthSpec(type="query_token", env="DEFINITELY_NOT_SET_ENV_VAR_XYZ")
    f = Fetcher(base_url="https://example.test/", auth=auth)
    with pytest.raises(RuntimeError, match="DEFINITELY_NOT_SET_ENV_VAR_XYZ"):
        f.fetch("x.bin")
