"""FrameDiet command-line interface."""

from __future__ import annotations

import argparse
import json
import os
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

# Only tools whose output is mostly progress noise are rewritten. ffprobe and
# whisper are left alone: their output is the data the agent asked for.
DIRECT_BINARIES = {"ffmpeg", "manim", "yt-dlp"}
NODE_MEDIA_TOOLS = {"hyperframes", "remotion"}
NODE_RENDER_SUBCOMMANDS = {"render", "still", "bundle", "benchmark"}
SHELL_SYNTAX = re.compile(r"(?:&&|\|\||[;|&<>`()\r\n]|\$\()")

_COMMON_INFO_FLAGS = {"-h", "-help", "--help", "-version", "--version", "-?"}
_FFMPEG_INFO_FLAGS = {
    "-buildconf", "-formats", "-demuxers", "-muxers", "-devices", "-codecs",
    "-decoders", "-encoders", "-bsfs", "-protocols", "-filters", "-pix_fmts",
    "-layouts", "-sample_fmts", "-dispositions", "-colors", "-hwaccels", "-l", "-L",
    "-sources", "-sinks",
}
# Filters whose log lines are the result: summarizing them would drop data.
_FFMPEG_ANALYSIS = re.compile(
    r"(?:blackdetect|blackframe|freezedetect|silencedetect|cropdetect|scdet|"
    r"astats|ebur128|volumedetect|loudnorm|showinfo|ashowinfo|idet|signalstats|"
    r"metadata=print|ametadata=print|bbox|psnr|ssim|vmaf)",
    re.IGNORECASE,
)
_YTDLP_INFO_FLAGS = {
    "-F", "--list-formats", "-j", "--dump-json", "-J", "--dump-single-json",
    "--print", "-O", "--print-to-file", "-g", "--get-url", "-e", "--get-title",
    "--get-id", "--get-filename", "--get-duration", "--get-format", "--get-thumbnail",
    "--get-description", "-s", "--simulate", "--list-subs", "--list-thumbnails",
    "--list-extractors", "--extractor-descriptions", "-U", "--update",
}
_MANIM_INFO_SUBCOMMANDS = {"cfg", "checkhealth", "plugins", "init"}


