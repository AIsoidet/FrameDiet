---
name: framediet
description: Use FrameDiet when checking a rendered or edited video for defects (black frames, freezes, audio peaks), reading Whisper/WhisperX or caption JSON, probing media files, or reading render logs and large HTML. Run `framediet qa` before sampling frames or writing your own FFmpeg/Python analysis.
---

# FrameDiet workflow

Use FrameDiet when a video task produces verbose CLI logs, word-level transcript JSON, many rendered frames, or large inline HTML/SVG payloads.

## Choose the right command

- Use `framediet qa <video> --frames-dir <directory>` first, before visual inspection and before writing your own detectors. It runs black, freeze, crop and audio-peak checks in one pass. `- note:` lines are likely intentional (title or end card, fade, held beat under 0.75 s); mention them but do not call them defects unless the brief says the shot should move. If it reports intervals, the command extracts small previews at those interval start times (up to 36), and you should look only at those.
- Use `framediet probe <video>` before cutting to audio: it prints `WARN` lines for rotated video and a likely variable frame rate; handle those first. It also reports local project/media metadata.
- Use `framediet frames <video> <time...> -o <directory>` when specific moments need inspection; times are seconds.
- Use `framediet json <file>` to create a compact transcript view or TOON serialization. Preserve the source file; the compact output may omit optional metadata.
- Use `framediet exec -- <command>` for a single media-tool invocation whose output is noisy (instead of piping it to `tail`). It returns the wrapped command's exit status. Run the original command directly when the complete output is needed.
- Use `framediet sheet <video> -o <image>` to sample a clip at regular intervals for visual review. Check the sheet at full size when small text or details matter.
- Use `framediet digest <tsx/jsx/html>` for a bounded source index with approximate line ranges.
- Use `framediet html <file>` to print an inspection copy with large embedded content replaced by markers; add `--strip-classes` for Tailwind-heavy pages. Redirect to a separate file if needed; the source is never changed.
- Use `framediet slim <skills-dir>` to preview code-block extraction. Only add `--apply` after reviewing the preview; the command writes references and a backup.

## Safety and accuracy

- The Claude Code hook only rewrites direct, single, progress-heavy calls (an `ffmpeg` encode with an output file, a `yt-dlp` download, a `manim` render, `remotion`/`hyperframes` `render`/`still`/`bundle`). `ffprobe`, `whisper`, FFmpeg analysis filters, listings and `--help` pass through, as do shell chains and operators.
- A summary header such as `Showing 12 of 116 lines` means lines were dropped. Prefix the call with `command` (`command ffmpeg ...`) to get the full output without the hook.
- `framediet qa --strict` exits 1 on `WARN`, for render scripts and CI.
- In a transcript, `word[?]` means the source has no timing for that word; do not invent one.
- Transcript timestamps are rounded to milliseconds and optional confidence data is omitted.
- `--precision` on JSON-to-TOON conversion is lossy by design; omit it when preserving floating-point values matters.
- A clean FFmpeg QA report does not prove that typography, composition, or safe-area placement is correct.
- Savings vary with the model and the task; do not promise a fixed saving to the user.
