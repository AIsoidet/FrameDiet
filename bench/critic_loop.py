"""Which injected defects would a third-party "critic loop" sampling rule even put in front of a model?

Usage: python bench/critic_loop.py <defect-clip.mp4> [qa-report.txt]

Reproduces, with ffmpeg only (no model call, no third-party code run), the sampling rules of
  * echris6/motion-video-kit  (business-motion-film/scripts/contact-sheet.sh and critic-prompts.md)
  * Zane-0x5a/remotion-director (claude-plugin/tools/time-overview.ts, thumbnails only)
and checks by timestamp whether a sampled frame falls inside each injected defect.

Ground truth (same defects as bench/frames_vs_qa.py, frame-accurate for the regenerated clip):
  black A 7.35-7.55 s, black B 14.00-14.20 s, freeze 3.00-4.00 s (frames 90-119 held), +5 dB audio gain.
A black defect counts as covered if one sampled frame lies inside it. A freeze counts as
covered only if at least two sampled frames lie inside it (identical neighbours; one frame cannot
show a hold). Audio is never in frames. Vision tokens are the formula estimate from frames_vs_qa.py.
"""
from __future__ import annotations

import math
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from frames_vs_qa import vision_tokens  # noqa: E402

FPS = 30.0
TRUTH = {  # name: (kind, start, end) in seconds; end exclusive for frames
    "black A (0.20 s)": ("black", 7.35, 7.55 + 1e-6),
    "black B (0.20 s)": ("black", 14.00, 14.20 + 1e-6),
    "freeze (1.0 s)": ("freeze", 3.00, 4.00 - 1e-6),
}


def probe(clip: Path) -> tuple[int, int, float]:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
         "-of", "csv=p=0", str(clip)], capture_output=True, text=True, check=True).stdout.split()
    w, h = out[0].split(",")[:2]
    return int(w), int(h), float(out[-1])


def sample_times(clip: Path, every: float) -> list[float]:
    """Source-frame times chosen by `fps=1/every` (nearest frame), as ffmpeg itself reports them."""
    res = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(clip), "-vf", f"fps=1/{every},showinfo", "-an", "-f", "null", "-"],
        capture_output=True, text=True)
    pts = [float(m) for m in re.findall(r"pts_time:([\d.]+)", res.stderr)]
    return [round(t * FPS) / FPS for t in pts]  # snap to the 30 fps source grid


def coverage(times: list[float]) -> dict[str, bool]:
    out = {}
    for name, (kind, lo, hi) in TRUTH.items():
        n = sum(1 for t in times if lo <= t < hi)
        out[name] = n >= (2 if kind == "freeze" else 1)
    return out


def main(clip: Path, qa_report: Path | None) -> None:
    w, h, dur = probe(clip)
    rows = []

    # motion-video-kit: contact-sheet.sh = fps=1/E, scale=480:-1, tile=6x5 -> one JPEG per 30 cells
    tw = 480
    th = round(h * tw / w)
    sheet_tok, sw, sh = vision_tokens(6 * tw, 5 * th)
    for label, every in (("mvk contact-sheet.sh default (1 s)", 1.0),
                         ("mvk full-film critic prompt (0.2 s)", 0.2),
                         ("mvk component critic prompt (0.1 s)", 0.1)):
        t = sample_times(clip, every)
        sheets = math.ceil(len(t) / 30)
        rows.append((label, f"{len(t)} cells / {sheets} sheet(s) {6*tw}x{5*th}", sheets, sheets * sheet_tok, coverage(t)))

    # remotion-director: 0.25 s cells up to 20 s, else 0.5 s; 12 per row, 4 rows per page,
    # thumbnail 90x160 (portrait), page = 12*(90+4)-4+40 wide, 240 px per row + header (header height estimated)
    cell = 0.25 if dur <= 20 else 0.5
    t = sample_times(clip, cell)
    rows_n = math.ceil(len(t) / 12)
    pages = math.ceil(rows_n / 4)
    toks = 0
    for p in range(pages):
        r = min(4, rows_n - 4 * p)
        toks += vision_tokens(12 * 94 - 4 + 40, r * 240 + 100)[0]
    rows.append((f"remotion-director overview ({cell} s cells), thumbnails only",
                 f"{len(t)} cells / {pages} page(s) ~1164 px wide", pages, toks, coverage(t)))
    rows.append(("  + each settle frame (full res, count depends on content)", "1 frame",
                 1, vision_tokens(w, h)[0], {k: False for k in TRUTH}))

    print("| Rule | Samples | Images/iteration | Est. vision tokens | black A | black B | freeze | audio | of 4 |")
    print("|---|---|---:|---:|---|---|---|---|---:|")
    for label, desc, imgs, tok, cov in rows:
        cells = ["yes" if cov[k] else "no" for k in TRUTH]
        n = sum(cov.values())
        print(f"| {label} | {desc} | {imgs} | {tok:,} | {' | '.join(cells)} | no | {n} |")

    if qa_report and qa_report.exists():
        text = qa_report.read_text(encoding="utf-8", errors="replace")
        try:
            import tiktoken
            tok = len(tiktoken.get_encoding("cl100k_base").encode(text))
        except ImportError:
            tok = len(text) // 4
        print(f"\nfdiet qa report: {len(text)} chars, ~{tok} text tokens (cl100k proxy)")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None)
