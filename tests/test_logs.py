from framediet.logs import compress_ffprobe_json, compress_output

ESC = chr(27)


def test_ansi_sequences_are_removed():
    raw = f"{ESC}[32mRendered 5/90{ESC}[0m\n{ESC}[1mOutput: out.mp4{ESC}[0m"
    out = compress_output(["npx", "remotion", "render"], 0, raw, "")
    assert ESC not in out
    assert "out.mp4" in out


def test_remotion_progress_lines_are_dropped_on_success():
    progress = "\n".join(f"Rendered {i}/90, time remaining: 1s" for i in range(1, 91))
    encoded = "\n".join(f"Encoded {i}/90" for i in range(1, 91))
    raw = f"Composition: Reel\n{progress}\n{encoded}\n+ out/reel.mp4 2.1 MB"
    out = compress_output(["npx", "remotion", "render"], 0, raw, "")
    assert "Rendered 45/90" not in out
    assert "Encoded 45/90" not in out
    assert "out/reel.mp4" in out
    assert len(out.splitlines()) < 10


def test_failure_keeps_diagnostics():
    stderr = "frame=  10\nfoo.mp4: No such file or directory\nframe=  11"
    out = compress_output(["ffmpeg", "-i", "foo.mp4"], 1, "", stderr)
    assert out.startswith("[EXIT 1]")
    assert "No such file or directory" in out


def test_failure_line_survives_long_noise():
    noise = "\n".join(f"progress line {i}" for i in range(500))
    out = compress_output(["tool"], 1, "", noise + "\nFATAL: boom\n" + noise)
    assert "FATAL: boom" in out
    assert len(out.splitlines()) <= 52


def test_empty_output_is_reported():
    assert "no output" in compress_output(["tool"], 3, "", "")


def test_only_progress_is_ok_marker():
    out = compress_output(["ffmpeg"], 0, "", "frame=  10 fps=30\nframe=  20 fps=30")
    assert out.startswith("[OK]")


def test_ffprobe_json_known_shape_is_summarized():
    raw = (
        '{"streams":[{"index":0,"codec_type":"video","codec_name":"h264",'
        '"width":1080,"height":1920,"avg_frame_rate":"30/1"}],'
        '"format":{"filename":"a.mp4","duration":"12.5","size":"1048576"}}'
    )
    out = compress_ffprobe_json(raw)
    assert "1080x1920" in out
    assert "12.500s" in out
    assert "1.00 MiB" in out


def test_ffprobe_json_unknown_fields_are_preserved():
    raw = '{"streams":[{"index":0,"codec_type":"video","tags":{"rotate":"90"}}],"format":{}}'
    out = compress_ffprobe_json(raw)
    assert "rotate" in out


def test_ffprobe_invalid_json_does_not_crash():
    assert compress_ffprobe_json("not json") == "not json"
