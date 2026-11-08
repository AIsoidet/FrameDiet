---
name: framediet
description: Use FrameDiet to summarize video render output, compact Whisper or caption JSON for inspection, create timestamped contact sheets, and preview safe extraction of large skill examples.
---

# FrameDiet workflow

Use FrameDiet when a video task produces verbose CLI logs, word-level transcript JSON, many rendered frames, or large inline HTML/SVG payloads.

## Choose the right command

- Use `framediet exec -- <command>` for a single media-tool invocation whose output is noisy. It returns the wrapped command's exit status. Run the original command directly when the complete output is needed.
- Use `framediet json <file>` to create a compact transcript view or TOON serialization. Preserve the source file; the compact output may omit optional metadata.
- Use `framediet sheet <video> -o <image>` to sample a clip at regular intervals for visual review. Check the sheet at full size when small text or details matter.
- Use `framediet qa <video>` before visual inspection. If it reports black/freeze intervals, add `--frames-dir <directory>` to extract small previews at those interval start times (up to 36).
- Use `framediet frames <video> <time...>` when specific moments need inspection; times are seconds.
- Use `framediet digest <tsx/jsx/html>` for a bounded source index with approximate line ranges, or `framediet probe <path>` for local project/media metadata.
- Use `framediet html <file>` to print an inspection copy with large embedded content replaced by markers. Redirect to a separate file if needed; the source is never changed.
- Use `framediet slim <skills-dir>` to preview code-block extraction. Only add `--apply` after reviewing the preview; the command writes references and a backup.

## Safety and accuracy

- The Claude Code hook only rewrites direct, single, progress-heavy calls (an `ffmpeg` encode with an output file, a `yt-dlp` download, a `manim` render, `remotion`/`hyperframes` `render`/`still`/`bundle`). `ffprobe`, `whisper`, FFmpeg analysis filters, listings and `--help` pass through, as do shell chains and operators.
- A summary header such as `Showing 12 of 116 lines` means lines were dropped. Prefix the call with `command` (`command ffmpeg ...`) to get the full output without the hook.
- `framediet qa --strict` exits 1 on `WARN`, for render scripts and CI.
- In a transcript, `word[?]` means the source has no timing for that word; do not invent one.
- `framediet probe <file>` prints `WARN` lines for rotated video and a likely variable frame rate; handle those before cutting to audio.
- The hook preserves Claude Code's normal permission policy. Do not add an automatic allow decision.
- Transcript timestamps are rounded to milliseconds and optional confidence data is omitted.
- `--precision` on JSON-to-TOON conversion is lossy by design; omit it when preserving floating-point values matters.
- A clean FFmpeg QA report does not prove that typography, composition, or safe-area placement is correct.
- Token and vision savings vary with the model and input. Do not present fixture measurements as guaranteed savings for a full task.
