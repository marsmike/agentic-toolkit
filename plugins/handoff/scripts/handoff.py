#!/usr/bin/env python3
"""handoff — portable, tool-agnostic session handoff.

Deterministic mechanics for the `handoff` / `handoff-resume` skills. The model writes
the narrative (goal / status / tried / decisions / next step); this script handles
everything that must be exact: repo resolution, git state, chain sequencing, file
layout, profile reads, and the vault index. Plain markdown so Claude, Codex, or Gemini
can all resume.

Two independent "root" concepts, never conflated:
- `project_repo_root()` — the repo being worked on, where `_handoff/` lives (git
  top-level, honoring `$CLAUDE_PROJECT_DIR`). Almost never the agentic-toolkit repo.
- `resolve_vault()` — `$TOOLKIT_VAULT`, else the bundled `./vault` relative to
  *this plugin's own* repo (contract/PROFILE.md). Optional: handoffs work fully
  in-repo with no vault at all; vault-dependent extras (profile, index, DLQ) degrade
  silently to their shipped defaults / a skip when nothing is resolvable.

Subcommands:
  save      Assemble narrative + git state into _handoff/HANDOFF-<stream>-NN.md
  resume    Print the latest handoff (+ newer autosnapshot) for a fresh session
  list      List handoffs in the current repo
  snapshot  Cheap git-state dump for the PreCompact hook (no model, never fails)

stdlib only, Python 3.8+.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HANDOFF_DIRNAME = "_handoff"
LATEST = "HANDOFF.md"
SNAPSHOT = ".autosnapshot.md"
DRAFT = ".draft.md"

MARKETPLACE_MARKER = Path(".claude-plugin") / "marketplace.json"
PROFILE_PLUGIN_NAME = "handoff"
DEFAULT_INDEX_PATH = "00_Memory/handoffs/index.md"
DEFAULT_AUTOSNAPSHOT = True
DEFAULT_VISIBILITY = "commit"
MAX_SNAPSHOT_BYTES = 200_000


# ---------------------------------------------------------------- git helpers
def _git(args, cwd):
    try:
        out = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=8
        )
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def project_repo_root(start=None):
    """The user's project repo root — where `_handoff/` lives. Honors
    `$CLAUDE_PROJECT_DIR`, falls back to git's own top-level, falls back to cwd. This is
    deliberately independent of the vault resolution below: a handoff lives in the repo
    being worked on, which is almost never the agentic-toolkit repo itself."""
    start = start or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    top = _git(["rev-parse", "--show-toplevel"], start)
    return Path(top) if top else Path(start)


def has_project_repo(start=None) -> bool:
    """True if there's a real git repo or an explicit `$CLAUDE_PROJECT_DIR` — gates the
    PreCompact hook's silent no-op, per the memory-plugin hook standard ("silent no-op
    without a repo"). Interactive commands (save/resume/list) don't need this gate: a
    user running them from an arbitrary directory gets the cwd-fallback instead."""
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        return True
    start = start or os.getcwd()
    return bool(_git(["rev-parse", "--show-toplevel"], start))


def _slug(text, default="session"):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or default


def _yaml(text):
    """Double-quote a free-text scalar so colons/#/quotes stay valid YAML."""
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def git_state(root):
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], root) or "(no git)"
    status = _git(["status", "--short"], root)
    commits = _git(["log", "-3", "--pretty=format:%h %s"], root)
    changed = _git(["diff", "--name-only"], root)
    staged = _git(["diff", "--name-only", "--cached"], root)
    untracked = _git(["ls-files", "--others", "--exclude-standard"], root)
    files = sorted(set(filter(None, (changed + "\n" + staged + "\n" + untracked).splitlines())))
    # don't let the handoff report itself as touched work
    files = [f for f in files if not f.startswith(HANDOFF_DIRNAME + "/")]
    return branch, status, commits, files


