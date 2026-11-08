"""FrameDiet command-line interface."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
import tempfile
from pathlib import Path
from typing import Any

from framediet.bench import run_benchmark
from framediet.frames import MAX_FRAME_COUNT, extract_frames
from framediet.logs import exec_and_compress
from framediet.probe import probe_path
from framediet.qa import run_video_qa
from framediet.scene_digest import digest_file
from framediet.slim_skill import slim_skill_directory
from framediet.toon import slim_html_dom, to_toon
from framediet.transcripts import compress_whisper, is_whisper_json
from framediet.vlm_sheet import create_contact_sheet

DIRECT_BINARIES = {"ffmpeg", "ffprobe", "manim", "whisper", "faster-whisper", "yt-dlp"}
NODE_MEDIA_TOOLS = {"hyperframes", "remotion"}
SHELL_SYNTAX = re.compile(r"(?:&&|\|\||[;|&<>`()\r\n]|\$\()")


def _basename(token: str) -> str:
    return token.replace("\\", "/").rsplit("/", 1)[-1].lower()


def is_safe_media_command(command: str) -> bool:
    """Accept only a single direct media executable call without shell syntax."""
    if not command or SHELL_SYNTAX.search(command):
        return False
    try:
        # Classification only: turn Windows separators into "/" so POSIX
        # splitting does not eat the backslashes in C:\tools\ffmpeg.exe.
        tokens = shlex.split(command.replace("\\", "/"), posix=True)
    except ValueError:
        return False
    if not tokens:
        return False

    first = _basename(tokens[0])
    if first in {"framediet", "fdiet"}:
        return False
    if first in DIRECT_BINARIES or first in {f"{name}.exe" for name in DIRECT_BINARIES}:
        return True
    if first in {"npx", "npx.cmd", "bunx", "bunx.cmd"} and len(tokens) >= 2:
        return _basename(tokens[1]) in NODE_MEDIA_TOOLS
    if first in {"pnpm", "pnpm.cmd"} and len(tokens) >= 3:
        return tokens[1].lower() in {"exec", "dlx"} and _basename(tokens[2]) in NODE_MEDIA_TOOLS
    return False


def _write_hook_decision(payload: dict[str, Any]) -> None:
    """Rewrite an eligible command but leave Claude's permission policy intact."""
    if payload.get("tool_name") != "Bash":
        return
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    command = tool_input.get("command")
    if not isinstance(command, str) or not is_safe_media_command(command.strip()):
        return

    rewritten_input = dict(tool_input)
    rewritten_input["command"] = f"framediet exec -- {command.strip()}"
    # Do not set permissionDecision: Claude Code's normal approval policy remains active.
    response = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": rewritten_input,
        }
    }
    print(json.dumps(response, ensure_ascii=False))


def handle_claude_hook() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return
    if isinstance(payload, dict):
        _write_hook_decision(payload)


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        handle.write(content)
        handle.flush()
    temp_path.replace(path)


def install_claude_hook(project_dir: str | Path = ".") -> str:
    project = Path(project_dir)
    claude_dir = project / ".claude"
    settings_path = claude_dir / "settings.json"
    settings: dict[str, Any] = {}
    if settings_path.exists():
        loaded = json.loads(settings_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"Expected a JSON object in {settings_path}")
        settings = loaded

    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"Expected an object at 'hooks' in {settings_path}")
    pre_tool_use = hooks.setdefault("PreToolUse", [])
    if not isinstance(pre_tool_use, list):
        raise ValueError(f"Expected an array at 'hooks.PreToolUse' in {settings_path}")

    entry = {"matcher": "Bash", "hooks": [{"type": "command", "command": "framediet hook"}]}
    if entry not in pre_tool_use:
        pre_tool_use.append(entry)
    _atomic_write(settings_path, json.dumps(settings, ensure_ascii=False, indent=2) + "\n")
    return f"Installed FrameDiet hook in {settings_path}"


