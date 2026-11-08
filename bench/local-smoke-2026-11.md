# Local smoke run (2026-11-08)

This records read-only checks on existing local media. The source videos are outside this repository and are not copied here. No render command, project script, or test suite was run.

## Synthetic `framediet bench`

Token counts use the cached `cl100k_base` encoding. They are a tokenizer proxy and measure the included tool-output fixtures, not total conversation savings.

| Fixture | Raw chars | Compact chars | Char reduction | Raw proxy tokens | Compact proxy tokens | Token reduction |
|---|---:|---:|---:|---:|---:|---:|
| Whisper word timestamps (50 words) | 6,634 | 969 | 85.4% | 2,047 | 463 | 77.4% |
| Keyframe timeline (60 rows) | 3,634 | 2,428 | 33.2% | 1,868 | 1,318 | 29.4% |
| FFmpeg render log (183 lines) | 14,507 | 102 | 99.3% | 7,009 | 34 | 99.5% |

## FrameDiet QA on existing videos

Both runs used the default thresholds: black interval 0.1 s, freeze interval 0.5 s, freeze noise -60 dB, and audio peak warning above -1.0 dBFS. `cropdetect` returned the full-frame dimensions for both clips. A `WARN` is a review signal, not a judgment of visual quality.

| Local source | Duration / video | Black | Freeze | Audio peak | Result |
|---|---|---:|---|---:|---|
| `AI_Channel/.../11-09-pixelfx-reel/reel.mp4` | 26.453 s; 1080x1920 at 30 fps | 0 | 4 intervals: 11.967-12.500 s, 17.233-17.833 s, 18.200-18.867 s, 25.200 s to end | -1.6 dBFS | WARN: freeze intervals |
| `kinetic-test/film/out/aviasales-concept-1080p60.mp4` | 29.000 s; 1920x1080 at 60 fps | 0 | 0 | +0.5 dBFS | WARN: above the configured audio peak threshold |

The FFmpeg build did not emit a clipped-sample count, so the report shows `clipped_samples=unavailable`. The +0.5 dBFS sample-peak warning does not by itself confirm clipping. Freeze detections may be intentional holds; review those timestamps in context.

The PixelFX run was repeated with `--frames-dir`; it extracted four JPEG previews at the detected freeze start times. Separate 3x3 contact sheets were also created for visual inspection:

- `generated/pixelfx-reel.jpg`
- `generated/kinetic-aviasales.jpg`
- `generated/pixelfx-qa-frames/` (4 previews)

These generated images are ignored by Git and remain local under `bench/generated/`.

## Limits

- This is a two-video smoke check, not a representative quality benchmark.
- No before/after vision-token or conversation-savings comparison was measured.
- The kinetic-film project's own `finish.py` was not run; its existing gates have not been compared with FrameDiet's output.
