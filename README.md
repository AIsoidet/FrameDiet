# FrameDiet

**Deterministic video QA and compact media context for agents that make video with code** (Remotion, HyperFrames, FFmpeg, Whisper).

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![tests](https://github.com/AIsoidet/FrameDiet/actions/workflows/tests.yml/badge.svg)](https://github.com/AIsoidet/FrameDiet/actions/workflows/tests.yml)

When an AI agent renders and checks a video, most of its context goes to things a script could answer: per-frame render logs, dozens of screenshots to find a black frame, word-level caption JSON. FrameDiet is a small CLI that gives the agent the answer instead of the raw material, and keeps the numbers public so you can check them.

No required dependencies. `ffmpeg` and `ffprobe` on `PATH` for the video commands.

## What it measured

Every row is one real run on one project; token counts use `cl100k_base`, which is a proxy and not Claude's tokenizer. Limits are written next to each result.

| Question | Without FrameDiet | With FrameDiet | Notes |
|---|---:|---:|---|
| Remotion render log, 90 frames, default verbosity | 1,529 tokens | 164 | `--log=error` gives 28 but drops composition, codec and output path. [Details](bench/logs-three-columns.md) |
| Find defects in a 30 s clip (4 injected: 2 black flashes, 1 s freeze, audio over 0 dBFS) | 27 full frames, about 42,000 vision tokens, found 1 of 4 | `fdiet qa` report, about 224 tokens, found 4 of 4 | Vision tokens are estimates from the documented formula, not measured. One clip: it shows the mechanism, not a detection rate. [Details](bench/frames-vs-qa.md) |
| Whisper word timestamps, 50 words (synthetic) | 2,047 tokens | 463 | Synthetic fixture. |

Not claimed: a fixed percentage saving, total-conversation savings, or that `qa` replaces looking at the video. A `PASS` means the configured numeric checks found nothing, not that the layout is right. Raw logs and scripts are in [`bench/`](bench), so the numbers reproduce.

## Install

```bash
pip install git+https://github.com/AIsoidet/FrameDiet.git
```

From a checkout: `python -m pip install -e .`. Optional `pip install -e ".[benchmark]"` adds `tiktoken` for the proxy token counts in `bench`.

`framediet` and the short alias `fdiet` are the same command. Windows, macOS and Linux are supported by the code; the live Claude Code check below was done on Windows only.

## Quick start

```bash
fdiet qa render.mp4                       # black, freeze, crop, audio peak: a short verdict
fdiet qa render.mp4 --frames-dir qa       # plus small previews at each detected problem
fdiet sheet render.mp4 --grid 3x3         # one timestamped contact sheet instead of many frames
fdiet exec -- npx remotion render src/index.ts Main out.mp4   # run, keep a short summary
fdiet json captions.json                  # compact word-timed transcript
fdiet init                                # optional: Claude Code hook for the above
```

### What the agent actually sees

A 6 s clip with one 0.3 s black flash, checked with `fdiet qa`:

```text
[QA WARN] | duration=6.000s | video=360x640 | fps=30.000 | black=1 | freeze=0 | crop_observed=360x640+0+0 | audio_peak=-28.1dBFS | clipped_samples=unavailable
- black intervals: 1 (from 00:00:02.000 - 00:00:02.333)
```

A WhisperX segment with one untimed token, through `fdiet json`:

```text
# FrameDiet transcript (unit=ms; word[start-end]); ?=no timing in source
[500-4200 SPEAKER_00] In[500-700] 2014.[800-1300] it[1400-1500] cost[1600-2000] £13.60[?]
```

Both outputs were produced by the current version on a generated clip and a hand-written JSON.

## Commands

### Layer 1: check a render (QA and vision)

**`fdiet qa <video>`** runs FFmpeg's `blackdetect`, `freezedetect`, `cropdetect` and `astats` and prints one summary line plus a line per warning. `--frames-dir` extracts small JPEG previews at the start of each black or freeze interval (up to 36). Without flags it always exits 0, even on `WARN`, so an agent can read the verdict. Add `--strict` and it exits 1 on `WARN`, so a render script or CI job can fail on its own (invalid input or a missing FFmpeg exits 2). Thresholds are flags (`--freeze-min-duration`, `--audio-peak-warn-dbfs`, and others). Intentional pauses and held title cards can trigger freeze warnings; raise `--freeze-min-duration` for slow-paced videos. `cropdetect` reports removable borders, not a content bounding box.

**`fdiet sheet <video> --grid 3x3`** builds a timestamped contact sheet. It reduces the number of images, but small details are harder to see in a grid, and in our test a 3x3 sheet did not show a 0.2 s black flash. Use it for overall structure, and `qa` for defects. Existing files are not overwritten without `--overwrite`. If your FFmpeg build has no default font, pass `--font-file`.

**`fdiet frames <video> 4.2 7.5 10.0`** writes bounded, timestamp-named JPEG previews and reports source and preview sizes. The quality option is FFmpeg's qscale, not a percentage.

On image cost: [Anthropic's vision docs](https://platform.claude.com/docs/en/build-with-claude/vision) count 28x28 patches after model-tier-specific resizing. FrameDiet does not estimate image tokens, because the receiving model and tier are not known to it.

### Layer 2: compact context about media and scenes

**`fdiet json <file>`** detects Whisper, WhisperX, Faster-Whisper or Remotion caption JSON and prints `word[start-end]` per word, in integer milliseconds (`--unit s` for seconds). Any other JSON goes to the TOON encoder instead (see below). Detection is by shape, not a lossless conversion; keep the source file when confidence scores or other metadata matter.

Words the aligner could not time (WhisperX leaves `start` and `end` off tokens such as `"2014."` or `"£13.60"`) are written `word[?]` rather than a made-up `[0-0]`, and the header gains `?=no timing in source`. A segment's `speaker` stays in its label: `[500-4200 SPEAKER_00]`.

**TOON output.** For other JSON, `fdiet json timeline.json` writes [TOON 4.4 (working draft)](https://github.com/toon-format/spec/blob/main/SPEC.md). The encoder is a small independent implementation, not a copy of the reference one, and has only its own tests so far. Uniform arrays of objects become tables; non-uniform arrays use list form, so optional fields are never dropped. `--precision N` rounds floats on purpose; without it values round-trip.

**`fdiet digest <Scene.tsx>`** prints a bounded index of Remotion `Composition`, `Sequence`, section and media tags with line ranges. It is a heuristic index, not a JSX parser, and does not infer rendered timing.

**`fdiet probe <path>`** summarizes stream metadata for one media file, or dependencies, likely source files and media assets for a project directory. For video streams it adds `WARN` lines when the display is rotated (for example phone footage with `rotation=90`) or the frame rate looks variable (average rate more than 2% off the base rate, a heuristic), the two usual reasons a preview drifts from the audio.

**`fdiet html <file>`** prints HTML with long SVG paths, base64 data URIs and inline script and style bodies replaced by markers. It is a reading aid; the source file is not changed.

### Layer 3: shorten command output

**`fdiet exec -- <command>`** runs a command directly (no shell), removes progress lines and ANSI codes, and keeps a bounded set of diagnostics. A failing command returns its exit code and the last diagnostic lines, with critical lines such as `FATAL` kept even after long noise. Successful runs are summarized, so run the command yourself when you need the full log.

**`fdiet init`** adds a Claude Code `PreToolUse` hook for the `Bash` tool. It rewrites only a single, direct call of `ffmpeg`, `ffprobe`, `yt-dlp`, `manim`, `whisper`, `faster-whisper`, or `npx`/`bunx`/`pnpm` with `remotion` or `hyperframes`, into `framediet exec -- ...`. Pipes, chains, redirects and other shell syntax pass through untouched. The hook returns no permission decision, so your configured approvals stay in force.

Live check: on Claude Code 2.1.319 (Windows, `claude -p --allowedTools Bash`, default permission mode) a hooked `ffmpeg` call came back as the `[OK] FrameDiet: ...` summary without `frame=` progress lines. Claude Code's documentation says permission rules are evaluated against the input the hook returns. Not tested: auto mode, interactive approval prompts, other versions or platforms.

### Layer 4: housekeeping

**`fdiet slim <skills-dir>`** is a separate utility that ships here because video skills and prompts tend to carry long code blocks (Remotion scenes, FFmpeg recipes) that cost context on every load. It previews long fenced code blocks in skill Markdown files that could move to reference files; `--apply` writes them under `references_diet/` with backups of the changed files. The preview is the default. It is a narrow Markdown transformation, not a lazy-loading system.

**`fdiet bench`** prints sizes for bundled synthetic examples. The synthetic FFmpeg log is deliberately progress-heavy (99% reduction); that is not a general expectation for quiet logs. Real-run measurements are in [`bench/`](bench).

## How the numbers are made

- Tokens: `cl100k_base` through `tiktoken` as a stand-in. Claude's tokenizer is different, so absolute counts differ; ratios are indicative.
- Images: tokens from the documented `ceil(w/28) x ceil(h/28)` rule with the published resize limits (1568 px / 1568 tokens standard; 2576 px / 4784 tokens high-resolution tier). Estimates, not measurements.
- Detection tests use a ground-truth clip with known injected defects and a control clip. The control showed false positives (freeze warnings on pauses that were intentional), which is why thresholds are exposed.
- Everything is one project's output. Treat the figures as evidence that the mechanism works, and run `bench/*.py` on your own material before relying on them.

## Scope and limitations

- FrameDiet summarizes and checks. It does not render, edit or replace FFmpeg, Remotion or HyperFrames.
- `sheet` needs an FFmpeg build with `drawtext`.
- `qa` checks objective signals only. It cannot judge design, typography or safe areas.
- `digest` is a source index, not a TypeScript or JSX parser.
- Command-output filtering saves little when you already run tools quietly (`--log=error`).
- Word-level `speaker` fields (WhisperX) are not read; only segment-level speaker is kept.

## Related tools

This is a survey of tools we found and read, not a market study; stars as read on 2026-11-08.

- General CLI output compressors: [RTK](https://github.com/rtk-ai/rtk), [token-saver](https://github.com/ppgranger/token-saver). They do not target media commands, to our reading.
- [video-use](https://github.com/browser-use/video-use) (MIT, about 30.7k stars): an agent edits video by reading a phrase-level transcript and rarely looking at frames; its ASR is a cloud service. Different job (editing), same instinct (give the agent text, not frames).
- [claude-video](https://github.com/bradautomates/claude-video) (MIT): understanding someone else's video with timestamped frames and a transcript.
- [claudeclip](https://github.com/gulkoa/claudeclip): FFmpeg MCP with contact sheets.
- [auto-editor](https://github.com/WyattBlue/auto-editor) (Unlicense): automatic cutting of silence and dead time.
- [OpenScreen](https://github.com/getopenscreen/openscreen) (MIT): screen recording and editing with an agent skill.

None of these publish token measurements that we could find; that is why this repository keeps its raw logs.

## Origin

FrameDiet comes from the video workflow of the [ai_soidet](https://t.me/ai_soidet) channel, where Claude renders 9:16 reels with Remotion and the context bill grew with every frame and log. See [`docs/ROADMAP.md`](docs/ROADMAP.md) for where it goes next (anatomy/SVG is a proposal, not a shipped feature).

Issues with a failing log or a clip your `qa` got wrong are the most useful contribution.

## License

MIT. See [LICENSE](LICENSE).
