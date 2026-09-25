# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy"]
# ///
"""Synthesize the explainer's music bed: calm, warm, understated. Writes public/music/explainer-bed.wav.

    uv run video/scripts/make_music.py

Everything is generated here from a fixed seed, so there is no licence to check and nothing to download.
It reads src/timeline.json, the same file the video reads, so the music follows the picture:

- 80 BPM, one bar = 3 s; every scene starts on a bar.
- A pad under everything: D major colours, one chord every two bars (Dmaj9, Bm9, Gmaj9, Asus2).
- A soft plucked arpeggio from the vault scene on, with a quiet sub pulse from the plugins scene
  to the end card. No drums and no drops: nothing competes with the picture.
- A low-pass filter opens as the graph forms and again for INFERRED, and settles for the end card.
- One soft bell per cue (a search hit, the neighbours lighting up, an INFERRED pair), in key.
"""
from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

VIDEO = Path(__file__).resolve().parent.parent
TIMELINE = json.loads((VIDEO / "src/timeline.json").read_text(encoding="utf-8"))
MUSIC = json.loads((VIDEO / "music.json").read_text(encoding="utf-8"))
OUT = VIDEO / MUSIC["file"]

SR = 44100
BEAT = 60 / TIMELINE["bpm"]
BAR = 4 * BEAT
TOTAL = TIMELINE["total"] + 3.0          # a tail past the last frame; the render fades out before it
N = int(TOTAL * SR)
T = np.arange(N) / SR
rng = np.random.default_rng(80)
SCENE = {s["id"]: s for s in TIMELINE["scenes"]}

# One chord per two bars. MIDI notes: pad voicing, bass root, arpeggio tones.
CHORDS = [
    ([50, 57, 61, 64, 66], 38, [62, 66, 69, 73, 76]),   # Dmaj9
    ([47, 54, 57, 61, 62], 35, [59, 62, 66, 69, 73]),   # Bm9
    ([43, 50, 54, 57, 62], 31, [55, 59, 62, 66, 69]),   # Gmaj9
    ([45, 52, 57, 59, 64], 33, [57, 59, 64, 69, 71]),   # Asus2
]


