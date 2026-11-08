"""Compact word-aligned transcript formatting."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

_NUMERIC_TEXT = re.compile(r"^[+-]?[0-9]+(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?$", re.IGNORECASE)


def is_whisper_json(data: Any) -> bool:
    """Return whether a parsed JSON value looks like Whisper or caption data."""
    if isinstance(data, dict):
        segments = data.get("segments")
        if isinstance(segments, list) and segments:
            first = segments[0]
            if isinstance(first, dict) and (
                "text" in first or isinstance(first.get("words"), list)
            ) and ("start" in first or "startMs" in first):
                return True
        words = data.get("words")
        if isinstance(words, list) and words:
            first = words[0]
            return isinstance(first, dict) and ("word" in first or "text" in first) and (
                "start" in first or "startMs" in first
            )
    if isinstance(data, list) and data and isinstance(data[0], dict):
        sample = data[0]
        return ("word" in sample or "text" in sample) and (
            "start" in sample or "startMs" in sample
        )
    return False


def _time_ms(seconds_value: Any = None, milliseconds_value: Any = None) -> int:
    """Convert either a seconds or millisecond field to the nearest ms."""
    if milliseconds_value is not None:
        value = float(milliseconds_value)
    else:
        value = float(seconds_value or 0.0) * 1000
    if not math.isfinite(value):
        raise ValueError("Transcript timestamps must be finite numbers")
    return int(round(value))


def _format_time(seconds_value: Any, milliseconds_value: Any, unit: str) -> str:
    ms = _time_ms(seconds_value, milliseconds_value)
    return str(ms) if unit == "ms" else f"{ms / 1000:.3f}"


UNKNOWN_TIME = "?"


def _format_optional_time(item: dict[str, Any], key: str, unit: str) -> str:
    """Format a start/end value, or ``?`` when the source has no timing for it.

    WhisperX leaves ``start``/``end`` off words it could not align (for example
    some numbers). Writing ``0`` for those would present a made-up timestamp.
    """
    seconds_value, milliseconds_value = item.get(key), item.get(f"{key}Ms")
    if seconds_value is None and milliseconds_value is None:
        return UNKNOWN_TIME
    return _format_time(seconds_value, milliseconds_value, unit)


def _format_word(value: Any) -> str:
    word = str(value).strip()
    # Keep the compact bare form for ordinary tokens and quote ambiguous text.
    if (
        not word
        or any(char.isspace() for char in word)
        or any(char in word for char in "[]\"\\")
        or word in {"true", "false", "null"}
        or _NUMERIC_TEXT.fullmatch(word)
    ):
        return json.dumps(word, ensure_ascii=False)
    return word


def _word_token(item: dict[str, Any], unit: str) -> str:
    text = item.get("word", item.get("text", ""))
    start = _format_optional_time(item, "start", unit)
    end = _format_optional_time(item, "end", unit)
    if start == UNKNOWN_TIME and end == UNKNOWN_TIME:
        return f"{_format_word(text)}[{UNKNOWN_TIME}]"
    return f"{_format_word(text)}[{start}-{end}]"


def _with_unknown_note(lines: list[str]) -> str:
    """Join lines; explain ``?`` in the header only when the body uses it."""
    body = "\n".join(lines[1:])
    if re.search(r"\[\?\]|\[\?-|-\?\]", body):
        lines = [lines[0] + "; ?=no timing in source"] + lines[1:]
    return "\n".join(lines)


def compress_whisper(data: str | Path | dict[str, Any] | list[Any], unit: str = "ms") -> str:
    """Format Whisper/Faster-Whisper or Remotion caption data compactly.

    Timestamps are rounded to the nearest millisecond by default. Optional
    fields such as confidence scores are omitted; this is a context view, not
    a lossless replacement for the source JSON.
    """
    if unit not in {"ms", "s"}:
        raise ValueError("unit must be 'ms' or 's'")
    if isinstance(data, (str, Path)):
        raw = json.loads(Path(data).read_text(encoding="utf-8"))
    else:
        raw = data

    lines = [f"# FrameDiet transcript (unit={unit}; word[start-end])"]
    if isinstance(raw, list):
        tokens = [_word_token(item, unit) for item in raw if isinstance(item, dict)]
        lines.append(" ".join(tokens))
        return _with_unknown_note(lines)
    if not isinstance(raw, dict):
        raise ValueError("Transcript JSON must be an object or a list of caption objects")

    segments = raw.get("segments")
    if isinstance(segments, list) and segments:
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            start = _format_optional_time(segment, "start", unit)
            end = _format_optional_time(segment, "end", unit)
            speaker = segment.get("speaker")
            label = f"{start}-{end}" + (f" {speaker}" if isinstance(speaker, str) and speaker else "")
            words = segment.get("words")
            if isinstance(words, list) and words:
                tokens = [_word_token(word, unit) for word in words if isinstance(word, dict)]
                lines.append(f"[{label}] " + " ".join(tokens))
            else:
                lines.append(f"[{label}] {str(segment.get('text', '')).strip()}")
        return _with_unknown_note(lines)

    words = raw.get("words")
    if isinstance(words, list):
        lines.append(" ".join(_word_token(word, unit) for word in words if isinstance(word, dict)))
    return _with_unknown_note(lines)
