"""Deterministic FFmpeg-based checks for rendered video files.

This module reports objective signals (detected black intervals, low-motion
intervals, cropdetect observations, and audio level measurements). It does not
prove that a composition is visually correct or that text is inside a safe
zone. In particular, cropdetect only estimates removable borders; it is not a
general content bounding-box or layout validator.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

_NUMBER = r"-?(?:\d+(?:\.\d*)?|\.\d+)"
_BLACK_RE = re.compile(
    rf"black_start:\s*(?P<start>{_NUMBER})"
    rf"(?:\s+black_end:\s*(?P<end>{_NUMBER}))?"
    rf"(?:\s+black_duration:\s*(?P<duration>{_NUMBER}))?"
)
_FREEZE_RE = re.compile(rf"freeze_(?P<kind>start|end|duration):\s*(?P<value>{_NUMBER})")
_CROP_RE = re.compile(r"crop=(?P<width>\d+):(?P<height>\d+):(?P<x>\d+):(?P<y>\d+)")
_PEAK_RE = re.compile(rf"Peak level dB:\s*(?P<value>-?(?:\d+(?:\.\d*)?|\.\d+)|-inf)", re.IGNORECASE)
_CLIPPED_RE = re.compile(r"Number of clipped samples:\s*(?P<value>\d+(?:\.\d+)?)", re.IGNORECASE)


@dataclass(frozen=True)
class TimeInterval:
    start: float
    end: float | None = None
    duration: float | None = None

    def as_dict(self) -> dict[str, float | None]:
        return asdict(self)


@dataclass(frozen=True)
class CropObservation:
    width: int
    height: int
    x: int
    y: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class VideoQAReport:
    """A compact QA result; ``PASS`` means only that configured checks passed."""

    file: str
    duration_seconds: float
    width: int
    height: int
    fps: float | None
    audio_streams: int
    black_intervals: tuple[TimeInterval, ...]
    freeze_intervals: tuple[TimeInterval, ...]
    crop_observations: tuple[CropObservation, ...]
    audio_peak_dbfs: float | None
    clipped_samples: int | None
    warnings: tuple[str, ...]
    notes: tuple[str, ...] = ()

    @property
    def status(self) -> str:
        return "WARN" if self.warnings else "PASS"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "file": self.file,
            "duration_seconds": self.duration_seconds,
            "video": {"width": self.width, "height": self.height, "fps": self.fps},
            "audio_streams": self.audio_streams,
            "black_intervals": [item.as_dict() for item in self.black_intervals],
            "freeze_intervals": [item.as_dict() for item in self.freeze_intervals],
            "crop_observations": [item.as_dict() for item in self.crop_observations],
            "audio_peak_dbfs": self.audio_peak_dbfs,
            "clipped_samples": self.clipped_samples,
            "warnings": list(self.warnings),
            "notes": list(self.notes),
        }

    def to_text(self) -> str:
        """Return a one-line agent-facing summary plus warning details."""
        parts = [
            f"[QA {self.status}]",
            f"duration={self.duration_seconds:.3f}s",
            f"video={self.width}x{self.height}",
            f"fps={self.fps:.3f}" if self.fps is not None else "fps=unknown",
            f"black={len(self.black_intervals)}",
            f"freeze={len(self.freeze_intervals)}",
        ]
        if self.crop_observations:
            crop = self.crop_observations[-1]
            parts.append(f"crop_observed={crop.width}x{crop.height}+{crop.x}+{crop.y}")
        else:
            parts.append("crop_observed=none")
        if self.audio_streams:
            parts.append(
                f"audio_peak={self.audio_peak_dbfs:.1f}dBFS"
                if self.audio_peak_dbfs is not None else "audio_peak=unavailable"
            )
            parts.append(
                f"clipped_samples={self.clipped_samples}"
                if self.clipped_samples is not None else "clipped_samples=unavailable"
            )
        else:
            parts.append("audio=none")
        summary = " | ".join(parts)
        details = [f"- {warning}" for warning in self.warnings]
        details.extend(f"- note: {note}" for note in self.notes)
        return "\n".join([summary, *details])


def _resolve_tools(ffmpeg_path: str | None, ffprobe_path: str | None) -> tuple[str, str]:
    ffmpeg = ffmpeg_path or shutil.which("ffmpeg")
    ffprobe = ffprobe_path or shutil.which("ffprobe")
    if not ffmpeg:
        raise FileNotFoundError("ffmpeg was not found; install FFmpeg or pass ffmpeg_path")
    if not ffprobe:
        raise FileNotFoundError("ffprobe was not found; install FFmpeg or pass ffprobe_path")
    return ffmpeg, ffprobe


def _run(command: list[str], timeout: float | None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Timed out running {Path(command[0]).name}") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not start {command[0]}: {exc}") from exc


def _probe(video: Path, ffprobe: str, timeout: float | None) -> dict[str, Any]:
    command = [
        ffprobe,
        "-v", "error",
        "-show_entries",
        "format=duration:stream=index,codec_type,width,height,avg_frame_rate,r_frame_rate,sample_rate,channels",
        "-of", "json",
        str(video),
    ]
    result = _run(command, timeout)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"ffprobe failed for {video}: {detail}")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ffprobe returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise RuntimeError("ffprobe returned an unexpected JSON shape")
    return data


def _parse_fps(stream: dict[str, Any]) -> float | None:
    value = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
    if not isinstance(value, str) or value in {"0/0", "N/A", ""}:
        return None
    try:
        fps = float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None
    return fps if math.isfinite(fps) and fps > 0 else None


def _parse_black_events(log: str) -> tuple[TimeInterval, ...]:
    events: list[TimeInterval] = []
    for match in _BLACK_RE.finditer(log):
        start = float(match.group("start"))
        end_text = match.group("end")
        duration_text = match.group("duration")
        end = float(end_text) if end_text is not None else None
        duration = float(duration_text) if duration_text is not None else (
            max(0.0, end - start) if end is not None else None
        )
        events.append(TimeInterval(start=start, end=end, duration=duration))
    return tuple(events)


def _parse_freeze_events(log: str) -> tuple[TimeInterval, ...]:
    events: list[dict[str, float | None]] = []
    for match in _FREEZE_RE.finditer(log):
        kind = match.group("kind")
        value = float(match.group("value"))
        if kind == "start":
            events.append({"start": value, "end": None, "duration": None})
        elif events:
            events[-1][kind] = value
        else:
            # Defensive fallback for partial or unusual FFmpeg logs.
            events.append({"start": value, "end": value if kind == "end" else None, "duration": value if kind == "duration" else None})
    return tuple(TimeInterval(**event) for event in events)


def _parse_crop_observations(log: str) -> tuple[CropObservation, ...]:
    observations: list[CropObservation] = []
    seen: set[tuple[int, int, int, int]] = set()
    for match in _CROP_RE.finditer(log):
        item = tuple(int(match.group(name)) for name in ("width", "height", "x", "y"))
        if item not in seen:
            seen.add(item)
            observations.append(CropObservation(*item))
    return tuple(observations)


def _parse_audio_metrics(log: str) -> tuple[float | None, int | None]:
    peak_matches = list(_PEAK_RE.finditer(log))
    peak: float | None = None
    if peak_matches:
        try:
            peak = float(peak_matches[-1].group("value"))
        except ValueError:
            peak = None

    clipped_matches = list(_CLIPPED_RE.finditer(log))
    clipped: int | None = None
    if clipped_matches:
        try:
            clipped = int(round(float(clipped_matches[-1].group("value"))))
        except ValueError:
            clipped = None
    return peak, clipped


def _format_time(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{whole_seconds:02}.{millis:03}"


EDGE_SECONDS = 0.5
MAX_EDGE_HOLD_SECONDS = 3.0


def _span(item: TimeInterval, duration: float) -> tuple[float, float]:
    end = item.end if item.end is not None else duration
    return item.start, max(item.start, end)


def _describe(items: list[TimeInterval], duration: float) -> str:
    shown = ", ".join(
        f"{_format_time(start)} - {_format_time(end)} ({end - start:.2f}s)"
        for start, end in (_span(item, duration) for item in items[:5])
    )
    more = f", +{len(items) - 5} more" if len(items) > 5 else ""
    return shown + more


def _merge_adjacent(items: tuple[TimeInterval, ...], duration: float, gap: float = 0.05) -> list[TimeInterval]:
    """Join intervals that touch: FFmpeg may split one long still into two."""
    merged: list[TimeInterval] = []
    for item in sorted(items, key=lambda value: value.start):
        if merged:
            last_start, last_end = _span(merged[-1], duration)
            if merged[-1].end is not None and item.start - last_end <= gap:
                end = item.end
                merged[-1] = TimeInterval(
                    start=last_start, end=end,
                    duration=None if end is None else end - last_start,
                )
                continue
        merged.append(item)
    return merged


def classify_intervals(
    black: tuple[TimeInterval, ...],
    freezes: tuple[TimeInterval, ...],
    duration: float,
    freeze_warn_duration: float = 0.75,
) -> tuple[list[str], list[str]]:
    """Split detections into warnings and notes about likely intentional shots.

    A still or black interval touching the start or end (title card, end card,
    fade) and no longer than 3 s is a note, and so is a still in the middle
    shorter than ``freeze_warn_duration`` (a held beat in motion graphics).
    Everything else, and anything covering half the video, is a warning.
    Notes are still printed: the tool cannot know what was intended.
    """
    def at_edge(item: TimeInterval) -> bool:
        start, end = _span(item, duration)
        return (start <= EDGE_SECONDS or end >= duration - EDGE_SECONDS) and end - start <= MAX_EDGE_HOLD_SECONDS

    def most_of_video(item: TimeInterval) -> bool:
        start, end = _span(item, duration)
        return end - start >= duration / 2

    warnings: list[str] = []
    notes: list[str] = []
    black, freezes = _merge_adjacent(black, duration), _merge_adjacent(freezes, duration)

    black_warn = [item for item in black if most_of_video(item) or not at_edge(item)]
    black_edge = [item for item in black if item not in black_warn]
    if black_warn:
        warnings.append(f"black intervals: {len(black_warn)} ({_describe(black_warn, duration)})")
    if black_edge:
        notes.append(f"black at start/end, likely a fade: {_describe(black_edge, duration)}")

    freeze_warn, freeze_edge, freeze_short = [], [], []
    for item in freezes:
        start, end = _span(item, duration)
        if most_of_video(item):
            freeze_warn.append(item)
        elif at_edge(item):
            freeze_edge.append(item)
        elif end - start < freeze_warn_duration:
            freeze_short.append(item)
        else:
            freeze_warn.append(item)
    if freeze_warn:
        warnings.append(f"freeze intervals: {len(freeze_warn)} ({_describe(freeze_warn, duration)})")
    if freeze_edge:
        notes.append(f"still at start/end, likely a title or end card: {_describe(freeze_edge, duration)}")
    if freeze_short:
        notes.append(
            f"short stills under {freeze_warn_duration:g}s, likely held beats: {_describe(freeze_short, duration)}"
        )
    return warnings, notes


def run_video_qa(
    video_path: str | Path,
    *,
    black_min_duration: float = 0.1,
    black_pixel_threshold: float = 0.10,
    freeze_min_duration: float = 0.5,
    freeze_noise_db: float = -60.0,
    crop_limit: int = 24,
    audio_silence_warn_dbfs: float = -60.0,
    audio_peak_warn_dbfs: float = -1.0,
    timeout: float | None = 1800,
    ffmpeg_path: str | None = None,
    ffprobe_path: str | None = None,
    freeze_warn_duration: float = 0.75,
) -> VideoQAReport:
    """Run black/freeze/crop and optional audio checks against one video.

    ``cropdetect`` output is reported as a heuristic observation only. It does
    not calculate a general content bounding box, detect clipping of a subject,
    or prove that content fits a 3:4 or 9:16 safe area.

    A report is ``WARN`` when a configured black/freeze/audio check flags a
    condition or when the audio peak cannot be parsed. Clipped-sample count is
    shown when FFmpeg exposes it. Absence of an audio track is reported as
    ``audio=none`` and is not itself a warning.
    """
    source = Path(video_path)
    if not source.is_file():
        raise FileNotFoundError(f"Video file not found: {source}")
    numeric = {
        "black_min_duration": black_min_duration,
        "black_pixel_threshold": black_pixel_threshold,
        "freeze_min_duration": freeze_min_duration,
        "freeze_noise_db": freeze_noise_db,
        "audio_silence_warn_dbfs": audio_silence_warn_dbfs,
        "audio_peak_warn_dbfs": audio_peak_warn_dbfs,
        "freeze_warn_duration": freeze_warn_duration,
    }
    if any(not math.isfinite(value) for value in numeric.values()):
        raise ValueError("QA thresholds must be finite numbers")
    if black_min_duration <= 0 or freeze_min_duration <= 0 or freeze_warn_duration < 0:
        raise ValueError("black/freeze durations must be positive (freeze_warn_duration may be 0)")
    if not 0 < black_pixel_threshold <= 1:
        raise ValueError("black_pixel_threshold must be in (0, 1]")
    if not -120 <= freeze_noise_db <= 0:
        raise ValueError("freeze_noise_db must be between -120 and 0")
    if not -120 <= audio_silence_warn_dbfs <= 0 or not -120 <= audio_peak_warn_dbfs <= 0:
        raise ValueError("audio dBFS thresholds must be between -120 and 0")
    if not 0 <= crop_limit <= 255:
        raise ValueError("crop_limit must be between 0 and 255")
    if timeout is not None and (not math.isfinite(timeout) or timeout <= 0):
        raise ValueError("timeout must be positive or None")

    ffmpeg, ffprobe = _resolve_tools(ffmpeg_path, ffprobe_path)
    probe = _probe(source, ffprobe, timeout)
    streams = [stream for stream in probe.get("streams", []) if isinstance(stream, dict)]
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if not video_streams:
        raise ValueError(f"No video stream found in {source}")
    video_stream = video_streams[0]
    try:
        duration = float(probe.get("format", {}).get("duration"))
        width, height = int(video_stream["width"]), int(video_stream["height"])
    except (TypeError, ValueError, KeyError) as exc:
        raise RuntimeError("ffprobe did not return duration and video dimensions") from exc
    if not math.isfinite(duration) or duration <= 0 or width <= 0 or height <= 0:
        raise RuntimeError("ffprobe returned invalid duration or video dimensions")

    video_filter = (
        f"blackdetect=d={black_min_duration:g}:pix_th={black_pixel_threshold:g},"
        f"freezedetect=n={freeze_noise_db:g}dB:d={freeze_min_duration:g},fps=1,"
        f"cropdetect=limit={crop_limit}:round=2:reset=0"
    )
    command = [ffmpeg, "-hide_banner", "-nostats", "-v", "info", "-i", str(source), "-map", "0:v:0", "-vf", video_filter]
    if audio_streams:
        command.extend(["-map", "0:a:0", "-af", "astats=metadata=0:reset=0"])
    command.extend(["-f", "null", "-"])
    result = _run(command, timeout)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"FFmpeg QA analysis failed for {source}: {detail[-4000:]}")

    log = result.stderr + "\n" + result.stdout
    black = _parse_black_events(log)
    freezes = _parse_freeze_events(log)
    crops = _parse_crop_observations(log)
    peak, clipped = _parse_audio_metrics(log) if audio_streams else (None, None)

    warnings, notes = classify_intervals(black, freezes, duration, freeze_warn_duration)
    if audio_streams:
        if peak is None:
            warnings.append("audio peak could not be parsed from FFmpeg astats output")
        else:
            if not math.isfinite(peak) or peak <= audio_silence_warn_dbfs:
                shown_peak = "-inf" if not math.isfinite(peak) else f"{peak:.1f}"
                warnings.append(f"audio peak {shown_peak} dBFS indicates silence or near-silence")
            elif peak > audio_peak_warn_dbfs:
                warnings.append(f"audio peak {peak:.1f} dBFS exceeds warning threshold {audio_peak_warn_dbfs:.1f} dBFS")
            if clipped is not None and clipped > 0:
                warnings.append(f"audio reports {clipped} clipped sample(s)")

    return VideoQAReport(
        file=str(source),
        duration_seconds=duration,
        width=width,
        height=height,
        fps=_parse_fps(video_stream),
        audio_streams=len(audio_streams),
        black_intervals=black,
        freeze_intervals=freezes,
        crop_observations=crops,
        audio_peak_dbfs=peak,
        clipped_samples=clipped,
        warnings=tuple(warnings),
        notes=tuple(notes),
    )
