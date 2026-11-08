"""Frames vs `fdiet qa` on a clip with injected defects (ground truth known).

Usage: python bench/frames_vs_qa.py <dir with qa-control.txt qa-defect.txt raw-ffmpeg.txt sheet.jpg>
Vision tokens use the documented formula ceil(w/28)*ceil(h/28) after the documented
resize rule (standard tier: 1568 px side / 1568 tokens). This is an estimate; the
text tokens use cl100k_base, which is not Claude's tokenizer.
"""
from __future__ import annotations

import math
import re
import subprocess
import sys
from pathlib import Path

import tiktoken

ENC = tiktoken.get_encoding("cl100k_base")
DURATION = 26.453
# Injected ground truth (seconds)
TRUTH = {
    "black A (0.20 s)": ("black", 7.35, 7.55),
    "black B (0.20 s)": ("black", 14.00, 14.20),
    "freeze (1.0 s)": ("freeze", 3.0, 4.0),
}
AUDIO_TRUTH = "audio peak > -1 dBFS (+5 dB gain)"


def vision_tokens(w: int, h: int, side: int = 1568, limit: int = 1568) -> tuple[int, int, int]:
    long_, short = max(w, h), min(w, h)
    for target in range(min(long_, side), 0, -1):
        other = round(target * short / long_)
        pw, ph = (target, other) if w >= h else (other, target)
        tokens = math.ceil(pw / 28) * math.ceil(ph / 28)
        if tokens <= limit:
            return tokens, pw, ph
    raise ValueError("cannot fit")


def text_tokens(path: Path) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return len(text), len(ENC.encode(text))


def parse_intervals(qa_text: str, kind: str) -> list[tuple[float, float]]:
    line = next((l for l in qa_text.splitlines() if l.startswith(f"- {kind} intervals")), "")
    out = []
    for a, b in re.findall(r"(\d+:\d+:\d+\.\d+) - (\d+:\d+:\d+\.\d+|ongoing)", line):
        def sec(s: str) -> float:
            h, m, x = s.split(":")
            return int(h) * 3600 + int(m) * 60 + float(x)
        out.append((sec(a), DURATION if b == "ongoing" else sec(b)))
    return out


def overlaps(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def main(folder: Path) -> None:
    qa_def = (folder / "qa-defect.txt").read_text(encoding="utf-8")
    qa_ctl = (folder / "qa-control.txt").read_text(encoding="utf-8")
    found = {"black": parse_intervals(qa_def, "black"), "freeze": parse_intervals(qa_def, "freeze")}

    one_fps = [float(t) for t in range(int(DURATION) + 1)]
    sheet = [k * DURATION / 9 for k in range(9)]

    def seen(times: list[float], kind: str, lo: float, hi: float) -> str:
        if kind == "freeze":
            return "no (single frames cannot show a hold)"
        return "yes" if any(lo <= t <= hi for t in times) else "no"

    print("## Detection of injected defects")
    print("| Defect | 1 fps frames | 3x3 sheet | fdiet qa |")
    print("|---|---|---|---|")
    for name, (kind, lo, hi) in TRUTH.items():
        qa_hit = "yes" if any(overlaps(i, (lo, hi)) for i in found[kind]) else "no"
        print(f"| {name} | {seen(one_fps, kind, lo, hi)} | {seen(sheet, kind, lo, hi)} | {qa_hit} |")
    peak = re.search(r"audio_peak=(-?[\d.]+)dBFS", qa_def)
    qa_audio = "yes" if peak and float(peak.group(1)) > -1.0 else "no"
    print(f"| {AUDIO_TRUTH} | no (no audio in frames) | no | {qa_audio} (reported {peak.group(1) if peak else '?'} dBFS) |")

    truth_windows = [(lo, hi) for _, lo, hi in TRUTH.values()]
    print("\n## False positives of fdiet qa")
    for label, text in (("control (no injected defects)", qa_ctl), ("defect clip", qa_def)):
        fp = [i for k in ("black", "freeze") for i in parse_intervals(text, k)
              if not any(overlaps(i, w) for w in truth_windows)]
        print(f"- {label}: {len(fp)} intervals outside injected windows: "
              + ", ".join(f"{a:.2f}-{b:.2f}s" for a, b in fp))

    print("\n## Context cost")
    full = vision_tokens(1080, 1920)
    prev = vision_tokens(384, 684)
    sheet_dims = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0",
         str(folder / "sheet.jpg")], capture_output=True, text=True).stdout.strip().split(",")
    sh = vision_tokens(int(sheet_dims[0]), int(sheet_dims[1]))
    q_chars, q_tok = text_tokens(folder / "qa-defect.txt")
    r_chars, r_tok = text_tokens(folder / "raw-ffmpeg.txt")
    n = len(one_fps)
    print("| Item | Pixels (after resize) | Est. vision tokens (standard tier) |")
    print("|---|---|---:|")
    print(f"| one full 1080x1920 frame | {full[1]}x{full[2]} | {full[0]} |")
    print(f"| one fdiet preview 384x684 | {prev[1]}x{prev[2]} | {prev[0]} |")
    print(f"| {n} frames at 1 fps, full size | | {n * full[0]} |")
    print(f"| {n} frames at 1 fps, fdiet previews | | {n * prev[0]} |")
    print(f"| one 3x3 sheet {sheet_dims[0]}x{sheet_dims[1]} | {sh[1]}x{sh[2]} | {sh[0]} |")
    print("\n| Text | Chars | cl100k tokens |")
    print("|---|---:|---:|")
    print(f"| raw ffmpeg detector output (blackdetect+freezedetect+cropdetect+volumedetect) | {r_chars} | {r_tok} |")
    print(f"| fdiet qa report | {q_chars} | {q_tok} |")
    combo = q_tok + sh[0] + prev[0]
    raw_text = (folder / "raw-ffmpeg.txt").read_text(encoding="utf-8", errors="replace")
    keep = [l for l in raw_text.splitlines()
            if re.search(r"black_start|freeze_(start|end|duration)|max_volume|mean_volume", l)]
    g_tok = len(ENC.encode("\n".join(keep)))
    print(f"| same output filtered with grep for detector lines only ({len(keep)} lines) | {sum(map(len, keep))} | {g_tok} |")
    print(f"\nqa + sheet + 1 preview frame ~ {combo} tokens (mixed text proxy + vision estimate)")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