def _load_json(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"Could not read {path}: {exc}") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="framediet",
        description="Media-aware context utilities for HyperFrames, Remotion, FFmpeg, and Whisper workflows.",
    )
    commands = parser.add_subparsers(dest="cmd", required=True)

    init_parser = commands.add_parser("init", help="Add a permission-preserving Claude Code hook")
    init_parser.add_argument("--dir", default=".", help="Project directory")

    commands.add_parser("hook", help="Internal entry point for the Claude Code PreToolUse hook (reads JSON on stdin)")
    commands.add_parser("bench", help="Measure deterministic sample fixtures locally")

    exec_parser = commands.add_parser("exec", help="Run one media command and summarize its output")
    exec_parser.add_argument("command", nargs=argparse.REMAINDER)

    json_parser = commands.add_parser("json", help="Compact a transcript or encode JSON data as TOON")
    json_parser.add_argument("file", help="Input JSON path")
    json_parser.add_argument("--unit", choices=("ms", "s"), default="ms", help="Transcript output time unit")
    json_parser.add_argument("--precision", type=int, default=None, help="Explicitly round TOON floats")

    sheet_parser = commands.add_parser("sheet", help="Create a timestamped, uniformly sampled contact sheet")
    sheet_parser.add_argument("video", help="Input video path")
    sheet_parser.add_argument("-o", "--out", default="framediet_sheet.jpg", help="Output image path")
    sheet_parser.add_argument("--grid", default="3x3", help="Grid size, for example 3x3 or 4x3")
    sheet_parser.add_argument("--width", type=int, default=384, help="Width of each thumbnail")
    sheet_parser.add_argument("--font-file", help="Font file for drawtext if FFmpeg has no default font")
    sheet_parser.add_argument("--overwrite", action="store_true", help="Replace an existing output image")

    qa_parser = commands.add_parser("qa", help="Check a rendered video for common objective issues")
    qa_parser.add_argument("video", help="Input video path")
    qa_parser.add_argument("--black-min-duration", type=float, default=0.1, help="Minimum black interval in seconds")
    qa_parser.add_argument("--black-pixel-threshold", type=float, default=0.10, help="Black pixel threshold in (0, 1]")
    qa_parser.add_argument("--freeze-min-duration", type=float, default=0.5, help="Minimum low-motion interval in seconds")
    qa_parser.add_argument("--freeze-noise-db", type=float, default=-60.0, help="Freeze detector noise threshold in dB")
    qa_parser.add_argument("--crop-limit", type=int, default=24, help="FFmpeg cropdetect threshold")
    qa_parser.add_argument("--audio-silence-warn-dbfs", type=float, default=-60.0, help="Warn at or below this audio peak")
    qa_parser.add_argument("--audio-peak-warn-dbfs", type=float, default=-1.0, help="Warn above this audio peak")
    qa_parser.add_argument("--timeout", type=float, default=1800, help="Analysis timeout in seconds")
    qa_parser.add_argument("--ffmpeg", help="Path to ffmpeg executable")
    qa_parser.add_argument("--ffprobe", help="Path to ffprobe executable")
    qa_parser.add_argument("--frames-dir", help="Also extract previews at detected black/freeze start times")

    frames_parser = commands.add_parser("frames", help="Extract bounded JPEG previews at selected times")
    frames_parser.add_argument("video", help="Input video path")
    frames_parser.add_argument("timestamps", nargs="+", type=float, help="Presentation times in seconds")
    frames_parser.add_argument("--out-dir", default="framediet_frames", help="Preview output directory")
    frames_parser.add_argument("--width", type=int, default=384, help="Maximum preview width in pixels")
    frames_parser.add_argument("--qscale", type=int, default=8, help="FFmpeg JPEG qscale (2 is highest quality; 31 is lowest)")
    frames_parser.add_argument("--overwrite", action="store_true", help="Replace existing preview files")

    digest_parser = commands.add_parser("digest", help="Print a bounded heuristic index of scene source")
    digest_parser.add_argument("source", help="Input .tsx, .jsx, or .html file")
    digest_parser.add_argument("--max-items", type=int, default=40, help="Maximum indexed items")
    digest_parser.add_argument("--max-chars", type=int, default=8000, help="Maximum report characters")

    probe_parser = commands.add_parser("probe", help="Summarize one media file or a local video project")
    probe_parser.add_argument("path", help="Media file or project directory")
    probe_parser.add_argument("--ffprobe", help="Path to ffprobe executable for media files")
    probe_parser.add_argument("--timeout", type=float, default=30, help="FFprobe timeout in seconds")
    probe_parser.add_argument("--max-sources", type=int, default=8, help="Maximum project source digests")
    probe_parser.add_argument("--max-assets", type=int, default=20, help="Maximum listed project assets")
    probe_parser.add_argument("--max-chars", type=int, default=8000, help="Maximum project report characters")

    slim_parser = commands.add_parser("slim", help="Preview or extract long code blocks in skill files")
    slim_parser.add_argument("path", nargs="?", default=".claude/skills", help="Skills directory")
    slim_parser.add_argument("--threshold", type=int, default=25, help="Minimum fenced-block line count")
    slim_parser.add_argument("--apply", action="store_true", help="Write references and make timestamp-safe backups")

    html_parser = commands.add_parser("html", help="Print HTML with large embedded payloads replaced by markers")
    html_parser.add_argument("file", help="Input HTML file; the source file is not modified")
    return parser


