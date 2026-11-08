"""Heuristic, line-numbered digests for Remotion and HTML scene source.

This module is a compact source index, not a TypeScript/JSX/HTML parser. It
masks common comments and quoted strings in TSX/JSX mode, and HTML comments in
HTML mode, then reports approximate source ranges and simple attributes. Input
reads and tag scans are capped. JSX expressions, script contents, template
interpolation, regex literals, generated code, and unusual syntax can be misread;
inspect the source before making edits based on a digest.
"""

from __future__ import annotations

import bisect
import codecs
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

_TAG_START = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9:.-]*)\b")
_ATTR_NAME = re.compile(r"[A-Za-z_:][A-Za-z0-9_:.-]*")
_SECTION_TAGS = {
    "div", "section", "article", "main", "header", "footer", "nav", "aside", "figure",
}
_MEDIA_TAGS = {
    "audio", "audioclip", "html5audio", "video", "videoclip", "source", "img", "image",
    "imageclip", "offthreadvideo", "html5video", "staticfile",
}
_VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_COMPOSITION_ATTRS = ("id", "fps", "width", "height", "durationInFrames", "component")
_SEQUENCE_ATTRS = ("name", "from", "durationInFrames", "layout", "showInTimeline")
_MEDIA_ATTRS = (
    "src", "startFrom", "endAt", "trimBefore", "trimAfter", "volume",
    "playbackRate", "muted", "width", "height", "poster",
)
MAX_SOURCE_BYTES = 1_000_000
MAX_SOURCE_CHARS = 1_000_000
MAX_TAGS = 20_000


@dataclass(frozen=True)
class _Tag:
    name: str
    closing: bool
    self_closing: bool
    start: int
    end: int
    start_line: int
    end_line: int
    attrs: dict[str, str]


@dataclass(frozen=True)
class _Element:
    tag: _Tag
    end_line: int


def _blank_preserving_lines(text: str, start: int, end: int) -> None:
    """Replace characters by spaces but keep newline positions stable."""
    for index in range(start, end):
        if text[index] not in "\r\n":
            text[index] = " "


def _mask_comments_and_strings(source: str) -> str:
    """Hide ordinary comments and quoted strings without moving source offsets."""
    view = list(source)
    index = 0
    length = len(source)
    while index < length:
        char = source[index]
        if char in {'"', "'", "`"}:
            quote = char
            start = index
            index += 1
            while index < length:
                if source[index] == "\\":
                    index += 2
                    continue
                if source[index] == quote:
                    index += 1
                    break
                index += 1
            _blank_preserving_lines(view, start, min(index, length))
            continue

        if source.startswith("/*", index):
            start = index
            close = source.find("*/", index + 2)
            index = length if close < 0 else close + 2
            _blank_preserving_lines(view, start, index)
            continue

        if source.startswith("//", index) and (index == 0 or source[index - 1] != ":"):
            start = index
            newline = source.find("\n", index + 2)
            index = length if newline < 0 else newline
            _blank_preserving_lines(view, start, index)
            continue
        index += 1
    return "".join(view)


def _mask_html_comments(source: str) -> str:
    """Hide HTML comments while preserving offsets and line positions."""
    view = list(source)
    index = 0
    while index < len(source):
        start = source.find("<!--", index)
        if start < 0:
            break
        close = source.find("-->", start + 4)
        end = len(source) if close < 0 else close + 3
        _blank_preserving_lines(view, start, end)
        index = end
    return "".join(view)


def _balanced_brace_end(text: str, start: int) -> int:
    """Return the exclusive end of a simple JSX expression beginning with `{`."""
    depth = 0
    quote: str | None = None
    index = start
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'", "`"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return len(text)


def _tag_end(view: str, start: int, after_name: int, *, html_mode: bool = False) -> int:
    """Find a tag's closing `>`, ignoring JSX braces and HTML quoted values."""
    depth = 0
    quote: str | None = None
    index = after_name
    while index < len(view):
        char = view[index]
        if html_mode and quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
        elif html_mode and char in {'"', "'"} and depth == 0:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}" and depth:
            depth -= 1
        elif char == ">" and depth == 0:
            return index + 1
        index += 1
    return len(view)


