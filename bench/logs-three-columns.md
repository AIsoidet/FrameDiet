# Remotion log: default vs `--log=error` vs `fdiet exec` (2026-11-08)

Script: `bench/three_columns.py`. Fixtures in `bench/fixtures/` are the raw stdout+stderr of real Remotion runs on the local PixelFX reel project (90 frames, `--frames=0-89`), captured with a shell `time` wrapper, so the three `real/user/sys` lines are included in every count. Token counts use `cl100k_base`, a proxy and not Claude's tokenizer. The `fdiet exec` column uses the current `logs.py`, which strips ANSI sequences and filters `Encoded N/M` lines.

| Run | Default output (tokens) | `--log=error` (tokens) | `fdiet exec` (tokens) |
|---|---:|---:|---:|
| `remotion render`, 90 frames | 1,529 | 28 | 164 |
| `remotion bundle` | 140 | n/a (not run) | 84 |

Earlier compressor, before the ANSI and `Encoded` fixes, on the same raw logs: 213 tokens for render and 90 for bundle (measured with the version of `logs.py` in commit `fd27cff`). The fixtures can be re-run, so the current numbers are reproducible.

## What each column keeps

- **Default output:** composition name, codec, output path, concurrency, one `Rendered N/90, time remaining` line per frame, the `Encoded` progress and a final path and size line, with ANSI colour codes.
- **`--log=error`:** nothing from Remotion on success. The only text left is the `time` wrapper's lines. The composition, codec, output path and output size are not shown, and a long run gives no sign of progress.
- **`fdiet exec`:** composition, codec, output path, concurrency and the final path and size line, without per-frame progress or colour codes. A non-zero exit still returns diagnostic lines.

## Limits

- One project, one 90-frame run and one bundle run; not a representative benchmark.
- The raw render has 90 progress lines; a longer render has proportionally more. That was not measured.
- Existing local workflows already run with `--log=error` or print short summaries, and for those there is little to remove.
- Output paths in the fixtures point into a temporary directory of the machine that produced them.
