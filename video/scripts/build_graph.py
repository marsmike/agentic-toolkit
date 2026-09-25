# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy"]
# ///
"""Write src/graph.json: the example vault's real link graph, laid out once, for the explainer.

    uv run video/scripts/build_graph.py [--gaiafield PATH]

gaiafield indexes vault/ into a throwaway SQLite file (the same extraction `toolkit demo` reports as
nodes=83 edges=783); this script reads its nodes and resolved edges and places them with a seeded
force layout, so every render draws the same picture. The scenes' highlights (search hits, the
neighbours note, the INFERRED pairs) are looked up by path from the capture the video replays, so
the graph and the terminal can never disagree.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import numpy as np

VIDEO = Path(__file__).resolve().parent.parent
REPO = VIDEO.parent
CAPTURE = VIDEO / "capture/from-source-main-0dd21a7/session.txt"
OUT = VIDEO / "src/graph.json"


def gaiafield_db(binary: str) -> sqlite3.Connection:
    tmp = Path(tempfile.mkdtemp()) / "graph.db"
    subprocess.run([binary, "index", "--vault", str(REPO / "vault"), "--db", str(tmp), "--full", "--json"],
                   check=True, capture_output=True)
    return sqlite3.connect(tmp)


def layout(n: int, pairs: list[tuple[int, int]], seed: int = 11, steps: int = 900) -> np.ndarray:
    """Fruchterman-Reingold in a 16:9 box, then normalised to [-1, 1] x [-0.5625, 0.5625]."""
    rng = np.random.default_rng(seed)
    pos = rng.uniform(-1, 1, (n, 2)) * [1.0, 0.5625]
    k = 1.25 / np.sqrt(n)
    src = np.array([a for a, _ in pairs])
    dst = np.array([b for _, b in pairs])
    for step in range(steps):
        t = 0.08 * (1 - step / steps) + 0.002
        delta = pos[:, None, :] - pos[None, :, :]
        dist = np.linalg.norm(delta, axis=-1) + 1e-9
        disp = ((k * k / dist**2)[..., None] * delta).sum(axis=1)       # repulsion
        d = pos[src] - pos[dst]
        dl = np.linalg.norm(d, axis=-1, keepdims=True) + 1e-9
        f = d * dl / k                                                    # attraction along edges
        np.add.at(disp, src, -f)
        np.add.at(disp, dst, f)
        disp -= pos * [0.9, 1.6] * 0.6                                    # gravity, wider than tall
        length = np.linalg.norm(disp, axis=-1, keepdims=True) + 1e-9
        pos += disp / length * np.minimum(length, t)
    pos -= pos.mean(axis=0)
    pos /= np.abs(pos).max(axis=0) / [1.0, 0.5625]
    return pos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gaiafield", default=shutil.which("gaiafield")
                    or str(Path.home() / ".local/share/agentic-toolkit/bin/gaiafield"))
    args = ap.parse_args()

    db = gaiafield_db(args.gaiafield)
    nodes = [dict(path=p, title=t) for p, t in db.execute("SELECT path, title FROM nodes ORDER BY path")]
    index = {n["path"]: i for i, n in enumerate(nodes)}
    edges = [(s, t) for s, t in db.execute("SELECT source, target FROM edges WHERE dangling = 0 AND target IS NOT NULL")]
    pairs = sorted({tuple(sorted((index[s], index[t]))) for s, t in edges if s != t})
    degree = np.zeros(len(nodes), int)
    for a, b in pairs:
        degree[a] += 1
        degree[b] += 1
    pos = layout(len(nodes), pairs)

    session = CAPTURE.read_text(encoding="utf-8")
    hits = re.findall(r"^\s+(\d\.\d{3})\s+(\S+\.md)$", session, re.M)
    focus = re.search(r"^\s+neighbors of (\S+\.md):", session, re.M).group(1)
    inferred = re.findall(r"^\s+(\d\.\d{3})\s+(\S+\.md) <-> (\S+\.md)\s+\[INFERRED\]", session, re.M)
    stats = re.search(r"nodes=(\d+) edges=(\d+)", session)

    def node(path: str) -> int:
        return index[path]

    out = {
        "source": "gaiafield index of vault/ (scripts/build_graph.py); highlights from " + CAPTURE.relative_to(VIDEO).as_posix(),
        "stats": {"nodes": int(stats.group(1)), "edges": int(stats.group(2)),
                  "notes": len(nodes), "extractedEdges": len(edges)},
        "nodes": [dict(title=n["title"], group=n["path"].split("/")[1] if n["path"].count("/") > 1 else n["path"].split("/")[0],
                       x=round(float(x), 4), y=round(float(y), 4), degree=int(d))
                  for n, (x, y), d in zip(nodes, pos, degree, strict=True)],
        "links": [list(p) for p in pairs],
        "hits": [dict(node=node(p), score=s) for s, p in hits],
        "focus": node(focus),
        "neighbors": sorted({b if a == node(focus) else a for a, b in pairs if node(focus) in (a, b)}),
        "inferred": [dict(a=node(a), b=node(b), score=s) for s, a, b in inferred],
    }
    assert out["stats"]["edges"] == len(edges), (out["stats"], len(edges))
    OUT.write_text(json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{OUT.relative_to(REPO)}: {len(nodes)} notes, {len(edges)} edges ({len(pairs)} drawn pairs), "
          f"{len(out['hits'])} hits, {len(out['neighbors'])} neighbours, {len(out['inferred'])} inferred")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