def _parse_attributes(raw_tag: str, name_end: int, closing: bool) -> dict[str, str]:
    if closing:
        return {}
    attrs: dict[str, str] = {}
    index = name_end
    limit = len(raw_tag) - 1
    while index < limit:
        while index < limit and (raw_tag[index].isspace() or raw_tag[index] == "/"):
            index += 1
        match = _ATTR_NAME.match(raw_tag, index)
        if not match:
            index += 1
            continue
        key = match.group(0)
        index = match.end()
        while index < limit and raw_tag[index].isspace():
            index += 1
        if index >= limit or raw_tag[index] != "=":
            attrs[key] = "true"
            continue
        index += 1
        while index < limit and raw_tag[index].isspace():
            index += 1
        if index >= limit:
            attrs[key] = ""
            continue

        if raw_tag[index] in {'"', "'"}:
            quote = raw_tag[index]
            value_start = index
            index += 1
            while index < limit:
                if raw_tag[index] == "\\":
                    index += 2
                    continue
                if raw_tag[index] == quote:
                    index += 1
                    break
                index += 1
            attrs[key] = raw_tag[value_start:index]
        elif raw_tag[index] == "{":
            value_end = _balanced_brace_end(raw_tag, index)
            attrs[key] = raw_tag[index:value_end]
            index = value_end
        else:
            value_start = index
            while index < limit and not raw_tag[index].isspace() and raw_tag[index] not in "/>" :
                index += 1
            attrs[key] = raw_tag[value_start:index]
    return attrs


def _scan_tags(source: str, view: str, *, html_mode: bool = False) -> tuple[list[_Tag], bool]:
    line_breaks = [index for index, char in enumerate(source) if char == "\n"]

    def line_at(position: int) -> int:
        return bisect.bisect_right(line_breaks, position) + 1

    tags: list[_Tag] = []
    index = 0
    while index < len(view):
        start = view.find("<", index)
        if start < 0:
            break
        match = _TAG_START.match(view, start)
        if not match:
            index = start + 1
            continue
        if len(tags) >= MAX_TAGS:
            return tags, True
        closing = bool(match.group(1))
        name = match.group(2)
        end = _tag_end(view, start, match.end(), html_mode=html_mode)
        raw_tag = source[start:end]
        attrs = _parse_attributes(raw_tag, match.end() - start, closing)
        structural_tag = view[start:end].rstrip()
        self_closing = not closing and (
            structural_tag.endswith("/>") or name.lower() in _VOID_TAGS
        )
        tags.append(
            _Tag(
                name=name,
                closing=closing,
                self_closing=self_closing,
                start=start,
                end=end,
                start_line=line_at(start),
                end_line=line_at(max(start, end - 1)),
                attrs=attrs,
            )
        )
        index = max(end, start + 1)
    return tags, False


def _is_relevant(tag: _Tag) -> bool:
    key = tag.name.lower()
    attrs = {attr.lower() for attr in tag.attrs}
    if key == "div" and not attrs:
        return False
    return (
        key in {"composition", "sequence"}
        or key in _SECTION_TAGS
        or key in _MEDIA_TAGS
        or "id" in attrs
        or "class" in attrs
        or "classname" in attrs
    )


def _elements(tags: Iterable[_Tag], source_line_count: int) -> list[_Element]:
    """Pair simple tag names to estimate element ranges."""
    stacks: dict[str, list[_Tag]] = {}
    found: list[_Element] = []
    for tag in tags:
        key = tag.name.lower()
        if tag.closing:
            stack = stacks.get(key)
            if stack:
                opening = stack.pop()
                # Relevance belongs to the opening tag: a closing tag has no
                # attributes, even when its opening custom component had className/id.
                if _is_relevant(opening):
                    found.append(_Element(opening, tag.end_line))
            continue
        if tag.self_closing:
            if _is_relevant(tag):
                found.append(_Element(tag, tag.end_line))
            continue
        stacks.setdefault(key, []).append(tag)

    for stack in stacks.values():
        for opening in stack:
            if _is_relevant(opening):
                found.append(_Element(opening, source_line_count))
    return sorted(found, key=lambda item: item.tag.start)


def _attribute(attrs: dict[str, str], wanted: str) -> str | None:
    wanted_lower = wanted.lower()
    for name, value in attrs.items():
        if name.lower() == wanted_lower:
            return value
    return None


def _display_attribute(value: str | None, limit: int = 100) -> str | None:
    if value is None:
        return None
    compact = " ".join(value.strip().split())
    if len(compact) > limit:
        compact = compact[: limit - 3] + "..."
    return compact