def mtof(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def chord_at(t: float):
    return CHORDS[int(t // (2 * BAR)) % len(CHORDS)]


def envelope(points: list[tuple[float, float]]) -> np.ndarray:
    xs, ys = zip(*points, strict=True)
    return np.interp(T, xs, ys)


def lowpass_sweep(x: np.ndarray, cutoff: np.ndarray, lo: float = 450, hi: float = 3800) -> np.ndarray:
    """A click-free filter sweep: the signal low-passed dark and bright, crossfaded on a log scale."""
    dark = sosfilt(butter(2, lo, "low", fs=SR, output="sos"), x, axis=0)
    bright = sosfilt(butter(2, hi, "low", fs=SR, output="sos"), x, axis=0)
    w = np.clip(np.log(cutoff / lo) / np.log(hi / lo), 0, 1)[:, None]
    return dark * (1 - w) + bright * w


def pad() -> np.ndarray:
    """Detuned soft saws per chord tone, two-bar chords with slow attack and overlap."""
    out = np.zeros((N, 2))
    seg = 2 * BAR
    for k in range(int(np.ceil(TOTAL / seg))):
        t0 = k * seg
        voices, _, _ = chord_at(t0 + 0.01)
        a, b = int(max(0, t0 - 0.8) * SR), min(N, int((t0 + seg + 1.6) * SR))
        t = np.arange(b - a) / SR
        env = np.minimum(1, t / 1.6) * np.clip((seg + 2.4 - t) / 1.6, 0, 1)
        for m in voices:
            f = mtof(m)
            for side, det in ((0, -0.07), (1, 0.07)):
                for d in (det, det * 2.3):
                    ph = rng.uniform()
                    v = 2 * ((f * 2 ** (d / 12) * t + ph) % 1) - 1
                    out[a:b, side] += v * env * 0.016
            out[a:b] += (np.sin(2 * np.pi * f * t) * env * 0.009)[:, None]         # a little sine body
    return sosfilt(butter(2, 140, "high", fs=SR, output="sos"), out, axis=0)  # the pulse owns the low end


def pluck(freq: float, dur: float, bright: float = 1.0) -> np.ndarray:
    t = np.arange(int(dur * SR)) / SR
    tone = np.sin(2 * np.pi * freq * t) + 0.35 * bright * np.sin(2 * np.pi * 2 * freq * t) * np.exp(-t * 6)
    return tone * np.exp(-t * 3.2) * np.minimum(1, t / 0.004)


def arpeggio(start: float, end: float) -> np.ndarray:
    out = np.zeros((N, 2))
    step = BEAT / 2
    pattern = [0, 2, 1, 3, 2, 4, 3, 1]
    k = 0
    t = start
    while t < end:
        _, _, tones = chord_at(t)
        m = tones[pattern[k % len(pattern)]]
        vel = 0.55 + 0.25 * (k % 4 == 0) + rng.uniform(-0.06, 0.06)
        note = pluck(mtof(m), 1.6, bright=0.8) * vel * 0.16
        i = int(t * SR)
        j = min(N, i + len(note))
        pan = 0.5 + 0.3 * np.sin(k * 0.9)
        out[i:j, 0] += note[: j - i] * (1 - pan)
        out[i:j, 1] += note[: j - i] * pan
        t += step
        k += 1
    return out


def pulse(start: float, end: float) -> np.ndarray:
    """A quiet sub note on beats 1 and 3: felt more than heard."""
    out = np.zeros((N, 2))
    t = start
    while t < end:
        _, root, _ = chord_at(t)
        d = np.arange(int(BEAT * 1.6 * SR)) / SR
        f = mtof(root)
        note = np.sin(2 * np.pi * f * d) * np.exp(-d * 2.2) * np.minimum(1, d / 0.03) * 0.09
        i = int(t * SR)
        j = min(N, i + len(note))
        out[i:j] += note[: j - i, None]
        t += 2 * BEAT
    return out


def bell(at: float) -> np.ndarray:
    out = np.zeros((N, 2))
    _, _, tones = chord_at(at)
    f = mtof(tones[-1] + 12)
    d = np.arange(int(3.0 * SR)) / SR
    mod = np.sin(2 * np.pi * f * 3.5 * d) * 1.4 * np.exp(-d * 4)
    tone = np.sin(2 * np.pi * f * d + mod) * np.exp(-d * 1.6) * np.minimum(1, d / 0.002) * 0.07
    i = int(at * SR)
    j = min(N, i + len(tone))
    out[i:j, 0] += tone[: j - i] * 0.8
    out[i:j, 1] += tone[: j - i]
    return out


def reverb(x: np.ndarray, seconds: float = 3.2, wet: float = 0.32) -> np.ndarray:
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-t * 6.9 / seconds)[:, None]
    ir = sosfilt(butter(1, 5000, "low", fs=SR, output="sos"), ir, axis=0)
    ir /= np.sqrt((ir**2).sum(axis=0))
    y = np.stack([fftconvolve(x[:, c], ir[:, c])[:N] for c in range(2)], axis=1)
    return x * (1 - wet) + y * wet


def main() -> int:
    s = SCENE
    cutoff = envelope([
        (0, 500), (s["vault"]["start"], 700), (s["vault"]["start"] + 9, 2400), (s["search"]["start"], 2800),
        (s["map"]["start"], 2200), (s["inferred"]["start"], 2400), (s["inferred"]["start"] + 6, 3600),
        (s["local"]["start"], 2600), (s["end"]["start"], 1800), (TOTAL, 700),
    ])
    mix = lowpass_sweep(pad(), cutoff)
    mix += arpeggio(s["vault"]["start"], s["end"]["start"] + BAR)
    mix += pulse(s["plugins"]["start"], s["end"]["start"])
    for cue in TIMELINE["cues"]:
        mix += bell(cue["at"])
    mix = reverb(mix)
    mix = sosfilt(butter(2, 35, "high", fs=SR, output="sos"), mix, axis=0)
    fade = np.clip(T / 2.0, 0, 1) * np.clip((TOTAL - T) / 5.0, 0, 1)
    mix *= fade[:, None]
    mix *= 10 ** (-3 / 20) / np.abs(mix).max()                  # peak at -3 dBFS
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(OUT), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())
    print(f"wrote {OUT.relative_to(VIDEO)}: {TOTAL:.1f} s, {TIMELINE['bpm']} BPM, {len(TIMELINE['cues'])} cues")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
