# Listing draft for awesome-claude-video-skills

A draft, not submitted. Open the PR only after the 0.1.0 release steps in `docs/ROADMAP.md` (marketplace install checked, tag, PyPI). The upstream README was restructured since this draft was first written: it now says it lists 454 repos graded by Agent Skills Hub and has a "Which one to install" section. Re-read the current table layout before editing, and follow its contribution rules.

Suggested title: `Add FrameDiet (token-saving QA and context tools for video agents)`

```markdown
| [FrameDiet](https://github.com/AIsoidet/FrameDiet) | MIT | Claude Code plugin + CLI that gives video agents answers instead of raw material: deterministic FFmpeg QA verdicts instead of frame sampling, short Remotion/HyperFrames/FFmpeg render logs, compact Whisper/WhisperX transcripts. Raw benchmark logs in the repo. |
```

Suggested summary:

> Adds FrameDiet, a small MIT CLI and Claude Code plugin for agents that make video with code. `framediet qa` checks a render for black frames, freezes and audio peaks in one text verdict (it marks likely title cards and held beats as notes); the plugin hook shortens progress-heavy render logs (Remotion 1,529 → 175 tokens, HyperFrames 7,191 → 362 on our runs); `framediet json` compacts word-level transcripts. In a small end-to-end test (n=2 per arm, one task) a Claude Code session cost $0.26 with FrameDiet and $0.58 without, with the same defects found. All numbers come with raw logs and scripts in `bench/`; no fixed percentage saving is claimed.

Do not make a first-mover or universal token-savings claim, and keep the n=2 caveat if the session numbers are quoted.
