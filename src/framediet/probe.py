"""Compact discovery for one media file or a local Remotion/HyperFrames project.

Project inspection is bounded and heuristic: package dependencies, likely scene
source files, and common media assets are listed, but this is not a build-system
or TypeScript dependency-graph parser. Files are only read; nothing is changed.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from itertools import islice
from pathlib import Path
from typing import Any, Iterator

from framediet.scene_digest import digest_file

_SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules",
    "dist", "build", "out", ".next", ".nuxt", ".cache", "coverage",
    "vendor", "references_diet",
}
_SOURCE_SUFFIXES = {".tsx", ".jsx", ".html"}
_MEDIA_SUFFIXES = {
    ".mp4", ".webm", ".mov", ".mkv", ".m4v", ".avi",
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg",
}
_FORMAT_FIELDS = ("filename", "duration", "size")
_STREAM_FIELDS = (
    "index", "codec_type", "codec_name", "width", "height",
    "avg_frame_rate", "r_frame_rate", "sample_rate", "channels",
    "channel_layout", "bit_rate",
)
DEFAULT_FFPROBE_TIMEOUT = 30.0


def _positive_timeout(value: float, name: str = "timeout") -> float:
    try:
        timeout_seconds = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a positive finite number of seconds") from exc
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError(f"{name} must be a positive finite number of seconds")
    return timeout_seconds


def _human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{size} B"
        value /= 1024
    return f"{value:.1f} GiB"


def _run_ffprobe(
    media_path: Path,
    ffprobe_path: str | None = None,
    timeout: float = DEFAULT_FFPROBE_TIMEOUT,
) -> dict[str, Any]:
    timeout = _positive_timeout(timeout)
    executable = ffprobe_path or shutil.which("ffprobe")
    if not executable:
        raise FileNotFoundError("ffprobe was not found; install FFmpeg or pass ffprobe_path")
    entries = (
        "format=" + ",".join(_FORMAT_FIELDS)
        + ":stream=" + ",".join(_STREAM_FIELDS)
    )
    command = [
        executable,
        "-v", "error",
        "-show_entries", entries,
        "-of", "json",
        str(media_path.resolve()),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"ffprobe timed out after {timeout:g}s for {media_path}") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not start ffprobe: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"ffprobe failed for {media_path}: {detail[-2000:]}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ffprobe returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("ffprobe returned an unexpected JSON shape")
    return payload


def _format_duration(value: Any) -> str:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if seconds < 0:
        return "unknown"
    minutes, remainder = divmod(seconds, 60)
    hours, minutes = divmod(int(minutes), 60)
    if hours:
        return f"{hours:02}:{minutes:02}:{remainder:05.2f}"
    return f"{int(minutes):02}:{remainder:05.2f}"


def _media_report(
    path: Path,
    *,
    ffprobe_path: str | None = None,
    timeout: float = DEFAULT_FFPROBE_TIMEOUT,
) -> str:
    payload = _run_ffprobe(path, ffprobe_path=ffprobe_path, timeout=timeout)
    media_format = payload.get("format")
    if not isinstance(media_format, dict):
        media_format = {}
    lines = [f"# Media probe: {path}"]
    if "filename" in media_format:
        lines.append(f"format.filename={media_format['filename']}")
    duration = media_format.get("duration")
    lines.append(f"format.duration={duration if duration is not None else 'unknown'}s ({_format_duration(duration)})")
    size = media_format.get("size")
    if size is not None:
        try:
            lines.append(f"format.size={int(size)} bytes ({_human_size(int(size))})")
        except (TypeError, ValueError):
            lines.append(f"format.size={size}")

    streams = payload.get("streams", [])
    if not isinstance(streams, list) or not streams:
        lines.append("streams: none")
        return "\n".join(lines)

    for stream in streams:
        if not isinstance(stream, dict):
            continue
        # Render every field requested from ffprobe so no queried metadata is
        # lost just because a stream has an unusual codec or field combination.
        kind = str(stream.get("codec_type", "unknown"))
        index = stream.get("index", "?")
        fields = [f"{field}={stream[field]}" for field in _STREAM_FIELDS if field in stream]
        lines.append(f"stream #{index} [{kind}]: " + " | ".join(fields))
    return "\n".join(lines)


def _walk_project(root: Path, max_scanned_files: int) -> Iterator[Path]:
    """Yield bounded project files while pruning generated and dependency trees."""
    scanned = 0
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name not in _SKIP_DIRS and not name.startswith("."))
        for filename in sorted(files):
            scanned += 1
            if scanned > max_scanned_files:
                return
            yield Path(current) / filename


def _read_package(root: Path) -> tuple[dict[str, Any] | None, str | None]:
    package_path = root / "package.json"
    if not package_path.is_file():
        return None, None
    try:
        data = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"package.json could not be read: {exc}"
    if not isinstance(data, dict):
        return None, "package.json does not contain a JSON object"
    return data, None


def _dependencies(package: dict[str, Any] | None) -> tuple[int, list[str]]:
    if package is None:
        return 0, []
    names: set[str] = set()
    relevant: set[str] = set()
    for group_name in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        group = package.get(group_name)
        if not isinstance(group, dict):
            continue
        names.update(str(name) for name in group)
        for name in group:
            lowered = str(name).lower()
            if "remotion" in lowered or "hyperframes" in lowered or lowered in {"ffmpeg", "fluent-ffmpeg"}:
                relevant.add(str(name))
    return len(names), sorted(relevant)


def probe_project(
    project_dir: str | Path,
    *,
    max_sources: int = 8,
    max_assets: int = 20,
    max_scanned_files: int = 20_000,
    max_chars: int = 8_000,
) -> str:
    """Return a bounded summary of a local Remotion/HyperFrames-like project.

    Source digests are heuristic; they list likely scene/media tags but do not
    execute JavaScript or evaluate conditional JSX. The scan skips common build
    and dependency directories and stops after ``max_scanned_files`` entries.
    """
    root = Path(project_dir)
    if not root.is_dir():
        raise NotADirectoryError(f"Project directory not found: {root}")
    for name, value, maximum in (
        ("max_sources", max_sources, 50),
        ("max_assets", max_assets, 200),
        ("max_scanned_files", max_scanned_files, 100_000),
        ("max_chars", max_chars, 100_000),
    ):
        if not isinstance(value, int) or value < 1 or value > maximum:
            raise ValueError(f"{name} must be between 1 and {maximum}")
    if max_chars < 256:
        raise ValueError("max_chars must be at least 256")

    package, package_error = _read_package(root)
    # Keep no more than the configured cap, then look ahead once to distinguish
    # an exactly-full scan from one that actually omitted at least one file.
    walker = _walk_project(root, max_scanned_files + 1)
    all_files = list(islice(walker, max_scanned_files))
    scan_capped = next(walker, None) is not None
    sources = sorted(
        (path for path in all_files if path.suffix.lower() in _SOURCE_SUFFIXES),
        key=lambda path: path.as_posix().lower(),
    )
    assets = sorted(
        (path for path in all_files if path.suffix.lower() in _MEDIA_SUFFIXES),
        key=lambda path: path.as_posix().lower(),
    )

    title = root.name or str(root)
    lines = [f"# Project probe: {title}"]
    if scan_capped:
        lines.append(f"scan cap reached ({max_scanned_files} files); source and asset counts may be incomplete")
    if package_error:
        lines.append(f"warning: {package_error}")
    if package is None:
        lines.append("package: package.json not found")
    else:
        lines.append(f"package: {package.get('name', 'unnamed')}@{package.get('version', 'unknown')}")
        dependency_count, relevant = _dependencies(package)
        lines.append(f"dependencies: {dependency_count} unique package(s)")
        if relevant:
            lines.append("video stack: " + ", ".join(relevant))

    lines.append(f"source candidates: {len(sources)} found; showing {min(len(sources), max_sources)}")
    for source_path in sources[:max_sources]:
        relative = source_path.relative_to(root)
        try:
            digest = digest_file(source_path, max_items=10, max_chars=900)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            lines.append(f"- {relative}: digest unavailable ({exc})")
            continue
        # The digest includes the path argument; replace absolute paths with a
        # project-relative one for a shorter, portable report.
        digest = digest.replace(str(source_path), relative.as_posix(), 1)
        lines.append(digest)

    lines.append(f"media assets: {len(assets)} found; showing {min(len(assets), max_assets)}")
    for asset in assets[:max_assets]:
        try:
            size = _human_size(asset.stat().st_size)
        except OSError:
            size = "unavailable"
        lines.append(f"- {asset.relative_to(root).as_posix()} ({size})")

    report = "\n".join(lines)
    if len(report) > max_chars:
        report = report[: max_chars - 32].rstrip() + "\n... report truncated by max_chars."
    return report


def probe_path(
    path: str | Path,
    *,
    ffprobe_path: str | None = None,
    timeout: float = DEFAULT_FFPROBE_TIMEOUT,
    **project_options: Any,
) -> str:
    """Inspect a media file with FFprobe or summarize a project directory."""
    timeout = _positive_timeout(timeout)
    target = Path(path)
    if target.is_dir():
        return probe_project(target, **project_options)
    if target.is_file():
        return _media_report(target, ffprobe_path=ffprobe_path, timeout=timeout)
    raise FileNotFoundError(f"Path not found: {target}")
