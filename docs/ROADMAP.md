# Roadmap

FrameDiet gives an agent that makes video with code the answer instead of the raw material: a QA verdict instead of frames, a short log instead of progress lines, a compact transcript instead of word JSON. This file says what is shipped, what comes next and what will not be built. Every claim it plans for has to be measured the way `bench/` measures today.

## Where it stands (2026-11-08)

Shipped in `main`, version 0.1.0, not yet tagged or on PyPI:

- **Commands:** `qa` (with `--strict`, `--json` and hold notes), `frames` (including `-o`), `sheet` (with timeouts), `json` (transcripts, TOON), `digest`, `probe` (rotation and VFR warnings), `html` (with `--strip-classes`/`--strip-styles`), `exec`, `init`/`hook`, `slim`, `bench`.
- **Claude Code plugin:** hook, skill and a `bin/framediet` launcher that runs from source. The repo is its own marketplace. Validated with `claude plugin validate`, live-checked with `--plugin-dir`.
- **Hook fixes:** npx/bunx/pnpm and direct Remotion/HyperFrames render commands are recognized; plugin installs invoke their own launcher. Data-producing commands and shell chains still pass through.
- **Tests:** 142 in `tests/`, run by CI on Linux and Windows with Python 3.10 and 3.12; CI installs FFmpeg for generated-clip end-to-end coverage.
- **Evidence in `bench/`:**
  - end-to-end sessions on real usage: defect QA $0.58 → $0.26 and $0.61 → $0.43 per run; transcript and render tasks about equal; n=2 per arm;
  - render logs: Remotion 1,529 → 175 tokens, HyperFrames 7,191 → 362;
  - frame-sampling rules of two critic-loop skills compared with `qa`;
  - three landing pages through `html`;
  - a defect clip with ground truth.

## Principles

- **Deterministic first.** A check that a script can answer should not cost vision tokens. Anything that needs judgement (layout, typography, pacing) stays with the model and is not claimed.
- **No silent loss.** Every summary says what it dropped (`Showing 9 of 108 lines`, `note:` lines, `word[?]`). Commands whose output is the data are never rewritten.
- **Claims follow measurements.** A number reaches the README only with its raw inputs and a script in `bench/`, and with its limits written next to it. No fixed percentage claims.
- **Stay small.** No required dependencies; FFmpeg is the only external tool. Opt-in flags instead of changed defaults.

## Next: 0.1.0 release

1. **Install path:** Windows marketplace install checked 2026-11-08 (plugin enabled, 0.1.0). Still to check: one of macOS or Linux, and that the hook fires from the marketplace install. Document any Python-on-PATH issue found.
2. **PyPI (postponed by the owner):** upload 0.1.0 by hand per `docs/RELEASE.md`, then switch to Trusted Publishing from a tagged GitHub Actions release.
3. **Tag and release:** `v0.1.0` tag, GitHub release notes that list what is measured and what is not.
4. **Plugin icon:** a square PNG for the plugin directory. It follows the channel's brand book, which is frozen, so it is the owner's call.
5. **Listing:** the awesome-list is graded by a model from the README (see `docs/awesome-video-skills-pr.md`); prerequisites are stars and a README with a result image. Not a PR.

## 0.2: stronger evidence and fewer blind spots

