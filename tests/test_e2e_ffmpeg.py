import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
pytestmark = pytest.mark.skipif(not FFMPEG or not FFPROBE, reason="ffmpeg and ffprobe are required")
ROOT = Path(__file__).resolve().parent.parent
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False, timeout=90, env=ENV)


def _font_file() -> Path | None:
    candidates = []
    if os.environ.get("WINDIR"):
        candidates.append(Path(os.environ["WINDIR"]) / "Fonts" / "arial.ttf")
    candidates.extend([
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ])
    return next((path for path in candidates if path.is_file()), None)


def _generate_clip(path: Path, sections: list[tuple[str, float]]) -> Path:
    font_file = _font_file()
    command = [FFMPEG, "-hide_banner", "-loglevel", "error", "-y"]
    for source, duration in sections:
        if source == "black":
            input_spec = f"color=c=black:s=160x90:r=10:d={duration}"
        elif source == "title":
            input_spec = f"color=c=black:s=160x90:r=10:d={duration}"
        else:
            input_spec = f"testsrc2=size=160x90:rate=10:duration={duration}"
        command.extend(["-f", "lavfi", "-i", input_spec])

    filters = []
    for index, (source, _) in enumerate(sections):
        if source == "title":
            if font_file is None:
                pytest.skip("No system font available for the title card fixture")
            font_path = font_file.as_posix().replace(":", r"\:")
            filters.append(
                f"[{index}:v]drawtext=fontfile='{font_path}':text=TITLE:fontcolor=white:fontsize=14:x=10:y=10,format=yuv420p[v{index}]"
            )
        else:
            filters.append(f"[{index}:v]format=yuv420p[v{index}]")
    concat_inputs = "".join(f"[v{index}]" for index in range(len(sections)))
    filters.append(f"{concat_inputs}concat=n={len(sections)}:v=1:a=0[v]")
    command.extend([
        "-filter_complex", ";".join(filters), "-map", "[v]", "-an",
        "-c:v", "mpeg4", "-q:v", "5", str(path),
    ])
    result = _run(command)
    assert result.returncode == 0, result.stderr
    assert path.is_file()
    return path


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    return _run([sys.executable, "-m", "framediet", *args])


@pytest.fixture
def black_clip(tmp_path: Path) -> Path:
    return _generate_clip(tmp_path / "black-insert.mp4", [("moving", 1.0), ("black", 0.4), ("moving", 1.0)])


def test_qa_warns_on_mid_video_black_and_strict_exits_one(black_clip: Path):
    report = _cli("qa", str(black_clip))
    assert report.returncode == 0, report.stderr
    assert "[QA WARN]" in report.stdout
    assert "black intervals: 1" in report.stdout

    strict = _cli("qa", str(black_clip), "--strict")
    assert strict.returncode == 1
    assert "[QA WARN]" in strict.stdout


def test_qa_reports_initial_title_card_as_note(tmp_path: Path):
    clip = _generate_clip(tmp_path / "title-card.mp4", [("title", 2.0), ("moving", 3.0)])
    report = _cli("qa", str(clip))
    assert report.returncode == 0, report.stderr
    assert "[QA PASS]" in report.stdout
    assert "note:" in report.stdout
    assert "WARN" not in report.stdout


def test_frames_writes_preview_files(black_clip: Path, tmp_path: Path):
    output_dir = tmp_path / "frames"
    result = _cli("frames", str(black_clip), "0.5", "-o", str(output_dir))
    assert result.returncode == 0, result.stderr
    assert list(output_dir.glob("*.jpg"))


def test_sheet_writes_image_when_drawtext_is_available(black_clip: Path, tmp_path: Path):
    filters = _run([FFMPEG, "-filters"])
    if "drawtext" not in filters.stdout + filters.stderr:
        pytest.skip("ffmpeg build has no drawtext filter")
    output = tmp_path / "sheet.jpg"
    result = _cli("sheet", str(black_clip), "-o", str(output))
    assert result.returncode == 0, result.stderr
    assert output.is_file() and output.stat().st_size > 0


def test_probe_reports_display_rotation(tmp_path: Path):
    source = _generate_clip(tmp_path / "source.mp4", [("moving", 1.0)])
    rotated = tmp_path / "rotated.mp4"
    result = _run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-display_rotation", "90", "-i", str(source), "-c", "copy", str(rotated)])
    assert result.returncode == 0, result.stderr
    report = _cli("probe", str(rotated))
    assert report.returncode == 0, report.stderr
    assert "WARN" in report.stdout and "rotation=90" in report.stdout


def test_exec_encode_starts_with_ok(black_clip: Path, tmp_path: Path):
    output = tmp_path / "encoded.mp4"
    result = _cli("exec", "--", FFMPEG, "-hide_banner", "-y", "-i", str(black_clip), "-c:v", "mpeg4", "-q:v", "5", str(output))
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("[OK] FrameDiet: command completed successfully.")
    assert output.is_file()
