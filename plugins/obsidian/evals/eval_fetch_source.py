"""Eval: `fetch_source.py`, a stub capture's own source through the Tavily CLI (stubbed `extract`,
no network).

1. source   — the URL comes from the capture's `source` and nowhere else; the page comes back
              as Markdown with its title, `via: tavily`
2. none     — a capture without an http(s) source is refused before any call
3. domains  — with TOOLKIT_PIPELINE_FETCH_DOMAINS set, only those domains and their subdomains
              (a lookalike host is not a subdomain); unset, any http(s) host
4. contain  — a capture path outside the vault is refused
5. failure  — a tvly error or an empty extraction is ok: false with the reason, never an exception
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

NAME = "fetch_source"


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import fetch_source

    problems: list[str] = []
    calls: list[str] = []
    mode = {"answer": "page"}

    def stub(url: str) -> dict:
        calls.append(url)
        if mode["answer"] == "error":
            raise RuntimeError("HTTP 432: plan limit")
        if mode["answer"] == "empty":
            return {"results": [], "failed_results": [{"url": url, "error": "blocked by robots"}]}
        return {"results": [{"url": url, "title": "The Article", "raw_content": "# The Article\n\nBody text."}]}

    real_extract, saved = fetch_source.extract, os.environ.pop("TOOLKIT_PIPELINE_FETCH_DOMAINS", None)
    fetch_source.extract = stub
    try:
        with tempfile.TemporaryDirectory() as tmp:
            v = Path(tmp) / "vault"
            (v / "01_Capture").mkdir(parents=True)

            def capture(name: str, source: str | None) -> str:
                fm = f"source: {source}\n" if source else "origin: research-session\n"
                (v / "01_Capture" / name).write_text(f"---\n{fm}content: stub\n---\n# Stub\n\nSee https://evil.example/x\n",
                                                     encoding="utf-8")
                return f"01_Capture/{name}"

            # 1. source
            r = fetch_source.fetch(v, capture("a.md", "https://blog.example.org/post"))
            if not r["ok"] or calls != ["https://blog.example.org/post"] or r["title"] != "The Article" \
                    or "Body text." not in r["content"] or r["via"] != "tavily":
                problems.append(f"phase 1: expected the recorded source fetched once, got {r} {calls}")

            # 2. none
            calls.clear()
            for name, src in (("b.md", None), ("c.md", "ftp://files.example.org/x"), ("d.md", "not a url")):
                r = fetch_source.fetch(v, capture(name, src))
                if r["ok"] or calls:
                    problems.append(f"phase 2: {src!r} must be refused before any call, got {r} {calls}")

            # 3. domains
            os.environ["TOOLKIT_PIPELINE_FETCH_DOMAINS"] = "github.com raw.githubusercontent.com"
            for src, ok in (("https://github.com/acme/widget", True), ("https://gist.github.com/x/1", True),
                            ("https://raw.githubusercontent.com/a/b/main/README.md", True),
                            ("https://blog.example.org/post", False), ("https://evilgithub.com/x", False)):
                calls.clear()
                r = fetch_source.fetch(v, capture("e.md", src))
                if r["ok"] != ok or bool(calls) != ok:
                    problems.append(f"phase 3: {src} allowed={ok} expected, got {r} {calls}")
            os.environ.pop("TOOLKIT_PIPELINE_FETCH_DOMAINS")

            # 4. contain
            outside = Path(tmp) / "outside.md"
            outside.write_text("---\nsource: https://blog.example.org/post\n---\n", encoding="utf-8")
            try:
                fetch_source.fetch(v, "01_Capture/../../outside.md")
                problems.append("phase 4: a capture outside the vault must be refused")
            except SystemExit:
                pass

            # 5. failure
            for answer in ("error", "empty"):
                mode["answer"] = answer
                r = fetch_source.fetch(v, capture("f.md", "https://blog.example.org/post"))
                if r["ok"] or not r.get("reason"):
                    problems.append(f"phase 5: a tvly {answer} must be ok: false with a reason, got {r}")
    finally:
        fetch_source.extract = real_extract
        os.environ.pop("TOOLKIT_PIPELINE_FETCH_DOMAINS", None)
        if saved is not None:
            os.environ["TOOLKIT_PIPELINE_FETCH_DOMAINS"] = saved

    return {"eval": NAME, "pass": not problems, "detail": "; ".join(problems) or "all phases ok"}
