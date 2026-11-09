# End-to-end Claude Code, three tasks: plain vs FrameDiet plugin (2026-11-08)

Real numbers from `claude -p --output-format json`. Extends `e2e-session.md` (one task, `fdiet init` + CLAUDE.md). Here the diet arm is the **plugin** a real user installs. Reproduce with `bash bench/e2e_tasks.sh <workdir> [runs] [hyperframes-project-dir]`.

## Setup

- Claude Code 2.1.319, model in `modelUsage`: `claude-opus-5-5` for all 12 runs. Windows 11, Git Bash, FFmpeg 9.0 (gyan full build), HyperFrames 0.9.23 via `npx`.
- Command: `claude -p "<prompt>" [--plugin-dir D:/dev/FrameDiet] --output-format json --allowedTools Bash Read --max-turns 25 < /dev/null`, run in a fresh copy of the task dir for every run. Order per task: plain-1, diet-1, plain-2, diet-2.
- **diet** = `--plugin-dir` only (`.claude-plugin/`, `hooks/hooks.json`, `skills/framediet/SKILL.md`, `bin/framediet`). No `fdiet init`, no CLAUDE.md. **plain** = no flag. Verified from the session transcripts: the framediet skill appears in all diet sessions and in none of the plain ones.
- No `framediet` hook in `~/.claude/settings.json` (user level had no hooks at all), and the task dirs have no `.claude/`. The scratch dirs are created fresh by the script.
- **Pip-installed `framediet` is on PATH** (`<user>\AppData\Local\Programs\Python\Python311\Scripts`) in both arms. Plain agents never called it (no `framediet` in any plain command), because nothing told them it exists. In the diet arm it is unknown whether `framediet` resolved to the plugin's `bin/` or to the pip one; both are the same source tree version here.
- The user-level CLAUDE.md, memory and other plugins of the machine are loaded in both arms (about 19-20k tokens of fixed context, same as the earlier run).
- A first T1 attempt was discarded: the filter graph (`f.txt`) and the T2 `truth.json` sat inside the task dirs and the agents read `f.txt` (it spells out the defects). Those four runs are not used (cost was 0.29 / 0.29 diet, 0.41 / 0.39 plain). The script now keeps the filter file and the truth file outside the task dirs.

## Tasks, prompts, ground truth

**T1 QA.** `reel.mp4`, 1080x1920 (9:16), 30 fps, 25 s, testsrc2 pattern with burned-in timecode, 330 Hz tone.
Prompt: `Check reel.mp4 for visual and audio defects before publishing; list real defects with timestamps.`
Ground truth, 3 real defects: black flash 11.0-11.2 s; freeze 17.0-17.8 s (frame 510 held); audio peak above 0 dBFS (about +1.0 dBFS, in the first tens of ms because of the 9x gain). Not a defect: a static 2 s title card ("SPRING DROP") at 0-2 s. Score: real found (of 3) and false claims (the title card counts as one when it is listed as a defect, even hedged).

**T2 transcript.** `transcript.json`, WhisperX-shaped (`segments[].words[]` plus `word_segments`), 60.8 s, 157 words, 9 sentences. 4 number tokens (`40`, `12`, `2,400`, `1080p`) have no `start`/`end`/`score`. A decoy phrase "rebuild the index" occurs earlier.
Prompt: `In transcript.json find the exact start and end time of the phrase 'rebuild the whole index' and the total number of words.`
Ground truth: start 29.517 s, end 30.938 s, 157 words (counting the 4 untimed ones; 153 timed).

**T3 render + check.** A copy of the blank HyperFrames starter (static white "Title" on black, empty GSAP timeline, 10 s, 1920x1080, no audio; `package.json` scripts call `npx --yes hyperframes@0.9.23 ...`).
Prompt: `Render this HyperFrames project to out.mp4 and confirm the output is valid (duration, resolution, no black or frozen frames).`
Ground truth: a valid 10.000 s, 1920x1080 H.264 file; frames are all identical (frozen, by construction) and nearly all black with a small title. A correct answer reports the file valid and says honestly that "no frozen frames" does not hold because the project is the unedited starter.

## Results

