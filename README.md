# FrameDiet

**Deterministic video QA and compact media context for agents that make video with code** (Remotion, HyperFrames, FFmpeg, Whisper).

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![tests](https://github.com/AIsoidet/FrameDiet/actions/workflows/tests.yml/badge.svg)](https://github.com/AIsoidet/FrameDiet/actions/workflows/tests.yml)

When an AI agent renders and checks a video, most of its context goes to things a script could answer: per-frame render logs, dozens of screenshots to find a black frame, word-level caption JSON. FrameDiet is a small CLI that gives the agent the answer instead of the raw material, and keeps the numbers public so you can check them.

No required dependencies. `ffmpeg` and `ffprobe` on `PATH` for the video commands.

**Where it helps, and where it does not:** it pays off on tasks that include a quality check (`qa` replaces frame sampling and hand-written detectors) and on long renders or heavy HTML. On light tasks, such as a transcript lookup or a single short render, the measured cost was about the same with and without it. A `WARN` is a cue to look at the flagged frames, not proof of a defect; layout, typography and pacing are still judged by the model.

## What it measured

Every row is a small real run (one machine, a few clips, n=1 or 2), not a survey. The session table uses Claude Code's own usage report; the single-step tables use `cl100k_base`, a proxy and not Claude's tokenizer. Limits are written next to each result.

**One whole Claude Code session**, real usage from `claude -p --output-format json` (Opus 5.5, Claude Code 2.1.319): re-encode a 20 s clip with 4 known defects, then find them. Two runs each, same prompt, one project with FrameDiet's skill text and one without.

| | Cost per run | Turns | Cache-read tokens | Output tokens | Defects found |
|---|---:|---:|---:|---:|---:|
| Without FrameDiet (mean of 2) | $0.58 | 15.5 | 619,094 | 8,410 | 4 of 4 |
| With FrameDiet (mean of 2) | $0.26 | 9 | 293,476 | 1,992 | 4 of 4 |

The plain agent wrote its own FFmpeg detectors, Python analysis and spectrograms; the FrameDiet agent ran `framediet qa`. The saving came from that, not from the log hook (the agents piped their encodes through `tail`, which the hook leaves alone). n=2, one task, one synthetic clip. [Details](bench/e2e-session.md)

**Three more tasks**, same method, FrameDiet loaded only as the plugin (`--plugin-dir`), mean of 2 runs per arm:

| Task | Without | With | Result |
|---|---:|---:|---|
| QA of a 9:16 reel with 3 real defects and an intentional 2 s title card | $0.61 | $0.43 | All runs found 3 of 3; both plain runs also listed the title card as a defect, neither FrameDiet run did |
| Find a phrase's times and count words in a 60 s WhisperX JSON | $0.23 | $0.23 | All correct; the file is small, so no gain |
| Render a HyperFrames project and check the output | $0.43 | $0.44 | All correct; no gain. Each FrameDiet run lost 2–3 turns on a wrong `frames` flag (`-o` is accepted now; not re-measured) |

The hook fired in none of these runs. The agents piped renders through `tail`, which the hook deliberately leaves untouched. At measurement time the direct `npx --yes hyperframes@0.9.23 render` form was also unrecognized; it is now covered. A separate check with a plain `ffmpeg` encode showed the plugin hook does fire. So the saving is in QA-heavy work; on light tasks FrameDiet costs about the same. [Details](bench/e2e-tasks.md)

**Single steps**, `cl100k_base` proxy counts:

| Question | Without FrameDiet | With FrameDiet | Notes |
|---|---:|---:|---|
| Remotion render log, 90 frames, default verbosity | 1,529 tokens | 175 | `--log=error` gives 28 but drops composition, codec and output path. [Details](bench/logs-three-columns.md) |
| HyperFrames 0.9.23 render log, 10 s blank example | 7,191 tokens | 362 | `--quiet` gives 1,798 and no longer prints the output path. [Details](bench/hyperframes-log.md) |
| Frame-sampling rules of two critic-loop skills (motion-video-kit, remotion-director) on the defect clip | 1–9 images, about 1,500–13,800 vision tokens, 1–3 of 4 defects in frame | `fdiet qa`, about 224 text tokens, 4 of 4 | Image sampling alone; both skills also ship their own numeric checks, which were not run. Audio cannot appear in a frame. [Details](bench/critic-loop.md) |
| Find defects in a 30 s clip (4 injected: 2 black flashes, 1 s freeze, audio over 0 dBFS) | 27 full frames, about 42,000 vision tokens, found 1 of 4 | `fdiet qa` report, about 224 tokens, found 4 of 4 | Vision tokens are estimates from the documented formula, not measured. One clip: it shows the mechanism, not a detection rate. [Details](bench/frames-vs-qa.md) |
| Whisper word timestamps, 50 words (synthetic) | 2,047 tokens | 463 | Synthetic fixture. |

Not claimed: a fixed percentage saving, total-conversation savings, or that `qa` replaces looking at the video. A `PASS` means the configured numeric checks found nothing, not that the layout is right. Raw logs and scripts are in [`bench/`](bench), so the numbers reproduce.

## Install

**As a Claude Code plugin** (hook, skill and the `framediet` command in one step, next to any video skill you already use):

```text
/plugin marketplace add AIsoidet/FrameDiet
/plugin install framediet@framediet
```

From a shell: `claude plugin marketplace add AIsoidet/FrameDiet`, then `claude plugin install framediet@framediet`. The plugin needs Python 3.10+ on `PATH` (it runs from source; there are no dependencies) and FFmpeg for the video commands. The plugin's hook is the same as `fdiet init`; do not install both, or remove the `framediet hook` entry from `.claude/settings.json`.

**As a Python CLI** (any agent, scripts, CI):

```bash
pip install git+https://github.com/AIsoidet/FrameDiet.git
```

From a checkout: `python -m pip install -e .`. Optional `pip install -e ".[benchmark]"` adds `tiktoken` for the proxy token counts in `bench`.

`framediet` and the short alias `fdiet` are the same command. Windows, macOS and Linux are supported by the code; CI runs tests with FFmpeg on Linux and Windows, and the live Claude Code checks were done on Windows only. A PyPI package is prepared but not published yet ([docs/RELEASE.md](docs/RELEASE.md)).

### For skill authors

The hook catches direct `ffmpeg`/`remotion`/`hyperframes` calls only. If your skill renders through its own script or pipes output through `tail`, add the check to the script itself, after the render:

```bash
framediet qa out.mp4 --strict          # one-line verdict; exit 1 on WARN
```

and tell the agent in your SKILL.md to read that verdict before sampling frames, and to use `framediet frames <video> <times>` only at the reported timestamps.

## Quick start

```bash
fdiet qa render.mp4                       # black, freeze, crop, audio peak: a short verdict
fdiet qa render.mp4 --frames-dir qa       # plus small previews at each detected problem
fdiet sheet render.mp4 --grid 3x3         # one timestamped contact sheet instead of many frames
fdiet exec -- npx remotion render src/index.ts Main out.mp4   # run, keep a short summary
fdiet json captions.json                  # compact word-timed transcript
fdiet init                                # optional: Claude Code hook without the plugin
```

### What the agent actually sees

A 6 s clip with one 0.3 s black flash, checked with `fdiet qa`:

```text
[QA WARN] | duration=6.000s | video=360x640 | fps=30.000 | black=1 | freeze=0 | crop_observed=360x640+0+0 | audio_peak=-28.1dBFS | clipped_samples=unavailable
- black intervals: 1 (00:00:02.000 - 00:00:02.333 (0.33s))
```

A WhisperX segment with one untimed token, through `fdiet json`:

```text
# FrameDiet transcript (unit=ms; word[start-end]); ?=no timing in source
[500-4200 SPEAKER_00] In[500-700] 2014.[800-1300] it[1400-1500] cost[1600-2000] £13.60[?]
```

Both outputs were produced by the current version on a generated clip and a hand-written JSON.

## Commands

### Layer 1: check a render (QA and vision)

**`fdiet qa <video>`** runs FFmpeg's `blackdetect`, `freezedetect`, `cropdetect` and `astats` and prints one summary line plus a line per warning. `--frames-dir` extracts small JPEG previews at the start of each black or freeze interval (up to 36). `--json` prints the report as JSON, including `notes`; when combined with `--frames-dir`, preview paths go to stderr. Without flags it always exits 0, even on `WARN`, so an agent can read the verdict. Add `--strict` and it exits 1 on `WARN`, so a render script or CI job can fail on its own (invalid input or a missing FFmpeg exits 2). Thresholds are flags (`--freeze-min-duration`, `--audio-peak-warn-dbfs`, and others).

Motion graphics hold still on purpose, so stills and black are split into warnings and `note:` lines. Notes never change `PASS`/`WARN` or the `--strict` exit code:

- a still or black interval touching the first or last 0.5 s and no longer than 3 s is noted as a likely title card, end card or fade;
- a still in the middle shorter than `--freeze-warn-duration` (default 0.75 s) is noted as a likely held beat;
- touching intervals are merged first, because FFmpeg can split one long still in two;
- anything covering half the video is always a warning.

On the channel's published PixelFX reel this turned 4 freeze warnings into notes (`PASS`). On a diagram animation (`flow.mp4`, 10 fps) one 1.1 s pause still warns. The defect clips still give all 4 injected defects as warnings. The 0.75 s default comes from these two videos, not from a survey; change it for your pacing. `cropdetect` reports removable borders, not a content bounding box.

**`fdiet sheet <video> --grid 3x3`** builds a timestamped contact sheet. It reduces the number of images, but small details are harder to see in a grid, and in our test a 3x3 sheet did not show a 0.2 s black flash. Use it for overall structure, and `qa` for defects. Existing files are not overwritten without `--overwrite`. Each FFmpeg tool call has a 60-second timeout by default; change it with `--timeout`. If your FFmpeg build has no default font, pass `--font-file`.

**`fdiet frames <video> 4.2 7.5 10.0 -o previews`** writes bounded, timestamp-named JPEG previews to `previews` and reports source and preview sizes. `-o` aliases `--out-dir`. The quality option is FFmpeg's qscale, not a percentage.

On image cost: [Anthropic's vision docs](https://platform.claude.com/docs/en/build-with-claude/vision) count 28x28 patches after model-tier-specific resizing. FrameDiet does not estimate image tokens, because the receiving model and tier are not known to it.

### Layer 2: compact context about media and scenes

**`fdiet json <file>`** detects Whisper, WhisperX, Faster-Whisper or Remotion caption JSON and prints `word[start-end]` per word, in integer milliseconds (`--unit s` for seconds). Any other JSON goes to the TOON encoder instead (see below). Detection is by shape, not a lossless conversion; keep the source file when confidence scores or other metadata matter.

Words the aligner could not time (WhisperX leaves `start` and `end` off tokens such as `"2014."` or `"£13.60"`) are written `word[?]` rather than a made-up `[0-0]`, and the header gains `?=no timing in source`. A segment's `speaker` stays in its label: `[500-4200 SPEAKER_00]`.

**TOON output.** For other JSON, `fdiet json timeline.json` writes [TOON 4.4 (working draft)](https://github.com/toon-format/spec/blob/main/SPEC.md). The encoder is a small independent implementation, not a copy of the reference one, and has only its own tests so far. Uniform arrays of objects become tables; non-uniform arrays use list form, so optional fields are never dropped. `--precision N` rounds floats on purpose; without it values round-trip.

**`fdiet digest <Scene.tsx>`** prints a bounded index of Remotion `Composition`, `Sequence`, section and media tags with line ranges. It is a heuristic index, not a JSX parser, and does not infer rendered timing.

**`fdiet probe <path>`** summarizes stream metadata for one media file, or dependencies, likely source files and media assets for a project directory. For video streams it adds `WARN` lines when the display is rotated (for example phone footage with `rotation=90`) or the frame rate looks variable (average rate more than 2% off the base rate, a heuristic), the two usual reasons a preview drifts from the audio.

**`fdiet html <file>`** prints HTML with long SVG paths (`d` values of 60 characters or more), base64 data URIs and inline script and style bodies replaced by markers. Short paths, other attributes and text stay as they are. `--strip-classes` and `--strip-styles` also collapse long `class` and `style` values. On three landing pages the default removed 73–78% of the tokens and `--strip-classes` up to a further 46% (Tailwind-heavy page); the result was still 12–47 times the visible text. HyperFrames' own website workflow does not feed raw HTML to the model (it captures screenshots, visible text and computed styles), so this helps only when an agent reads a saved page itself. [Details](bench/website-html.md). It is a reading aid; the source file is not changed.

### Layer 3: shorten command output

**`fdiet exec -- <command>`** runs a command directly (no shell), removes progress lines and ANSI codes, and keeps a bounded set of diagnostics. A failing command returns its exit code and the last diagnostic lines, with critical lines such as `FATAL` kept even after long noise. A successful run keeps the tail, stream and output metadata, and the result lines of FFmpeg analysis filters (`black_start`, `Peak level dB`, `mean_volume` and similar). When it drops anything, the header says so: `Showing 9 of 108 lines (99 progress).`, plus `Full output: command ffmpeg ...` when non-progress lines were dropped too.

On successful encodes `exec` also drops final codec statistics; those lines remain visible on failures.

**`fdiet init`** adds a Claude Code `PreToolUse` hook for the `Bash` tool. It rewrites into `framediet exec -- ...` only a single, direct call whose output is mostly progress:

- `ffmpeg` with a real output file (not `-f null`, `-` or `/dev/null`) and no analysis filter such as `blackdetect`, `astats`, `volumedetect` or `ebur128`;
- `yt-dlp` downloads (not `-F`, `--dump-json`, `--print`, `-g`, `--simulate` and other listing flags);
- `manim` renders;
- direct `remotion`/`hyperframes` binaries, or `npx`/`bunx`/`pnpm exec|dlx` with those tools and the `render`, `still`, `bundle` or `benchmark` subcommand; package flags, scoped Remotion CLI and package versions are recognized.

`ffprobe`, `whisper`, `ffmpeg -version`/`-filters`/`-i file`, `remotion compositions`, `studio` and any `--help` pass through untouched, because their output is the data you asked for. So do pipes, chains, redirects and other shell syntax. To skip the hook for one call, prefix it with `command` (`command ffmpeg -i a.mp4 b.mp4`). The hook returns no permission decision, so your configured approvals stay in force.

Live check: on Claude Code 2.1.319 (Windows, `claude -p --allowedTools Bash`, default permission mode) a hooked `ffmpeg` call came back as the `[OK] FrameDiet: ...` summary without `frame=` progress lines. Claude Code's documentation says permission rules are evaluated against the input the hook returns. The same check passed with the plugin loaded through `claude --plugin-dir` and no pip-installed `framediet` on `PATH`: the hook ran the plugin's `bin/framediet` launcher and the rewritten call resolved to it. Installing from the GitHub marketplace (`claude plugin marketplace add` and `install`) was run on Windows on 2026-11-08 and the plugin showed as enabled, version 0.1.0; its hook was not re-run from that install. Not tested: auto mode, interactive approval prompts, macOS or Linux, other versions.

### Layer 4: housekeeping

**`fdiet slim <skills-dir>`** is a separate utility that ships here because video skills and prompts tend to carry long code blocks (Remotion scenes, FFmpeg recipes) that cost context on every load. It previews long fenced code blocks in skill Markdown files that could move to reference files; `--apply` writes them under `references_diet/` with backups of the changed files. The preview is the default. It is a narrow Markdown transformation, not a lazy-loading system.

**`fdiet bench`** prints sizes for bundled synthetic examples. The synthetic FFmpeg log is deliberately progress-heavy (99% reduction); that is not a general expectation for quiet logs. Real-run measurements are in [`bench/`](bench).

## How the numbers are made

- Tokens: `cl100k_base` through `tiktoken` as a stand-in. Claude's tokenizer is different, so absolute counts differ; ratios are indicative.
- Images: tokens from the documented `ceil(w/28) x ceil(h/28)` rule with the published resize limits (1568 px / 1568 tokens standard; 2576 px / 4784 tokens high-resolution tier). Estimates, not measurements.
- Detection tests use a ground-truth clip with known injected defects and a control clip. The control showed false positives (freeze warnings on pauses that were intentional); since then likely holds are reported as notes (see `qa` above), and thresholds are exposed.
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
