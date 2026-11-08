# FrameDiet

**Deterministic video QA and compact media context for code-driven video workflows.** Built by AI soidet.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

General-purpose CLI compressors such as [token-saver](https://github.com/ppgranger/token-saver) and [RTK](https://github.com/rtk-ai/rtk) reduce routine command output. FrameDiet focuses on media artifacts that benefit from purpose-built handling: render logs, word-aligned captions, video frame previews, and large embedded assets in HTML/SVG.

FrameDiet does not claim a fixed percentage reduction in total model usage. The output size depends on the input, the model tokenizer, and the visual model used to inspect images. Run `framediet bench` to measure the included synthetic examples on your machine.

The working direction is one repository with a small shared core and opt-in domain tools. Video is implemented first; anatomy/SVG is a later domain proposal, not a shipped feature. See the [product direction and rollout](docs/ROADMAP.md).

## Install

Install from a local checkout:

```bash
python -m pip install -e .
```

There is no public GitHub install URL yet. Add one after the repository is published.

The Python package has no required third-party runtime dependencies. Video commands need `ffmpeg` and `ffprobe` on `PATH`; timestamp drawing for `sheet` requires an FFmpeg build with `drawtext` support. FrameDiet uses a common system font when available, or pass `--font-file` if the build has no default font configured. Optional benchmark token counts use `tiktoken`:

```bash
python -m pip install -e ".[benchmark]"
```

## Commands

`framediet` and its short alias `fdiet` expose the same commands.

### Summarize media command output

```bash
fdiet exec -- ffmpeg -i input.mp4 -c:v libx264 output.mp4
fdiet exec -- npx remotion render src/index.ts Main out.mp4
fdiet exec -- npx hyperframes render
```

FrameDiet runs the arguments directly without a shell, removes common progress lines, and preserves a bounded set of diagnostics. A non-zero exit code is returned to the caller. Successful output is summarized, so inspect the original command directly if you need its full verbose log.

### Install the Claude Code hook

```bash
framediet init
```

The hook rewrites only a single direct invocation of a recognized media executable. Chained commands, pipes, redirects, and other shell expressions pass through unchanged. The hook does not return a permission decision; Claude Code retains its configured approval behavior. In some auto-mode situations, rewriting tool input can still cause Claude Code to review the changed call.

Claude Code's hook documentation says permission rules are evaluated against the input the hook returns, and that no output with exit code 0 means no decision. It does not say in so many words that `updatedInput` is applied without a `permissionDecision`, so this behaviour has been checked in unit tests only, not in a live session; test it on your Claude Code version.

The hook currently targets Claude Code's `Bash` tool. The CLI commands can be used manually from other agents and terminals.

### Compact JSON input

```bash
fdiet json voiceover.json
fdiet json captions.json --unit s
```

`fdiet json` automatically recognizes Whisper/Faster-Whisper or caption JSON with non-empty word/segment records and timestamp fields. It prints a transcript view for those shapes; other JSON values go through the TOON encoder. This is shape detection, not a lossless conversion or an explicit format flag.

The transcript notation uses integer milliseconds by default, for example `Build[0-350] fast[350-720]`. It rounds source timestamps to the nearest millisecond and omits fields such as confidence scores; keep the original JSON when those fields matter.

Words the aligner could not time (WhisperX leaves `start`/`end` off numbers such as `"2014."` or `"£13.60"`) are written as `word[?]` instead of a made-up `[0-0]`, and the header then adds `?=no timing in source`. A segment's `speaker` is kept in its label, for example `[500-4200 SPEAKER_00]`.

### TOON output for other JSON shapes

```bash
fdiet json timeline.json
fdiet json timeline.json --precision 3
```

The encoder targets the [TOON 4.4 working draft](https://github.com/toon-format/spec/blob/main/SPEC.md), whose specification repository is MIT licensed. FrameDiet's encoder is a small independent implementation; it does not copy the reference implementation. Uniform arrays of objects use tabular form; non-uniform arrays use list form, preserving their different shapes. `--precision` intentionally rounds floating-point values; without it, values use a round-trippable representation.

### Create a VLM contact sheet

```bash
fdiet sheet render.mp4 -o critic-grid.jpg --grid 3x3
fdiet sheet render.mp4 -o wide-grid.jpg --grid 4x3 --width 320
```

Frames are sampled at regular intervals across the clip and labeled with frame number and time. Existing output files are left alone unless `--overwrite` is supplied. A contact sheet reduces the number of image attachments; actual vision-token savings are model-dependent, and small details may be harder to inspect in a grid.
If the FFmpeg build lacks a default font configuration, FrameDiet uses a common system font path or accepts an explicit `--font-file` path.

[Anthropic's current vision docs](https://platform.claude.com/docs/en/build-with-claude/vision) count 28×28 image patches after model-tier-specific resizing; the `/750` estimate in the earlier proposal is not a reliable general formula. FrameDiet does not estimate provider-specific image tokens because the receiving model and tier are not known.

### Check a rendered video before opening frames

```bash
fdiet qa render.mp4
fdiet qa render.mp4 --frames-dir qa-frames
```

The report checks black intervals, low-motion freezes, crop-detection observations, and audio peak plus clipped-sample count when FFmpeg exposes it. `--frames-dir` extracts small JPEG previews at the start times of detected black/freeze intervals, up to 36 previews. A `PASS` only means the configured numeric checks did not flag a signal; it does not prove that layout, typography, or safe areas are correct. FFmpeg's [`cropdetect`](https://ffmpeg.org/ffmpeg-filters.html#cropdetect) reports likely removable borders, not a content bounding box.

### Extract specific frame previews

```bash
fdiet frames render.mp4 4.2 7.5 10.0 --out-dir review-frames
```

FrameDiet writes bounded, timestamp-named JPEG previews and reports source/preview dimensions. The JPEG quality option is FFmpeg's qscale, not a percentage.

### Summarize scene source or a project

```bash
fdiet digest src/Scene.tsx
fdiet probe .
fdiet probe public/preview.mp4
```

`digest` reports a bounded heuristic index of Remotion `Composition`/`Sequence`, section, and media tags with source line ranges. It does not evaluate JSX or infer rendered timing. `probe` summarizes package dependencies, likely source files, and media assets for a project directory, or stream metadata for one media file.

### Preview or apply skill-file extraction

```bash
# Preview long fenced blocks that would be extracted
fdiet slim .claude/skills

# Write references and a separate backup of each changed Markdown file
fdiet slim .claude/skills --apply
```

The preview is the default. `--apply` moves fenced code blocks at or above the line threshold into content-hash-named files under `references_diet/`. Existing references are not overwritten, and the original Markdown is backed up before it is changed.

### Reduce large HTML/SVG payloads for inspection

```bash
fdiet html landing-page.html > landing-page.compact.html
```

The source file is not modified. Long SVG paths, base64 data URIs, and inline script/style bodies are replaced with markers in the printed output; this is a reading aid, not a transformed production page.

### Measure the bundled examples

```bash
framediet bench
```

The command prints character counts for deterministic synthetic transcript, timeline, and FFmpeg-log examples. The synthetic FFmpeg fixture is deliberately progress-heavy and reduced by 99.5%; this is not a general expectation for quiet logs. With the optional benchmark dependency installed, `bench` also prints `cl100k_base` counts as a tokenizer proxy, not Claude tokens or total conversation savings. The [local size inventory](bench/baseline-skills.md) covers anatomy, watch, and the kinetic-test skill; the [`cl100k_base` report](bench/baseline-tiktoken.txt) records those per-file counts, not before/after FrameDiet savings. Real-run measurements, each on one project and with `cl100k_base` as a proxy:

- [Remotion log, three columns](bench/logs-three-columns.md): a 90-frame render is 1,529 tokens at default verbosity, 28 with `--log=error` and 164 through `fdiet exec`. The raw logs are in `bench/fixtures/`, and `bench/three_columns.py` reproduces the numbers. `--log=error` is cheaper but drops the composition, codec and output path; runs already using it have little to remove.
- [Frames versus `fdiet qa`](bench/frames-vs-qa.md): a clip with four injected defects and a known ground truth. `qa` found all four; 1 fps frames found one by grid luck and a 3x3 sheet found none. Text of the report is about 224 tokens, against roughly 42,000 for 27 full frames (vision-token estimates from the documented formula, not measured). One clip, so this shows the mechanism and is not a detection-rate claim.
- [Earlier notes](bench/real-render-log.md) and the [two-video QA smoke check](bench/local-smoke-2026-11.md). Neither is a representative benchmark.

## Scope and limitations

- FrameDiet summarizes command output; it does not replace media-processing tools.
- `sheet` requires external FFmpeg programs and a `drawtext`-enabled build.
- `qa` checks objective FFmpeg signals. A clean report cannot replace visual review of design quality or exact layout.
- `digest` is a source index, not a TypeScript/JSX parser.
- The transcript view preserves text and timestamps to millisecond precision, while omitting optional source metadata.
- TOON output is for compact agent context. Keep source JSON for archival or application interchange.
- Skill extraction is opt-in and creates backups; review the preview before applying it to third-party skills.

## Related tools

This is an adjacent-tool survey, not an exhaustive market study. Existing projects already cover parts of the workflow: [Token-Saver](https://github.com/ppgranger/token-saver) and [RTK](https://github.com/rtk-ai/rtk) handle common CLI output; [claudeclip](https://github.com/gulkoa/claudeclip) includes video inspection and contact sheets; [claude-video](https://github.com/bradautomates/claude-video) works with timestamped frames and transcripts; and [ffmpeg-video-analysis](https://github.com/JosiahSiegel/claude-plugin-marketplace/tree/main/plugins/ffmpeg-core/skills/ffmpeg-video-analysis) documents FFmpeg checks and automation patterns. FrameDiet packages local deterministic checks with a compact report and optional frame previews; it makes no first-mover or universal token-savings claim.
