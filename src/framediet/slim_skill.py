"""Preview or extract long fenced code blocks from agent skill files."""

from __future__ import annotations

import hashlib
import re
import tempfile
from pathlib import Path
from typing import Callable

_FENCE_OPEN = re.compile(r"^( {0,3})(?P<fence>`{3,}|~{3,})(?P<info>[^\r\n]*)$")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    ) as handle:
        temp_path = Path(handle.name)
        handle.write(content)
        handle.flush()
    temp_path.replace(path)


def _backup_path(path: Path) -> Path:
    candidate = path.with_name(path.name + ".framediet.bak")
    index = 1
    while candidate.exists():
        candidate = path.with_name(path.name + f".framediet.bak.{index}")
        index += 1
    return candidate


def _replace_long_fences(
    content: str,
    threshold: int,
    make_reference: Callable[[str, int], str],
) -> tuple[str, list[tuple[str, str, int]]]:
    lines = content.splitlines(keepends=True)
    output: list[str] = []
    extracted: list[tuple[str, str, int]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        opener_text = line.rstrip("\r\n")
        opener = _FENCE_OPEN.match(opener_text)
        if not opener:
            output.append(line)
            index += 1
            continue

        fence = opener.group("fence")
        marker = fence[0]
        # CommonMark forbids backticks in an opening backtick fence's info string.
        if marker == "`" and "`" in opener.group("info"):
            output.append(line)
            index += 1
            continue
        close_re = re.compile(r"^ {0,3}" + re.escape(marker) + r"{" + str(len(fence)) + r",}[ \t]*$")
        close_index = index + 1
        while close_index < len(lines) and not close_re.match(lines[close_index].rstrip("\r\n")):
            close_index += 1
        if close_index >= len(lines):
            output.extend(lines[index:])
            break

        block = "".join(lines[index:close_index + 1])
        line_count = len(block.splitlines())
        if line_count >= threshold:
            digest = hashlib.sha256(block.encode("utf-8")).hexdigest()[:12]
            filename = f"code_example_{digest}.md"
            extracted.append((filename, block, line_count))
            replacement = make_reference(filename, line_count)
            if block.endswith("\r\n"):
                replacement += "\r\n"
            elif block.endswith(("\n", "\r")):
                replacement += block[-1]
            output.append(replacement)
        else:
            output.append(block)
        index = close_index + 1
    return "".join(output), extracted


def slim_skill_directory(
    target_dir: str | Path,
    line_threshold: int = 25,
    apply: bool = False,
) -> str:
    """Find long fenced blocks; write references only when ``apply`` is true.

    Existing backups and reference files are never overwritten. A dry run is
    the default so a caller can review the proposed edits first.
    """
    root = Path(target_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Directory not found: {root}")
    if line_threshold < 1:
        raise ValueError("line_threshold must be positive")

    markdown_files = sorted(set(root.rglob("SKILL.md")) | set(root.rglob("CLAUDE.md")))
    if not markdown_files:
        return "No SKILL.md or CLAUDE.md files found."

    report: list[str] = []
    for markdown_path in markdown_files:
        with markdown_path.open("r", encoding="utf-8", newline="") as source:
            original = source.read()

        def make_reference(filename: str, line_count: int) -> str:
            return (
                f"> **FrameDiet reference** ({line_count} lines): `references_diet/{filename}`. "
                "Open this file when the full example is needed."
            )

        revised, extracted = _replace_long_fences(original, line_threshold, make_reference)
        if not extracted:
            continue

        if not apply:
            report.append(f"Preview: {markdown_path} - {len(extracted)} code block(s) would be extracted")
            continue

        ref_dir = markdown_path.parent / "references_diet"
        for filename, block, _ in extracted:
            reference_path = ref_dir / filename
            if reference_path.exists():
                with reference_path.open("r", encoding="utf-8", newline="") as reference:
                    existing = reference.read()
                if existing != block:
                    raise FileExistsError(f"Refusing to overwrite existing reference: {reference_path}")
            else:
                _atomic_write(reference_path, block)

        backup = _backup_path(markdown_path)
        _atomic_write(backup, original)
        _atomic_write(markdown_path, revised)
        report.append(
            f"Updated: {markdown_path} - {len(extracted)} block(s); backup: {backup.name}"
        )

    return "\n".join(report) if report else "No code blocks met the extraction threshold."
