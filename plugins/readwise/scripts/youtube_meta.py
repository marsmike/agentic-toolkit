#!/usr/bin/env python3
"""Fetch YouTube video metadata + auto-generated transcript for enrichment.

Optional enrichment: shells out to `yt-dlp`. Degrades cleanly (returns an "error" key)
when `yt-dlp` isn't installed, the video has no transcript, or the fetch otherwise fails —
YouTube enrichment is additive, never a gate on writing a capture.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


def yt_dlp_available() -> bool:
    return shutil.which("yt-dlp") is not None


def fetch_video_meta(url: str, langs: str = "en,de", max_chars: int = 15000, timeout: int = 60) -> dict:
    """Returns yt-dlp's metadata dict plus `transcript_text`/`transcript_chars`, or
    `{"error": "..."}` on failure. Tolerates partial subtitle-language availability —
    yt-dlp exits non-zero when *any* requested language is missing, which is normal."""
    if not yt_dlp_available():
        return {"error": "yt-dlp not on PATH — install: brew install yt-dlp"}

    with tempfile.TemporaryDirectory(prefix="readwise-yt-") as tmp:
        tmpdir = Path(tmp)
        try:
            proc = subprocess.run(
                ["yt-dlp", "--skip-download", "--print-json",
                 "--write-auto-subs", "--sub-lang", langs, "--sub-format", "json3",
                 "-o", str(tmpdir / "%(id)s.%(ext)s"), url],
                capture_output=True, text=True, timeout=timeout,
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            return {"error": f"yt-dlp call failed: {e}"}

        if not proc.stdout.strip():
            return {"error": f"yt-dlp produced no metadata (exit={proc.returncode}): {proc.stderr[:500]}"}

        try:
            meta = json.loads(proc.stdout.strip().splitlines()[0])
        except json.JSONDecodeError:
            return {"error": "yt-dlp metadata was not valid JSON"}

        vid_id = meta.get("id", "")
        transcript = ""
        for lang in langs.split(","):
            sub_path = tmpdir / f"{vid_id}.{lang}.json3"
            if sub_path.is_file():
                transcript = _json3_to_text(sub_path)
                break

        if len(transcript) > max_chars:
            transcript = transcript[:max_chars] + "…[truncated]"
        meta["transcript_text"] = transcript
        meta["transcript_chars"] = len(transcript)
        return meta


def _json3_to_text(path: Path) -> str:
    """Collapse yt-dlp's json3 subtitle events into plain text, dropping only *consecutive*
    duplicate lines (rolling auto-captions repeat lines) — never sort/dedupe globally,
    which scrambles chronological order (observed failure in v1, W30-2026)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return ""
    lines: list[str] = []
    for event in data.get("events", []):
        segs = event.get("segs")
        if not segs:
            continue
        line = "".join(seg.get("utf8", "") for seg in segs)
        line = " ".join(line.split())
        if not line:
            continue
        if lines and lines[-1] == line:
            continue
        lines.append(line)
    return " ".join(lines)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("usage: youtube_meta.py <youtube_url>", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(fetch_video_meta(sys.argv[1]), indent=2))
