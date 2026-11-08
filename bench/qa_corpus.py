#!/usr/bin/env python3
"""Summarize FrameDiet QA JSON reports for the approved external corpus.

Usage:
    python -I bench/qa_corpus.py C:\\Temp\\fd-corpus\\framediet-0.3-2026-11-08

The input directory must contain ``sources.json``, ``ffprobe/*.json`` and
``qa/*.json`` as produced by the T1 survey commands. No video is opened here.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any


DEFAULT_THRESHOLDS = ("0.5", "0.75", "1.0")
DEFAULT_THRESHOLD = "0.75"


def _field(obj: dict[str, Any], *names: str) -> Any:
    """Read a field from PowerShell or Python JSON casing."""
    for name in names:
        if name in obj:
            return obj[name]
    lowered = {key.lower(): value for key, value in obj.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def _threshold_token(value: str) -> str:
    return value.replace(".", "p")


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _fps(stream: dict[str, Any]) -> str:
    value = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
    if not isinstance(value, str) or value in {"0/0", "N/A", ""}:
        return "?"
    try:
        return f"{float(Fraction(value)):.3g}"
    except (ValueError, ZeroDivisionError):
        return "?"


def _clean_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _load_video(corpus: Path, item: dict[str, Any], thresholds: tuple[str, ...]) -> dict[str, Any]:
    filename = _field(item, "file", "name")
    category = _field(item, "category", "type") or "unspecified"
    if not isinstance(filename, str):
        raise ValueError("Every sources.json entry needs a file name")
    stem = Path(filename).stem

    probe = _read_json(corpus / "ffprobe" / f"{filename}.json")
    streams = probe.get("streams", [])
    if not isinstance(streams, list):
        raise ValueError(f"Invalid stream list for {filename}")
    videos = [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"]
    audios = [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "audio"]
    if not videos:
        raise ValueError(f"No video stream in ffprobe JSON for {filename}")
    video = videos[0]
    duration = float(probe.get("format", {}).get("duration"))

    reports: dict[str, dict[str, Any]] = {}
    for threshold in thresholds:
        token = _threshold_token(threshold)
        path = corpus / "qa" / f"{stem}--freeze-{token}.json"
        report = _read_json(path)
        for key in ("status", "warnings", "notes"):
            if key not in report:
                raise ValueError(f"{path} is missing {key!r}")
        reports[threshold] = report

    return {
        "file": filename,
        "category": str(category),
        "duration": duration,
        "resolution": f"{video.get('width', '?')}x{video.get('height', '?')}",
        "fps": _fps(video),
        "audio": len(audios),
        "reports": reports,
    }


def _warn(report: dict[str, Any]) -> bool:
    return report.get("status") == "WARN"


def _freeze_warning_count(report: dict[str, Any]) -> int:
    for warning in report.get("warnings", []):
        match = re.match(r"freeze intervals: (\d+)", warning)
        if match:
            return int(match.group(1))
    return 0


def _print_video_table(videos: list[dict[str, Any]], thresholds: tuple[str, ...]) -> None:
    print("## Per video")
    print()
    print("| File | Type | Length | Video / fps / audio | Status 0.5 / 0.75 / 1.0 s | Notes 0.5 / 0.75 / 1.0 s | Warnings at 0.75 s (# + text) | Notes at 0.75 s (# + text) |")
    print("|---|---|---:|---|---|---|---|---|")
    for video in videos:
        reports = video["reports"]
        statuses = "/".join(reports[t].get("status", "?") for t in thresholds)
        note_counts = "/".join(str(len(reports[t].get("notes", []))) for t in thresholds)
        default = reports[DEFAULT_THRESHOLD]
        warning_items = default.get("warnings", [])
        note_items = default.get("notes", [])
        warnings = f"{len(warning_items)}: " + ("; ".join(warning_items) or "—")
        notes = f"{len(note_items)}: " + ("; ".join(note_items) or "—")
        specs = f"{video['resolution']} / {video['fps']} / {video['audio']} audio"
        print(
            f"| {_clean_cell(video['file'])} | {_clean_cell(video['category'])} | "
            f"{video['duration']:.2f} s | {specs} | {statuses} | {note_counts} | "
            f"{_clean_cell(warnings)} | {_clean_cell(notes)} |"
        )


def _print_type_table(videos: list[dict[str, Any]], thresholds: tuple[str, ...]) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for video in videos:
        grouped[video["category"]].append(video)

    print()
    print("## By type")
    print()
    print("| Type | n | WARN 0.5 / 0.75 / 1.0 s | WARN share at 0.75 s | Mean notes at 0.75 s |")
    print("|---|---:|---|---:|---:|")
    for category, group in sorted(grouped.items()):
        warn_counts = [sum(_warn(video["reports"][t]) for video in group) for t in thresholds]
        notes_mean = sum(len(video["reports"][DEFAULT_THRESHOLD].get("notes", [])) for video in group) / len(group)
        rate = warn_counts[1] / len(group) * 100
        counts = " / ".join(f"{count}/{len(group)}" for count in warn_counts)
        print(f"| {_clean_cell(category)} | {len(group)} | {counts} | {rate:.0f}% | {notes_mean:.2f} |")


def _print_threshold_changes(videos: list[dict[str, Any]], thresholds: tuple[str, ...]) -> None:
    default = DEFAULT_THRESHOLD
    print()
    print("## Shifts relative to the 0.75 s threshold")
    print()
    print("Videos with WARN and freeze intervals are counted separately: audio or black WARNs can keep a video's status.")
    print()
    print("| Threshold | Videos with WARN | Freeze WARN intervals, total | Videos: new / gone WARN vs 0.75 s | Freeze intervals: added / removed vs 0.75 s |")
    print("|---:|---:|---:|---:|---:|")
    for threshold in thresholds:
        warn_videos = sum(_warn(video["reports"][threshold]) for video in videos)
        freeze_total = sum(_freeze_warning_count(video["reports"][threshold]) for video in videos)
        if threshold == default:
            video_delta = "—"
            freeze_delta = "—"
        else:
            new = sum(not _warn(video["reports"][default]) and _warn(video["reports"][threshold]) for video in videos)
            gone = sum(_warn(video["reports"][default]) and not _warn(video["reports"][threshold]) for video in videos)
            added_freezes = sum(
                max(0, _freeze_warning_count(video["reports"][threshold]) - _freeze_warning_count(video["reports"][default]))
                for video in videos
            )
            removed_freezes = sum(
                max(0, _freeze_warning_count(video["reports"][default]) - _freeze_warning_count(video["reports"][threshold]))
                for video in videos
            )
            video_delta = f"{new} / {gone}"
            freeze_delta = f"{added_freezes} / {removed_freezes}"
        print(f"| {threshold} s | {warn_videos}/{len(videos)} | {freeze_total} | {video_delta} | {freeze_delta} |")


def render(corpus: Path, thresholds: tuple[str, ...]) -> None:
    if DEFAULT_THRESHOLD not in thresholds:
        raise ValueError(f"Threshold list must include the default {DEFAULT_THRESHOLD}")
    manifest = _read_json(corpus / "sources.json")
    items = _field(manifest, "files")
    if not isinstance(items, list) or not items:
        raise ValueError("sources.json needs a non-empty files list")
    videos = [_load_video(corpus, item, thresholds) for item in items if isinstance(item, dict)]
    if len(videos) != len(items):
        raise ValueError("Every sources.json entry must be an object")
    _print_video_table(videos, thresholds)
    _print_type_table(videos, thresholds)
    _print_threshold_changes(videos, thresholds)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path, help="Directory containing sources.json, ffprobe/, and qa/")
    parser.add_argument("--thresholds", nargs="+", default=list(DEFAULT_THRESHOLDS))
    parser.add_argument("--output", type=Path, help="Also write the generated Markdown table as UTF-8")
    args = parser.parse_args()
    try:
        if args.output:
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture):
                render(args.corpus, tuple(args.thresholds))
            output = capture.getvalue()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8", newline="\n")
            sys.stdout.write(output)
        else:
            render(args.corpus, tuple(args.thresholds))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
