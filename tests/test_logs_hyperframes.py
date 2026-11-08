"""HyperFrames 0.9.23 render log: excerpts are real lines from bench/fixtures/hyperframes-render.raw.log."""
from framediet.logs import PROGRESS_NOISE, compress_output

CMD = ["npx", "hyperframes", "render"]
BAR = "\u2588" * 6 + "\u2591" * 16

NOISE = [
    f"  {BAR}  25%  Starting frame capture",
    f"  {BAR}  5%  Compiling composition",
    "    27%  Capturing frame 10/300 (6 workers)",
    "    90%  Encoding frame 300/300",
    "    99%  Assembling final video",
    '@hf-progress {"code":"capture","done":10,"total":300,"pct":27}',
    "[initSession:screenshot] page.goto complete (793ms)",
    "[initSession:screenshot] static-frame dedup: disabled (no GSAP tweens (non-GSAP animation)) (903ms)",
    "[BrowserManager] Browser launched (HeadlessChrome/152.0.7977.30, screenshot, headlessShell=true, platform=win32)",
    '[HyperFrames] render runtime fps {"canonicalFps":30,"source":"render-options","rawFpsSource":"render-options","rawFps":30}',
    '[INFO] [Render:trace] {"renderJobId":"x","phase":"compile","status":"start","elapsedMs":18}',
    "[INFO] Calibration: capturing test frame 3/5... {\"renderJobId\":\"x\"}",
    "[INFO] Launching browser for capture calibration... {\"renderJobId\":\"x\"}",
    "[INFO] Initializing calibration session... {\"renderJobId\":\"x\"}",
    '[INFO] streaming-encode gate {"renderJobId":"x","enabled":false,"reason":"multi_worker"}',
    '[INFO] [Render] Encoded frames while capturing {"renderJobId":"x","framesFed":300,"totalFrames":300}',
]

KEEP = [
    "[FrameCapture] Timed out closing browser; forcing browser process shutdown",
    "\u25c7  <tmp>/demo/renders/a.mp4",
    "   29.0 KB \u00b7 10.0s video \u00b7 rendered in 28.2s",
    "Error: Render failed: composition not found",
    "[WARN] [Compiler] Missing font",
    "100%  Render complete",
]


def test_noise_lines_match():
    for line in NOISE:
        assert PROGRESS_NOISE.match(line.strip()), line


def test_result_and_errors_not_matched():
    for line in KEEP:
        assert not PROGRESS_NOISE.match(line.strip()), line


def test_success_keeps_output_path_and_summary():
    raw = "\n".join(NOISE + KEEP[:3])
    out = compress_output(CMD, 0, raw, "")
    assert "<tmp>/demo/renders/a.mp4" in out
    assert "10.0s video" in out
    assert "Capturing frame" not in out
    assert "@hf-progress" not in out
    assert "[initSession:" not in out


def test_failure_keeps_error_drops_progress():
    raw = "\n".join(NOISE * 5 + ["Error: Render failed: composition not found"])
    out = compress_output(CMD, 1, raw, "")
    assert out.startswith("[EXIT 1]")
    assert "composition not found" in out
    assert "@hf-progress" not in out