def repo_state_block(root):
    branch, status, commits, files = git_state(root)
    lines = ["## Repo State (auto-captured)", ""]
    lines.append(f"- **Branch:** `{branch}`")
    if commits:
        lines.append("- **Recent commits:**")
        lines += [f"  - `{c}`" for c in commits.splitlines()]
    if files:
        lines.append(f"- **Files touched this session ({len(files)}):**")
        lines += [f"  - `{f}`" for f in files[:40]]
        if len(files) > 40:
            lines.append(f"  - …and {len(files) - 40} more")
    if status:
        lines += ["", "```", "# git status --short", status, "```"]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Vault resolution (contract/PROFILE.md: TOOLKIT_VAULT env var -> ./vault -> none)
# ---------------------------------------------------------------------------


def find_toolkit_repo_root(start: Path | None = None):
    """The agentic-toolkit repo root (marketplace.json marker) — used only to locate the
    bundled example `./vault` fallback. Independent of `project_repo_root()` above."""
    start = (start or Path.cwd()).resolve()
    for candidate in (start, *start.parents):
        if (candidate / MARKETPLACE_MARKER).is_file():
            return candidate
    return None


def resolve_vault():
    """`TOOLKIT_VAULT` env var wins if set and points at a real directory; otherwise
    `./vault` relative to the toolkit repo root. Returns `None` (never raises) when
    nothing is resolvable — every caller here treats that as "handoffs still work fully
    in-repo, vault-dependent extras silently skipped" per contract/PROFILE.md."""
    env_value = os.environ.get("TOOLKIT_VAULT")
    if env_value:
        p = Path(env_value).expanduser().resolve()
        return p if p.is_dir() else None
    repo_root = find_toolkit_repo_root(Path.cwd()) or find_toolkit_repo_root(Path(__file__).resolve().parent)
    if repo_root is None:
        return None
    candidate = repo_root / "vault"
    return candidate if candidate.is_dir() else None


# ---------------------------------------------------------------------------
# Profile (contract/PROFILE.md: env -> $VAULT/Config/toolkit/handoff.md -> default)
#
# Deliberately NOT a general frontmatter codec — see plugins/handoff/README.md's
# "Frontmatter decision" section. handoff.py only ever needs to pluck 3 known, flat,
# scalar fields (one bool, two strings) out of a note it never writes back to; a
# general read_frontmatter()/write_frontmatter() pair with unknown-field preservation
# and list/nested-mapping support (the pattern plugins/obsidian, plugins/readwise, and
# plugins/memory's vault_utils/memory_vault modules all ship, and that
# core/tests/test_contract.py's parity test guards) would be dead complexity here.
# ---------------------------------------------------------------------------

_PROFILE_SCALAR_KEYS = ("autosnapshot", "index_path", "default_visibility")

# Accepted boolean spellings (case-insensitive) for the `autosnapshot` field and its
# TOOLKIT_HANDOFF_AUTOSNAPSHOT env-var override. Anything else is left as-is (a string,
# for _read_profile_scalars) or treated as False (for the env-var path, matching prior
# behavior for unrecognized values).
_BOOL_TRUE = ("true", "yes", "1", "on")
_BOOL_FALSE = ("false", "no", "0", "off")


def _parse_bool(val: str):
    """`True`/`False` for a recognized spelling (case-insensitive), else `None`."""
    lowered = val.strip().lower()
    if lowered in _BOOL_TRUE:
        return True
    if lowered in _BOOL_FALSE:
        return False
    return None


def _profile_note_path(vault: Path) -> Path:
    return Path(vault) / "Config" / "toolkit" / f"{PROFILE_PLUGIN_NAME}.md"


def _strip_inline_comment(val: str) -> str:
    """Strip a trailing `# comment` from a flat scalar's raw value, respecting a quoted
    value: a `#` inside matching quotes is data, not a comment start. Supports this
    reader's known subset only (single value, one pair of quotes, no escaped quotes) —
    see README's "Frontmatter decision" section."""
    if val and val[0] in "\"'":
        quote = val[0]
        end = val.find(quote, 1)
        if end != -1:
            return val[: end + 1]  # keep only the quoted segment; drop any trailing comment
        return val  # unterminated quote -- nothing safe to strip
    hash_idx = val.find("#")
    return val[:hash_idx].rstrip() if hash_idx != -1 else val


