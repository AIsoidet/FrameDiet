"""Small, dependency-free TOON 4.4 encoder for JSON-shaped data.

Tabular encoding is used only when an array is uniform according to the TOON
specification. Non-uniform arrays use list form, so optional fields are never
silently discarded.
"""

from __future__ import annotations

import json
import math
import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

_SAFE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
_NUMERIC_TEXT = re.compile(r"^[+-]?[0-9]+(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?$", re.IGNORECASE)
_CONTROL = re.compile(r"[\x00-\x1f]")


def _escape_quoted(value: str) -> str:
    out: list[str] = []
    for char in value:
        code = ord(char)
        if char == "\\":
            out.append("\\\\")
        elif char == '"':
            out.append('\\"')
        elif char == "\n":
            out.append("\\n")
        elif char == "\r":
            out.append("\\r")
        elif char == "\t":
            out.append("\\t")
        elif code < 0x20:
            out.append(f"\\u{code:04x}")
        elif 0xD800 <= code <= 0xDFFF:
            raise ValueError("TOON cannot encode unpaired Unicode surrogates")
        else:
            out.append(char)
    return '"' + "".join(out) + '"'


def _encode_key(key: str) -> str:
    return key if _SAFE_KEY.fullmatch(key) else _escape_quoted(key)


def _encode_string(value: str) -> str:
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise ValueError("TOON cannot encode unpaired Unicode surrogates")
    must_quote = (
        value == ""
        or value != value.strip(" \t")
        or value in {"true", "false", "null"}
        or _NUMERIC_TEXT.fullmatch(value) is not None
        or any(char in value for char in ':"\\[]{},')
        or _CONTROL.search(value) is not None
        or value.startswith(("-", "#"))
    )
    return _escape_quoted(value) if must_quote else value


def _normalise(value: Any, precision: int | None) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return round(value, precision) if precision is not None else value
    if isinstance(value, list):
        return [_normalise(item, precision) for item in value]
    if isinstance(value, tuple):
        return [_normalise(item, precision) for item in value]
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("TOON object keys must be strings")
        return {key: _normalise(item, precision) for key, item in value.items()}
    raise ValueError(f"Unsupported JSON value: {type(value).__name__}")