def _basename(token: str) -> str:
    return token.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _strip_exe(name: str) -> str:
    for suffix in (".exe", ".cmd"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _node_binary_name(package: str) -> str:
    name = package.lower().replace("\\", "/")
    if name.startswith("@") and "/" in name:
        scope, name = name.split("/", 1)
        if scope == "@remotion" and name.split("@", 1)[0] == "cli":
            return "remotion"
    else:
        name = name.rsplit("/", 1)[-1]
    return name.split("@", 1)[0]


def _node_tool_invocation(tokens: list[str], runner: str) -> tuple[str, list[str]] | None:
    index = 1
    if runner == "pnpm":
        if len(tokens) < 2 or tokens[1].lower() not in {"exec", "dlx"}:
            return None
        index = 2

    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            index += 1
            break
        if token in {"-y", "--yes"}:
            index += 1
            continue
        if token in {"-p", "--package"}:
            if index + 1 >= len(tokens):
                return None
            index += 2
            continue
        if token.startswith("--package="):
            index += 1
            continue
        if token.startswith("-"):
            return None
        break

    if index >= len(tokens):
        return None
    tool = _node_binary_name(tokens[index])
    return tool, tokens[index + 1:]


_FFMPEG_NO_VALUE = {
    "-y", "-n", "-hide_banner", "-nostats", "-stats", "-nostdin", "-stdin", "-shortest",
    "-an", "-vn", "-sn", "-dn", "-re", "-copyts", "-start_at_zero", "-benchmark",
    "-benchmark_all", "-dump", "-hex", "-ignore_unknown", "-copy_unknown", "-accurate_seek",
    "-noaccurate_seek", "-autorotate", "-noautorotate", "-autoscale", "-noautoscale",
}
_NULL_OUTPUTS = {"-", "pipe:", "pipe:1", "pipe:2", "/dev/null", "nul"}


def _ffmpeg_outputs(args: list[str]) -> list[str]:
    """Positional ffmpeg arguments, i.e. output targets (inputs follow -i)."""
    outputs: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token.startswith("-") and len(token) > 1:
            index += 1 if token in _FFMPEG_NO_VALUE else 2
            continue
        outputs.append(token)
        index += 1
    return outputs


def _option_values(args: list[str], option: str) -> set[str]:
    return {args[i + 1].lower() for i, arg in enumerate(args[:-1]) if arg == option}


def _is_noisy_invocation(tool: str, args: list[str]) -> bool:
    """Return whether this call mainly prints progress, not requested data."""
    flags = set(args)
    if flags & _COMMON_INFO_FLAGS:
        return False
    if tool == "ffmpeg":
        if not args or flags & _FFMPEG_INFO_FLAGS:
            return False
        if any(_FFMPEG_ANALYSIS.search(arg) for arg in args):
            return False
        outputs = _ffmpeg_outputs(args)
        # Without a real output file (ffmpeg -i x, -f null -, stdout) the
        # printed stream info or measurements are the point of the call.
        return bool(outputs) and not any(out.lower() in _NULL_OUTPUTS for out in outputs) and "null" not in _option_values(args, "-f")
    if tool == "yt-dlp":
        return bool(args) and not any(arg.split("=", 1)[0] in _YTDLP_INFO_FLAGS for arg in args)
    if tool == "manim":
        return bool(args) and args[0] not in _MANIM_INFO_SUBCOMMANDS
    if tool in NODE_MEDIA_TOOLS:
        return bool(args) and args[0].lower() in NODE_RENDER_SUBCOMMANDS
    return False


def is_safe_media_command(command: str) -> bool:
    """Accept only a single direct, progress-heavy media call without shell syntax."""
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

    first = _strip_exe(_basename(tokens[0]))
    if first in {"framediet", "fdiet"}:
        return False
    if first in DIRECT_BINARIES:
        return _is_noisy_invocation(first, tokens[1:])
    if first in {"hyperframes", "remotion"}:
        return _is_noisy_invocation(first, tokens[1:])
    if first in {"npx", "bunx", "pnpm"}:
        invocation = _node_tool_invocation(tokens, first)
        if invocation is None:
            return False
        tool, args = invocation
        return tool in NODE_MEDIA_TOOLS and _is_noisy_invocation(tool, args)
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
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        launcher = (Path(plugin_root) / "bin" / "framediet").resolve().as_posix()
        executable = shlex.quote(launcher)
    else:
        executable = "framediet"
    rewritten_input["command"] = f"{executable} exec -- {command.strip()}"
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
    qa_parser.add_argument("--freeze-warn-duration", type=float, default=0.75, help="Mid-video stills shorter than this are notes (held beats), not warnings")
    qa_parser.add_argument("--freeze-noise-db", type=float, default=-60.0, help="Freeze detector noise threshold in dB")
    qa_parser.add_argument("--crop-limit", type=int, default=24, help="FFmpeg cropdetect threshold")
    qa_parser.add_argument("--audio-silence-warn-dbfs", type=float, default=-60.0, help="Warn at or below this audio peak")
    qa_parser.add_argument("--audio-peak-warn-dbfs", type=float, default=-1.0, help="Warn above this audio peak")
    qa_parser.add_argument("--timeout", type=float, default=1800, help="Analysis timeout in seconds")
    qa_parser.add_argument("--ffmpeg", help="Path to ffmpeg executable")
    qa_parser.add_argument("--ffprobe", help="Path to ffprobe executable")
    qa_parser.add_argument("--frames-dir", help="Also extract previews at detected black/freeze start times")
    qa_parser.add_argument("--strict", action="store_true", help="Exit with code 1 when the report is WARN (for CI and render scripts)")
    qa_parser.add_argument("--json", action="store_true", help="Print the QA report as JSON")

    frames_parser = commands.add_parser("frames", help="Extract bounded JPEG previews at selected times")
    frames_parser.add_argument("video", help="Input video path")
    frames_parser.add_argument("timestamps", nargs="+", type=float, help="Presentation times in seconds")
    frames_parser.add_argument("-o", "--out-dir", default="framediet_frames", help="Preview output directory")
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
    html_parser.add_argument("--strip-classes", action="store_true", help="Collapse long class attributes to a marker (visible text is kept)")
    html_parser.add_argument("--strip-styles", action="store_true", help="Collapse long inline style attributes to a marker")
    html_parser.add_argument("--attr-min", type=int, default=60, help="Minimum attribute value length to collapse (default 60)")
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
                freeze_warn_duration=args.freeze_warn_duration,
                freeze_noise_db=args.freeze_noise_db,
                crop_limit=args.crop_limit,
                audio_silence_warn_dbfs=args.audio_silence_warn_dbfs,
                audio_peak_warn_dbfs=args.audio_peak_warn_dbfs,
                timeout=args.timeout,
                ffmpeg_path=args.ffmpeg,
                ffprobe_path=args.ffprobe,
            )
            print(json.dumps(report.as_dict(), ensure_ascii=False) if args.json else report.to_text())
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
                    print(
                        f"preview {preview.timestamp_seconds:.3f}s: {preview.output_path}",
                        file=sys.stderr if args.json else sys.stdout,
                    )
                if omitted:
                    print(
                        f"preview limit reached; skipped {omitted} additional interval start(s)",
                        file=sys.stderr if args.json else sys.stdout,
                    )
            if args.strict and report.status == "WARN":
                raise SystemExit(1)
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
            print(
                slim_html_dom(
                    Path(args.file).read_text(encoding="utf-8"),
                    strip_classes=args.strip_classes,
                    strip_styles=args.strip_styles,
                    attr_min_length=args.attr_min,
                )
            )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"framediet: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
