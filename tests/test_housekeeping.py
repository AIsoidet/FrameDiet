import os
import subprocess
import sys
from pathlib import Path

import pytest

from framediet.scene_digest import digest_source
from framediet.slim_skill import slim_skill_directory


def test_digest_omits_attribute_less_div_sections():
    source = '<div>\n  <div className="shell">Content</div>\n</div>'
    output = digest_source(source, "Scene.tsx")
    assert not any(line.startswith("Section <div>") and line.endswith(": ") for line in output.splitlines())
    assert 'Section <div> L2: class="shell"' in output


def test_slim_missing_directory_exits_with_code_two(tmp_path: Path):
    source_root = Path(__file__).resolve().parent.parent / "src"
    env = {**os.environ, "PYTHONPATH": str(source_root)}
    missing = tmp_path / "missing-skills"
    result = subprocess.run(
        [sys.executable, "-m", "framediet", "slim", str(missing)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 2
    assert "Directory not found" in result.stderr


def test_slim_reference_comparison_preserves_newlines(tmp_path: Path):
    skill = tmp_path / "SKILL.md"
    original = "# Skill\n\n```text\n" + "line\n" * 25 + "```\n"
    skill.write_text(original, encoding="utf-8", newline="")
    slim_skill_directory(tmp_path, line_threshold=2, apply=True)
    reference = next((tmp_path / "references_diet").glob("*.md"))
    backup = next(tmp_path.glob("SKILL.md.framediet.bak*"))
    skill.write_bytes(backup.read_bytes())
    reference.write_bytes(reference.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(FileExistsError, match="Refusing to overwrite existing reference"):
        slim_skill_directory(tmp_path, line_threshold=2, apply=True)