def _encode_number(value: int | float) -> str:
    if isinstance(value, int):
        return str(value)
    if value == 0:
        return "0"
    absolute = abs(value)
    shortest = repr(value).lower()
    if 1e-6 <= absolute < 1e21:
        text = format(Decimal(shortest), "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text
    if "e" in shortest:
        mantissa, exponent = shortest.split("e", 1)
        sign = "+" if not exponent.startswith("-") else "-"
        digits = exponent.lstrip("+-0") or "0"
        return f"{mantissa}e{sign}{digits}"
    return shortest


def _encode_primitive(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return _encode_number(value)
    if isinstance(value, str):
        return _encode_string(value)
    raise TypeError("Expected a primitive JSON value")


def _field_tree(records: Sequence[Mapping[str, Any]]) -> list[tuple[str, Any]] | None:
    """Return a recursive tabular field tree, or None when list form is required."""
    if not records or any(not record for record in records):
        return None
    first_keys = list(records[0])
    expected = set(first_keys)
    if any(set(record) != expected for record in records[1:]):
        return None

    tree: list[tuple[str, Any]] = []
    for key in first_keys:
        values = [record[key] for record in records]
        if all(_is_primitive(item) for item in values):
            tree.append((key, None))
            continue
        if all(isinstance(item, dict) and item for item in values):
            nested = _field_tree(values)
            if nested is not None:
                tree.append((key, nested))
                continue
        return None
    return tree


def _is_primitive(value: Any) -> bool:
    return value is None or isinstance(value, (str, bool, int, float))


def _field_header(tree: Sequence[tuple[str, Any]]) -> str:
    result = []
    for key, nested in tree:
        part = _encode_key(key)
        if nested is not None:
            part += "{" + _field_header(nested) + "}"
        result.append(part)
    return ",".join(result)


def _flatten_record(record: Mapping[str, Any], tree: Sequence[tuple[str, Any]]) -> list[str]:
    values: list[str] = []
    for key, nested in tree:
        value = record[key]
        if nested is None:
            values.append(_encode_primitive(value))
        else:
            values.extend(_flatten_record(value, nested))
    return values


def _keyed_tree(value: Mapping[str, Any]) -> list[tuple[str, Any]] | None:
    if len(value) < 2 or any(not isinstance(item, dict) or not item for item in value.values()):
        return None
    return _field_tree(list(value.values()))


def _indent(depth: int) -> str:
    return "  " * depth


def _encode_tabular(
    records: Sequence[Mapping[str, Any]],
    tree: Sequence[tuple[str, Any]],
    depth: int,
    key: str | None,
) -> list[str]:
    prefix = _encode_key(key) if key is not None else ""
    lines = [f"{_indent(depth)}{prefix}[{len(records)}]{{{_field_header(tree)}}}:"]
    lines.extend(_indent(depth + 1) + ",".join(_flatten_record(record, tree)) for record in records)
    return lines


def _encode_keyed(value: Mapping[str, Any], tree: Sequence[tuple[str, Any]], depth: int, key: str | None) -> list[str]:
    prefix = _encode_key(key) if key is not None else ""
    lines = [f"{_indent(depth)}{prefix}[{len(value)}:]{{{_field_header(tree)}}}:"]
    for entry_key, record in value.items():
        row = _encode_key(str(entry_key)) + ": " + ",".join(_flatten_record(record, tree))
        lines.append(_indent(depth + 1) + row)
    return lines


def _encode_object_field(key: str, value: Any, depth: int) -> list[str]:
    prefix = _indent(depth) + _encode_key(key)
    if _is_primitive(value):
        return [prefix + ": " + _encode_primitive(value)]
    if isinstance(value, dict):
        if not value:
            return [prefix + ":"]
        keyed = _keyed_tree(value)
        if keyed is not None:
            return _encode_keyed(value, keyed, depth, key)
        lines = [prefix + ":"]
        lines.extend(_encode_object(value, depth + 1))
        return lines
    if isinstance(value, list):
        if not value:
            return [prefix + ": []"]
        if all(_is_primitive(item) for item in value):
            row = ",".join(_encode_primitive(item) for item in value)
            return [f"{prefix}[{len(value)}]: {row}"]
        if all(isinstance(item, dict) for item in value):
            tree = _field_tree(value)
            if tree is not None:
                return _encode_tabular(value, tree, depth, key)
        lines = [f"{prefix}[{len(value)}]:"]
        for item in value:
            lines.extend(_encode_list_item(item, depth + 1))
        return lines
    raise ValueError(f"Unsupported value for key {key!r}")


def _encode_object(value: Mapping[str, Any], depth: int) -> list[str]:
    lines: list[str] = []
    for key, item in value.items():
        lines.extend(_encode_object_field(key, item, depth))
    return lines


def _encode_list_item(value: Any, depth: int) -> list[str]:
    prefix = _indent(depth) + "-"
    if _is_primitive(value):
        return [prefix + " " + _encode_primitive(value)]
    if isinstance(value, list):
        if not value:
            return [prefix + " []"]
        if all(_is_primitive(item) for item in value):
            return [prefix + f" [{len(value)}]: " + ",".join(_encode_primitive(item) for item in value)]
        lines = [prefix + f" [{len(value)}]:"]
        for item in value:
            lines.extend(_encode_list_item(item, depth + 1))
        return lines
    if isinstance(value, dict):
        if not value:
            return [prefix]
        lines: list[str] = []
        first_key = next(iter(value))
        first_value = value[first_key]
        lines.extend(_encode_object_field(first_key, first_value, depth + 1))
        # A list-item object's first field must sit on the hyphen line.
        first_lines = lines
        first_line = first_lines[0].lstrip()
        first_lines[0] = prefix + " " + first_line
        for key, item in list(value.items())[1:]:
            first_lines.extend(_encode_object_field(key, item, depth + 1))
        return first_lines
    raise ValueError(f"Unsupported array item: {type(value).__name__}")


def to_toon(
    data: str | Path | Any,
    name: str = "timeline",
    precision: int | None = None,
) -> str:
    """Encode JSON-shaped data as TOON 4.4 text.

    ``precision`` explicitly rounds floating-point values. With its default
    ``None``, values are emitted with a shortest round-trippable representation.
    Non-uniform arrays use TOON list form instead of filling absent fields.
    """
    if precision is not None and precision < 0:
        raise ValueError("precision must be zero or greater")
    if isinstance(data, (str, Path)):
        data = json.loads(Path(data).read_text(encoding="utf-8"))
    value = _normalise(data, precision)

    if isinstance(value, dict):
        keyed = _keyed_tree(value)
        if keyed is not None:
            return "\n".join(_encode_keyed(value, keyed, 0, None))
        return "\n".join(_encode_object(value, 0))
    if isinstance(value, list):
        if not value:
            return "[]"
        if all(_is_primitive(item) for item in value):
            return f"{_encode_key(name)}[{len(value)}]: " + ",".join(_encode_primitive(item) for item in value)
        if all(isinstance(item, dict) for item in value):
            tree = _field_tree(value)
            if tree is not None:
                return "\n".join(_encode_tabular(value, tree, 0, name))
        lines = [f"{_encode_key(name)}[{len(value)}]:"]
        for item in value:
            lines.extend(_encode_list_item(item, 1))
        return "\n".join(lines)
    if isinstance(value, str) and value.startswith("\ufeff"):
        return _escape_quoted(value)
    return _encode_primitive(value)


def slim_html_dom(html_content: str) -> str:
    """Replace large HTML payloads with markers while retaining structure."""
    output = re.sub(r"\bd\s*=\s*([\"']).{60,}?\1", 'd="[SVG_PATH]"', html_content, flags=re.DOTALL)
    output = re.sub(
        r"\b(src|href)\s*=\s*([\"'])data:[^;\"']+;base64,.*?\2",
        lambda match: f'{match.group(1)}="[BASE64_DATA_URI]"',
        output,
        flags=re.IGNORECASE | re.DOTALL,
    )
    output = re.sub(
        r"<script\b([^>]*)>[\s\S]*?</script\s*>",
        r"<script\1>[SCRIPT_CONTENT_OMITTED]</script>",
        output,
        flags=re.IGNORECASE,
    )
    output = re.sub(
        r"<style\b([^>]*)>[\s\S]*?</style\s*>",
        r"<style\1>[STYLE_CONTENT_OMITTED]</style>",
        output,
        flags=re.IGNORECASE,
    )
    return output
