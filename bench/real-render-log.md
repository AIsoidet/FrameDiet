# Real Remotion render log (2026-11-08)

Raw stdout+stderr of two real Remotion commands on the local PixelFX reel project, captured at default log level (no `--log=error`), then passed once through the pre-cleanup `framediet.logs.compress_output`. Token counts use `cl100k_base` (a proxy, not Claude's tokenizer).

Commands (run from the AI_Channel `video/` project, output outside this repository):

- `npx remotion bundle src/index.tsx`
- `npx remotion render <bundle> PixelfxReel probe.mp4 --codec=h264 --crf=18 --frames=0-89` (90 of the reel's frames, 8.8 s wall time)

| Command | Raw chars | Compact chars | Raw tokens | Compact tokens | Token reduction |
|---|---:|---:|---:|---:|---:|
| bundle | 270 | 187 | 140 | 90 | 36% |
| render, 90 frames | 3,767 | 487 | 1,529 | 213 | 86% |

## Observations

- Raw output grows with frame count: Remotion prints one `Rendered N/total, time remaining` line per frame. This sample covers 90 frames; a full-length render would have proportionally more lines, but that longer run was not measured here.
- Existing local workflows already run Remotion with `--log=error` (for example the FosterVox render log, 33 lines) or print two summary lines (`kinetic-test/film/render.log`, 122 bytes). On those, log compression saves little. The measured gain applies to default-verbosity runs.
- The measured compact output still contained ANSI colour escape sequences and one `Encoded N/total` line per progress step. The current `logs.py` strips ANSI sequences and filters `Encoded` progress lines.
- The table above is the historical result of the pre-cleanup compressor. The raw logs of a repeat run are kept in `bench/fixtures/`, and [`logs-three-columns.md`](logs-three-columns.md) gives the current numbers (render 1,529 to 175 tokens, bundle 140 to 95). The shell `time` lines (`real/user/sys`) were included in all counts.

## Limits

- One project, one 90-frame run; not a representative benchmark.
- The wrapper `time` output is included in both raw and compact counts.
- Not measured: total conversation tokens, or any effect on task outcome.
