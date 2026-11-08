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


def test_success_summary_says_how_much_was_omitted():
    raw = "\n".join(f"key_{i}=value" for i in range(100))
    out = compress_output(["ffprobe", "-show_streams", "a.mp4"], 0, raw, "")
    header = out.splitlines()[0]
    assert "of 100 lines" in header
    assert "`command ffprobe ...`" in header


def test_progress_only_omission_has_no_bypass_hint():
    progress = "\n".join(f"frame={i} fps=30" for i in range(50))
    out = compress_output(["ffmpeg", "-i", "a", "b.mp4"], 0, "", progress + "\nOutput #0, mp4, to 'b.mp4':")
    assert "(50 progress)." in out
    assert "Full output" not in out


def test_success_omits_encoder_statistics_without_full_output_hint():
    raw = "\n".join([
        "frame=  90 fps=30 q=-1.0 Lsize=     250kB time=00:00:03.00 bitrate=683.0kbits/s",
        "[libx264 @ 0x1234] frame I:1 Avg QP:12.00 size: 11234",
        "[libx264 @ 0x1234] kb/s:612.34",
        "[aac @ 0x5678] Qavg: 132.456",
        "video:220kB audio:28kB subtitle:0kB other streams:0kB",
    ])
    out = compress_output(["ffmpeg", "-i", "clip.mp4", "out.mp4"], 0, "", raw)
    assert "Full output" not in out
    assert "libx264" not in out
    assert "Qavg" not in out
    assert "(4 progress)" in out


def test_failed_encode_keeps_encoder_statistics():
    raw = "[libx264 @ 0x1234] frame I:1 Avg QP:12.00 size: 11234"
    out = compress_output(["ffmpeg", "-i", "clip.mp4", "out.mp4"], 1, "", raw)
    assert "libx264" in out


def test_short_success_output_is_complete_without_note():
    out = compress_output(["ffmpeg"], 0, "", "Output #0, mp4, to 'b.mp4':")
    assert out.splitlines()[0] == "[OK] FrameDiet: command completed successfully."


def test_analysis_lines_are_kept_on_success():
    filler = "\n".join(f"[Parsed_astats_0 @ 0x1] Channel stat {i}" for i in range(40))
    raw = f"[blackdetect @ 0x1] black_start:2 black_end:2.3 black_duration:0.3\n{filler}\n[Parsed_astats_0 @ 0x1] Peak level dB: -3.1\n" + filler
    out = compress_output(["ffmpeg", "-i", "a"], 0, "", raw)
    assert "black_start:2" in out
    assert "Peak level dB: -3.1" in out


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
