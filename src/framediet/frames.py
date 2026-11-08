"""Extract bounded, timestamped JPEG previews from video files.

This module uses the local FFmpeg programs and the Python standard library.
It reports source and output dimensions, but does not estimate vision-token
costs: those depend on the receiving model and its image-resolution tier.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from itertools import islice
from pathlib import Path
from typing import Any, Iterable

MAX_FRAME_COUNT = 36
MIN_PREVIEW_WIDTH = 64
MAX_PREVIEW_WIDTH = 768
DEFAULT_FFPROBE_TIMEOUT = 30.0
DEFAULT_FFMPEG_TIMEOUT = 60.0


def _positive_timeout(value: float, name: str) -> float:
    try:
        timeout = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be a positive finite number of seconds") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError(f"{name} must be a positive finite number of seconds")
    return timeout


@dataclass(frozen=True)
class FramePreview:
    """Details for one extracted preview image."""

    timestamp_seconds: float
    output_path: str
    source_width: int
    source_height: int
    preview_width: int
    preview_height: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _VideoInfo:
    duration: float
    width: int
    height: int


def _video_info(
    source: Path,
    ffprobe: str,
    timeout: float = DEFAULT_FFPROBE_TIMEOUT,
) -> _VideoInfo:
    timeout = _positive_timeout(timeout, "ffprobe_timeout")
    command = [
        ffprobe,
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "format=duration:stream=width,height",
        "-of", "json",
        str(source),
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
        raise RuntimeError(f"ffprobe timed out after {timeout:g}s while probing {source}") from exc
    if result.returncode:
        raise RuntimeError(f"ffprobe failed: {result.stderr.strip() or result.stdout.strip()}")
    try:
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        duration = float(data["format"]["duration"])
        width = int(stream["width"])
        height = int(stream["height"])
    except (json.JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise RuntimeError("ffprobe did not return a valid duration and first video-stream dimensions") from exc
    if not math.isfinite(duration) or duration <= 0 or width <= 0 or height <= 0:
        raise ValueError("Video duration and dimensions must be positive finite values")
    return _VideoInfo(duration=duration, width=width, height=height)


def _preview_size(source_width: int, source_height: int, max_width: int) -> tuple[int, int]:
    width = min(source_width, max_width)
    height = max(2, round(source_height * width / source_width))
    # Keep the dimensions even for broad codec compatibility. The rounding is
    # at most one pixel and preserves the source aspect ratio to preview scale.
    if height % 2:
        height += 1
    return width, height


def _seconds(value: Any) -> float:
    try:
        timestamp = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid frame timestamp: {value!r}") from exc
    if not math.isfinite(timestamp) or timestamp < 0:
        raise ValueError(f"Frame timestamps must be finite non-negative seconds: {value!r}")
    return timestamp


def extract_frames(
    video_path: str | Path,
    timestamps: Iterable[float],
    output_dir: str | Path = "framediet_frames",
    *,
    thumb_width: int = 384,
    jpeg_qscale: int = 8,
    overwrite: bool = False,
    ffprobe_timeout: float = DEFAULT_FFPROBE_TIMEOUT,
    ffmpeg_timeout: float = DEFAULT_FFMPEG_TIMEOUT,
) -> list[FramePreview]:
    """Extract at most 36 requested timestamps to small JPEG previews.

    Args:
        video_path: Input video readable by FFmpeg.
        timestamps: Requested presentation times in seconds. A time equal to
            the clip duration is rejected because there may be no frame there.
        output_dir: Destination directory, created if needed.
        thumb_width: Maximum preview width; accepted range is 64–768 pixels.
        jpeg_qscale: FFmpeg MJPEG qscale, where smaller numbers are higher
            quality. This is not a JPEG quality percentage; accepted range 2–31.
        overwrite: Replace destination images only when explicitly true.
        ffprobe_timeout: Maximum seconds for the metadata probe (default 30).
        ffmpeg_timeout: Maximum seconds for each extracted frame (default 60).

    Returns:
        One :class:`FramePreview` per requested timestamp, in the same order.

    Raises:
        FileNotFoundError: If the input video or FFmpeg programs are missing.
        FileExistsError: If an output already exists and overwrite is false.
        ValueError: If a timestamp or option is out of range.
        RuntimeError: If FFprobe or FFmpeg cannot extract a requested frame.
    """
    source = Path(video_path)
    if not source.is_file():
        raise FileNotFoundError(f"Video file not found: {source}")
    if not MIN_PREVIEW_WIDTH <= thumb_width <= MAX_PREVIEW_WIDTH:
        raise ValueError(f"thumb_width must be between {MIN_PREVIEW_WIDTH} and {MAX_PREVIEW_WIDTH}")
    if not 2 <= jpeg_qscale <= 31:
        raise ValueError("jpeg_qscale must be between 2 and 31 (lower values mean higher quality)")
    ffprobe_timeout = _positive_timeout(ffprobe_timeout, "ffprobe_timeout")
    ffmpeg_timeout = _positive_timeout(ffmpeg_timeout, "ffmpeg_timeout")

    requested = list(islice(iter(timestamps), MAX_FRAME_COUNT + 1))
    if len(requested) > MAX_FRAME_COUNT:
        raise ValueError(f"At most {MAX_FRAME_COUNT} timestamps can be extracted per call")
    parsed_times = [_seconds(value) for value in requested]
    if not parsed_times:
        return []

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise FileNotFoundError("Frame extraction needs ffmpeg and ffprobe on PATH")

    info = _video_info(source, ffprobe, timeout=ffprobe_timeout)
    for timestamp in parsed_times:
        if timestamp >= info.duration:
            raise ValueError(
                f"Timestamp {timestamp:.3f}s is outside the video duration ({info.duration:.3f}s)"
            )

    destination = Path(output_dir)
    preview_width, preview_height = _preview_size(info.width, info.height, thumb_width)
    output_paths = [
        destination / f"frame_{index:02d}_{round(timestamp * 1000):010d}ms.jpg"
        for index, timestamp in enumerate(parsed_times, start=1)
    ]
    if not overwrite:
        existing = next((path for path in output_paths if path.exists()), None)
        if existing is not None:
            raise FileExistsError(f"Output already exists: {existing} (pass overwrite=True to replace it)")

    destination.mkdir(parents=True, exist_ok=True)
    previews: list[FramePreview] = []
    for timestamp, output_path in zip(parsed_times, output_paths):
        temporary_path: Path | None = None
        try:
            # Render to a temporary JPEG first so a failed extraction never
            # leaves a partial image at the requested destination path.
            with tempfile.NamedTemporaryFile(
                dir=destination, prefix=".framediet-frame-", suffix=".jpg", delete=False
            ) as temporary:
                temporary_path = Path(temporary.name)

            command = [
                ffmpeg,
                "-hide_banner", "-loglevel", "error",
                "-y",
                "-ss", f"{timestamp:.6f}",
                "-i", str(source),
                "-map", "0:v:0",
                "-frames:v", "1",
                "-vf", f"scale={preview_width}:{preview_height}:flags=lanczos",
                "-q:v", str(jpeg_qscale),
                "-f", "image2",
                str(temporary_path),
            ]
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    errors="replace",
                    check=False,
                    timeout=ffmpeg_timeout,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    f"ffmpeg timed out after {ffmpeg_timeout:g}s while extracting frame at {timestamp:.3f}s"
                ) from exc
            if result.returncode:
                raise RuntimeError(
                    f"ffmpeg failed at {timestamp:.3f}s: {result.stderr.strip() or result.stdout.strip()}"
                )
            if not temporary_path.is_file() or temporary_path.stat().st_size == 0:
                raise RuntimeError(f"ffmpeg produced no frame at {timestamp:.3f}s")

            if overwrite:
                os.replace(temporary_path, output_path)
                temporary_path = None
            else:
                try:
                    # Hard-link creation is atomic and fails if another process
                    # created this destination after our earlier preflight.
                    os.link(temporary_path, output_path)
                except FileExistsError:
                    raise FileExistsError(
                        f"Output already exists: {output_path} (pass overwrite=True to replace it)"
                    ) from None
                temporary_path.unlink()
                temporary_path = None

            previews.append(
                FramePreview(
                    timestamp_seconds=timestamp,
                    output_path=str(output_path),
                    source_width=info.width,
                    source_height=info.height,
                    preview_width=preview_width,
                    preview_height=preview_height,
                )
            )
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    return previews
