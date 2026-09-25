"""Eval: a tweet capture is enriched at ingest (no network: resolver and fetcher are fakes).

1. html     — tweet HTML keeps a media image and a video poster, drops the avatar, marks the video,
              names a quoted post
2. expand   — every t.co link is replaced by its target in the summary and the text
3. links    — `links` holds the external targets only (not x.com, pbs.twimg.com or a t.me promo), in order
4. linked   — a GitHub repo is excerpted through its API and README, an arXiv paper through its
              API, any other page by its title and description
5. partial  — an unresolvable t.co link and a page that doesn't load make the status `partial`,
              and the short link stays in the text
6. capture  — write_capture on a tweet writes `links`, `enrichment` and a `## Linked` section
8. safety   — loopback, private, link-local (cloud metadata) and non-http destinations are refused
              before any request; a malformed URL in tweet text is ignored, not raised; a media
              write that fails (no directory) loses the local copy, never the capture
7. media    — the media image is stored under 04_Resources/Attachments/Tweets/, embedded by vault
              path with its original link beside it, and listed in `media:`; the video poster
              that can't be fetched stays a link and makes the capture `partial`
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

TARGETS = {"https://t.co/repo": "https://github.com/acme/widget",
           "https://t.co/paper": "https://arxiv.org/abs/2601.00001",
           "https://t.co/blog": "https://blog.example.org/post",
           "https://t.co/self": "https://x.com/acme/status/9"}
PAGES = {
    "https://api.github.com/repos/acme/widget": ("application/json", json.dumps(
        {"description": "A widget for agents.", "language": "Rust", "stargazers_count": 42})),
    "https://raw.githubusercontent.com/acme/widget/HEAD/README.md": ("text/plain", "# Widget\n\nIt widgets."),
    "https://export.arxiv.org/api/query?id_list=2601.00001": ("application/atom+xml",
        "<feed><entry><title>Widgets\n Considered</title><summary>We show widgets work.</summary></entry></feed>"),
    "https://blog.example.org/post": ("text/html", '<html><head><title>Post</title>'
        '<meta property="og:description" content="Why widgets."></head><body><article><p>Body.</p></article></body></html>'),
}
HTML = ('<p>Look <img src="https://pbs.twimg.com/profile_images/1/me.jpg"> at '
        '<a href="https://t.co/repo">github.com/acme/widget</a>, <a href="https://t.co/paper">https://t.co/paper</a> '
        'and <a href="https://t.co/blog">blog</a>. Thread: https://t.co/self Join https://t.me/promo</p>'
        '<img src="https://pbs.twimg.com/media/shot.jpg"><video poster="https://pbs.twimg.com/ext_tw_video_thumb/1/pu/img/p.jpg"></video>'
        '<a href="https://x.com/other/status/7"> </a>')


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import build_captures as bc
    import tweet_enrich as te
    from vault_utils import read_frontmatter

    problems: list[str] = []
    md = bc._html_to_md_basic(HTML, keep_media=True)
    if "profile_images" in md:
        problems.append("html: avatar kept")
    for want in ("![](https://pbs.twimg.com/media/shot.jpg)", "![](https://pbs.twimg.com/ext_tw_video_thumb/1/pu/img/p.jpg)",
                 "*(video: watch it at the source)*", "Quoted post: <https://x.com/other/status/7>"):
        if want not in md:
            problems.append(f"html: missing {want!r}")

    r = te.enrich("See https://t.co/repo", md, bc._html_to_md_basic, TARGETS.get, PAGES.get)
    if "t.co" in r["text"] + r["summary"] or "github.com/acme/widget" not in r["summary"]:
        problems.append("expand: a t.co link survived")
    want_links = ["https://github.com/acme/widget", "https://arxiv.org/abs/2601.00001", "https://blog.example.org/post"]
    if r["links"] != want_links:
        problems.append(f"links: {r['links']}")
    titles = [e["title"] for e in r["linked"]]
    if titles != ["GitHub: acme/widget", "arXiv 2601.00001: Widgets Considered", "Post"]:
        problems.append(f"linked: titles {titles}")
    elif "Rust, 42 stars" not in r["linked"][0]["text"] or "Why widgets." not in r["linked"][2]["text"]:
        problems.append("linked: excerpt text")
    if r["status"] != "full":
        problems.append(f"status {r['status']}, expected full")

    p = te.enrich("", "https://t.co/gone and https://t.co/blog", bc._html_to_md_basic, TARGETS.get, lambda u: None)
    if p["status"] != "partial" or "https://t.co/gone" not in p["text"]:
        problems.append(f"partial: status {p['status']}")

    for bad in ("http://127.0.0.1/x", "http://169.254.169.254/latest/meta-data", "http://10.1.2.3/",
                "http://localhost:8080/", "file:///etc/passwd", "https://[bad", "https://example.com:99999/x"):
        if te.public(bad) or te.get(bad) is not None or te.get_bytes(bad) is not None or te.resolve(bad) is not None:
            problems.append(f"safety: {bad} was not refused")
    import http.server
    import threading
    srv = http.server.HTTPServer(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    conn = te._CheckedHTTP("127.0.0.1", srv.server_address[1], timeout=2)
    try:
        conn.connect()
        problems.append("safety: a connection that landed on loopback was not refused (rebinding)")
    except OSError:
        pass
    finally:
        srv.server_close()
    if te.external_links("see https://[not-a-host and https://github.com/acme/widget") != ["https://github.com/acme/widget"]:
        problems.append("safety: a malformed URL was not ignored")
    blocker = Path(__import__("tempfile").mkdtemp()) / "not-a-dir"
    blocker.write_text("x")
    kept, got, lost = te.save_media("![](https://pbs.twimg.com/media/shot.jpg)", blocker, "d", lambda u: b"\xff\xd8\xff")
    if got or lost != 1 or "https://pbs.twimg.com/media/shot.jpg" not in kept:
        problems.append(f"safety: a failed media write should keep the link, got {got}, {lost}")

    saved, sandbox = os.environ.get("TOOLKIT_READWISE_ENRICH"), make_sandbox(vault)
    orig = (te.resolve, te.get, te.get_bytes)
    try:
        os.environ["TOOLKIT_READWISE_ENRICH"] = "1"
        te.resolve, te.get = TARGETS.get, PAGES.get
        te.get_bytes = lambda u: b"\xff\xd8\xffjpeg" if "/media/shot" in u else None
        path, _ = bc.write_capture(sandbox, {"id": "tw-enrich", "category": "tweet", "title": "Look",
                                             "author": "acme", "source_url": "https://x.com/acme/status/1",
                                             "saved_at": "2026-09-25", "html_content": HTML})
        fm, body = read_frontmatter(path)
        if fm.get("links") != want_links or "## Linked" not in body:
            problems.append(f"capture: links={fm.get('links')}")
        img = "04_Resources/Attachments/Tweets/tweet-twenrich-1.jpg"
        if fm.get("media") != [img] or not (sandbox / img).is_file() or f"![[{img}]] ([original](" not in body:
            problems.append(f"media: {fm.get('media')}")
        if fm.get("enrichment") != "partial" or "![](https://pbs.twimg.com/ext_tw_video_thumb/1/pu/img/p.jpg)" not in body:
            problems.append(f"media: unfetchable poster should stay a link, enrichment={fm.get('enrichment')}")
    finally:
        te.resolve, te.get, te.get_bytes = orig
        if saved is None:
            os.environ.pop("TOOLKIT_READWISE_ENRICH", None)
        else:
            os.environ["TOOLKIT_READWISE_ENRICH"] = saved
        teardown_sandbox(sandbox)
    return {"eval": "tweet_enrich", "pass": not problems, "detail": "; ".join(problems) or "enriched as expected"}