| Run | Input | Cache creation | Cache read | Output | Turns | Cost USD | Correct |
|---|---:|---:|---:|---:|---:|---:|---|
| T1 plain-1 | 26 | 41,037 | 615,149 | 7,112 | 14 | 0.594 | 3/3 real, 1 false (title card listed as defect #3, "fine if intended") |
| T1 plain-2 | 26 | 40,708 | 586,722 | 8,709 | 18 | 0.617 | 3/3 real, 1 false (title card under "Real defects" #3, hedged) |
| T1 diet-1 | 18 | 26,771 | 440,685 | 3,105 | 13 | 0.364 | 3/3 real, 0 false (title card named "not a defect") |
| T1 diet-2 | 22 | 37,368 | 543,570 | 4,249 | 16 | 0.493 | 3/3 real, 0 false |
| T2 plain-1 | 10 | 19,441 | 218,837 | 1,343 | 5 | 0.226 | correct |
| T2 plain-2 | 10 | 19,928 | 219,199 | 1,360 | 5 | 0.231 | correct |
| T2 diet-1 | 12 | 20,942 | 222,107 | 994 | 6 | 0.232 | correct |
| T2 diet-2 | 10 | 21,031 | 173,775 | 1,028 | 5 | 0.224 | correct |
| T3 plain-1 | 18 | 33,949 | 457,462 | 3,150 | 10 | 0.426 | correct |
| T3 plain-2 | 18 | 34,730 | 471,936 | 3,112 | 10 | 0.435 | correct |
| T3 diet-1 | 24 | 33,719 | 588,975 | 2,479 | 14 | 0.437 | correct |
| T3 diet-2 | 26 | 33,913 | 638,191 | 2,390 | 14 | 0.447 | correct |

Per-task means (n=2 per cell):

| Task | plain cost | diet cost | diff | plain turns / output tok | diet turns / output tok | Correctness |
|---|---:|---:|---:|---|---|---|
| T1 QA | 0.605 | 0.429 | -29% | 16 / 7,911 | 14.5 / 3,677 | real defects 3/3 vs 3/3; false claims 2 of 2 runs (plain) vs 0 of 2 (diet) |
| T2 transcript | 0.228 | 0.228 | 0% | 5 / 1,352 | 5.5 / 1,011 | all four correct |
| T3 render + check | 0.430 | 0.442 | +3% | 10 / 3,131 | 14 / 2,435 | all four correct |

## What the agents did

- **T1 plain**: FFmpeg `blackdetect`/`freezedetect`, numpy peak and LUFS analysis, contact sheet and zoom crops (4-5 image Reads). Both listed the title card as a numbered "defect" with "fine if intended" and added advisories (timecode overlay, loud tone, title box close to edges). Run 2 also noted a click at 0-34 ms. All three real defects found.
- **T1 diet**: `framediet qa reel.mp4 --frames-dir`, then `framediet frames` at the flagged times (5 and 7 image Reads of tiny previews), plus per-window audio peaks. Both called the title card intentional and put it under "Not a defect". The audio defect was located at 0-0.22 s (run 1) and 0-0.04 s (run 2). Both added a "loud throughout" advisory.
- **T2 plain**: `head -c 1500 transcript.json`, one Python script, then a count check (3 Bash calls). No images.
- **T2 diet**: both runs ran `framediet json transcript.json` first (run 2 with `| head -c 6000`), then a Python check for the phrase and the word count (2 Bash calls each); the Python check was what produced the exact timings and the 157. The compact view did not reduce cost here: the file is small (about 25 KB), and about 70% of each T2 run's cost is cache creation, mostly the fixed starting context that the compact view does not touch (prices fitted to the 12 runs in the table: about 8, 0.2 and 20 USD per million tokens for cache creation, cache read and output).
- **T3 plain**: `npx --yes hyperframes@0.9.23 check`, `render`, `ffprobe`, FFmpeg blackdetect/freezedetect, 1 still read. 10 turns.
- **T3 diet**: `check`, `render`, `ffprobe`, then `framediet qa out.mp4 --frames-dir` and `framediet frames out.mp4 5 9.9 ...` (2 image Reads). In both runs the first `frames` call failed on a wrong flag (`-o`; the working one is `--out-dir`), then `frames --help`, then a retry. That costs 2 to 3 extra turns. 14 turns vs 10.

## Did the hook fire?

- **T3: no.** Both diet runs used `npx --yes hyperframes@0.9.23 render -o out.mp4 2>&1 | tail -N`. Two reasons it passes through: the pipe (a shell chain, by design) and the `--yes` / `@version` form, which `framediet hook` does not recognize even without a pipe. Checked offline: `echo '{...}' | bin/framediet hook` rewrites `npx hyperframes render -o out.mp4` to `framediet exec -- ...`, but returns nothing for `npx --yes hyperframes@0.9.23 render -o out.mp4`, for a bare `hyperframes render`, and for the pipe form. The starter project's own `package.json` scripts use exactly the `--yes ...@0.9.23` form, so this is probably the common real-world command. The string `Showing 12 of 116 lines` in the diet transcripts is SKILL.md text, not hook output, and `[OK] FrameDiet` never appeared in T1-T3.
- **Diagnostic run (a 13th, extra run, cost 0.214, 3 turns, stream-json `--verbose`):** `--plugin-dir D:/dev/FrameDiet`, prompt asked for exactly `ffmpeg -y -i reel.mp4 -c:v libx264 -crf 30 -an small.mp4` with no pipes. The tool result carried `[OK] FrameDiet: command completed successfully. Showing 18 of 59 lines (7 progress)...`. So the plugin hook loads and fires through `--plugin-dir` on Windows when the command shape matches; agents just rarely write that shape.

## Limits

- n=2 per cell, one model, synthetic inputs, a single day. Differences of a few percent (T2, T3) are inside run-to-run noise; T1's -29% is larger than the in-arm spread (diet 0.364-0.493, plain 0.594-0.617) but still n=2.
- The T1 gain comes from `framediet qa` plus the skill pointing agents to it, not from the hook. Plain agents might close part of the gap with a tuned one-pass prompt.
- T1 false-claim scoring is a judgement: the plain agents hedged the title card ("fine if intended"); counted as false because it was listed as a numbered defect. A lenient reading gives 0 false for both arms.
- Extra advisories (loud tone, timecode overlay, title box margins) were not scored either way.
- T2's file is small; compaction needs bigger transcripts to pay off. The plugin did not hurt: the skill listing adds a little cache-creation (about +1-2k tokens vs plain), visible in T2 cache-creation.
- The pip-installed `framediet` on PATH in both arms is a possible contaminant for plain (not used by any plain agent) and an unknown for which binary diet used.
- The T1 discarded attempt shows how easily the task dir can leak ground truth; the current script keeps it outside.
- Cost includes about 19-20k tokens of the test machine's own context in all runs; prompt-cache timing differs between runs.
