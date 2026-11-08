# Hook coverage survey

Static survey of five public video-skill repositories. Star counts are GitHub API values recorded during this review. Only README, `SKILL.md`, and referenced script text was read through GitHub API; no third-party code was run or downloaded. Exact commands and source locations are in `bench/hook-coverage-commands.txt`.

## Results

Reproduce the table with `python bench/hook_coverage.py` from the FrameDiet worktree. The script calculates every Hook result with local `is_safe_media_command`. Rows marked `non-target` are setup or telemetry examples, not render, encode, or download commands.

| Skill (stars) | Source | Kind | Command | Scope | Hook | Reason |
|---|---|---|---|---|---|---|
| heygen-com/hyperframes (81042) | skills/hyperframes/SKILL.md:12 | text-example | `npx hyperframes <command>` | non-target | n/a | Generic CLI placeholder; no render subcommand specified |
| heygen-com/hyperframes (81042) | skills/hyperframes/SKILL.md:8 | instruction | `npx hyperframes events --skill=hyperframes` | non-target | n/a | Telemetry, not render/encode/download |
| heygen-com/hyperframes (81042) | skills/hyperframes/SKILL.md:14 | instruction | `npx hyperframes init <dir> --skip-skills --skill=hyperframes` | non-target | n/a | Project setup |
| haidrrrry/claude-remotion-skill (893) | remotion-motion-graphics/SKILL.md:65 | instruction | `npx remotion render src/index.ts CompId out/video.mp4 --codec h264 --crf 17` | target | rewrite | Documented render CLI |
| haidrrrry/claude-remotion-skill (893) | remotion-motion-graphics/SKILL.md:72 | text-example | `npx remotion render ... --browser-executable=path` | target | rewrite | Documented illustrative render variant |
| haidrrrry/claude-remotion-skill (893) | remotion-motion-graphics/SKILL.md:83 | instruction | `npx remotion still src/index.ts CompId out/check_15.png --frame 15 --overwrite` | target | rewrite | Representative command from documented loop |
| haidrrrry/claude-remotion-skill (893) | remotion-motion-graphics/SKILL.md:90 | instruction | `ffmpeg -v error -ss 1.5 -i out/video.mp4 -frames:v 1 check_1.png` | target | rewrite | Frame extraction invocation |
| wshuyi/remotion-video-skill (465) | SKILL.md:523 | instruction | `npx remotion render MyVideo out/video.mp4` | target | rewrite | Documented render |
| wshuyi/remotion-video-skill (465) | SKILL.md:526 | instruction | `npx remotion render --codec=h264 MyVideo out/video.mp4` | target | rewrite | Documented render |
| wshuyi/remotion-video-skill (465) | SKILL.md:529 | instruction | `npx remotion render --codec=vp8 MyVideo out/video.webm` | target | rewrite | Documented render |
| wshuyi/remotion-video-skill (465) | SKILL.md:532 | instruction | `npx remotion render --codec=gif MyVideo out/video.gif` | target | rewrite | Documented render |
| wshuyi/remotion-video-skill (465) | SKILL.md:535 | instruction | `npx remotion render --codec=mp3 MyVideo out/audio.mp3` | target | rewrite | Documented audio encode |
| wshuyi/remotion-video-skill (465) | SKILL.md:538 | instruction | `npx remotion render --sequence MyVideo out/frames` | target | rewrite | Documented frame render |
| wshuyi/remotion-video-skill (465) | SKILL.md:541 | instruction | `npx remotion still MyVideo --frame=30 out/thumbnail.png` | target | rewrite | Documented still render |
| wshuyi/remotion-video-skill (465) | SKILL.md:601 | instruction | `npx remotion lambda render site-url MyVideo` | target | pass-through | Nested cloud subcommand is not recognized as a direct render invocation |
| wshuyi/remotion-video-skill (465) | SKILL.md:1523 | instruction | `npm run audio` | target | pass-through | Project script wrapper for audio preparation |
| wshuyi/remotion-video-skill (465) | SKILL.md:1524 | instruction | `npm run render` | target | pass-through | Project script wrapper for render |
| wshuyi/remotion-video-skill (465) | SKILL.md:1527 | instruction | `bash scripts/render.sh` | target | pass-through | Shell wrapper invocation |
| wshuyi/remotion-video-skill (465) | SKILL.md:1530 | text-example | `npm run render &` | target | pass-through | Background shell syntax is rejected |
| echris6/motion-video-kit (1370) | business-motion-film/SKILL.md:59 | prose-only | `Render the whole film.` | target | pass-through | No executable command supplied in prose |
| echris6/motion-video-kit (1370) | business-motion-film/SKILL.md:36 | script-reference | `scripts/contact-sheet.sh` | non-target | n/a | Script named for a contact sheet; no render/encode/download invocation |
| nateherkai/herk-edit-kit (2658) | README.md:86 | instruction | `npm run demo` | non-target | n/a | Starts the example workflow; the direct render command follows |
| nateherkai/herk-edit-kit (2658) | README.md:96 | instruction | `npx hyperframes render --quality draft --output renders/demo.mp4` | target | rewrite | Direct render invocation |
| nateherkai/herk-edit-kit (2658) | .agents/skills/edit-video/SKILL.md:33 | prose-only | `Render a draft` | target | pass-through | No executable command supplied in prose |

## Unsupported target forms

The three most common unsupported executable forms tie at one skill each:

1. `npm run <script>` wrappers — 1 skill (`wshuyi/remotion-video-skill`).
2. `bash scripts/*.sh` wrappers — 1 skill (`wshuyi/remotion-video-skill`).
3. Nested `npx remotion lambda render` — 1 skill (`wshuyi/remotion-video-skill`).

Background shell syntax such as `npm run render &` is also passed through in that skill. Prose-only render directions occur in two skills, but do not provide a command string to classify. The command inventory also includes examples that are outside render/encode/download scope and labels them `non-target`.

## Findings and limits

The hook captures direct `npx remotion render`, `npx remotion still`, direct `npx hyperframes render`, and the documented FFmpeg frame-extraction command in this sample. It passes through project script wrappers and shell wrappers. This is a static sample of commands in the selected README/`SKILL.md` sources; it does not establish that every linked reference or every repository script was exhaustively reviewed. Where a skill gives only prose, an agent may independently choose a different executable command.

## ROADMAP suggestion

Consider opt-in support for common project wrappers such as `npm run <script>` and `bash scripts/*.sh`, or a user-configured allowlist. These wrappers can perform arbitrary work, so any expansion should remain conservative. This survey alone does not justify changing hook behavior.

## Sources

- [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes), 81,042 stars; `skills/hyperframes/SKILL.md`.
- [haidrrrry/claude-remotion-skill](https://github.com/haidrrrry/claude-remotion-skill), 893 stars; `remotion-motion-graphics/SKILL.md`.
- [wshuyi/remotion-video-skill](https://github.com/wshuyi/remotion-video-skill), 465 stars; `SKILL.md`.
- [echris6/motion-video-kit](https://github.com/echris6/motion-video-kit), 1,370 stars; `business-motion-film/SKILL.md`.
- [nateherkai/herk-edit-kit](https://github.com/nateherkai/herk-edit-kit), 2,658 stars; `README.md` and `.agents/skills/edit-video/SKILL.md`.

Star counts are point-in-time metadata. A command described only in prose is marked as prose-only rather than reconstructed as an executable invocation.
