"""Eval: `fetch_source.py`, a stub capture's own source through the Tavily CLI (stubbed `extract`,
no network).

1. source   — the URL comes from the capture's `source` and nowhere else; the page comes back
              as Markdown with its title, `via: tavily`
2. none     — a capture without an http(s) source is refused before any call
3. domains  — with TOOLKIT_PIPELINE_FETCH_DOMAINS set, only those domains and their subdomains
              (a lookalike host is not a subdomain); unset, any http(s) host
4. contain  — a capture path outside the vault is refused
5. failure  — a tvly error or an empty extraction is ok: false with the reason, never an exception
6. shape    — a non-dict `tvly extract --json` reply is ok: false, never an AttributeError past it
7. ledger   — a keyed call records one row to this plugin's own extract ledger (radar's row shape);
              a keyless call is free and records nothing
8. budget   — a keyed call that would pass tavily_weekly_budget_usd is refused, ok: false, never
              raised; a non-numeric budget value falls back to the default
9. retry    — a keyed basic extraction with no content retries once at advanced depth (recorded at
              2 credits); a keyless one does not retry
"""
from __future__ import annotations

import json
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
    calls: list[tuple[str, str]] = []
    mode = {"answer": "page"}

    def stub(url: str, depth: str = "basic") -> dict:
        calls.append((url, depth))
        if mode["answer"] == "error":
            raise RuntimeError("HTTP 432: plan limit")
        if mode["answer"] == "empty":
            return {"results": [], "failed_results": [{"url": url, "error": "blocked by robots"}]}
        if mode["answer"] == "empty-then-content":
            if depth == "basic":
                return {"results": [], "failed_results": [{"url": url, "error": "js-rendered"}]}
            return {"results": [{"url": url, "title": "Advanced Article", "raw_content": "# Advanced\n\nRendered."}]}
        return {"results": [{"url": url, "title": "The Article", "raw_content": "# The Article\n\nBody text."}]}

    real_extract = fetch_source.extract
    saved_domains = os.environ.pop("TOOLKIT_PIPELINE_FETCH_DOMAINS", None)
    saved_key = os.environ.pop("TAVILY_API_KEY", None)
    saved_budget = os.environ.pop("TOOLKIT_OBSIDIAN_TAVILY_WEEKLY_BUDGET_USD", None)
    fetch_source.extract = stub
    try:
        with tempfile.TemporaryDirectory() as tmp:
            v = Path(tmp) / "vault"
            (v / "01_Capture").mkdir(parents=True)
            ledger = v / fetch_source.LEDGER

            def capture(name: str, source: str | None) -> str:
                fm = f"source: {source}\n" if source else "origin: research-session\n"
                (v / "01_Capture" / name).write_text(f"---\n{fm}content: stub\n---\n# Stub\n\nSee https://evil.example/x\n",
                                                     encoding="utf-8")
                return f"01_Capture/{name}"

            # 1. source
            r = fetch_source.fetch(v, capture("a.md", "https://blog.example.org/post"))
            if not r["ok"] or calls != [("https://blog.example.org/post", "basic")] or r["title"] != "The Article" \
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
            mode["answer"] = "page"

            # 6. shape — a non-dict tvly reply must fail cleanly inside extract(), never crash
            # fetch() with an AttributeError on data.get(...)
            class _FakeProc:
                def __init__(self, stdout: str) -> None:
                    self.stdout, self.returncode, self.stderr = stdout, 0, ""

            real_run, real_binary = fetch_source.subprocess.run, fetch_source.tvly_binary
            fetch_source.extract = real_extract  # test the real extract(), not the stub, for this phase
            fetch_source.tvly_binary = lambda: "/bin/true"
            fetch_source.subprocess.run = lambda *a, **k: _FakeProc("[1, 2, 3]")
            try:
                r = fetch_source.fetch(v, capture("shape.md", "https://blog.example.org/shape"))
                if r["ok"] or not r.get("reason"):
                    problems.append(f"phase 6: a non-dict tvly reply must be ok: false with a reason, got {r}")
            except Exception as e:  # noqa: BLE001 — the eval itself must not crash either
                problems.append(f"phase 6: a non-dict tvly reply must never raise past fetch(), got {type(e).__name__}: {e}")
            finally:
                fetch_source.subprocess.run, fetch_source.tvly_binary = real_run, real_binary
                fetch_source.extract = stub

            # 7. ledger — keyed records one row in this plugin's own ledger; keyless records none
            calls.clear()
            before = ledger.read_text(encoding="utf-8").splitlines() if ledger.is_file() else []
            r = fetch_source.fetch(v, capture("g.md", "https://blog.example.org/g"))
            after = ledger.read_text(encoding="utf-8").splitlines() if ledger.is_file() else []
            if not r["ok"] or after != before:
                problems.append(f"phase 7: a keyless call must record nothing, got {r} ledger +{len(after) - len(before)}")
            os.environ["TAVILY_API_KEY"] = "stub-key-not-a-secret"
            before = after
            r = fetch_source.fetch(v, capture("h.md", "https://blog.example.org/h"))
            after = ledger.read_text(encoding="utf-8").splitlines() if ledger.is_file() else []
            row = json.loads(after[-1]) if len(after) == len(before) + 1 else None
            if not r["ok"] or row is None or row.get("kind") != "extract" or row.get("query") != "https://blog.example.org/h" \
                    or row.get("credits") != 0.2 or abs(row.get("usd", 0) - 0.2 * fetch_source.USD_PER_CREDIT) > 1e-9 \
                    or row.get("balance") is not None:
                problems.append(f"phase 7: a keyed call must record one row, got {r} row={row}")

            # 8. budget — a keyed call over budget is refused without raising; a non-numeric
            # profile value falls back to the default
            os.environ["TOOLKIT_OBSIDIAN_TAVILY_WEEKLY_BUDGET_USD"] = "0.0001"
            before = ledger.read_text(encoding="utf-8").splitlines()
            r = fetch_source.fetch(v, capture("i.md", "https://blog.example.org/i"))
            after = ledger.read_text(encoding="utf-8").splitlines()
            if r["ok"] or "budget" not in r.get("reason", "").lower() or after != before:
                problems.append(f"phase 8: a call over budget must be refused and record nothing, got {r}")
            os.environ["TOOLKIT_OBSIDIAN_TAVILY_WEEKLY_BUDGET_USD"] = "not-a-number"
            if fetch_source._weekly_budget(v) != fetch_source.DEFAULT_WEEKLY_BUDGET_USD:
                problems.append("phase 8: a non-numeric weekly budget must fall back to the default")
            os.environ.pop("TOOLKIT_OBSIDIAN_TAVILY_WEEKLY_BUDGET_USD")

            # 9. retry — a keyed empty basic extraction retries once at advanced depth
            mode["answer"] = "empty-then-content"
            calls.clear()
            r = fetch_source.fetch(v, capture("j.md", "https://blog.example.org/j"))
            if not r["ok"] or r["title"] != "Advanced Article" or [d for _, d in calls] != ["basic", "advanced"]:
                problems.append(f"phase 9: a keyed empty basic extraction must retry once at advanced depth, got {r} {calls}")
            os.environ.pop("TAVILY_API_KEY")  # back to keyless
            calls.clear()
            r = fetch_source.fetch(v, capture("k.md", "https://blog.example.org/k"))
            if r["ok"] or [d for _, d in calls] != ["basic"]:
                problems.append(f"phase 9: a keyless empty basic extraction must not retry, got {r} {calls}")
            mode["answer"] = "page"
    finally:
        fetch_source.extract = real_extract
        os.environ.pop("TOOLKIT_PIPELINE_FETCH_DOMAINS", None)
        os.environ.pop("TAVILY_API_KEY", None)
        os.environ.pop("TOOLKIT_OBSIDIAN_TAVILY_WEEKLY_BUDGET_USD", None)
        if saved_domains is not None:
            os.environ["TOOLKIT_PIPELINE_FETCH_DOMAINS"] = saved_domains
        if saved_key is not None:
            os.environ["TAVILY_API_KEY"] = saved_key
        if saved_budget is not None:
            os.environ["TOOLKIT_OBSIDIAN_TAVILY_WEEKLY_BUDGET_USD"] = saved_budget

    return {"eval": NAME, "pass": not problems, "detail": "; ".join(problems) or "all phases ok"}
