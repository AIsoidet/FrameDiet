# End-to-end Claude Code session: plain vs FrameDiet (2026-11-08)

Real usage numbers from `claude -p --output-format json`, not token proxies. Reproduce with `bench/e2e_session.sh <workdir> [runs]`.

## Setup

- Claude Code 2.1.319. Model reported in `modelUsage`: `claude-opus-5-5` (all four runs).
- Windows 11, Git Bash, FFmpeg 9.0 (gyan full build), FrameDiet installed with `pip install -e` into a scratch venv whose `Scripts` dir was first on `PATH` for the `diet` runs (`framediet` resolved there).
- Two identical dirs, each with the same `clip.mp4` (640x360, 30 fps, 20 s, testsrc2 with burned-in timecode, 440 Hz tone). The script regenerates the clip; the old bench has no generator.
- `diet/`: `framediet init --dir .` (project-level PreToolUse hook in `.claude/settings.json`) plus a short `CLAUDE.md` copied from `SKILL.md` wording (`framediet qa`, `framediet frames`). `plain/`: nothing.
- Prompt (identical): `Re-encode clip.mp4 to out.mp4 with libx264 crf 23, then check out.mp4 for visual and audio defects and list each with timestamps.`
- Command: `claude -p "<prompt>" --output-format json --allowedTools Bash Read --max-turns 25 < /dev/null`, run in each dir; order plain-1, diet-1, plain-2, diet-2.

## Ground truth (injected into the clip)

1. Black 6.0-6.3 s
2. Freeze 9.0-10.0 s
3. Black 13.0-13.3 s
4. Audio peak above 0 dBFS (source about +1.0 dBFS by `fdiet qa`)

## Results

| Run | Input (uncached) | Cache creation | Cache read | Output | Turns | Cost USD | Defects found (of 4) |
|---|---:|---:|---:|---:|---:|---:|---|
| plain-1 | 26 | 39,723 | 692,736 | 8,470 | 17 | 0.626 | 4 (both blacks, freeze, audio) |
| plain-2 | 22 | 31,444 | 545,452 | 8,349 | 14 | 0.528 | 4 |
| diet-1 | 12 | 20,805 | 268,019 | 1,682 | 8 | 0.254 | 4 |
| diet-2 | 14 | 20,606 | 318,932 | 2,302 | 10 | 0.275 | 4 |
| **plain mean** | 24 | 35,584 | 619,094 | 8,410 | 15.5 | **0.577** | |
| **diet mean** | 13 | 20,706 | 293,476 | 1,992 | 9 | **0.264** | |

Diet runs cost about 54% less on average (0.264 vs 0.577 USD); cache-read tokens about 53% fewer, output tokens about 76% fewer, turns 9 vs 15.5. Run-to-run spread inside each arm is small relative to the gap, but n=2.

## What each agent did

- **plain**: no full-frame review. It ran its own FFmpeg analysis (blackdetect, freezedetect, scene select, astats/ametadata RMS and peak, raw-sample analysis with Python/numpy), rendered spectrograms and waveforms and read a few images (run 1: about 6 image Reads, among them 2 grabbed frames; run 2: one contact sheet), compared against the source (SSIM). It re-encoded audio to AAC. Both plain runs also reported an extra audio click at about 12.89 s (+4.8 dBFS) as "added by the re-encode". That is not in the ground truth; it was not verified independently here and it is not counted as a hit or a false positive.
- **diet**: ran `framediet qa out.mp4` (run 1 also `--frames-dir`), read about 3 tiny preview JPEGs at the flagged times (1 KB for black frames), reported all four with the QA line's timestamps. Both runs used `-c:a copy` for the audio, so the encode task differed slightly from plain (audio untouched, so the audio defect is source-only). Run 2 additionally used `framediet frames`.

## Did the hook fire?

No visible evidence. Searching the session transcripts for the hook's `Showing N of M lines` header found nothing. The encode commands the agents wrote were `ffmpeg ... 2>&1 | tail -5`, a shell chain, which the hook passes through by design. So the savings here come from `framediet qa` plus the CLAUDE.md pointer, not from the log-shortening hook. This test does not measure the hook.

## Limits

- n=2 per arm, one task, one synthetic 640x360 clip with simple defects, one model. Agent behaviour varies a lot: another plain run could be cheaper or cost more.
- Not isolated: the `diet` advantage mixes the CLAUDE.md nudge toward `qa` with the tool itself. A plain agent told to use `ffmpeg blackdetect,freezedetect,astats` in one pass might close much of the gap.
- Audio handling differed (copy vs AAC re-encode), which changes both the work and the "defects" list for audio.
- Cost includes a roughly 19-20k-token base context (user-level CLAUDE.md, memory, plugins and skills of the machine running the test) in both arms; a clean environment has a smaller fixed cost, so relative savings would be larger and absolute ones similar.
- Prompt cache state differed between runs (cache-creation and read both depend on timing), so cost is not perfectly comparable.
- Detection is judged by the final answer text only; no checks beyond the four injected defects.
- Both arms found all four, so this clip does not show a detection difference. The earlier frame-based finding (1 of 4) does not apply: the plain agent here used FFmpeg detectors and not frames.