def _read_profile_scalars(path: Path) -> dict:
    """Extract this plugin's 3 known scalar fields from a profile note's frontmatter
    block via a small targeted line scan. Ignores anything that isn't a bare
    `key: value` line at column 0 (a list item, a nested mapping, an unknown key) —
    there is nothing here to preserve or round-trip, only to read."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    m = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n?", text, re.DOTALL)
    if not m:
        return {}
    result: dict = {}
    for line in m.group(1).splitlines():
        if not line or line[0] in " \t-":
            continue  # indented/nested or list-item line -- not one of our flat keys
        key, sep, val = line.partition(":")
        if not sep:
            continue
        key = key.strip()
        if key not in _PROFILE_SCALAR_KEYS:
            continue
        val = _strip_inline_comment(val.strip())
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        parsed_bool = _parse_bool(val)
        result[key] = parsed_bool if parsed_bool is not None else val
    return result


def read_profile(vault) -> dict:
    """This plugin's known profile fields, or {} if no vault / no profile note — a
    missing profile is a normal, fully-functional state."""
    if vault is None:
        return {}
    path = _profile_note_path(vault)
    if not path.is_file():
        return {}
    return _read_profile_scalars(path)


def profile_value(vault, key: str, default):
    """Resolve one profile value: `TOOLKIT_HANDOFF_<KEY>` env var -> profile note field
    -> `default`. The type of `default` decides how an env var string is coerced."""
    env_name = f"TOOLKIT_HANDOFF_{key.upper()}"
    if env_name in os.environ:
        raw = os.environ[env_name]
        if isinstance(default, bool):
            parsed_bool = _parse_bool(raw)
            return parsed_bool if parsed_bool is not None else False
        return raw
    profile = read_profile(vault)
    if key in profile and profile[key] not in (None, ""):
        return profile[key]
    return default


# ---------------------------------------------------------------------------
# Dead-letter queue -- 00_Memory/dlq/, matching the vault's established convention
# ---------------------------------------------------------------------------


def write_dlq_note(
    vault,
    slug: str,
    title: str,
    what_happened: str,
    why_recorded: str,
    resolution: str = "Unresolved — needs manual review.",
    confidence: str = "low",
    related=None,
):
    """Write a dead-letter entry to `$VAULT/00_Memory/dlq/` — same convention
    plugins/obsidian, plugins/readwise, and plugins/memory use (frontmatter
    description/status/created/tags/confidence; a "What happened / Why it's here /
    Resolution" body). Returns `None` (never raises) if even the DLQ write itself
    fails — a DLQ writer that can crash its caller defeats its own purpose."""
    try:
        dlq_dir = Path(vault) / "00_Memory" / "dlq"
        dlq_dir.mkdir(parents=True, exist_ok=True)
        today = time.strftime("%Y-%m-%d")
        dest = dlq_dir / f"{today}-{slug}.md"
        n = 2
        while dest.exists():
            dest = dlq_dir / f"{today}-{slug}-{n}.md"
            n += 1
        related_lines = "\n".join(f"- [[{r}]]" for r in (related or [])) or "- (none)"
        content = (
            "---\n"
            f"description: {_yaml(title)}\n"
            "status: active\n"
            f"created: {today}\n"
            "tags:\n"
            "  - domain/toolkit-meta\n"
            f"confidence: {confidence}\n"
            "---\n\n"
            f"# DLQ — {title}\n\n"
            f"**What happened:** {what_happened}\n\n"
            f"**Why it's here and not just a skipped step:** {why_recorded}\n\n"
            f"**Resolution:** {resolution}\n\n"
            f"## Related\n\n{related_lines}\n"
        )
        dest.write_text(content, encoding="utf-8")
        return dest
    except Exception:
        return None


# ---------------------------------------------------------------- layout (_handoff/)
def hdir(root):
    d = Path(root) / HANDOFF_DIRNAME
    d.mkdir(exist_ok=True)
    return d


def next_seq(d, stream):
    seqs = []
    for p in glob.glob(str(d / f"HANDOFF-{stream}-*.md")):
        m = re.search(rf"HANDOFF-{re.escape(stream)}-(\d+)\.md$", p)
        if m:
            seqs.append(int(m.group(1)))
    return (max(seqs) + 1) if seqs else 1


# ---------------------------------------------------------------------------
# Vault index -- append-only discovery list, one line per saved handoff
# ---------------------------------------------------------------------------


def _index_header() -> str:
    today = time.strftime("%Y-%m-%d")
    return (
        "---\n"
        'description: "Cross-project index of handoffs written by the handoff plugin."\n'
        "status: active\n"
        f"created: {today}\n"
        "tags:\n"
        "  - domain/toolkit-meta\n"
        "---\n\n"
        "# Handoff Index\n\n"
        "Append-only. One line per saved handoff: ISO date, repo, stream, seq, title, "
        "path. Never edited by hand except to prune. Not linked from active content — "
        "`00_Memory/` is agent operational memory, not vault content "
        "(`contract/VAULT_SCHEMA.md`).\n\n"
    )


def append_vault_index(vault, repo_name: str, stream: str, seq: int, title: str, fpath: Path):
    """Append one line to the vault's handoff index. Returns `(path, error)` —
    `error` is `None` on success, or a short string describing what went wrong (the
    caller decides whether that is DLQ-worthy). Never raises."""
    index_rel = profile_value(vault, "index_path", DEFAULT_INDEX_PATH)
    idx = Path(vault) / index_rel
    try:
        idx.parent.mkdir(parents=True, exist_ok=True)
        if not idx.exists():
            idx.write_text(_index_header(), encoding="utf-8")
        now = datetime.now().isoformat(timespec="seconds")
        line = f'- {now} | repo={repo_name} | stream={stream} seq{seq} | "{title}" | `{fpath}`\n'
        with idx.open("a", encoding="utf-8") as f:
            f.write(line)
        return idx, None
    except Exception as exc:
        return idx, f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------- commands
def cmd_save(args):
    root = project_repo_root()
    repo_name = root.name
    stream = _slug(args.stream or _git(["rev-parse", "--abbrev-ref", "HEAD"], root))

    body_src = Path(args.body_file) if args.body_file else None
    if body_src and body_src.exists():
        narrative = body_src.read_text(encoding="utf-8").rstrip() + "\n"
    elif not sys.stdin.isatty():
        narrative = sys.stdin.read().rstrip() + "\n"
    else:
        narrative = "## Notes\n\n(no narrative supplied)\n"

    vault = resolve_vault()
    title = args.title or f"{stream} handoff"

    try:
        d = hdir(root)
        seq = next_seq(d, stream)
        prev = f"HANDOFF-{stream}-{seq - 1:02d}.md" if seq > 1 else ""

        now = datetime.now().isoformat(timespec="seconds")
        fm = [
            "---",
            f"stream: {stream}",
            f"seq: {seq}",
            f"prev: {prev}" if prev else "prev:",
            f"title: {_yaml(title)}",
            f"date: {now}",
            f"repo: {_yaml(repo_name)}",
            f"branch: {_yaml(_git(['rev-parse', '--abbrev-ref', 'HEAD'], root) or 'none')}",
            "tool: claude-code",
            "---",
            "",
            f"# Handoff — {title}",
            f"_stream `{stream}` · seq {seq}"
            + (f" · follows [{prev}]({prev})_" if prev else "_"),
            "",
            "",
        ]
        content = "\n".join(fm) + narrative + "\n" + repo_state_block(root)

        fname = f"HANDOFF-{stream}-{seq:02d}.md"
        fpath = d / fname
        fpath.write_text(content, encoding="utf-8")
        (d / LATEST).write_text(
            f"<!-- latest handoff pointer — see {fname} -->\n\n" + content,
            encoding="utf-8",
        )

        # drain the draft so it doesn't leak into the next handoff
        draft = d / DRAFT
        if body_src and draft.exists() and body_src.resolve() == draft.resolve():
            try:
                draft.unlink()
            except Exception:
                pass
    except Exception as exc:
        # The _handoff/ write itself failed -- this would silently lose the handoff
        # narrative, which is exactly this plugin's DLQ criterion (see README's Dead-
        # letter queue section). Embed the narrative in the DLQ note itself (if a vault
        # is resolvable) so it isn't lost; otherwise there's nowhere durable to put it,
        # so print it back to the user instead of swallowing it.
        detail = f"{type(exc).__name__}: {exc}"
        if vault is not None:
            write_dlq_note(
                vault,
                slug="handoff-save-failure",
                title=f"Handoff save failed for stream '{stream}' in {repo_name}",
                what_happened=(
                    f"Writing to {root / HANDOFF_DIRNAME} raised {detail}. The narrative "
                    f"that would have been saved is preserved below so it is not lost.\n\n"
                    f"```markdown\n{narrative}\n```"
                ),
                why_recorded=(
                    "A failed _handoff/ write silently loses the handoff narrative unless "
                    "recorded somewhere durable -- this is the DLQ criterion for this plugin."
                ),
                resolution=f"Fix the permissions/disk issue at {root / HANDOFF_DIRNAME}, "
                "then re-run save.",
            )
            print(f"ERROR: could not write handoff ({detail}); recorded to vault DLQ.", file=sys.stderr)
        else:
            print(
                f"ERROR: could not write handoff ({detail}); no vault to record a DLQ "
                f"note. Narrative follows so it isn't lost:\n\n{narrative}",
                file=sys.stderr,
            )
        sys.exit(1)

    print(f"✅ Handoff saved: {fpath}")
    print(f"   Latest pointer: {d / LATEST}")
    if prev:
        print(f"   Chained after: {prev}")

    if vault is None:
        print("   Vault index:   skipped (no vault resolvable)")
    else:
        idx, err = append_vault_index(vault, repo_name, stream, seq, title, fpath)
        if err is None:
            print(f"   Vault index:   {idx}")
        else:
            write_dlq_note(
                vault,
                slug="handoff-index-append-failure",
                title=f"Handoff vault-index append failed for {repo_name}/{stream} seq{seq}",
                what_happened=f"Appending to {idx} raised {err}.",
                why_recorded=(
                    "The handoff itself saved fine -- this is only the cross-project "
                    "discoverability index failing against a resolvable vault, which is "
                    "this plugin's DLQ criterion (an index-append failure that was instead "
                    "swallowed would look identical to 'no vault configured')."
                ),
                resolution=f"Fix the permissions/disk issue at {idx}, then re-run save to "
                "re-append, or add the line by hand.",
                related=[fname],
            )
            print(f"   Vault index:   FAILED ({err}) — recorded to vault DLQ")

    visibility = profile_value(vault, "default_visibility", DEFAULT_VISIBILITY)
    if visibility == "gitignore":
        print(f"   Suggested:     gitignore {HANDOFF_DIRNAME}/ (profile default_visibility=gitignore)")
    else:
        print(f"   Suggested:     git add {HANDOFF_DIRNAME}/ (profile default_visibility={visibility})")


def _latest_handoff(d):
    latest = d / LATEST
    if latest.exists():
        return latest
    files = sorted(glob.glob(str(d / "HANDOFF-*.md")), key=os.path.getmtime)
    return Path(files[-1]) if files else None


def cmd_resume(args):
    root = project_repo_root()
    d = root / HANDOFF_DIRNAME
    if not d.exists():
        print(f"No _handoff/ directory in {root.name}. Nothing to resume.")
        return
    latest = _latest_handoff(d)
    if not latest:
        print(f"No handoff files in {d}. Nothing to resume.")
        return
    print(f"===== RESUMING FROM: {latest} =====\n")
    print(latest.read_text(encoding="utf-8").rstrip())

    snap = d / SNAPSHOT
    if snap.exists() and snap.stat().st_mtime > latest.stat().st_mtime:
        print("\n\n===== NEWER AUTO-SNAPSHOT (captured after the handoff) =====\n")
        print(snap.read_text(encoding="utf-8").rstrip())


def cmd_list(args):
    root = project_repo_root()
    d = root / HANDOFF_DIRNAME
    files = sorted(glob.glob(str(d / "HANDOFF-*.md")))
    files = [f for f in files if not f.endswith(LATEST)]
    if not files:
        print(f"No handoffs in {d}")
        return
    print(f"Handoffs in {root.name}:")
    for f in files:
        txt = Path(f).read_text(encoding="utf-8")[:600]
        title = re.search(r"^title: (.+)$", txt, re.M)
        date = re.search(r"^date: (.+)$", txt, re.M)
        print(f"  {Path(f).name:34}  {(date.group(1) if date else ''):20}  "
              f"{title.group(1) if title else ''}")


def cmd_snapshot(args):
    """PreCompact hook target. Must be fast and NEVER raise/block compaction. Follows
    the memory-plugin hook standard: silent no-op without a repo, byte-bounded output,
    failures recorded to DLQ rather than raised or spammed to stderr (hooks/precompact.sh
    already redirects this process's own stdout/stderr to /dev/null regardless)."""
    try:
        if not has_project_repo():
            return 0  # no real repo context -- don't create _handoff/ in an arbitrary cwd

        root = project_repo_root()
        vault = resolve_vault()
        if not profile_value(vault, "autosnapshot", DEFAULT_AUTOSNAPSHOT):
            return 0  # disabled via profile/env

        d = hdir(root)
        now = datetime.now().isoformat(timespec="seconds")
        content = (
            f"<!-- auto-snapshot before context compaction @ {now} -->\n\n"
            f"# Pre-Compaction Snapshot\n\n"
            f"_Captured automatically at {now}. Not a full handoff — git state only. "
            f"Run the `handoff:handoff` skill for a real handoff with decisions and "
            f"next steps._\n\n" + repo_state_block(root)
        )
        encoded = content.encode("utf-8")
        if len(encoded) > MAX_SNAPSHOT_BYTES:
            content = encoded[:MAX_SNAPSHOT_BYTES].decode("utf-8", errors="ignore") + "\n\n…(truncated)\n"
        (d / SNAPSHOT).write_text(content, encoding="utf-8")
    except Exception as exc:
        try:
            vault = resolve_vault()
            if vault is not None:
                write_dlq_note(
                    vault,
                    slug="handoff-snapshot-failure",
                    title="PreCompact auto-snapshot failed",
                    what_happened=f"scripts/handoff.py snapshot raised {type(exc).__name__}: {exc}",
                    why_recorded="A PreCompact hook must never raise or spam stderr; recorded here instead.",
                )
        except Exception:
            pass  # compaction must proceed regardless
    return 0


def main():
    try:  # non-ASCII output must not crash under a C/POSIX locale
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    p = argparse.ArgumentParser(prog="handoff", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("save", help="write a handoff")
    s.add_argument("--stream", help="short kebab tag for this line of work")
    s.add_argument("--title", help="one-line title")
    s.add_argument("--body-file", help="markdown file with the narrative body ('-' or omit = stdin)")
    s.set_defaults(func=cmd_save)

    sub.add_parser("resume", help="print latest handoff").set_defaults(func=cmd_resume)
    sub.add_parser("list", help="list handoffs").set_defaults(func=cmd_list)
    sub.add_parser("snapshot", help="git-state dump (PreCompact hook)").set_defaults(func=cmd_snapshot)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
