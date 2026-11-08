"""Bounded summaries for noisy media command output."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from typing import Sequence

MAX_CAPTURE_BYTES = 2_000_000
MAX_SUMMARY_CHARS = 2_000_000
MAX_SUMMARY_LINES = 50

ANSI_ESCAPE = re.compile(
    r"\x1B(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1B\\))"
)

PROGRESS_NOISE = re.compile(
    r"^(?:"
    r"frame=\s*\d+|size=\s*\d+|"
    r"Rendering frame \d+|Rendered \d+/\d+|Encoded\s+\d+/\d+|Stitching frames|"
    r"Bundling \d+%|Copying public dir|Compiling \d+%|"
    r"\[download\]\s*\d+(?:\.\d+)?%|"
    r"Fra:\d+\s+Mem:|Animation \d+:.*%|"
    r"\s*\d+%\|[█▏▎▍▌▋▊▉ ]*|"
    r"\s*[#=<>. ]+\s*\d+%"
    r")"
)

CRITICAL_KEYWORDS = (
    "error", "exception", "traceback", "failed", "invalid", "fatal",
    "cannot", "not found", "no such", "syntaxerror", "typeerror",
    "referenceerror", "permission denied",
)


def _limit_capture(text: str, limit: int = MAX_SUMMARY_CHARS) -> str:
    """Keep both ends of unusually large output, where diagnostics often live."""
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n[... FrameDiet omitted {len(text) - limit} characters ...]\n{text[-half:]}"


def _strip_ansi(text: str) -> str:
    """Remove common CSI color/control and OSC terminal sequences."""
    return ANSI_ESCAPE.sub("", text)


def compress_ffprobe_json(raw_output: str) -> str:
    """Summarize a narrow, recognized ffprobe shape; preserve other JSON fields."""
    raw_output = _strip_ansi(raw_output)
    try:
        data = json.loads(raw_output)
    except (json.JSONDecodeError, TypeError):
        return _limit_capture(raw_output)

    if not isinstance(data, dict) or set(data) - {"format", "streams"}:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    fmt = data.get("format", {})
    if not isinstance(fmt, dict) or set(fmt) - {"filename", "duration", "size"}:
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    streams = data.get("streams", [])
    if not isinstance(streams, list):
        return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    for stream in streams:
        if not isinstance(stream, dict):
            return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        kind = stream.get("codec_type")
        allowed = (
            {"index", "codec_type", "codec_name", "width", "height", "avg_frame_rate", "r_frame_rate", "pix_fmt"}
            if kind == "video"
            else {"index", "codec_type", "codec_name", "sample_rate", "channels"}
            if kind == "audio"
            else set()
        )
        if not allowed or set(stream) - allowed:
            return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    try:
        duration = f"{float(fmt['duration']):.3f}s" if fmt.get("duration") is not None else "unknown"
    except (TypeError, ValueError):
        duration = "unknown"
    try:
        size = f"{int(fmt['size']) / (1024 * 1024):.2f} MiB" if fmt.get("size") is not None else "unknown"
    except (TypeError, ValueError):
        size = "unknown"

    lines = [f"Media: {fmt.get('filename', 'input')} | Duration: {duration} | Size: {size}"]
    for stream in streams:
        kind = stream.get("codec_type", "unknown")
        codec = stream.get("codec_name", "unknown")
        index = stream.get("index", "?")
        if kind == "video":
            width, height = stream.get("width", "?"), stream.get("height", "?")
            rates = []
            if stream.get("avg_frame_rate"):
                rates.append(f"avg {stream['avg_frame_rate']}")
            if stream.get("r_frame_rate"):
                rates.append(f"r {stream['r_frame_rate']}")
            rate = ", ".join(rates) or "rate unknown"
            pix_fmt = f" {stream['pix_fmt']}" if stream.get("pix_fmt") else ""
            lines.append(f"Video #{index}: {codec} {width}x{height} ({rate}){pix_fmt}")
        elif kind == "audio":
            lines.append(
                f"Audio #{index}: {codec} {stream.get('sample_rate', '?')} Hz "
                f"{stream.get('channels', '?')} ch"
            )
        else:
            lines.append(f"Stream #{index}: {kind} {codec}")
    return "\n".join(lines)


def compress_output(
    command: Sequence[str],
    returncode: int,
    stdout: str,
    stderr: str,
) -> str:
    """Summarize output while keeping diagnostics and a bounded amount of context."""
    stdout = _strip_ansi(stdout)
    stderr = _strip_ansi(stderr)
    executable = command[0].replace("\\", "/").rsplit("/", 1)[-1].lower() if command else ""

    if executable in {"ffprobe", "ffprobe.exe"} and returncode == 0:
        wants_json = any(
            arg.lower() in {"json", "-of=json", "-print_format=json"}
            for arg in command[1:]
        )
        if wants_json:
            return compress_ffprobe_json(stdout)

    combined = _limit_capture("\n".join(part for part in (stdout, stderr) if part).strip())
    if not combined:
        return f"FrameDiet: command exited with code {returncode} (no output)."

    lines = [line.rstrip() for line in combined.splitlines() if line.strip()]
    clean = [line for line in lines if not PROGRESS_NOISE.match(line.strip())]
    if returncode:
        critical = [line for line in clean if any(word in line.lower() for word in CRITICAL_KEYWORDS)]
        # Reserve room for the last diagnostics first so a long tail cannot
        # push them out of the bounded summary, then fill with the tail.
        keep_critical = list(dict.fromkeys(critical))[-MAX_SUMMARY_LINES // 2:]
        tail_room = MAX_SUMMARY_LINES - len(keep_critical)
        tail = [line for line in clean[-tail_room:] if line not in keep_critical] if tail_room else []
        wanted = set(keep_critical) | set(tail)
        # Preserve original order of the chosen lines.
        selected = [line for line in dict.fromkeys(clean) if line in wanted]
        if not selected:
            selected = clean[-MAX_SUMMARY_LINES:]
        return f"[EXIT {returncode}] Command failed; diagnostic output follows:\n" + "\n".join(selected)

    if not clean:
        return "[OK] FrameDiet: command completed successfully; progress output omitted."

    # Keep the tail (usually the final artifact or completion message) plus any
    # stream/output metadata that appeared earlier.
    metadata = [
        line for line in clean
        if any(marker in line.lower() for marker in ("stream #", "duration:", "output #", "rendered", "saved", "done", "created"))
    ]
    selected = list(dict.fromkeys(metadata + clean[-12:]))[-MAX_SUMMARY_LINES:]
    return "[OK] FrameDiet: command completed successfully.\n" + "\n".join(selected)


def exec_and_compress(command: Sequence[str]) -> tuple[int, str]:
    """Execute an argv command without a shell, then summarize its output."""
    if not command:
        return 2, "FrameDiet: no command was provided."
    argv = list(command)
    executable = argv[0].replace("\\", "/").rsplit("/", 1)[-1].lower()
    if executable in {"ffmpeg", "ffprobe", "ffmpeg.exe", "ffprobe.exe"} and "-hide_banner" not in argv:
        argv.insert(1, "-hide_banner")
    try:
        # Spool command output to disk so a verbose render cannot allocate its
        # entire log in RAM before FrameDiet applies its capture limit.
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            result = subprocess.run(
                argv,
                stdout=stdout_file,
                stderr=stderr_file,
                check=False,
            )
            stdout_text, stdout_truncated = _read_bounded(stdout_file)
            stderr_text, stderr_truncated = _read_bounded(stderr_file)
    except FileNotFoundError as exc:
        return 127, f"FrameDiet: executable not found: {argv[0]}\n{exc}"
    except OSError as exc:
        return 126, f"FrameDiet: could not start {argv[0]}: {exc}"

    output = compress_output(argv, result.returncode, stdout_text, stderr_text)
    if stdout_truncated or stderr_truncated:
        output = "[FrameDiet: command output exceeded the capture limit; only a head/tail sample is available]\n" + output
    return result.returncode, output


def _read_bounded(stream, limit: int = MAX_CAPTURE_BYTES) -> tuple[str, bool]:
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    if size <= limit:
        return stream.read().decode("utf-8", errors="replace"), False
    half = limit // 2
    head = stream.read(half)
    stream.seek(-half, 2)
    tail = stream.read(half)
    omitted = max(size - limit, 0)
    sample = head + f"\n[... FrameDiet omitted {omitted} bytes ...]\n".encode() + tail
    return sample.decode("utf-8", errors="replace"), True
