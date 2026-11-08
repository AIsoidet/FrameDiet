"""Create a uniformly sampled contact sheet with the local FFmpeg tools."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _default_font_file() -> Path | None:
    """Find a common system font when FFmpeg's Fontconfig lookup is unavailable."""
    candidates: list[Path] = []
    windows_dir = os.environ.get("WINDIR")
    if windows_dir:
        candidates.append(Path(windows_dir) / "Fonts" / "arial.ttf")
    candidates.extend(
        [
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
            Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        ]
    )
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _filter_path(path: Path) -> str:
    """Escape a font path for an FFmpeg filter option value."""
    return path.as_posix().replace(":", r"\:").replace("'", r"\'")


def create_contact_sheet(
    video_path: str | Path,
    output_path: str | Path = "framediet_sheet.jpg",
    cols: int = 3,
    rows: int = 3,
    thumb_width: int = 384,
    overwrite: bool = False,
    font_file: str | Path | None = None,
) -> str:
    """Render one timestamped grid of uniformly sampled video frames.

    FFmpeg and FFprobe must be installed. The sheet reduces the number of image
    attachments, but image-token savings depend on the receiving vision model.
    """
    source = Path(video_path)
    destination = Path(output_path)
    if not source.is_file():
        raise FileNotFoundError(f"Video file not found: {source}")
    if cols < 1 or rows < 1 or cols * rows > 36 or thumb_width < 64 or thumb_width > 1024:
        raise ValueError("Use 1-36 tiles total and a thumbnail width from 64 to 1024 pixels")
    if cols * thumb_width > 4096:
        raise ValueError("Total contact-sheet width must not exceed 4096 pixels")
    if rows * thumb_width > 2048:
        raise ValueError("Grid height is too large; rows multiplied by thumbnail width must not exceed 2048")
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Output already exists: {destination} (pass --overwrite to replace it)")

    selected_font = Path(font_file) if font_file is not None else _default_font_file()
    if font_file is not None and not selected_font.is_file():
        raise FileNotFoundError(f"Font file not found: {selected_font}")

    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise FileNotFoundError("FrameDiet sheet needs ffmpeg and ffprobe on PATH")

    probe = subprocess.run(
        [
            ffprobe, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(source),
        ],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if probe.returncode:
        raise RuntimeError(f"ffprobe failed: {probe.stderr.strip() or probe.stdout.strip()}")
    try:
        duration = float(probe.stdout.strip())
    except ValueError as exc:
        raise RuntimeError(f"Could not read video duration from ffprobe: {probe.stdout!r}") from exc
    if duration <= 0:
        raise ValueError("Video duration must be greater than zero")

    total_tiles = cols * rows
    sample_rate = total_tiles / duration
    font_option = f"fontfile='{_filter_path(selected_font)}':" if selected_font else ""
    filter_chain = (
        f"fps={sample_rate:.8f},"
        f"scale={thumb_width}:-2,"
        f"drawtext={font_option}text='F\\:%{{n}} T\\:%{{pts\\:hms}}':x=8:y=8:fontsize=18:"
        "fontcolor=white:box=1:boxcolor=black@0.85:boxborderw=6,"
        f"tile={cols}x{rows}:nb_frames={total_tiles}:padding=8:margin=8:color=black"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error",
        *( ["-y"] if overwrite else ["-n"] ),
        "-i", str(source), "-vf", filter_chain,
        "-frames:v", "1", "-q:v", "4", str(destination),
    ]
    result = subprocess.run(command, capture_output=True, text=True, errors="replace", check=False)
    if result.returncode:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip() or result.stdout.strip()}")
    if not destination.is_file():
        raise RuntimeError("ffmpeg completed without creating a contact sheet")
    return f"Contact sheet created: {destination} ({cols}x{rows}, samples spaced across about {duration:.2f}s)"