def _props(attrs: dict[str, str], names: Iterable[str]) -> str:
    pairs = []
    for name in names:
        value = _display_attribute(_attribute(attrs, name))
        if value is not None:
            pairs.append(f"{name}={value}")
    return " ".join(pairs)


def digest_source(
    source: str,
    name: str = "<source>",
    max_items: int = 40,
    max_chars: int = 8000,
    *,
    source_truncated: bool = False,
) -> str:
    """Return a bounded heuristic digest from TSX/JSX/HTML source text.

    The result lists likely Remotion Composition/Sequence tags, media elements,
    and section-like tags with IDs/classes. It is not a parser and does not
    evaluate JSX expressions or infer rendered timing, layout, or visibility.
    """
    if max_items < 1 or max_items > 500:
        raise ValueError("max_items must be between 1 and 500")
    if max_chars < 256 or max_chars > 100_000:
        raise ValueError("max_chars must be between 256 and 100000")
    source_truncated = source_truncated or len(source) > MAX_SOURCE_CHARS
    source = source[:MAX_SOURCE_CHARS]
    html_mode = Path(name).suffix.lower() == ".html"
    view = _mask_html_comments(source) if html_mode else _mask_comments_and_strings(source)
    line_count = source.count("\n") + (1 if source else 0)
    tags, tag_scan_truncated = _scan_tags(source, view, html_mode=html_mode)
    elements = _elements(tags, line_count)
    lines = [
        f"# Scene digest: {name} ({line_count} source lines)",
        "Heuristic tag scan only; verify source before editing.",
    ]
    if source_truncated:
        lines.append(f"Input truncated at the {MAX_SOURCE_CHARS:,}-byte/character scan limit; later source was omitted.")
    if tag_scan_truncated:
        lines.append(f"Tag scan truncated after {MAX_TAGS:,} tags; later tags were omitted.")
    emitted = 0
    omitted = 0

    for element in elements:
        if emitted >= max_items:
            omitted += 1
            continue
        tag = element.tag
        lower = tag.name.lower()
        attrs = tag.attrs
        line_range = f"L{tag.start_line}" if element.end_line == tag.start_line else f"L{tag.start_line}-L{element.end_line}"
        if lower == "composition":
            props = _props(attrs, _COMPOSITION_ATTRS)
            line = f"Composition {line_range}" + (f": {props}" if props else "")
        elif lower == "sequence":
            props = _props(attrs, _SEQUENCE_ATTRS)
            line = f"Sequence {line_range}" + (f": {props}" if props else "")
        elif lower in _MEDIA_TAGS:
            props = _props(attrs, _MEDIA_ATTRS)
            line = f"Media <{tag.name}> {line_range}" + (f": {props}" if props else "")
        else:
            id_value = _display_attribute(_attribute(attrs, "id"))
            class_value = _display_attribute(_attribute(attrs, "class")) or _display_attribute(_attribute(attrs, "className"))
            if lower not in _SECTION_TAGS and id_value is None and class_value is None:
                continue
            details = []
            if id_value is not None:
                details.append(f"id={id_value}")
            if class_value is not None:
                details.append(f"class={class_value}")
            line = f"Section <{tag.name}> {line_range}: " + " ".join(details)

        if sum(len(part) + 1 for part in lines) + len(line) > max_chars:
            omitted += 1
            continue
        lines.append(line)
        emitted += 1

    if omitted:
        lines.append(f"... {omitted} additional matching element(s) omitted by output limits.")
    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[: max_chars - 40].rstrip() + "\n... output truncated."
    return result


def digest_file(path: str | Path, max_items: int = 40, max_chars: int = 8000) -> str:
    """Read a TSX/JSX/HTML file and return its heuristic scene digest.

    At most :data:`MAX_SOURCE_BYTES` are read. Larger inputs include an explicit
    truncation note. The input is read as UTF-8 and never modified.
    """
    source_path = Path(path)
    if source_path.suffix.lower() not in {".tsx", ".jsx", ".html"}:
        raise ValueError("digest_file supports only .tsx, .jsx, and .html source files")
    with source_path.open("rb") as handle:
        raw = handle.read(MAX_SOURCE_BYTES + 1)
    source_truncated = len(raw) > MAX_SOURCE_BYTES
    raw = raw[:MAX_SOURCE_BYTES]
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    source = decoder.decode(raw, final=not source_truncated)
    return digest_source(
        source,
        str(source_path),
        max_items=max_items,
        max_chars=max_chars,
        source_truncated=source_truncated,
    )
