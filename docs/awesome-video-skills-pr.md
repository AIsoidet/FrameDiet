# Listing draft for awesome-claude-video-skills

Not submitted. Checked 2026-11-08 against upstream (`zhuyansen/awesome-claude-video-skills`): the list is generated, not edited by hand. A decision model reads each repo's README and grades it. Rules from its README: (1) it makes or edits video or motion graphics, (2) an agent operates it, (3) it has a README, (4) at 50 stars or more it is listed on topic alone; under 50 it must clear a README quality bar (shows the result, one-command start, concrete outcome, complete docs) and have 5 stars unless it names Claude Opus 5.5. Entries are image cells in generated tables, so the table row below is only a description for an issue. Two risks: FrameDiet is QA and logging tooling for video agents, not a video maker (rule 1), and it has few stars. Before opening anything: get to 5 stars, name Claude Opus 5.5 in the README where the end-to-end runs are described (they used it), and put a result image and a one-command start at the top. Then open an issue (the list's own route for misfiled repos), not a PR. PyPI is postponed by the owner.

Suggested title: `Add FrameDiet (token-saving QA and context tools for video agents)`

```markdown
| [FrameDiet](https://github.com/AIsoidet/FrameDiet) | MIT | Claude Code plugin + CLI that gives video agents answers instead of raw material: deterministic FFmpeg QA verdicts instead of frame sampling, short Remotion/HyperFrames/FFmpeg render logs, compact Whisper/WhisperX transcripts. Raw benchmark logs in the repo. |
```

Suggested summary:

> Adds FrameDiet, a small MIT CLI and Claude Code plugin for agents that make video with code. `framediet qa` checks a render for black frames, freezes and audio peaks in one text verdict (it marks likely title cards and held beats as notes); the plugin hook shortens progress-heavy render logs (Remotion 1,529 → 175 tokens, HyperFrames 7,191 → 362 on our runs); `framediet json` compacts word-level transcripts. In a small end-to-end test (n=2 per arm, one task) a Claude Code session cost $0.26 with FrameDiet and $0.58 without, with the same defects found. All numbers come with raw logs and scripts in `bench/`; no fixed percentage saving is claimed.

Do not make a first-mover or universal token-savings claim, and keep the n=2 caveat if the session numbers are quoted.
