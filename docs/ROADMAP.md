# Product direction

FrameDiet can remain one repository for video and anatomy/SVG workflows if the shared core stays small and the domain tools remain opt-in. This is the working architecture; the package layout should change only when a second domain has a concrete implementation.

## Boundaries

- **Shared core:** command-line wiring, permission-preserving hooks, bounded command output, common file/input limits, and benchmark reporting. A capability belongs here only when more than one domain needs it.
- **Video domain, implemented now:** transcript views, contact sheets, frame previews, FFmpeg QA, Remotion/HTML scene digests, and media/project probing. Keep these as path/data-in, report-out operations; `cli.py` handles argument parsing and printing.
- **Anatomy/SVG domain, later:** prototype one source or SVG digest and one deterministic check derived from real workflow requirements, such as a compact result for selected `verify.md` checks. Do not copy another skill wholesale; preserve upstream licenses when adapting code or examples.

The current Python modules live in a flat `src/framediet/` package. Keep that layout while video stabilizes. If the anatomy/SVG domain lands, group its implementation under an explicit domain package (for example `framediet.anatomy`) and move video modules only as part of a reviewed API change. Do not turn `framediet` into an optimizer for arbitrary data or applications.

## Skill loading and scope

The `slim` command is a narrow Markdown transformation: it previews long fenced-code extraction and can write references plus backups when explicitly applied. It is not a general lazy-loading system for skills. A future shared reference loader should be based on demonstrated use across at least two domains and should preserve the source skill unchanged by default.

## Rollout

1. Stabilize the video commands and their bounded reports.
2. Compare FrameDiet's report with the existing local kinetic-film workflow before making broad claims about video QA. That workflow already has render gates and contact-sheet support.
3. Prototype one anatomy/SVG check and measure its output against the real skill task, not only the size of all reference files.
4. Move shared capabilities into a core package only after both domains use them.
5. Revisit the `FrameDiet` name if anatomy/SVG becomes a first-class part of the product. Keep the current name while the shipped product is video-first.

Tests (54, `pytest tests`) cover transcript formatting, log filtering, TOON shapes, hook command matching and QA log parsing. Still missing: tests that run the FFmpeg-backed commands end to end, and a comparison of the TOON encoder against the reference implementation.

## Local measurement notes

`bench/baseline-skills.md` records source-size measurements and `cl100k_base` token counts for the local anatomy, watch, and kinetic-test skills, plus a PixelFX directory inventory. `bench/baseline-tiktoken.txt` contains the per-file counts; these are a tokenizer proxy, not Claude token counts or end-to-end savings. The benchmark command itself uses synthetic fixtures and reports those separately.

The local PixelFX materials have demo source and rendered media but no skill instruction file, so they can inform a future media-QA check but not a skill-reference token benchmark. One FrameDiet QA smoke run has been recorded for a PixelFX reel and one for a kinetic-test render; these are not representative benchmarks. The kinetic-test skill and references are token-counted, but its `finish.py` gates have not been run or compared with FrameDiet. Its skill prose and script thresholds also need reconciliation: the prose describes under one-quarter of frames as still, while `finish.py` uses a 40% still-share gate.

## Positioning

Adjacent tools already cover parts of this problem. Do not claim first-mover status, exclusive video QA, or a universal token reduction. FrameDiet's candidate distinction is a compact deterministic report with optional frame previews and context summaries; validate that distinction against the local kinetic-film workflow and other tools before publishing stronger claims.
