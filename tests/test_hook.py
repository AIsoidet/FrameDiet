import json

import pytest

from framediet import cli
from framediet.cli import install_claude_hook, is_safe_media_command


@pytest.mark.parametrize("command", [
    "ffmpeg -i a.mp4 b.mp4",
    "ffmpeg -y -i a.mp4 -c:v libx264 -crf 20 b.mp4",
    "ffmpeg -i a.mp4 -vf scale=720:-2 -an b.mp4 -y",
    "yt-dlp https://example.com/v",
    "yt-dlp -f best -o out.mp4 https://example.com/v",
    "npx remotion render src/index.tsx Reel out.mp4",
    "npx hyperframes render",
    "npx --yes hyperframes@0.9.23 render -o out.mp4",
    "npx -y remotion@4.0.1 render a b c",
    "npx @remotion/cli render src/index.ts Main out.mp4",
    "npx --package=hyperframes@0.9.23 hyperframes render out.mp4",
    "npx -p hyperframes@0.9.23 hyperframes render out.mp4",
    "hyperframes render -o a.mp4",
    "remotion render a b c",
    "bunx hyperframes@latest render",
    "pnpm dlx --yes hyperframes@0.9.23 render out.mp4",
    "pnpm exec remotion still",
    "manim -pql scene.py Intro",
    r"C:\tools\ffmpeg.exe -i a.mp4 b.mp4",
])
def test_progress_heavy_media_commands_are_rewritten(command):
    assert is_safe_media_command(command)


@pytest.mark.parametrize("command", [
    # The printed output is the data the agent asked for.
    "ffprobe -v error -show_streams a.mp4",
    "ffprobe -of json -show_format a.mp4",
    "ffmpeg -version",
    "ffmpeg -filters",
    "ffmpeg -hide_banner -codecs",
    "ffmpeg -i a.mp4",
    "ffmpeg -i a.mp4 -af astats -f null -",
    "ffmpeg -i a.mp4 -vf blackdetect=d=0.1 -f null /dev/null",
    "ffmpeg -i a.mp4 -af volumedetect -f null NUL",
    "ffmpeg -i a.mp4 -f null -",
    "ffmpeg -i a.mp4 -af ebur128 out.wav",
    "whisper audio.mp3 --model small",
    "yt-dlp -F https://example.com/v",
    "yt-dlp --dump-json https://example.com/v",
    "yt-dlp --print title https://example.com/v",
    "yt-dlp --help",
    "npx remotion compositions src/index.tsx",
    "npx --yes hyperframes@0.9.23 --help",
    "npx -y remotion compositions",
    "npx remotion studio",
    "npx remotion --help",
    "npx remotion render --help",
    "manim cfg show",
    "command ffmpeg -i a.mp4 b.mp4",
])
def test_data_producing_commands_are_left_alone(command):
    assert not is_safe_media_command(command)


@pytest.mark.parametrize("command", [
    "",
    "ls -la",
    "ffmpeg -i a.mp4 b.mp4 && rm -rf x",
    "ffmpeg -i a.mp4 b.mp4 | tee log",
    "ffmpeg -i a.mp4 b.mp4 > log.txt",
    "ffmpeg -i $(cat f) b.mp4",
    "echo hi; ffmpeg -i a.mp4 b.mp4",
    "framediet exec -- ffmpeg -i a b",
    "npx prettier --write .",
    "ffmpeg -i 'unterminated",
])
def test_compound_or_other_commands_are_left_alone(command):
    assert not is_safe_media_command(command)


def test_hook_emits_updated_input(capsys):
    cli._write_hook_decision({"tool_name": "Bash", "tool_input": {"command": "ffmpeg -i a b", "description": "d"}})
    data = json.loads(capsys.readouterr().out)
    out = data["hookSpecificOutput"]
    assert out["hookEventName"] == "PreToolUse"
    assert out["updatedInput"]["command"] == "framediet exec -- ffmpeg -i a b"
    assert out["updatedInput"]["description"] == "d"
    assert "permissionDecision" not in out


def test_hook_is_silent_for_other_tools_and_commands(capsys):
    cli._write_hook_decision({"tool_name": "Read", "tool_input": {"file_path": "x"}})
    cli._write_hook_decision({"tool_name": "Bash", "tool_input": {"command": "ls"}})
    cli._write_hook_decision({"tool_name": "Bash", "tool_input": "oops"})
    assert capsys.readouterr().out == ""


def test_install_is_idempotent_and_keeps_existing_settings(tmp_path):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}}), encoding="utf-8")
    install_claude_hook(tmp_path)
    install_claude_hook(tmp_path)
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["permissions"] == {"allow": ["Bash(ls)"]}
    assert len(data["hooks"]["PreToolUse"]) == 1


def test_install_rejects_malformed_settings(tmp_path):
    settings = tmp_path / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        install_claude_hook(tmp_path)
