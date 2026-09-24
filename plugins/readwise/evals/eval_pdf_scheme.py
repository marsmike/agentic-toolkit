"""Eval: `pdf_extract._download` fetches only http(s), before and after redirects
(review-01 SEC-4). A `file://` source_url must not turn a local file into a capture the
pipeline commits and pushes, and neither may a web URL that redirects off the web.

Offline: the local-file case reads a temp file (never the vault), and the redirect cases stub
`urllib.request.urlopen`.
"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

NAME = "pdf_scheme"
PDF_BYTES = b"%PDF-1.4 a private local document\n"


class _Resp(io.BytesIO):
    def __init__(self, data: bytes, final_url: str):
        super().__init__(data)
        self._final_url = final_url
        self.headers = {"Content-Type": "application/pdf"}

    def geturl(self) -> str:
        return self._final_url


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import pdf_extract

    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        local = Path(tmp) / "statement.pdf"
        local.write_bytes(PDF_BYTES)
        if pdf_extract._download(local.as_uri()) is not None:
            problems.append("a file:// source_url was read")

    real = pdf_extract.urllib.request.urlopen
    try:
        pdf_extract.urllib.request.urlopen = lambda req, timeout=None: _Resp(PDF_BYTES, "ftp://example.invalid/x.pdf")
        if pdf_extract._download("https://example.invalid/x.pdf") is not None:
            problems.append("an https URL redirected to ftp:// was read")
        pdf_extract.urllib.request.urlopen = lambda req, timeout=None: _Resp(PDF_BYTES, "https://cdn.example.invalid/x.pdf")
        if pdf_extract._download("https://example.invalid/x.pdf") != PDF_BYTES:
            problems.append("an https PDF (redirected within https) was refused")
    finally:
        pdf_extract.urllib.request.urlopen = real

    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else "file:// refused, off-web redirect refused, https accepted"}
