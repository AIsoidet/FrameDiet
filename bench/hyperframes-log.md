# HyperFrames log: default vs `--quiet` vs `fdiet exec` (2026-11-08)

Script: `bench/hyperframes_columns.py`. Fixtures in `bench/fixtures/` (`hyperframes-render.raw.log`, `hyperframes-render.quiet.log`) are the raw stdout+stderr of real runs of `hyperframes` 0.9.23 (Node v26.7.0, FFmpeg 9.0, Windows 11, 16 cores, Intel UHD GPU), redirected to a file (`> log 2>&1`). Token counts use `cl100k_base`, a proxy and not Claude's tokenizer. The `fdiet exec` columns use the current `logs.py` with the new HyperFrames patterns in `PROGRESS_NOISE`. In the fixtures the temporary project path is replaced by `<tmp>` and the home directory by `C:\Users\<user>`.

## What was run

```
npx hyperframes init demo --example blank --non-interactive --skip-skills
cd demo
npx hyperframes render -o renders/a.mp4            # default
npx hyperframes render --quiet -o renders/b.mp4    # quiet variant
```

The blank example is a 1920x1080, 30 fps, 10 s composition (300 frames), rendered with 6 workers; the render took 28 s and produced a 29 KB MP4. Both runs exited 0.

| Run | Default output (tokens) | `--quiet` (tokens) | `fdiet exec`, default log (tokens) | `fdiet exec`, `--quiet` log (tokens) |
|---|---:|---:|---:|---:|
| `hyperframes render`, 10 s blank | 7,191 | 1,798 | 362 | 199 |

Raw lines: 216 (default), 80 (`--quiet`).

## What each column keeps

- **Default output:** progress bars with a percentage for each stage (compile, capture, encode, assemble), a `@hf-progress {...}` JSON line next to each bar, a `[INFO] [Render:trace]` JSON line per phase, per-worker `[BrowserManager]` and `[initSession:screenshot]` setup lines, calibration lines, and at the end the output path, size, duration and a timing breakdown.
- **`--quiet`:** removes the bars, `@hf-progress` lines, trace lines, the result block (output path, size, duration, timings) and the `@hf-result` line. What remains is the per-worker `[initSession:...]` and `[BrowserManager]` chatter, the compiler and GPU probe lines and `[FrameCapture] Timed out closing browser` warnings. The output path is not printed at all, so a quiet run does not say where the file went or how long it took.
- **`fdiet exec` on the default log:** the header with line counts, the output path, size/duration line, timing breakdown, GPU probe line, the "Timed out closing browser" warning (repeated lines collapsed), one `[INFO]` line about fast capture, and the trailing promo and `@hf-result` lines. Bars, per-frame percentages, trace JSON and worker setup lines are dropped. Non-zero exit still returns diagnostic lines (errors and warnings are not matched by the noise patterns).
- **`fdiet exec` on the `--quiet` log:** the compiler lines, GPU probe and the timeout warning. It cannot restore the output path that `--quiet` never printed.

Patterns added to `PROGRESS_NOISE`: block-character bars followed by a percentage, `NN% Compiling|Extracting|Processing|Starting|Checking|Measuring|Capturing|Encoding|Assembling`, `@hf-progress`, `[initSession:`, `[BrowserManager] Browser launched`, `[HyperFrames] render runtime fps`, `[INFO] [Render:trace]`, `[INFO] Calibration`, calibration launch and init lines, `streaming-encode gate`, and the `[Render]` lines `Encoded frames while capturing`, `Calibration config`, `Pipeline started`. Tests: `tests/test_logs_hyperframes.py`.

## Limits

- One machine, one blank 10 s composition, one default and one `--quiet` run; not a representative benchmark. A composition with video, audio or fonts adds more lines that were not seen.
- The raw log is dominated by per-worker setup lines and trace JSON, whose count depends on the worker count (6 here) and on the HyperFrames version.
- The `fdiet exec` summary keeps the last 12 non-noise lines plus lines containing words like `rendered` or `done`, so some low-value lines survive (the fast-capture notice, the promo and feedback lines).
- `--quiet` was not combined with other flags such as `--json` (documented as printing no progress); `--json` was not run.
- Percentages and some timings are from one run and will differ between runs.
