"""Signal Radar: `signal.json` -> one self-contained HTML page and a short Obsidian note.

Every value already left `signal_radar.py`'s `build()`; this module only lays it out, so it makes
no network call and touches nothing outside its own return value. `render_html` embeds the data
verbatim as `<script type="application/json" id="data">` (escaping `</` so a fetched title can't
close the tag early) and leaves every render to the page's own inline JS — a polar radar scope,
a sortable signals table, the vault pulse and the knowledge-graph view. `render_md` is the short
Obsidian companion note that links to the HTML file.

Nothing here reaches the network or the filesystem except reading its own template next to it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TEMPLATE = Path(__file__).resolve().parent / "signal_template.html"
MD_TOP_SIGNALS = 15
MD_TOP_EARLY = 8
MD_TOP_BLIND = 8
MD_TOP_TAGS = 8

STAGE_LABEL = {"new": "New", "rising": "Rising", "hot": "Hot", "steady": "Steady", "fading": "Fading"}
FAMILY_LABEL = {"hn": "Hacker News", "hf": "Hugging Face", "github": "GitHub", "reddit": "Reddit",
                "rss": "Blogs & news", "arxiv": "arXiv", "feed": "Reader feeds", "kagi": "Kagi news",
                "graph": "Knowledge graph", "vault": "Your vault"}


def render_html(data: dict[str, Any]) -> str:
    """The whole self-contained page: the template with `signal.json` dropped into it."""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)


def _wikilink(path: str, title: str) -> str:
    """Same-vault link for the companion note, which lives inside the vault itself."""
    stem = path[:-3] if path.endswith(".md") else path
    title = title.replace("|", "–").replace("[", "(").replace("]", ")")
    return f"[[{stem}|{title}]]" if stem != title else f"[[{stem}]]"


def _fam_badges(families: list[str]) -> str:
    return ", ".join(FAMILY_LABEL.get(f, f) for f in families)


def _top_link(blip: dict[str, Any]) -> str:
    items = blip.get("items") or []
    if not items:
        return ""
    it = items[0]
    title = (it.get("title") or blip["name"]).replace("\n", " ").replace("[", "(").replace("]", ")").strip()
    url = it.get("url") or ""
    return f"[{title}]({url})" if url else title


def _blip_line(b: dict[str, Any]) -> str:
    stage = STAGE_LABEL.get(b.get("stage"), b.get("stage", ""))
    fams = _fam_badges(b.get("families") or [])
    link = _top_link(b)
    tail = f" — {link}" if link else ""
    return f"- **{b['name']}** — {stage}, strength {b.get('strength', 0)}, {fams}{tail}{_graph_tail(b)}"


def _graph_tail(b: dict[str, Any]) -> str:
    """Where the thing sits in the owner's graph: its newest note and the hubs it connects to."""
    notes = b.get("vault_notes") or []
    if not notes:
        return ""
    g = b.get("graph") or {}
    hubs = ", ".join(_wikilink(h["path"], h["title"]) for h in (g.get("hubs") or [])[:2] if h.get("path"))
    head = f"\n  - in your graph: {_wikilink(notes[0]['path'], notes[0]['title'])} ({b.get('in_vault', len(notes))} notes"
    head += f", {g.get('neighborhood', 0)} linked)" + (f" → {hubs}" if hubs else "")
    return head


def render_md(data: dict[str, Any]) -> str:
    """Short Obsidian note: early warnings, top signals, blind spots, rising vault tags, and a
    link to the full page. Notes and hubs are wikilinks (same vault); outside items are plain
    markdown links (someone else's URL)."""
    generated = str(data.get("generated") or "")
    created = generated[:10] or "1970-01-01"
    blips = data.get("blips") or []
    early_keys = data.get("early") or []
    blind_keys = data.get("blind_spots") or []
    by_key = {b["key"]: b for b in blips}
    top = blips[:MD_TOP_SIGNALS]
    early = [by_key[k] for k in early_keys if k in by_key][:MD_TOP_EARLY]
    blind = [by_key[k] for k in blind_keys if k in by_key][:MD_TOP_BLIND]
    vault = data.get("vault") or {}
    rising_tags = [t for t in (vault.get("tags") or []) if t.get("rising") or t.get("new")][:MD_TOP_TAGS]
    graph = data.get("graph") or {}
    hubs = (graph.get("growing_hubs") or [])[:MD_TOP_TAGS]

    lines: list[str] = [
        "---",
        f"description: \"Signal Radar {created} — {len(blips)} signals, {len(early)} early warnings, "
        f"{len(blind)} not yet in the vault.\"",
        "status: active",
        f"created: {created}",
        "tags:",
        "  - domain/toolkit-meta",
        "---",
        "",
        "# Signal Radar",
        "",
        f"Generated {generated}. Full page: [[Signal-Radar.html|Signal Radar (HTML)]].",
        "",
    ]

    lines += ["## Early warning", ""]
    if early:
        for b in early:
            lines.append(_blip_line(b))
    else:
        lines.append("Nothing crossed the early-warning bar this run.")
    lines.append("")

    lines += [f"## Top {len(top)} signals", ""]
    if top:
        for b in top:
            lines.append(_blip_line(b))
    else:
        lines.append("No signals scored this run.")
    lines.append("")

    lines += ["## Not in your vault yet", "", "Strong outside, no anchor in the graph yet:", ""]
    if blind:
        for b in blind:
            link = _top_link(b)
            tail = f" — {link}" if link else ""
            lines.append(f"- **{b['name']}** — strength {b.get('strength', 0)}, {_fam_badges(b.get('families') or [])}{tail}")
    else:
        lines.append("None — everything strong enough already has a note.")
    lines.append("")

    lines += ["## Rising in your vault", ""]
    if rising_tags:
        for t in rising_tags:
            examples = t.get("examples") or []
            ex = ", ".join(_wikilink(e["path"], e["title"]) for e in examples[:2] if e.get("path"))
            mark = "new" if t.get("new") else "rising"
            tail = f" ({ex})" if ex else ""
            lines.append(f"- **{t['tag']}** — {mark}, {t.get('this_week', 0)} this week vs {t.get('baseline', 0)} baseline{tail}")
    else:
        lines.append("Nothing rising in your own notes this week.")
    lines.append("")

    if hubs:
        lines += ["## Your graph is growing around", ""]
        for h in hubs:
            examples = h.get("examples") or []
            ex = ", ".join(_wikilink(e["path"], e["title"]) for e in examples[:2] if e.get("path"))
            tail = f" — {ex}" if ex else ""
            mark = " (new hub)" if h.get("new") else ""
            lines.append(f"- {_wikilink(h['path'], h['title'])}{mark} — {h.get('this_week', 0)} this week vs "
                         f"{h.get('baseline', 0)} baseline{tail}")
        lines.append("")

    lines.append("See the full page for the radar scope, sortable table and interest trend.")
    return "\n".join(lines) + "\n"