- **Closed defects from the three-task run and 08.11 audit:** hook package parsing and plugin launcher selection, `frames -o`, successful encoder-stat filtering, FFmpeg end-to-end CI tests, `qa --json`, `digest`/`slim`/`sheet` housekeeping, and Python/Markdown LF normalization. The render-log scripts were rerun after T4; their token counts were unchanged.
- **More end-to-end tasks.** Results of the three-task run: QA reel −29% with no false title-card claim; transcript lookup and HyperFrames render +0–3%, because the work is light and the hook did not fire. Next: 5 runs per arm instead of 2, one non-Opus model, and a "nudged plain" arm whose prompt names the FFmpeg filters. That arm shows how much of the gain is just knowing which checks to run.
- **Hook coverage.** In the real session the agents wrote `ffmpeg … | tail -5`, and the hook correctly left that alone. Plan:
  - Static survey done (`bench/hook-coverage.md`, 5 skills): direct `npx remotion render|still` and `npx hyperframes render` are rewritten; `npm run <script>`, `bash scripts/*.sh`, `npx remotion lambda render` and background `&` pass through. Several skills only describe the render in prose, so the agent picks the command. This does not yet justify wrapping scripts, so the opt-in list below stays the plan.
  - an opt-in list of extra commands to wrap (for example a skill's `scripts/render.sh`), in plugin `userConfig` or an environment variable;
  - deciding, with data, whether `<render command> 2>&1 | tail -N` should become `framediet exec`. It already shortens the output, so the gain may be too small to justify rewriting pipes.
- **Auto mode.** Test the hook under Claude Code's auto mode. The docs say a changed input can be denied there.
- **`qa` thresholds on more videos.** First pass done (`bench/qa-corpus.md`, 10 published demo videos from 6 repos, thresholds 0.5/0.75/1.0 s): 7 of 10 get WARN at every threshold, 0.5 s adds 11 freeze intervals, 1.0 s removes 2. Visual spot checks suggest many freeze and black WARNs are intentional holds, title cards or dark grading. Verdict: 0.75 s is a cue to look, not proof of a defect; the default stays until a larger labelled set exists. Next: label a set by hand, then consider recognising mid-video end cards and tuning the black threshold for dark grading.
- **Loudness.** Add integrated loudness (EBU R128) next to the peak check, because platforms normalize to about −14 LUFS and the channel already mixes to it.
- **Transcripts:** read `whisper-ctranslate2` and `parakeet-mlx` JSON from real output files; keep WhisperX word-level `speaker` when present; compare the TOON encoder with the reference implementation.

## 0.3: integration with existing video skills

- **Skill-author kit.** A short section and a copy-paste block for SKILL.md: run `framediet qa --strict` after render, read the verdict, then look only at `--frames-dir` previews. Measure it on one real skill with its author's consent before claiming anything for that skill.
- **Upstream proposals.** Offer the `qa` step to two or three popular skills (HyperFrames, a Remotion skill, motion-video-kit) as an optional step, with their own numbers from `bench/`. Do not copy their code. Respect each license; AGPL and non-commercial projects are reference only.
- **Agents other than Claude Code.** Document use from Codex or other agents through the CLI and their instruction files. The hook is Claude Code only; the commands are not.
- **MCP server: only if asked.** The CLI already works from any agent; an MCP wrapper adds a dependency and a second interface to keep in sync.

## Later: anatomy/SVG domain (proposal)

The `anatomy` skill builds detailed isometric SVG figures; its `SKILL.md` plus `references/` measure 92,619 `cl100k_base` tokens when all are loaded. A possible FrameDiet domain:

- **SVG index:** parts, layers and painter's order with line ranges, like `digest` for scenes.
- **Deterministic checks:** one or two checks from its `verify.md`, such as draw order or parts outside the frame.

Build it only after 0.2, prototype on real figures, and measure against the real skill task, not against the size of the reference files. If it lands, it goes under `framediet.anatomy` and the project name is revisited.

## Not planned

- Rendering, editing or replacing FFmpeg, Remotion or HyperFrames.
- Judging design, typography, safe areas or "does this look good". That is the model's job, and a deterministic tool claiming it would mislead.
- A general output compressor for all commands; RTK and similar tools cover that.
- Cloud services, accounts or telemetry.

## Known risks

- **Savings depend on behaviour.** Savings depend on the agent choosing `framediet qa` over its own analysis. The skill text nudges it, but nothing forces it.
- **Untested platforms.** The plugin launcher needs Python 3.10+ on `PATH` and has only been run on Windows.
- **Small samples.** The end-to-end numbers rest on n=2 per arm and synthetic clips; they show the mechanism, not a guaranteed saving.
- **Tool updates.** Upstream tools change their log formats (HyperFrames 0.9.23 was measured), so the progress patterns need a fixture per version that is claimed.

## Local measurement notes

`bench/baseline-skills.md` and `bench/baseline-tiktoken.txt` hold source-size counts for the local anatomy, watch and kinetic-test skills (a tokenizer proxy, not end-to-end savings). The kinetic-test skill's `finish.py` gates have not been run or compared with FrameDiet. Its prose and script also disagree on the still-frame share (under one quarter in the prose, 40% in the script).