def main() -> None:
    # Keep JSON, source text, and report output reliable in Windows consoles
    # whose inherited code page cannot encode arbitrary Unicode.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
    parser = _build_parser()
    args = parser.parse_args()
    try:
        if args.cmd == "init":
            print(install_claude_hook(args.dir))
        elif args.cmd == "hook":
            handle_claude_hook()
        elif args.cmd == "bench":
            run_benchmark()
        elif args.cmd == "exec":
            argv = list(args.command)
            if argv and argv[0] == "--":
                argv.pop(0)
            code, output = exec_and_compress(argv)
            print(output)
            raise SystemExit(code)
        elif args.cmd == "json":
            data = _load_json(args.file)
            if is_whisper_json(data):
                print(compress_whisper(data, unit=args.unit))
            else:
                print(to_toon(data, name=Path(args.file).stem, precision=args.precision))
        elif args.cmd == "sheet":
            try:
                cols, rows = (int(part) for part in args.grid.lower().split("x", 1))
            except (ValueError, TypeError) as exc:
                raise ValueError("--grid must look like 3x3 or 4x3") from exc
            print(create_contact_sheet(
                args.video, args.out, cols=cols, rows=rows,
                thumb_width=args.width, overwrite=args.overwrite, font_file=args.font_file,
            ))
        elif args.cmd == "qa":
            report = run_video_qa(
                args.video,
                black_min_duration=args.black_min_duration,
                black_pixel_threshold=args.black_pixel_threshold,
                freeze_min_duration=args.freeze_min_duration,
                freeze_noise_db=args.freeze_noise_db,
                crop_limit=args.crop_limit,
                audio_silence_warn_dbfs=args.audio_silence_warn_dbfs,
                audio_peak_warn_dbfs=args.audio_peak_warn_dbfs,
                timeout=args.timeout,
                ffmpeg_path=args.ffmpeg,
                ffprobe_path=args.ffprobe,
            )
            print(report.to_text())
            if args.frames_dir:
                timestamps = sorted({
                    interval.start
                    for interval in (*report.black_intervals, *report.freeze_intervals)
                    if interval.start < report.duration_seconds
                })
                omitted = max(0, len(timestamps) - MAX_FRAME_COUNT)
                timestamps = timestamps[:MAX_FRAME_COUNT]
                previews = extract_frames(args.video, timestamps, args.frames_dir)
                for preview in previews:
                    print(f"preview {preview.timestamp_seconds:.3f}s: {preview.output_path}")
                if omitted:
                    print(f"preview limit reached; skipped {omitted} additional interval start(s)")
        elif args.cmd == "frames":
            previews = extract_frames(
                args.video,
                args.timestamps,
                args.out_dir,
                thumb_width=args.width,
                jpeg_qscale=args.qscale,
                overwrite=args.overwrite,
            )
            for preview in previews:
                print(
                    f"{preview.timestamp_seconds:.3f}s {preview.output_path} "
                    f"({preview.source_width}x{preview.source_height} -> "
                    f"{preview.preview_width}x{preview.preview_height})"
                )
        elif args.cmd == "digest":
            print(digest_file(args.source, max_items=args.max_items, max_chars=args.max_chars))
        elif args.cmd == "probe":
            print(probe_path(
                args.path,
                ffprobe_path=args.ffprobe,
                timeout=args.timeout,
                max_sources=args.max_sources,
                max_assets=args.max_assets,
                max_chars=args.max_chars,
            ))
        elif args.cmd == "slim":
            print(slim_skill_directory(args.path, line_threshold=args.threshold, apply=args.apply))
        elif args.cmd == "html":
            print(slim_html_dom(Path(args.file).read_text(encoding="utf-8")))
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"framediet: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
