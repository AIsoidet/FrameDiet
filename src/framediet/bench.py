"""Repeatable measurements over deterministic synthetic media artifacts."""

from __future__ import annotations

import json
from typing import Callable

from framediet.logs import compress_output
from framediet.toon import to_toon
from framediet.transcripts import compress_whisper


def _samples() -> list[tuple[str, str, str]]:
    words = [
        {
            "word": f" word{i}",
            "start": round(i * 0.28, 3),
            "end": round((i + 1) * 0.28, 3),
            "probability": 0.9876,
        }
        for i in range(50)
    ]
    whisper = {"segments": [{"start": 0.0, "end": 14.0, "text": "synthetic benchmark", "words": words}]}
    raw_whisper = json.dumps(whisper, ensure_ascii=False, indent=2)
    compact_whisper = compress_whisper(whisper)

    timeline = [
        {
            "frame": frame,
            "x": round(100 + frame * 2.5, 4),
            "y": 540.0,
            **({"easing": "bezier(0.4,0,0.2,1)"} if frame % 10 == 0 else {}),
        }
        for frame in range(60)
    ]
    raw_timeline = json.dumps(timeline, ensure_ascii=False, indent=2)
    compact_timeline = to_toon(timeline, name="keyframes")

    render_lines = [
        f"frame= {frame:5} fps=30.0 q=24.0 size={frame * 16:6}KiB time=00:00:{frame / 30:05.2f} bitrate=900kbits/s"
        for frame in range(1, 181)
    ]
    render_lines.extend(["Output #0, mp4, to 'out.mp4':", "frame=  180 fps=30.0 Lsize=  920KiB time=00:00:06.00", "video:880KiB audio:32KiB"])
    raw_log = "\n".join(render_lines)
    compact_log = compress_output(["ffmpeg"], 0, "", raw_log)
    return [
        ("Whisper word timestamps (synthetic, 50 words)", raw_whisper, compact_whisper),
        ("Keyframe timeline (synthetic, 60 rows)", raw_timeline, compact_timeline),
        ("FFmpeg render log (synthetic, 183 lines)", raw_log, compact_log),
    ]


def run_benchmark(write: Callable[[str], None] = print) -> None:
    """Print char counts and optional cl100k_base proxy counts.

    cl100k_base is not Claude's tokenizer and is presented only as an optional,
    reproducible proxy. Character counts are always shown.
    """
    encoder = None
    try:
        import tiktoken  # type: ignore[import-not-found]

        encoder = tiktoken.get_encoding("cl100k_base")
    except ImportError:
        pass

    write("Synthetic fixture measurements (tool-output size, not total conversation savings).")
    if encoder:
        write("Token counts use cl100k_base as a proxy; they are not Claude token counts.")
    else:
        write("Install `framediet[benchmark]` for cl100k_base proxy counts; no token estimate is shown by default.")
    if encoder:
        write("| Artifact | Raw chars | FrameDiet chars | Char reduction | Raw cl100k proxy tokens | FrameDiet cl100k proxy tokens | Token reduction |")
        write("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    else:
        write("| Artifact | Raw chars | FrameDiet chars | Char reduction |")
        write("| --- | ---: | ---: | ---: |")

    for name, raw, compact in _samples():
        char_reduction = (1 - len(compact) / max(len(raw), 1)) * 100
        if encoder:
            raw_tokens = len(encoder.encode(raw))
            compact_tokens = len(encoder.encode(compact))
            token_reduction = (1 - compact_tokens / max(raw_tokens, 1)) * 100
            write(
                f"| {name} | {len(raw)} | {len(compact)} | {char_reduction:.1f}% | "
                f"{raw_tokens} | {compact_tokens} | {token_reduction:.1f}% |"
            )
        else:
            write(f"| {name} | {len(raw)} | {len(compact)} | {char_reduction:.1f}% |")
